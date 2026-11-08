# -*- coding: utf-8 -*-
"""t09f 冒烟测试：device(DeviceDataSimulator) + flink(VehicleTrackFlinkJob) + Flink 框架替身。

运行：
    python refactor/_smoke_t09f.py

覆盖范围
1) 目录结构对照：com/ruoyi/base/device、com/ruoyi/base/flink 下 .java 与 .py 一一对应；
   Flink 替身的 27 个文件路径逐一存在。
2) DeviceDataSimulator：DEVICES/PLATE_PREFIX 常量、4 类设备数据生成、
   default 分支、车牌/颜色/车型取值域、formatDate、Kafka 上报（含 jsonData 未使用缺陷）。
3) VehicleTrackFlinkJob 常量与 main 的 7 步装配（execute 只记录不启动集群）。
4) CDCEventParser：Debezium 格式 / 普通 JSON / 无车牌兜底 / 坏 JSON 兜底。
5) RawEventParser：数字与字符串 captureTime / 缺字段兜底 / 坏 JSON 兜底。
6) 数据模型：TrailInfo.appendPoint 排序与 type 翻转、TrailState.createNewTrail。
7) TrailAggregatorProcessFunction：processElement / processBroadcastElement /
   onTimer（先快照再 clear）/ 7 天切分 / 定时器重试 3 次后丢弃。
8) Flink 替身：Time / TypeHint / Types(无 OBJECT) / StateTtlConfig /
   SimpleStringSchema / CheckpointingMode / FlinkKafkaConsumer /
   DictionarySourceFunction(用 sleep 桩避免真等 10 分钟) / TrailResultSink。

【注意】sys.path 的三个根目录必须都指向 refactor 内，否则会 import 到原始 Java 目录。
"""
from __future__ import annotations

import glob
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal

# ---------------------------------------------------------------------- 路径
_ROOT = os.path.dirname(os.path.abspath(__file__))  # .../refactor
for _path in (_ROOT,
              os.path.join(_ROOT, "pro-base-common", "src", "main", "java"),
              os.path.join(_ROOT, "pro-business-api", "src", "main", "java")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ---------------------------------------------------------------------- 断言工具
PASS = 0


def check(condition, label):
    global PASS
    if not condition:
        raise AssertionError("FAILED: " + label)
    PASS += 1
    print("  [OK] %s" % label)


def expect_raises(exc_type, func, label):
    """断言 func() 抛出 exc_type，返回捕获到的异常实例。"""
    global PASS
    try:
        func()
    except exc_type as error:  # noqa: BLE001 - 测试断言
        PASS += 1
        print("  [OK] %s" % label)
        return error
    except Exception as error:  # noqa: BLE001 - 类型不符也要报错
        raise AssertionError("FAILED(%s != %s): %s" %
                             (type(error).__name__, exc_type.__name__, label))
    raise AssertionError("FAILED(no raise): " + label)


def section(title):
    print("\n=== %s ===" % title)


class _Capture(logging.Handler):
    """收集日志消息，用于断言 Sink / 丢弃告警是否输出。"""

    def __init__(self):
        logging.Handler.__init__(self)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())

    def text(self):
        return "\n".join(self.messages)


# ====================================================================== 1 结构
section("1. 目录结构对照 + Flink 替身文件清单")

for _pkg in (os.path.join("com", "ruoyi", "base", "device"),
             os.path.join("com", "ruoyi", "base", "flink")):
    _rel = os.path.join("pro-business-api", "src", "main", "java", _pkg)
    _py_root = os.path.join(_ROOT, _rel)
    _java_root = os.path.join(os.path.dirname(_ROOT), _rel)
    _java = sorted(os.path.relpath(p, _java_root)[:-5] for p in
                   glob.glob(os.path.join(_java_root, "*.java")))
    _py = sorted(os.path.relpath(p, _py_root)[:-3] for p in
                 glob.glob(os.path.join(_py_root, "*.py")))
    print("  %s -> java=%s py=%s" % (_pkg.replace(os.sep, "/"), _java, _py))
    check(_java == _py and len(_java) == 1, "%s 结构一一对应" % _pkg.replace(os.sep, "/"))

_FLINK_STUBS = [
    "api/common/time/Time.py",
    "api/common/typeinfo/TypeHint.py",
    "api/common/typeinfo/TypeInformation.py",
    "api/common/typeinfo/Types.py",
    "api/common/state/StateTtlConfig.py",
    "api/common/state/ValueStateDescriptor.py",
    "api/common/state/ListStateDescriptor.py",
    "api/common/state/MapStateDescriptor.py",
    "api/common/state/ValueState.py",
    "api/common/state/ListState.py",
    "api/common/state/MapState.py",
    "api/common/state/BroadcastState.py",
    "api/common/functions/RichMapFunction.py",
    "api/common/functions/RuntimeContext.py",
    "api/common/serialization/SimpleStringSchema.py",
    "configuration/Configuration.py",
    "util/Collector.py",
    "streaming/api/CheckpointingMode.py",
    "streaming/api/datastream/DataStream.py",
    "streaming/api/datastream/BroadcastStream.py",
    "streaming/api/datastream/KeyedStream.py",
    "streaming/api/datastream/DataStreamSink.py",
    "streaming/api/datastream/BroadcastConnectedStream.py",
    "streaming/api/environment/StreamExecutionEnvironment.py",
    "streaming/api/environment/CheckpointConfig.py",
    "streaming/api/functions/source/SourceFunction.py",
    "streaming/api/functions/sink/SinkFunction.py",
    "streaming/api/functions/co/KeyedBroadcastProcessFunction.py",
    "streaming/connectors/kafka/FlinkKafkaConsumer.py",
]
_flink_root = os.path.join(_ROOT, "org", "apache", "flink")
_missing = [item for item in _FLINK_STUBS
            if not os.path.exists(os.path.join(_flink_root, item.replace("/", os.sep)))]
check(not _missing and len(_FLINK_STUBS) == 29,
      "Flink 替身 %d 个文件全部存在（缺失=%s）" % (len(_FLINK_STUBS), _missing))
check(os.path.exists(os.path.join(_ROOT, "java", "util", "concurrent",
                                 "ThreadLocalRandom.py")),
      "java.util.concurrent.ThreadLocalRandom 替身存在")

# ====================================================================== 2 常量
section("2. 常量与 DEVICES / PLATE_PREFIX")

from com.ruoyi.base.device.DeviceDataSimulator import (  # noqa: E402
    DeviceDataSimulator,
    DeviceInfo,
)
from com.ruoyi.base.flink.VehicleTrackFlinkJob import (  # noqa: E402
    CDCEventParser,
    DictionarySourceFunction,
    PendingEvent,
    RawEventParser,
    StandardEvent,
    TrailAggregatorProcessFunction,
    TrailInfo,
    TrailResult,
    TrailResultSink,
    TrailState,
    VehicleTrackFlinkJob,
)
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (  # noqa: E402
    OdsRtSzdnSnapshotFlowAddcode,
)
from com.ruoyi.common.core.domain.JavaBean import JavaBean  # noqa: E402
from java.lang.System import System  # noqa: E402
from java.util.concurrent.ThreadLocalRandom import ThreadLocalRandom  # noqa: E402
from org.apache.flink.api.common.state.ListStateDescriptor import (  # noqa: E402
    ListStateDescriptor,
)
from org.apache.flink.api.common.state.MapStateDescriptor import (  # noqa: E402
    MapStateDescriptor,
)
from org.apache.flink.api.common.state.StateTtlConfig import StateTtlConfig  # noqa: E402
from org.apache.flink.api.common.state.ValueStateDescriptor import (  # noqa: E402
    ValueStateDescriptor,
)
from org.apache.flink.api.common.time.Time import Time  # noqa: E402
from org.apache.flink.api.common.typeinfo.TypeHint import TypeHint  # noqa: E402
from org.apache.flink.api.common.typeinfo.TypeInformation import (  # noqa: E402
    TypeInformation,
)
from org.apache.flink.api.common.typeinfo.Types import Types  # noqa: E402
from org.apache.flink.configuration.Configuration import Configuration  # noqa: E402
from org.apache.flink.streaming.api.CheckpointingMode import CheckpointingMode  # noqa: E402
from org.apache.flink.streaming.api.environment.StreamExecutionEnvironment import (  # noqa: E402
    StreamExecutionEnvironment,
)
from org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction import (  # noqa: E402
    Context,
    KeyedBroadcastProcessFunction,
    OnTimerContext,
    ReadOnlyContext,
)
from org.apache.flink.streaming.api.functions.sink.SinkFunction import SinkFunction  # noqa: E402
from org.apache.flink.streaming.api.functions.source.SourceFunction import (  # noqa: E402
    SourceContext,
    SourceFunction,
)
from org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer import (  # noqa: E402
    FlinkKafkaConsumer,
)
from org.apache.flink.api.common.serialization.SimpleStringSchema import (  # noqa: E402
    SimpleStringSchema,
)
from org.apache.flink.util.Collector import Collector  # noqa: E402
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate  # noqa: E402

check(DeviceDataSimulator.KAFKA_TOPIC_RAW_DATA == "device-raw-data", "KAFKA_TOPIC_RAW_DATA")
check(len(DeviceDataSimulator.DEVICES) == 6, "DEVICES 共 6 个设备")
_first = DeviceDataSimulator.DEVICES[0]
check((_first.deviceId, _first.deviceType, _first.roadName, _first.district,
       _first.lon, _first.lat) == ("Gantry-001", "GANTRY", "京承高速", "朝阳区",
                                   116.404, 39.915),
      "DeviceInfo 按 @AllArgsConstructor 顺序装配")
check(DeviceDataSimulator.PLATE_PREFIX == ["京A", "京B", "京C", "京E", "京F",
                                          "京G", "京H", "京J", "京K", "京L"],
      "PLATE_PREFIX 10 个前缀")

check(VehicleTrackFlinkJob.KAFKA_BOOTSTRAP_SERVERS == "127.0.0.1:9092", "KAFKA_BOOTSTRAP_SERVERS")
check(VehicleTrackFlinkJob.CDC_TOPIC
      == "gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode", "CDC_TOPIC")
check(VehicleTrackFlinkJob.RAW_DATA_TOPIC == "device-raw-data", "RAW_DATA_TOPIC")
check(VehicleTrackFlinkJob.TRAIL_SPLIT_THRESHOLD == 604800000, "TRAIL_SPLIT_THRESHOLD=7天")
check(VehicleTrackFlinkJob.STATE_TTL == 2592000000, "STATE_TTL=30天")
check(VehicleTrackFlinkJob.PENDING_RETRY_INTERVAL == 60000, "PENDING_RETRY_INTERVAL=60秒")
check(VehicleTrackFlinkJob.MAX_PENDING_RETRY == 3, "MAX_PENDING_RETRY=3")

# ====================================================================== 3 设备模拟
section("3. DeviceDataSimulator 数据生成与上报")

_kt = KafkaTemplate()
_sim = DeviceDataSimulator(kafkaTemplate=_kt)
_gantry = _sim.generateGantryData(DeviceDataSimulator.DEVICES[0])
check(isinstance(_gantry, OdsRtSzdnSnapshotFlowAddcode),
      "generateGantryData 返回 OdsRtSzdnSnapshotFlowAddcode 实体")
check(_gantry.getDatasource() == "SIMULATED_GANTRY", "datasource=SIMULATED_GANTRY")
check(_gantry.getGantrycode() == "Gantry-001" and _gantry.getDeviceid() == "Gantry-001",
      "gantrycode / deviceid 取设备号")
check(_gantry.getSectionname() == "朝阳区段", "sectionname = district + 段")
check(_gantry.getRoadcode() == "G101" and _gantry.getSectioncode() == "SEC-001",
      "roadcode / sectioncode 固定值")
check(_gantry.getLon() == Decimal("116.404") and _gantry.getLat() == Decimal("39.915"),
      "new BigDecimal(lon/lat) → Decimal 透传")
check(_gantry.getSnapshottimeunix() == int(_gantry.getSnapshottime().timestamp() * 1000),
      "snapshottimeunix = snapshottime.getTime()")
check(_gantry.getReceivedtime() >= _gantry.getSnapshottime(),
      "receivedtime >= snapshottime（+100~499ms）")
check(_gantry.getSnappicturepath().startswith("/images/")
      and _gantry.getSnappicturepath().endswith(".jpg")
      and _gantry.getBigId() in _gantry.getSnappicturepath(),
      "图片路径 /images/{yyyy/MM/dd}/{bigId}.jpg")
check(_gantry.getPlatenumber().startswith(tuple(DeviceDataSimulator.PLATE_PREFIX)),
      "车牌号以 PLATE_PREFIX 之一开头")
check(_gantry.getPlatecolor() in ("蓝", "黄", "绿", "白", "黑"), "platecolor 取值域")
check(_gantry.getPlatetypecode() in (1, 2), "platetypecode = nextBoolean ? 1 : 2")
check(_gantry.getCartype() in ("小型轿车", "大型客车", "货车", "危险品运输车"),
      "cartype 取值域")
check(1 <= _gantry.getCartypecode() <= 9, "cartypecode ∈ [1,10)")

_border = _sim.generateBorderWeighingData(DeviceDataSimulator.DEVICES[2])
check((_border["deviceType"], _border["location"]) == ("BORDER_WEIGHING", "京冀界"),
      "省界称重 deviceType / location")
check(1.0 <= _border["vehicleWeight"] < 49.0, "vehicleWeight ∈ [1.0, 49.0)")
check(2 <= _border["axleCount"] <= 6, "axleCount ∈ [2, 7)")
check(isinstance(_border["overweight"], bool), "overweight 是布尔")

_toll = _sim.generateTollStationData(DeviceDataSimulator.DEVICES[3])
check(_toll["deviceType"] == "TOLL_STATION" and _toll["direction"] in ("IN", "OUT"),
      "收费站 deviceType / direction")
check(_toll["laneId"].startswith("LANE-") and _toll["laneId"][5:].isdigit(),
      "laneId = LANE-{1..5}")
check(5.0 <= _toll["tollFee"] < 500.0, "tollFee ∈ [5.0, 500.0)")

_service = _sim.generateServiceAreaData(DeviceDataSimulator.DEVICES[5])
check(_service["deviceType"] == "SERVICE_AREA"
      and _service["action"] in ("ENTER", "EXIT", "PARKING"),
      "服务区 deviceType / action")

_unknown = DeviceInfo("X-1", "UNKNOWN", "某路", "某区", 1.0, 2.0)
_unknown_data = _sim.generateDeviceData(_unknown)
check(isinstance(_unknown_data, JavaBean)
      and _unknown_data.getDatasource() == "SIMULATED_GANTRY",
      "switch default 分支 → generateGantryData")

check(_sim.formatDate(datetime(2024, 1, 5)) == "2024/01/05", "formatDate(yyyy/MM/dd)")
check(_sim.generatePlateNumber().startswith(tuple(DeviceDataSimulator.PLATE_PREFIX)),
      "generatePlateNumber 前缀来自 PLATE_PREFIX")

_sim.reportToKafka(DeviceDataSimulator.DEVICES[0], _gantry)
_records = _kt.sentRecords()
check(len(_records) == 1 and _records[0][0] == "device-raw-data",
      "reportToKafka 发到 device-raw-data")
check(_records[0][1].startswith("Gantry-001:") and _records[0][1][11:].isdigit(),
      "key = deviceId:currentTimeMillis")
check(_records[0][2] is _gantry, "value 是 data 对象（不是 jsonData 字符串）")
_src_text = open(os.path.join(_ROOT, "pro-business-api", "src", "main", "java",
                             "com", "ruoyi", "base", "device",
                             "DeviceDataSimulator.py"), encoding="utf-8").read()
check("jsonData: str = JSON.toJSONString(data)  # noqa: F841" in _src_text,
      "原缺陷 jsonData 计算后未使用（忠实保留 + 标注）")

_sim.simulateSingleReport()
check(len(_kt.sentRecords()) == 2, "simulateSingleReport 上报 1 条")
_sim.simulateBatchReport(0)
check(len(_kt.sentRecords()) == 2, "simulateBatchReport(0) 不上报")

# ====================================================================== 4 CDC 解析
section("4. CDCEventParser")

_cdc = CDCEventParser()
_expected_ms = int(datetime(2024, 1, 15, 10, 30, 0).timestamp() * 1000)
_debezium = ('{"payload":{"after":{"bigId":"B-1","platenumber":"京A12345",'
             '"snapshottime":"2024-01-15 10:30:00","deviceid":"Gantry-001"}}}')
_e1 = _cdc.map(_debezium)
check((_e1.getPointUuid(), _e1.getPlateKey(), _e1.getCaptureTime(),
       _e1.getLocationCode(), _e1.getSourceType())
      == ("B-1", "京A12345", _expected_ms, "Gantry-001", "GANTRY-CDC"),
      "Debezium payload.after → GANTRY-CDC")
check(_e1.getRawData() == _debezium, "rawData 保存原始 JSON")

_e2 = _cdc.map('{"bigId":"B-2","platenumber":"京B1","snapshottime":"2024-01-15 10:30:00"}')
check((_e2.getPointUuid(), _e2.getPlateKey(), _e2.getSourceType())
      == ("B-2", "京B1", "GANTRY-RAW"), "退化分支普通 JSON → GANTRY-RAW")
check(_e2.getCaptureTime() == _expected_ms, "普通 JSON 的 snapshottime 解析")

_e3 = _cdc.map('{"bigId":"B-3"}')
check(_e3.getSourceType() == "PARSE-ERROR"
      and _e3.getPlateKey().startswith("UNKNOWN-")
      and len(_e3.getPlateKey()) == 16,
      "无车牌 → PARSE-ERROR + UNKNOWN-{8位}")
check(len(_e3.getPointUuid()) == 36, "兜底 pointUuid = UUID.randomUUID().toString()")

_e4 = _cdc.map("not-json")
check(_e4.getSourceType() == "PARSE-ERROR" and _e4.getRawData() == "not-json",
      "坏 JSON → PARSE-ERROR（异常被吞掉）")

_e5 = _cdc.map('{"payload":{"after":null},"bigId":"B-5","platenumber":"京C5"}')
check((_e5.getPointUuid(), _e5.getSourceType()) == ("B-5", "GANTRY-RAW"),
      "payload.after 为 null → 退化普通 JSON 分支")

# ====================================================================== 5 Raw 解析
section("5. RawEventParser")

_raw = RawEventParser()
_r1 = _raw.map('{"bigId":"R-1","plateNumber":"京D88888","captureTime":1700000000000,'
               '"deviceId":"Gantry-009","deviceType":"GANTRY"}')
check((_r1.getPointUuid(), _r1.getPlateKey(), _r1.getCaptureTime(),
       _r1.getLocationCode(), _r1.getSourceType())
      == ("R-1", "京D88888", 1700000000000, "Gantry-009", "GANTRY"),
      "数字 captureTime 直接作为毫秒时间戳")

_r2 = _raw.map('{"bigId":"R-2","plateNumber":"京E1","captureTime":"2024-01-15 10:30:00"}')
check(_r2.getCaptureTime() == _expected_ms, "字符串 captureTime → data.getDate 解析")
check(_r2.getSourceType() == "DEVICE-RAW", "缺 deviceType → DEVICE-RAW")

_before = System.currentTimeMillis()
_r3 = _raw.map('{"bigId":"R-3"}')
check(_r3.getPlateKey().startswith("UNKNOWN-") and len(_r3.getPlateKey()) == 16,
      "缺 plateNumber → UNKNOWN-{8位}")
check(_r3.getCaptureTime() >= _before - 5, "缺 captureTime → currentTimeMillis")

_r4 = _raw.map("{bad json")
check(_r4.getSourceType() == "PARSE-ERROR" and len(_r4.getPointUuid()) == 36,
      "坏 JSON → PARSE-ERROR + 新 UUID")

_r5 = _raw.map('{"bigId":"R-5","plateNumber":"京F1","captureTime":"不是时间"}')
check(_r5.getSourceType() == "DEVICE-RAW"
      and _r5.getCaptureTime() >= _before - 5,
      "时间字符串解析失败 → currentTimeMillis（内层 catch）")

# ====================================================================== 6 数据模型
section("6. TrailInfo / TrailState 数据模型")

_event = StandardEvent()
_event.setPointUuid("P-1")
_event.setPlateKey("京A00001")
_event.setCaptureTime(1000)

_state = TrailState()
check(_state.getLatestTrail().getUuid() is None,
      "空 TrailState.getLatestTrail() 返回新对象（不是 null）")
_state.createNewTrail(_event)
_trail = _state.getLatestTrail()
check(len(_state.trails) == 1 and len(_trail.getUuid()) == 32,
      "createNewTrail 生成 32 位 uuid（去掉连字符）")
check((_trail.getPlateKey(), _trail.getEnterTime(), _trail.getExitTime(),
       _trail.getType(), len(_trail.getPoints()))
      == ("京A00001", 1000, 1000, 0, 1),
      "createNewTrail 初始化 enter/exit/type/points")

_e_late = StandardEvent()
_e_late.setCaptureTime(3000)
_e_mid = StandardEvent()
_e_mid.setCaptureTime(2000)
_trail.appendPoint(_e_late)
_trail.appendPoint(_e_mid)
check([p.getCaptureTime() for p in _trail.getPoints()] == [1000, 2000, 3000],
      "appendPoint 按 captureTime 排序")
check((_trail.getEnterTime(), _trail.getExitTime()) == (1000, 3000),
      "appendPoint 刷新首尾时间")
check(_trail.getType() == 1, "点数 >= 3 → type=1")

_trail2 = TrailInfo()
_trail2.appendPoint(_event)
check(_trail2.getType() == 0, "点数 < 3 → type 仍为 0")

# ====================================================================== 7 处理函数
section("7. TrailAggregatorProcessFunction")

_fn = TrailAggregatorProcessFunction()
_fn.open(Configuration())
check(_fn.trailState._name == "trail-state" and _fn.pendingQueue._name == "pending-queue",
      "open() 创建 trail-state / pending-queue 状态")
check(_fn.dictStateDesc.getName() == "dict-broadcast-state"
      and _fn.dictStateDesc.getValueTypeInfo().getTypeClass() is not None,
      "open() 重建同名广播状态描述符")
check(_fn.trailState._context is _fn.getRuntimeContext(),
      "状态句柄绑定同一个 RuntimeContext")

# processElement：首次事件直接建轨迹
_fn.getRuntimeContext().setCurrentKey("京A00001")
_out = Collector()
_fn.processElement(_event, ReadOnlyContext(_fn), _out)
check(len(_out.getOutput()) == 1
      and _out.getOutput()[0].getTrail().getPlateKey() == "京A00001",
      "processElement 首次事件 → 输出 1 条 TrailResult")
check(_fn._timers == [], "appended=true 时不注册定时器")

# processBroadcastElement：写广播状态
_ctx_b = Context(_fn)
_fn.processBroadcastElement({"Gantry-001": {"roadName": "京承高速"}}, _ctx_b, Collector())
check(_fn._broadcast_store["dict-broadcast-state"]
      == {"Gantry-001": {"roadName": "京承高速"}},
      "processBroadcastElement 写入广播状态")
_fn.processBroadcastElement({}, _ctx_b, Collector())
check(_fn._broadcast_store["dict-broadcast-state"]
      == {"Gantry-001": {"roadName": "京承高速"}},
      "空字典不写入（原代码 len>0 判断）")

# 只读上下文不能写广播状态
_ro = ReadOnlyContext(_fn).getBroadcastState(_fn.dictStateDesc)
expect_raises(AttributeError, lambda: _ro.put("k", "v"),
              "ReadOnlyBroadcastState.put 不存在（等价 Java 类型约束）")

# onTimer：待处理队列里的元素被成功拼接
_fn2 = TrailAggregatorProcessFunction()
_fn2.open(Configuration())
_fn2.getRuntimeContext().setCurrentKey("京A00002")
_pending = PendingEvent()
_pending.event = _event
_pending.retryCount = 0
_pending.createTime = 0
_fn2.pendingQueue.add(_pending)
_out2 = Collector()
_fn2.onTimer(0, OnTimerContext(_fn2), _out2)
check(len(_out2.getOutput()) == 1 and len(_fn2.pendingQueue.get()) == 0,
      "onTimer 成功拼接 → 输出 1 条且清空待处理队列")
check(_fn2._timers == [], "onTimer 无剩余重试 → 不再注册定时器")

# ====================================================================== 8 整条流水线
section("8. 完整流水线（源 feed + 广播 + keyBy + process + sink）")


def _build_pipeline(process_function, broadcast_payload=None, data_payload=None):
    env = StreamExecutionEnvironment.getExecutionEnvironment()
    dict_source = env.addSource(DictionarySourceFunction()) \
        .name("Redis 字典数据").setParallelism(1)
    dict_desc = MapStateDescriptor(
        "dict-broadcast-state", Types.STRING,
        TypeInformation.of(TypeHint[dict]))
    broadcast = dict_source.broadcast(dict_desc)
    if broadcast_payload is not None:
        dict_source.feed([broadcast_payload])

    consumer = FlinkKafkaConsumer(VehicleTrackFlinkJob.RAW_DATA_TOPIC,
                                  SimpleStringSchema(), {})
    source = env.addSource(consumer)
    if data_payload:
        source.feed(data_payload)

    result = source.map(RawEventParser()) \
        .keyBy(lambda event: event.getPlateKey()) \
        .connect(broadcast) \
        .process(process_function)
    result.addSink(TrailResultSink())
    return env, dict_source, consumer


_json_t0 = ('{"bigId":"P1","plateNumber":"京Z00001","captureTime":1700000000000,'
            '"deviceId":"Gantry-001","deviceType":"GANTRY"}')
_json_t1 = ('{"bigId":"P2","plateNumber":"京Z00001","captureTime":1700086400000,'
            '"deviceId":"Gantry-001","deviceType":"GANTRY"}')
# t1=1700086400000；+8 天 = 1700777600000（> 7 天阈值 → 切分新轨迹）。
# 注意不能写 +7 天整（1700691200000）：原代码用 `>` 而非 `>=`，正好 7 天不会切分。
_json_t2 = ('{"bigId":"P3","plateNumber":"京Z00001","captureTime":1700777600000,'
            '"deviceId":"Gantry-002","deviceType":"GANTRY"}')

_fn3 = TrailAggregatorProcessFunction()
_env3, _, _consumer3 = _build_pipeline(
    _fn3,
    broadcast_payload={"Gantry-001": {"roadName": "京承高速"}},
    data_payload=[_json_t0, _json_t1, _json_t2])
_emitted3 = _env3.execute("车辆轨迹实时处理 Job")

check(_env3.getJobName() == "车辆轨迹实时处理 Job" and _env3.isExecuted(),
      "execute(jobName) 记录作业名并标记已执行")
check(_consumer3.getTopics() == ["device-raw-data"], "FlinkKafkaConsumer 拿到主题")
check(len(_emitted3) == 3, "3 条事件各输出 1 条 TrailResult")
check(len(_emitted3[0].getTrail().getPoints()) == 1, "第 1 条 → 新轨迹 1 个点")
check(len(_emitted3[1].getTrail().getPoints()) == 2
      and _emitted3[1].getTrail().getType() == 0,
      "第 2 条（+1天）→ 追加到同一轨迹")
check(len(_emitted3[2].getTrail().getPoints()) == 1, "第 3 条（+8天）→ 7 天切分新建轨迹")
check(len(_fn3.trailState.value().trails) == 2,
      "键控状态里共 2 条轨迹（按车牌分桶）")
check(_fn3._broadcast_store["dict-broadcast-state"]
      == {"Gantry-001": {"roadName": "京承高速"}},
      "流水线里 processBroadcastElement 先于数据元素执行")

# 另一个车牌拥有独立状态（keyBy 分桶）
_fn4 = TrailAggregatorProcessFunction()
_json_other = ('{"bigId":"Q1","plateNumber":"京Y00002","captureTime":1700000000000}')
_env4, _, _ = _build_pipeline(_fn4, data_payload=[_json_t0, _json_other])
_emitted4 = _env4.execute("other-plate")
check(len(_emitted4) == 2, "两个车牌各输出 1 条")
_fn4.getRuntimeContext().setCurrentKey("京Y00002")
check(len(_fn4.trailState.value().trails) == 1, "京Y00002 的状态独立")
_fn4.getRuntimeContext().setCurrentKey("京Z00001")
check(len(_fn4.trailState.value().trails) == 1, "京Z00001 的状态独立")

# ---- 定时器重试链路：tryAppendToTrail 恒 false → 60 秒重试 3 次后丢弃 ----
section("9. onTimer 重试 3 次后丢弃（定时器自动触发）")

_capture = _Capture()
_log = logging.getLogger("com.ruoyi.base.flink.VehicleTrackFlinkJob")
_log.addHandler(_capture)
_log.setLevel(logging.DEBUG)


class _NeverAppend(TrailAggregatorProcessFunction):
    """仅用于验证重试逻辑：让 tryAppendToTrail 始终失败。"""

    def tryAppendToTrail(self, state, event):
        return False


_fn5 = _NeverAppend()
_env5, _, _ = _build_pipeline(_fn5, data_payload=[_json_t0])
_emitted5 = _env5.execute("retry-job")
_log.removeHandler(_capture)
_log.setLevel(logging.WARNING)

check(_emitted5 == [], "重试期间不产生输出")
check(_fn5.pendingQueue.get() == [], "重试 3 次后从待处理队列丢弃")
check(_fn5._timers == [], "丢弃后不再注册定时器（替身不会死循环）")
check("超过最大重试次数(3)" in _capture.text(),
      "丢弃时输出 warn 日志（MAX_PENDING_RETRY=3）")

# ====================================================================== 10 替身
section("10. Flink / JDK 替身行为")

check(Time.milliseconds(1500).toMilliseconds() == 1500, "Time.milliseconds")
check(Time.minutes(2).toMilliseconds() == 120000, "Time.minutes")
check(Time.seconds(3).toMinutes() == 0 and Time.days(1).toSeconds() == 86400,
      "Time 单位换算")
check(Time.milliseconds(5) == Time.milliseconds(5), "Time 值相等")

check(TypeHint[TrailState].getType() is TrailState, "TypeHint[X] 显式携带类型（泛型擦除补偿）")
check(TypeInformation.of(TypeHint[TrailState]).getTypeClass() is TrailState,
      "TypeInformation.of(TypeHint) 取到类型")
check(TypeInformation.of(str).getTypeClass() is str, "TypeInformation.of(Class) 取到类型")

check(Types.STRING.getTypeClass() is str and Types.LONG.getTypeClass() is int,
      "Types.STRING / Types.LONG 静态字段")
expect_raises(AttributeError, lambda: Types.OBJECT,
              "Types 没有 OBJECT（[修复2] 的约束在 Python 侧同样成立）")

_ttl = StateTtlConfig.newBuilder(Time.milliseconds(VehicleTrackFlinkJob.STATE_TTL)) \
    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite) \
    .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired) \
    .cleanupIncrementally(10, True) \
    .build()
check(_ttl.getTtl().toMilliseconds() == 2592000000, "StateTtlConfig TTL=30天")
check(_ttl.getUpdateType() == "OnCreateAndWrite", "UpdateType.OnCreateAndWrite")
check(_ttl.getStateVisibility() == "NeverReturnExpired", "StateVisibility.NeverReturnExpired")
check((_ttl.cleanup_size, _ttl.cleanup_every_record) == (10, True),
      "cleanupIncrementally(10, true)")
_vsd = ValueStateDescriptor("trail-state", TypeInformation.of(TypeHint[TrailState]))
check(_vsd.enableTimeToLive(_ttl) is _vsd and _vsd.getTtlConfig() is _ttl,
      "enableTimeToLive 返回 this 且配置生效")
check(ListStateDescriptor("pending-queue", Types.STRING).getName() == "pending-queue",
      "ListStateDescriptor.name")
_msd = MapStateDescriptor("dict-broadcast-state", Types.STRING, Types.LONG)
check((_msd.getName(), _msd.getKeyTypeInfo().getTypeClass(),
       _msd.getValueTypeInfo().getTypeClass()) == ("dict-broadcast-state", str, int),
      "MapStateDescriptor(name, keyType, valueType)")

_schema = SimpleStringSchema()
check(_schema.serialize("京A") == "京A".encode("utf-8")
      and _schema.deserialize("京A".encode("utf-8")) == "京A",
      "SimpleStringSchema UTF-8 编解码")
check(_schema.getProducedType().getTypeClass() is str, "SimpleStringSchema 产出 String 类型")

check(CheckpointingMode.valueOf("EXACTLY_ONCE") == "EXACTLY_ONCE", "CheckpointingMode.valueOf")
expect_raises(ValueError, lambda: CheckpointingMode.valueOf("NONE"),
              "CheckpointingMode 非法枚举值 → ValueError")

_consumer = FlinkKafkaConsumer("t1", SimpleStringSchema(), {"group.id": "g"})
check(_consumer.getTopics() == ["t1"] and _consumer.getProperties()["group.id"] == "g",
      "FlinkKafkaConsumer 保存 topic / props")
_consumer.run(SourceContext(_consumer))
check(_consumer.isRunning() is True, "run() 立即返回（不连 Kafka）")
_consumer.cancel()
check(_consumer.isRunning() is False, "cancel() 置 isRunning=False")

# DictionarySourceFunction：用 sleep 桩跑一轮，避免真的等 10 分钟
import java.lang.Thread as _thread_module  # noqa: E402

_dict_fn = DictionarySourceFunction()
# run() 结束后 isRunning 会被 sleep 桩置 False（模拟另一线程 cancel），
# 所以“初值 True”必须在 run 之前采样；cancel() 另用新实例验证。
_initial_running = _dict_fn.isRunning
_sleep_calls = []
_original_sleep = _thread_module.Thread.sleep


def _fake_sleep(millis):
    _sleep_calls.append(millis)
    _dict_fn.isRunning = False  # 让 while 在下一轮退出


_thread_module.Thread.sleep = staticmethod(_fake_sleep)
try:
    _dict_ctx = SourceContext(_dict_fn)
    _dict_fn.run(_dict_ctx)
finally:
    # 【Java→Python】还原时必须再包一层 staticmethod，否则类属性变成普通函数
    _thread_module.Thread.sleep = staticmethod(_original_sleep)

check(_initial_running is True, "DictionarySourceFunction 初值 isRunning=True")
check(_dict_fn.isRunning is False, "桩内 cancel 后退出 while 循环")
check(_dict_ctx.getOutput() == [{}], "run() 首轮 collect 一个空 HashMap")
check(_sleep_calls == [600000], "TimeUnit.MINUTES.sleep(10) → 600000ms")
_dict_fn_cancel = DictionarySourceFunction()
_dict_fn_cancel.cancel()
check(_dict_fn_cancel.isRunning is False, "cancel() 置 isRunning=False")

# TrailResultSink
_sink = TrailResultSink()
_sink.invoke(None, SinkFunction.Context())
_sink.invoke(TrailResult(None), SinkFunction.Context())
check(True, "Sink 对 null / trail=null 直接 return（不抛异常）")
_sink_log = _Capture()
_sink_logger = logging.getLogger("com.ruoyi.base.flink.VehicleTrackFlinkJob")
_sink_logger.addHandler(_sink_log)
_sink_logger.setLevel(logging.DEBUG)
_sink.invoke(TrailResult(_trail), SinkFunction.Context())
_sink_logger.removeHandler(_sink_log)
_sink_logger.setLevel(logging.WARNING)
check("[Sink] 输出轨迹" in _sink_log.text()
      and _trail.getUuid() in _sink_log.text()
      and "类型=1" in _sink_log.text(),
      "TrailResultSink 打印 uuid / 车牌 / 点数 / 类型")

# 基类的抽象方法
expect_raises(NotImplementedError, lambda: SourceFunction().run(None),
              "SourceFunction.run 必须由子类实现")
expect_raises(NotImplementedError, lambda: SinkFunction().invoke(None, None),
              "SinkFunction.invoke 必须由子类实现")
expect_raises(NotImplementedError,
              lambda: KeyedBroadcastProcessFunction().processElement(None, None, None),
              "KeyedBroadcastProcessFunction.processElement 必须由子类实现")

_rand = ThreadLocalRandom.current()
_values = [_rand.nextInt(1, 10) for _ in range(200)]
check(min(_values) >= 1 and max(_values) <= 9, "nextInt(1,10) 左闭右开 → [1,9]")
_zeros = [_rand.nextInt(3) for _ in range(200)]
check(min(_zeros) >= 0 and max(_zeros) <= 2, "nextInt(3) → [0,2]")
_doubles = [_rand.nextDouble(1.0, 2.0) for _ in range(100)]
check(min(_doubles) >= 1.0 and max(_doubles) < 2.0, "nextDouble(1.0,2.0) → [1.0,2.0)")
check(isinstance(_rand.nextBoolean(), bool), "nextBoolean 返回 bool")

# ====================================================================== 11 main
section("11. VehicleTrackFlinkJob.main（不启动集群）")

VehicleTrackFlinkJob.main([])
check(True, "main 7 步装配完成且不阻塞")

# ====================================================================== 12 编译
section("12. py_compile 全量校验")

import py_compile  # noqa: E402

_compile_targets = [os.path.join(_ROOT, "pro-business-api", "src", "main", "java",
                                 "com", "ruoyi", "base", "device",
                                 "DeviceDataSimulator.py"),
                    os.path.join(_ROOT, "pro-business-api", "src", "main", "java",
                                 "com", "ruoyi", "base", "flink",
                                 "VehicleTrackFlinkJob.py"),
                    os.path.join(_ROOT, "com", "alibaba", "fastjson2", "JSONObject.py")]
_compile_targets += [os.path.join(_flink_root, item.replace("/", os.sep))
                     for item in _FLINK_STUBS]
_compile_targets.append(os.path.join(_ROOT, "java", "util", "concurrent",
                                     "ThreadLocalRandom.py"))
for _target in _compile_targets:
    py_compile.compile(_target, doraise=True)
check(len(_compile_targets) == 33, "py_compile 通过 %d 个文件" % len(_compile_targets))

print("\nT09F SMOKE PASSED: %d assertions" % PASS)
