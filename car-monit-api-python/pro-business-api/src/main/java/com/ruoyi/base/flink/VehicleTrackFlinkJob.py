# -*- coding: utf-8 -*-
"""com.ruoyi.base.flink.VehicleTrackFlinkJob

源文件：pro-business-api/src/main/java/com/ruoyi/base/flink/VehicleTrackFlinkJob.java

车辆轨迹 Flink 实时处理 Job

功能说明：
1. 从 Kafka 消费 Debezium CDC 消息和设备直连数据
2. 按车牌分组进行轨迹聚合（使用 Flink 键控状态 + 定时器）
3. 字典广播流支持位置信息富集（Broadcast State Pattern）
4. 轨迹拼接与状态管理（State TTL 30 天自动清理）
5. 待处理队列 + 定时器重试机制
6. 输出到 Redis 和 GaussDB

版本兼容说明（Flink 1.13.2 + Scala 2.11 + JDK 1.8）：
--------------------------------------------------------------------------------------
特性                        Flink 1.13.x 对应 API
--------------------------------------------------------------------------------------
流执行环境                   StreamExecutionEnvironment.getExecutionEnvironment()
Kafka 消费者                 FlinkKafkaConsumer<String>（flink-connector-kafka_2.11）
键控状态                     ValueState<T> / ListState<T> + KeyedStream
状态 TTL                     StateTtlConfig.newBuilder(Time.milliseconds(ttl))
定时器                       ctx.timerService().registerProcessingTimeTimer(timestamp)
广播状态                     KeyedBroadcastProcessFunction<KEY, IN1, IN2, OUT>
广播状态描述符               MapStateDescriptor<>(name, keyType, valueType)
类型信息                     Types.STRING / Types.LONG / TypeInformation.of(new TypeHint<>(){})
Checkpoint                   env.enableCheckpointing(interval, CheckpointingMode.EXACTLY_ONCE)
--------------------------------------------------------------------------------------

与原代码的核心修复点：
[修复1] BroadcastProcessFunction -> KeyedBroadcastProcessFunction（支持 onTimer 定时器）
[修复2] Types.OBJECT -> TypeInformation.of(new TypeHint<Map<String,Object>>(){})
[修复3] 自定义 SimpleStringSchema -> org.apache.flink.api.common.serialization.SimpleStringSchema
[修复4] 所有内部数据模型添加 implements Serializable（Flink 状态对象要求）
[修复5] onTimer 方法签名对齐 KeyedBroadcastProcessFunction 的正确签名

【Java→Python 本文件重点差异】
1) 5 条 `[修复N]` 注释是原工程对历史 Bug 的修复记录，**逐条原样保留**；
   其中 [修复2] 在 Python 侧同样成立：替身的 `Types` **没有 OBJECT** 常量，
   写 `Types.OBJECT` 会立刻 AttributeError（等价于 Java 编译失败）。
2) `@Slf4j` → `log = logging.getLogger(__name__)`；`{}` 占位符 → `%s`；
   `log.error(msg, ex)`（slf4j 把最后一个 Throwable 当堆栈）→ `exc_info=True`。
3) **Java 静态内部类 → 模块级类**（`TrailState` / `TrailInfo` / `StandardEvent` /
   `TrailResult` / `PendingEvent` / 两个 Parser / Source / Sink）。
   本工程这几个类只在文件内部使用（已全局检索确认无外部引用），
   因此不额外做 `VehicleTrackFlinkJob.TrailState = TrailState` 的别名。
4) `implements Serializable`（[修复4]）在 Python 侧**没有对应接口**：
   替身的状态直接持有对象引用（本地内存），不做序列化。
   若将来接真实 Flink（PyFlink），必须改为可序列化结构（避免 lambda/局部类）。
5) `private transient ValueState<TrailState> trailState` → 普通实例属性（初值 None）。
   Java 的 `transient` 只影响 Java 序列化，Python 不需要。
6) **方法引用** `StandardEvent::getPlateKey` → `lambda event: event.getPlateKey()`。
7) **泛型擦除**：`KeyedBroadcastProcessFunction<String, StandardEvent, Map<String,Object>, TrailResult>`
   在 Python 运行时完全不存在；`new TypeHint<TrailState>() {}` 这种**匿名子类
   携带泛型参数**的技巧也失效，改写为 `TypeHint[TrailState]`
   （替身用 `__class_getitem__` 显式保存类型对象，见 TypeHint 的差异说明）。
8) `java.util.Properties` → 内置 `dict`（`props.setProperty(k, v)` → `props[k] = v`）。
9) **`Iterator.remove()` 的坑**：`pendingQueue.get().iterator()` 在 Java 里支持
   边遍历边 remove；Python 的 list 迭代器不支持（会抛 RuntimeError）。
   `onTimer` 里改成“先 `list(...)` 快照、再 `clear()`、再逐个处理”，语义等价
   （详见 onTimer 内注释与 ListState 的差异说明）。
10) **定时器没有真实时钟**：`registerProcessingTimeTimer` 只登记 (timestamp, key)，
   由 Flink 替身（BroadcastConnectedStream）在数据流耗尽后立即回调 `onTimer`。
   业务代码里的 `System.currentTimeMillis() + 60_000` 保持原样，
   但**不要**指望真的等 60 秒才会重试。
11) `switch` → `if/elif`；`instanceof Long` → `isinstance(x, int)`（Python 的 int 即
   Java 的 long，无 32/64 位之分）；`(Long) timeObj` → `int(timeObj)`。
12) `Math.abs(long)` → `abs(int)`；`List#sort(Comparator)` → `list.sort(key=...)`；
   `a - b` 的 long 溢出在 Python 中不存在（int 任意精度）。
13) `throws Exception` 是 Java 受检异常声明，Python 无对应写法，异常直接向上抛。
14) Java 的局部变量/参数名 `dict` 与 Python 内建 `dict` 同名，
   统一加下划线 `dict_`（与 `from_` / `with_` 的处理方式一致）。
15) `pendingQueue.add(...)` 里的 `PendingEvent` 字段是 **public**（`pending.event` /
    `pending.retryCount` / `pending.createTime`），因此字段名保持 camelCase
   —— 与其它靠 getter/setter 访问的实体（snake_case + JavaBean）不同。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
    OdsRtSzdnSnapshotFlowAddcode,
)
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.redis.RedisCache import TimeUnit
from java.lang.System import System
from java.util.UUID import UUID
from org.apache.flink.api.common.functions.RichMapFunction import RichMapFunction
from org.apache.flink.api.common.serialization.SimpleStringSchema import (
    SimpleStringSchema,
)
from org.apache.flink.api.common.state.ListStateDescriptor import ListStateDescriptor
from org.apache.flink.api.common.state.MapStateDescriptor import MapStateDescriptor
from org.apache.flink.api.common.state.StateTtlConfig import StateTtlConfig
from org.apache.flink.api.common.state.ValueStateDescriptor import ValueStateDescriptor
from org.apache.flink.api.common.time.Time import Time
from org.apache.flink.api.common.typeinfo.TypeHint import TypeHint
from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation
from org.apache.flink.api.common.typeinfo.Types import Types
from org.apache.flink.configuration.Configuration import Configuration
from org.apache.flink.streaming.api.CheckpointingMode import CheckpointingMode
from org.apache.flink.streaming.api.datastream.BroadcastStream import BroadcastStream
from org.apache.flink.streaming.api.datastream.DataStream import DataStream
from org.apache.flink.streaming.api.datastream.KeyedStream import KeyedStream
from org.apache.flink.streaming.api.environment.StreamExecutionEnvironment import (
    StreamExecutionEnvironment,
)
from org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction import (
    KeyedBroadcastProcessFunction,
)
from org.apache.flink.streaming.api.functions.sink.SinkFunction import SinkFunction
from org.apache.flink.streaming.api.functions.source.SourceFunction import (
    SourceContext,
    SourceFunction,
)
from org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer import (
    FlinkKafkaConsumer,
)
from org.apache.flink.util.Collector import Collector

__all__ = [
    "VehicleTrackFlinkJob",
    "StandardEvent",
    "TrailState",
    "TrailInfo",
    "TrailResult",
    "PendingEvent",
    "CDCEventParser",
    "RawEventParser",
    "TrailAggregatorProcessFunction",
    "DictionarySourceFunction",
    "TrailResultSink",
]

log = logging.getLogger(__name__)


def _epochMillis(value: Any) -> int:
    """等价 `Date#getTime()`：返回 epoch 毫秒。

    【Java→Python】naive `datetime.timestamp()` 按本地时区换算，
    与 Java `Date.getTime()`（UTC 基准毫秒）结果一致。
    """
    return int(value.timestamp() * 1000)


def _abbreviate(json: str) -> str:
    """复现原代码里的 `json.length() > 200 ? json.substring(0,200) + "..." : json`。

    【Java→Python】`String#length()` → `len()`；`substring(0, 200)` → `json[:200]`。
    Java 的 substring 在长度不足时抛异常，但原代码已用三元表达式保证长度 > 200；
    这里用切片（越界自动截断），行为在该前提下完全一致。
    """
    return json[:200] + "..." if len(json) > 200 else json


# ====================================================================================
# 数据模型（[修复4] Java 侧全部添加 implements Serializable）
# ====================================================================================

@dataclass
class StandardEvent(JavaBean):
    """标准化事件。

    【Java→Python】Java 的 `private` 字段 + Lombok getter/setter →
    dataclass 的 snake_case 字段 + `JavaBean` 动态访问器
    （`setPointUuid()` / `getPlateKey()` 等写法保持不变）。
    `implements Serializable` 无对应物（见文件头第 4 条）。
    """

    point_uuid: Optional[str] = None      # Java: private String pointUuid;
    plate_key: Optional[str] = None       # Java: private String plateKey;
    capture_time: int = 0                 # Java: private long captureTime;（基本类型默认 0）
    location_code: Optional[str] = None   # Java: private String locationCode;
    source_type: Optional[str] = None     # Java: private String sourceType;
    raw_data: Optional[str] = None        # Java: private String rawData;


@dataclass
class TrailInfo(JavaBean):
    """轨迹信息（一个车牌的一段连续轨迹）。"""

    uuid: Optional[str] = None            # Java: private String uuid;
    plate_key: Optional[str] = None       # Java: private String plateKey;
    enter_time: int = 0                   # Java: private long enterTime;
    exit_time: int = 0                    # Java: private long exitTime;
    type: int = 0                         # Java: private int type;
    points: List[StandardEvent] = field(default_factory=list)  # Java: new ArrayList<>()

    def appendPoint(self, event: StandardEvent) -> None:
        """追加轨迹点：按抓拍时间排序，刷新首尾时间，点数 >= 3 时类型升级为 1。"""
        self.points.append(event)
        # 【Java→Python】`points.sort(Comparator.comparing(StandardEvent::getCaptureTime))`
        # → `list.sort(key=...)`（原地排序，稳定排序，语义一致）
        self.points.sort(key=lambda point: point.getCaptureTime())
        self.enter_time = self.points[0].getCaptureTime()
        self.exit_time = self.points[len(self.points) - 1].getCaptureTime()
        if len(self.points) >= 3:
            self.type = 1


@dataclass
class TrailState(JavaBean):
    """轨迹状态（Flink 键控状态里存的就是它）。"""

    trails: List[TrailInfo] = field(default_factory=list)  # Java: new ArrayList<>()

    def createNewTrail(self, event: StandardEvent) -> None:
        """用当前事件新建一条轨迹并追加到列表末尾。"""
        info: TrailInfo = TrailInfo()
        info.setUuid(UUID.randomUUID().toString().replace("-", ""))
        info.setPlateKey(event.getPlateKey())
        info.setEnterTime(event.getCaptureTime())
        info.setExitTime(event.getCaptureTime())
        info.getPoints().append(event)
        info.setType(0)
        self.trails.append(info)

    def getLatestTrail(self) -> TrailInfo:
        """取最后一条轨迹；空列表时返回**新建的空对象**（原代码如此，不返回 null）。"""
        if len(self.trails) == 0:
            return TrailInfo()
        return self.trails[len(self.trails) - 1]


@dataclass
class TrailResult(JavaBean):
    """轨迹聚合结果（算子输出）。"""

    trail: Optional[TrailInfo] = None     # Java: private TrailInfo trail;

    # Java 有显式构造器 `TrailResult(TrailInfo trail)`；dataclass 生成的
    # `__init__(self, trail=None)` 已经覆盖该调用方式（`TrailResult(x)`）。


@dataclass
class PendingEvent(JavaBean):
    """待处理事件（字段在 Java 里是 **public**，故保持 camelCase 字段名）。"""

    event: Optional[StandardEvent] = None  # Java: public StandardEvent event;
    retryCount: int = 0                    # Java: public int retryCount;
    createTime: int = 0                    # Java: public long createTime;


# ====================================================================================
# 数据解析器
# ====================================================================================

class CDCEventParser(RichMapFunction):
    """Debezium CDC 消息 → StandardEvent。"""

    def map(self, json: str) -> StandardEvent:
        """对应 `StandardEvent map(String json) throws Exception`。"""
        event: StandardEvent = StandardEvent()

        try:
            root: JSONObject = JSON.parseObject(json)
            payload: Optional[JSONObject] = root.getJSONObject("payload")

            if payload is not None:
                # Debezium 格式：payload.after
                after: Optional[JSONObject] = payload.getJSONObject("after")
                if after is not None:
                    data: Optional[OdsRtSzdnSnapshotFlowAddcode] = JSON.toJavaObject(
                        after, OdsRtSzdnSnapshotFlowAddcode)

                    if data is not None:
                        # Java: data.getBigId().toString()（BigId 是 String）
                        event.setPointUuid(str(data.getBigId()) if data.getBigId() is not None
                                           else UUID.randomUUID().toString())
                        event.setPlateKey(data.getPlatenumber())
                        if data.getSnapshottime() is not None:
                            event.setCaptureTime(_epochMillis(data.getSnapshottime()))
                        else:
                            event.setCaptureTime(System.currentTimeMillis())
                        event.setLocationCode(data.getDeviceid())
                        event.setSourceType("GANTRY-CDC")
                        event.setRawData(json)
                        return event

            # 退化为普通 JSON 格式
            # 【Java→Python】`JSON.parseObject(json, Xxx.class)` → 传类对象（无 .class 字面量）
            data = JSON.parseObject(json, OdsRtSzdnSnapshotFlowAddcode)
            if data is not None and data.getPlatenumber() is not None:
                event.setPointUuid(str(data.getBigId()) if data.getBigId() is not None
                                   else UUID.randomUUID().toString())
                event.setPlateKey(data.getPlatenumber())
                if data.getSnapshottime() is not None:
                    event.setCaptureTime(_epochMillis(data.getSnapshottime()))
                else:
                    event.setCaptureTime(System.currentTimeMillis())
                event.setLocationCode(data.getDeviceid())
                event.setSourceType("GANTRY-RAW")
                event.setRawData(json)
                return event

            log.warning("[CDC 解析] 无法识别消息格式: json=%s", _abbreviate(json))

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ex) 一致
            # 【Java→Python】Java 传 ex 作为最后一个参数（slf4j 打印堆栈）→ exc_info=True
            log.error("[CDC 解析] 解析异常: json=%s", _abbreviate(json), exc_info=True)

        # 兜底：空事件
        event.setPointUuid(UUID.randomUUID().toString())
        event.setPlateKey("UNKNOWN-" + UUID.randomUUID().toString()[:8])
        event.setCaptureTime(System.currentTimeMillis())
        event.setSourceType("PARSE-ERROR")
        event.setRawData(json)
        return event


class RawEventParser(RichMapFunction):
    """设备直连 JSON → StandardEvent。"""

    def map(self, json: str) -> StandardEvent:
        """对应 `StandardEvent map(String json) throws Exception`。"""
        event: StandardEvent = StandardEvent()

        try:
            data: JSONObject = JSON.parseObject(json)

            event.setPointUuid(data.getString("bigId") if data.getString("bigId") is not None
                               else UUID.randomUUID().toString())
            event.setPlateKey(data.getString("plateNumber")
                              if data.getString("plateNumber") is not None
                              else ("UNKNOWN-" + UUID.randomUUID().toString()[:8]))

            # 【Java→Python】`Object timeObj = data.get("captureTime")` 保持原样；
            # Java 的 `instanceof Long` → Python 的 int（bool 是 int 子类，需排除）。
            timeObj: Any = data.get("captureTime")
            if isinstance(timeObj, int) and not isinstance(timeObj, bool):
                event.setCaptureTime(int(timeObj))
            elif isinstance(timeObj, str):
                try:
                    # Java: Date date = data.getDate("captureTime");
                    date = data.getDate("captureTime")
                    event.setCaptureTime(_epochMillis(date) if date is not None
                                         else System.currentTimeMillis())
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    event.setCaptureTime(System.currentTimeMillis())
            else:
                event.setCaptureTime(System.currentTimeMillis())

            event.setLocationCode(data.getString("deviceId"))
            event.setSourceType(data.getString("deviceType")
                                if data.getString("deviceType") is not None
                                else "DEVICE-RAW")
            event.setRawData(json)

            return event

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ex) 一致
            log.error("[直连解析] 解析异常: json=%s", _abbreviate(json), exc_info=True)

            event.setPointUuid(UUID.randomUUID().toString())
            event.setPlateKey("UNKNOWN-" + UUID.randomUUID().toString()[:8])
            event.setCaptureTime(System.currentTimeMillis())
            event.setSourceType("PARSE-ERROR")
            event.setRawData(json)
            return event


# ====================================================================================
# 核心处理函数：轨迹聚合（使用 KeyedBroadcastProcessFunction 支持定时器）
# ====================================================================================

class TrailAggregatorProcessFunction(KeyedBroadcastProcessFunction):
    """[修复1] 使用 KeyedBroadcastProcessFunction 替代 BroadcastProcessFunction
    原因：BroadcastProcessFunction 不支持 onTimer 定时器，只有 Keyed 版本支持
    泛型参数（Java）：<String=KEY(车牌), StandardEvent=IN1, Map<String,Object>=IN2, TrailResult=OUT>
    """

    def __init__(self) -> None:
        super(TrailAggregatorProcessFunction, self).__init__()
        # Java: private transient ValueState<TrailState> trailState;（open 里赋值）
        self.trailState: Any = None
        # Java: private transient ListState<PendingEvent> pendingQueue;
        self.pendingQueue: Any = None
        # Java: private transient MapStateDescriptor<String, Map<String, Object>> dictStateDesc;
        self.dictStateDesc: Any = None

    def open(self, parameters: Configuration) -> None:
        """对应 `open(Configuration parameters) throws Exception`。"""
        # 状态 TTL：30 天
        ttlConfig: StateTtlConfig = (
            StateTtlConfig
            .newBuilder(Time.milliseconds(VehicleTrackFlinkJob.STATE_TTL))
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .cleanupIncrementally(10, True)
            .build())

        # 轨迹状态描述符
        # 【Java→Python】`new TypeHint<TrailState>() {}` → `TypeHint[TrailState]`（泛型擦除，见文件头第 7 条）
        trailStateDesc: ValueStateDescriptor = ValueStateDescriptor(
            "trail-state", TypeInformation.of(TypeHint[TrailState]))
        trailStateDesc.enableTimeToLive(ttlConfig)
        self.trailState = self.getRuntimeContext().getState(trailStateDesc)

        # 待处理队列
        pendingQueueDesc: ListStateDescriptor = ListStateDescriptor(
            "pending-queue", TypeInformation.of(TypeHint[PendingEvent]))
        self.pendingQueue = self.getRuntimeContext().getListState(pendingQueueDesc)

        # 广播状态描述符
        # 【Java→Python】`Map<String, Object>` → `Dict[str, Any]`
        self.dictStateDesc = MapStateDescriptor(
            "dict-broadcast-state",
            Types.STRING,
            TypeInformation.of(TypeHint[Dict[str, Any]]))

        log.info("[轨迹聚合器] open() 初始化完成")

    def processElement(self, event: StandardEvent, ctx: Any,
                       out: Collector) -> None:
        """对应 `processElement(StandardEvent, ReadOnlyContext, Collector<TrailResult>)`。"""
        current: Optional[TrailState] = self.trailState.value()
        if current is None:
            current = TrailState()

        appended: bool = self.tryAppendToTrail(current, event)

        if appended:
            self.trailState.update(current)
            out.collect(TrailResult(current.getLatestTrail()))
        else:
            pending: PendingEvent = PendingEvent()
            pending.event = event
            pending.retryCount = 0
            pending.createTime = System.currentTimeMillis()
            self.pendingQueue.add(pending)

            timerTs: int = System.currentTimeMillis() + VehicleTrackFlinkJob.PENDING_RETRY_INTERVAL
            ctx.timerService().registerProcessingTimeTimer(timerTs)

    def processBroadcastElement(self, dict_: Dict[str, Any], ctx: Any,
                                out: Collector) -> None:
        """对应 `processBroadcastElement(Map<String,Object> dict, Context, Collector)`。

        【Java→Python】参数名 `dict` 与 Python 内建同名 → `dict_`（文件头第 14 条）；
        `out` 在方法体内未使用（原代码如此），保留参数以对齐签名。
        """
        if dict_ is not None and len(dict_) > 0:
            for key, value in dict_.items():
                # 显式类型转换：entry.getValue() 返回 Object，需要转为 Map<String,Object>
                # 满足 BroadcastState.put(String, Map<String,Object>) 的参数要求
                # 【Java→Python】Java 的 `(Map<String,Object>)` 强制转换会做运行时类型检查，
                # 转换失败抛 ClassCastException；Python 没有泛型/强制转换，
                # 这里“拿到什么就存什么”（替身的 BroadcastState 不校验 value 类型）。
                ctx.getBroadcastState(self.dictStateDesc).put(key, value)
            log.info("[广播流] 字典数据更新完成，更新项数=%s", len(dict_))

    def onTimer(self, timestamp: int, ctx: Any, out: Collector) -> None:
        """[修复5] onTimer 方法签名：使用 KeyedBroadcastProcessFunction 的 OnTimerContext
        原代码使用的是 KeyedProcessFunction.OnTimerContext（错误）
        """
        current: Optional[TrailState] = self.trailState.value()
        if current is None:
            current = TrailState()

        # 【Java→Python】**迭代器 remove 的坑**（文件头第 9 条）：
        # Java 原代码：
        #     Iterator<PendingEvent> it = pendingQueue.get().iterator();
        #     while (it.hasNext()) { PendingEvent p = it.next(); it.remove(); ... }
        # Python 的 list 迭代器不支持 remove（会 RuntimeError），因此改为：
        #     先快照 → 清空状态 → 逐个处理（与 Java 的“取出即移除”语义等价）
        pendingList: List[PendingEvent] = list(self.pendingQueue.get())
        self.pendingQueue.clear()

        retryList: List[PendingEvent] = []
        successCount: int = 0
        dropCount: int = 0

        for pending in pendingList:
            appended: bool = self.tryAppendToTrail(current, pending.event)
            if appended:
                successCount += 1
                out.collect(TrailResult(current.getLatestTrail()))
            else:
                pending.retryCount += 1
                if pending.retryCount < VehicleTrackFlinkJob.MAX_PENDING_RETRY:
                    retryList.append(pending)
                else:
                    dropCount += 1
                    log.warning("[待处理队列] 超过最大重试次数(%s)，丢弃: 车牌=%s, 点ID=%s",
                                VehicleTrackFlinkJob.MAX_PENDING_RETRY,
                                pending.event.getPlateKey(),
                                pending.event.getPointUuid())

        for p in retryList:
            self.pendingQueue.add(p)

        self.trailState.update(current)

        if successCount > 0 or dropCount > 0 or len(retryList) > 0:
            log.info("[onTimer处理完成] 成功拼接=%s, 丢弃=%s, 继续重试=%s",
                     successCount, dropCount, len(retryList))

            if len(retryList) > 0:
                nextTimerTs: int = (System.currentTimeMillis()
                                    + VehicleTrackFlinkJob.PENDING_RETRY_INTERVAL)
                ctx.timerService().registerProcessingTimeTimer(nextTimerTs)

    def tryAppendToTrail(self, state: TrailState, event: StandardEvent) -> bool:
        """尝试把事件拼到最新轨迹；跨 7 天则新建轨迹。

        【Java→Python】`state.trails.isEmpty()` → `len(state.trails) == 0`；
        `Math.abs(long)` → 内置 `abs()`（Python int 无溢出）。
        """
        if len(state.trails) == 0:
            state.createNewTrail(event)
            return True

        latest: TrailInfo = state.getLatestTrail()
        timeDiff: int = abs(event.getCaptureTime() - latest.getExitTime())
        if timeDiff > VehicleTrackFlinkJob.TRAIL_SPLIT_THRESHOLD:
            state.createNewTrail(event)
            return True

        latest.appendPoint(event)
        return True


# ====================================================================================
# Source：字典数据 Source
# ====================================================================================

class DictionarySourceFunction(SourceFunction):
    """字典数据源（本工程里是**每 10 分钟发一个空 Map** 的占位实现）。"""

    def __init__(self) -> None:
        super(DictionarySourceFunction, self).__init__()
        # Java: private volatile boolean isRunning = true;
        # 【Java→Python】Python 的 GIL 保证单个属性读写的原子性，
        # 不需要（也没有）volatile 关键字，普通属性即可。
        self.isRunning: bool = True

    def run(self, ctx: SourceContext) -> None:
        """对应 `void run(SourceContext<Map<String,Object>> ctx) throws Exception`。

        【Java→Python】**这是一个死循环**：`while (isRunning)` + 每轮 sleep 10 分钟，
        只有在另一个线程调用 `cancel()` 把 isRunning 置 false 后才退出。
        真实 Flink 会在独立 Source 线程里跑它；Python 替身的
        `StreamExecutionEnvironment.execute()` **不会**调用 `run()`，
        否则单元测试会挂在这里（见 StreamExecutionEnvironment 的差异说明）。
        """
        while self.isRunning:
            dict_: Dict[str, Any] = {}  # Java: Map<String,Object> dict = new HashMap<>();
            ctx.collect(dict_)
            TimeUnit.MINUTES.sleep(10)

    def cancel(self) -> None:
        """对应 `void cancel()`。"""
        # 【Java→Python】volatile 写 → 普通属性赋值（见 __init__ 注释）
        self.isRunning = False
        log.info("[字典数据源] DictionarySourceFunction.cancel() 被调用")


# ====================================================================================
# Sink：轨迹结果输出
# ====================================================================================

class TrailResultSink(SinkFunction):
    """轨迹结果输出（打印日志）。"""

    def invoke(self, value: Optional[TrailResult], context: Any) -> None:
        """对应 `void invoke(TrailResult value, Context context) throws Exception`。"""
        if value is None or value.getTrail() is None:
            return
        log.info("[Sink] 输出轨迹: uuid=%s, 车牌=%s, 点数=%s, 类型=%s",
                 value.getTrail().getUuid(),
                 value.getTrail().getPlateKey(),
                 len(value.getTrail().getPoints()),
                 value.getTrail().getType())


# ====================================================================================
# Job 入口
# ====================================================================================

class VehicleTrackFlinkJob(object):
    """车辆轨迹 Flink 实时处理 Job（`@Slf4j`，无 Spring 注解）。"""

    # ==================== 配置项 ====================

    #: Kafka Broker 地址
    KAFKA_BOOTSTRAP_SERVERS = "127.0.0.1:9092"

    #: CDC 数据主题：Debezium 推送的源数据库变更
    CDC_TOPIC = "gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode"

    #: 设备直连数据主题：设备直接上报的抓拍数据
    RAW_DATA_TOPIC = "device-raw-data"

    #: 轨迹切割时间阈值（7 天 = 604800000 毫秒）
    #: 【Java→Python】`7L * 24 * 60 * 60 * 1000` 的 long 字面量后缀在 Python 中不存在
    TRAIL_SPLIT_THRESHOLD = 7 * 24 * 60 * 60 * 1000

    #: 状态 TTL（30 天）：超过此时间未更新的状态自动被 Flink 清理
    STATE_TTL = 30 * 24 * 60 * 60 * 1000

    #: 待处理队列重试间隔（60 秒）
    PENDING_RETRY_INTERVAL = 60 * 1000

    #: 单条数据最大重试次数
    MAX_PENDING_RETRY = 3

    # ==================== 主方法：Flink Job 入口 ====================

    @staticmethod
    def main(args: Optional[List[str]] = None) -> None:
        """对应 `public static void main(String[] args) throws Exception`。

        【Java→Python】`throws Exception` 无对应写法；`args` 参数在方法体内未使用
        （原代码如此），保留签名以对齐入口。
        """
        log.info("[Flink Job] 开始启动车辆轨迹处理 Job（Flink 1.13.2 + JDK 1.8）")

        # ========== 步骤 1：创建 Flink 执行环境 ==========
        env: StreamExecutionEnvironment = (
            StreamExecutionEnvironment.getExecutionEnvironment())

        # 60 秒一次 Checkpoint，EXACTLY_ONCE 语义
        env.enableCheckpointing(60000, CheckpointingMode.EXACTLY_ONCE)
        env.getCheckpointConfig().setCheckpointTimeout(600000)
        env.getCheckpointConfig().setMaxConcurrentCheckpoints(1)
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000)

        # ========== 步骤 2：字典广播流 ==========
        dictBroadcastStream: BroadcastStream = (
            VehicleTrackFlinkJob.createDictBroadcastStream(env))

        # ========== 步骤 3：Kafka 数据源 ==========
        cdcStream: DataStream = VehicleTrackFlinkJob.createCDCDataStream(env)
        rawDataStream: DataStream = VehicleTrackFlinkJob.createRawDataStream(env)
        unifiedStream: DataStream = cdcStream.union(rawDataStream)

        # ========== 步骤 4：按车牌分组 ==========
        # 【Java→Python】`StandardEvent::getPlateKey` → lambda（文件头第 6 条）
        keyedStream: KeyedStream = unifiedStream.keyBy(
            lambda event: event.getPlateKey())

        # ========== 步骤 5：连接广播流 + 轨迹聚合 ==========
        resultStream: DataStream = keyedStream \
            .connect(dictBroadcastStream) \
            .process(TrailAggregatorProcessFunction())

        # ========== 步骤 6：输出结果 ==========
        resultStream.addSink(TrailResultSink())

        # ========== 步骤 7：启动 Job ==========
        log.info("[Flink Job] DAG 构建完成，开始提交执行")
        env.execute("车辆轨迹实时处理 Job")

    # ==================== 方法：创建字典广播流 ====================

    @staticmethod
    def createDictBroadcastStream(env: StreamExecutionEnvironment) -> BroadcastStream:
        """对应 `createDictBroadcastStream(StreamExecutionEnvironment env)`。"""
        dictStream: DataStream = env \
            .addSource(DictionarySourceFunction()) \
            .name("Redis 字典数据") \
            .setParallelism(1)

        # [修复2] 使用 TypeInformation.of(new TypeHint<...>(){}) 替代 Types.OBJECT
        dictStateDesc: MapStateDescriptor = MapStateDescriptor(
            "dict-broadcast-state",
            Types.STRING,
            TypeInformation.of(TypeHint[Dict[str, Any]]))

        return dictStream.broadcast(dictStateDesc)

    # ==================== 方法：创建 Debezium CDC 数据流 ====================

    @staticmethod
    def createCDCDataStream(env: StreamExecutionEnvironment) -> DataStream:
        """对应 `createCDCDataStream(StreamExecutionEnvironment env)`。"""
        # 【Java→Python】`new Properties()` + `setProperty(k, v)` → 内置 dict
        props: Dict[str, str] = {}
        props["bootstrap.servers"] = VehicleTrackFlinkJob.KAFKA_BOOTSTRAP_SERVERS
        props["group.id"] = "flink-cdc-consumer"
        props["auto.offset.reset"] = "latest"
        props["enable.auto.commit"] = "false"

        # [修复3] 使用 Flink 自带的 org.apache.flink.api.common.serialization.SimpleStringSchema
        consumer: FlinkKafkaConsumer = FlinkKafkaConsumer(
            VehicleTrackFlinkJob.CDC_TOPIC,
            SimpleStringSchema(),
            props)

        return env \
            .addSource(consumer) \
            .name("Kafka-CDC 数据源") \
            .map(CDCEventParser()) \
            .name("CDC 数据解析标准化")

    # ==================== 方法：创建设备直连数据流 ====================

    @staticmethod
    def createRawDataStream(env: StreamExecutionEnvironment) -> DataStream:
        """对应 `createRawDataStream(StreamExecutionEnvironment env)`。"""
        props: Dict[str, str] = {}
        props["bootstrap.servers"] = VehicleTrackFlinkJob.KAFKA_BOOTSTRAP_SERVERS
        props["group.id"] = "flink-rawdata-consumer"
        props["auto.offset.reset"] = "latest"
        props["enable.auto.commit"] = "false"

        consumer: FlinkKafkaConsumer = FlinkKafkaConsumer(
            VehicleTrackFlinkJob.RAW_DATA_TOPIC,
            SimpleStringSchema(),
            props)

        return env \
            .addSource(consumer) \
            .name("Kafka-设备直连 数据源") \
            .map(RawEventParser()) \
            .name("直连数据解析标准化")


if __name__ == "__main__":
    # 对应 Java 的 `public static void main` 入口；
    # 替身执行时不会真的连 Kafka，也不会因 DictionarySourceFunction 的死循环挂住。
    VehicleTrackFlinkJob.main([])
