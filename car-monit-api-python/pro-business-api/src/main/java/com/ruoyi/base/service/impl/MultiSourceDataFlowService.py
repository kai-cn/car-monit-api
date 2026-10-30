# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.MultiSourceDataFlowService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/MultiSourceDataFlowService.java

多源数据流转服务：统一接收门架抓拍 / 省界称重 / 收费站 / 卡口流水等数据，转换为标准
`TrailBo`，按车牌拼接实时轨迹（Redis），乱序数据进待处理队列重试。

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → `logging.getLogger(__name__)` + 普通类；
   `@Autowired private RedisTemplate redisTemplate;` → 构造器可选参数，缺省
   `defaultRedisTemplate()`（进程级单例，等价 Spring 唯一的 RedisTemplate Bean）。
2) 5 个 `private static final` 常量 → 类属性（全大写）；
   注意 `PENDING_RETRY_INTERVAL` 在原文中**从未被使用**，原样保留。
3) `private static class PendingEvent`（`@lombok.Data` 静态内部类）→ 模块级
   `@dataclass PendingEvent(JavaBean)`；文件末尾挂到
   `MultiSourceDataFlowService.PendingEvent`，保持 Java 的访问路径。
4) `switch (dataType) { case "...": ... }` → if / elif 链。
   【差异】Java 对 `null` 做 switch 会抛 NPE；Python 的 `==` 比较不会抛，
   而是直接落到 `else`（对应 default 分支），此处行为差异已在下方注释标出。
5) 形参/返回值里的 `Object data` → `Any`；Java 的强制类型转换
   `(OdsRtSzdnSnapshotFlowAddcode) data` 在 Python 里无需强转
   （鸭子类型，方法按实际对象调用，传错类型同样会在取属性时抛错）。
6) `String.valueOf(Long)` → `_javaStr(...)`：Java 对 null 返回 "null"，
   Python `str(None)` 是 "None"，二者不同。
7) `DateUtils.parseDateToStr(pattern, date)` 内部就是
   `SimpleDateFormat.format(date)`：date 为 null 时 Java 抛 NPE，
   Python `datetime.strftime` 对 None 抛 AttributeError，语义一致。
8) `long diff = Math.abs(a.getTime() - b.getTime())` → `_epochMillis()` 差值取绝对值；
   `7 * 24 * 60 * 60 * 1000L` 在 Java 是 long 运算，Python int 无溢出概念，直接算。
9) `list.sort(Comparator.comparing(TrailBo::getCaptureTime))` → `sort(key=...)`
   原地排序；captureTime 是 `yyyy-MM-dd HH:mm:ss` 字符串，两种语言排序等价。
10) `Date#before/after` → Python `datetime` 直接比较 `a < b` / `a > b`；
    `a.equals(b)` 之类的引用比较在此无对应写法（Java 用的是 before/after）。
11) `UUID.randomUUID().toString().replace("-", "")` → `java.util.UUID` 替身；
    `String#replace(CharSequence,CharSequence)` 是**全部替换** → Python `str.replace` 同为全部替换。
12) `redisTemplate.opsForValue().set(k, v, 604800, TimeUnit.SECONDS)` 为 4 参重载
    → 替身 `_ValueOperations.set(key, value, timeout, time_unit)`；
    写入/读取都做 deepcopy，模拟 Redis 序列化往返（因此“取出来改完再 set 回去”是必须的）。
13) `(TrailInfo) opsForValue().get(...)` / `(PendingEvent) obj` 裸强转 → 直接使用
    （Python 无泛型擦除后的强转语法；类型错误会在使用处暴露）。
14) `log.error("[数据流转] 处理异常：dataType={}", dataType, e)` 是 SLF4J 的
    “最后一个参数为 Throwable”写法（打印堆栈） → Python `log.exception(...)`。
15) `Set<String> keys = redisTemplate.keys(prefix + "*")` → Python `set[str]`；
    替身用 fnmatch 实现 Redis 的 glob 匹配（含 `*` 通配）。`keys` 空集判断用
    `len(keys) == 0`（Redis KEYS 无匹配返回空集而非 null，替身保持同样语义）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import (
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
)
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
)
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.utils.DateUtils import DateUtils
from java.util.UUID import UUID
from java.util.concurrent.TimeUnit import TimeUnit
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate
import com.ruoyi.common.utils.CommonUtil as CommonUtil

__all__ = ["MultiSourceDataFlowService", "PendingEvent"]

log = logging.getLogger(__name__)


def _javaStr(value: Any) -> str:
    """等价 `String.valueOf(Object)`：null → ``"null"``（Python `str(None)` 是 "None"）。"""
    return "null" if value is None else str(value)


def _epochMillis(value: Optional[datetime]) -> int:
    """等价 `Date#getTime()`（epoch 毫秒）；None 时抛 AttributeError（Java 为 NPE）。"""
    return int(value.timestamp() * 1000)


# 【Java→Python】`@lombok.Data private static class PendingEvent` → 模块级 dataclass。
@dataclass
class PendingEvent(JavaBean):
    """待处理事件包装类（Java 静态内部类 PendingEvent 的等价物）。"""

    event: Optional[TrailBo] = None  # Java: private TrailBo event;
    retry_count: int = 0  # Java: private int retryCount;
    create_time: Optional[datetime] = None  # Java: private Date createTime;


class MultiSourceDataFlowService(object):
    """多源数据流转服务（`@Service`）。"""

    # ==================== 常量定义 ====================

    # Redis 中实时轨迹的 Key 前缀
    REALTIME_TRAIL_KEY_PREFIX = "trail:realtime:"

    # Redis 中待处理队列的 Key 前缀
    PENDING_QUEUE_KEY_PREFIX = "trail:pending:"

    # 实时轨迹 TTL（7 天，单位：秒）
    REALTIME_TRAIL_TTL = 604800

    # 轨迹切割时间阈值（7 天，单位：毫秒）
    # 【Java→Python】`7 * 24 * 60 * 60 * 1000L` 的 long 字面量在 Python 就是普通 int
    TRAIL_SPLIT_THRESHOLD = 7 * 24 * 60 * 60 * 1000

    # 待处理队列重试间隔（60 秒）—— 原文定义了但从未使用，原样保留
    PENDING_RETRY_INTERVAL = 60

    def __init__(self, redisTemplate: Optional[RedisTemplate] = None) -> None:
        # 【Java→Python】@Autowired 缺省用进程级单例 RedisTemplate（等价 Spring 单例 Bean）
        self.redisTemplate: RedisTemplate = redisTemplate or defaultRedisTemplate()

    # ==================== 核心处理流程 ====================

    def processData(self, data: Any, dataType: str) -> None:
        """处理多源数据入口方法。

        思路：统一接收不同来源的数据，转换为标准化TrailBo
        目的：屏蔽不同数据源的差异，提供统一的处理接口

        :param data: 原始数据对象
        :param dataType: 数据类型：GantryCapture/BorderWeighingCapture/StationCapture等
        """
        log.debug("[数据流转] 收到数据，类型：%s，数据：%s", dataType, data)

        try:
            # 步骤1：将不同来源的数据转换为标准化TrailBo
            standardEvent: Optional[TrailBo] = self.convertToStandardEvent(data, dataType)
            if standardEvent is None:
                log.warning("[数据流转] 数据转换失败，跳过：dataType=%s", dataType)
                return

            # 步骤2：获取车牌标识
            plateKey: Optional[str] = standardEvent.getPlatenumber()
            if CommonUtil.isBlank(plateKey):
                log.warning("[数据流转] 车牌号为空，跳过处理：pointUuid=%s",
                            standardEvent.getPointUuid())
                return

            # 步骤3：尝试直接拼接到轨迹
            appended = self.tryAppendToTrail(plateKey, standardEvent)

            # 步骤4：如果无法直接拼接，加入待处理队列
            if not appended:
                log.info("[数据流转] 无法直接拼接，加入待处理队列：plateKey=%s, pointUuid=%s",
                         plateKey, standardEvent.getPointUuid())
                self.addToPendingQueue(plateKey, standardEvent)

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 【Java→Python】原文 `log.error(msg, dataType, e)`：SLF4J 把末尾 Throwable 当堆栈
            log.exception("[数据流转] 处理异常：dataType=%s", dataType)

    def convertToStandardEvent(self, data: Any, dataType: str) -> Optional[TrailBo]:
        """将不同来源的数据转换为标准化TrailBo。

        思路：根据stateType判断数据来源，调用对应的转换方法
        目的：统一多源数据格式，为后续轨迹拼接提供标准化输入

        :param data: 原始数据对象
        :param dataType: 数据类型
        :return: 标准化的TrailBo对象
        """
        trailBo = TrailBo()
        trailBo.setStateType(dataType)

        # 【Java→Python】switch(dataType) → if/elif 链。
        # 【行为差异】Java 对 null 做 switch 会抛 NPE；Python 比较不会抛，
        # 会像未知类型一样落到末尾的 default 分支（打 warn 并返回 null）。
        if dataType == "GantryCapture":
            # 门架抓拍数据转换
            return self.convertFromGantryCapture(data, trailBo)
        elif dataType == "BorderWeighingCapture":
            # 省界称重数据转换
            return self.convertFromBorderWeighing(data, trailBo)
        elif dataType == "StationCapture":
            # 收费站抓拍数据转换
            return self.convertFromStationCapture(data, trailBo)
        elif dataType == "FeeRecord":
            # 卡口流水数据转换
            return self.convertFromFeeRecord(data, trailBo)
        elif dataType == "FeeStationEnter":
            # 收费站入口数据转换
            return self.convertFromFeeStationEnter(data, trailBo)
        elif dataType == "FeeStationExit":
            # 收费站出口数据转换
            return self.convertFromFeeStationExit(data, trailBo)
        else:
            log.warning("[数据转换] 未知的数据类型：%s", dataType)
            return None

    def convertFromGantryCapture(self,
                                 data: OdsRtSzdnSnapshotFlowAddcode,
                                 trailBo: TrailBo) -> TrailBo:
        """门架抓拍数据转换。"""
        trailBo.setPointUuid(data.getBigId())
        trailBo.setPlatenumber(data.getPlatenumber())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getSnapshottime()))
        trailBo.setLocationCode(data.getDeviceip())
        trailBo.setRoadCode(data.getRoadcode())
        trailBo.setSectionCode(data.getSectioncode())
        trailBo.setLon(data.getLon())
        trailBo.setLat(data.getLat())
        # 【Java→Python】TrailBo 中该字段无 private 修饰符（包级私有），Lombok 仍生成 setter
        trailBo.setGantryCaptureBO(data)
        trailBo.setIpType("gantryip")

        # 补充点UUID到原始数据中
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def convertFromBorderWeighing(self,
                                  data: OdsSzdnProvinceBorderVehicleWeightNewstructure,
                                  trailBo: TrailBo) -> TrailBo:
        """省界称重数据转换。"""
        trailBo.setPointUuid(data.getDatauuid())
        trailBo.setPlatenumber(data.getPlateNo())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getCheckTime()))
        trailBo.setLocationCode(data.getLocation())
        trailBo.setBorderWeighingCaptureBO(data)
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def convertFromStationCapture(self,
                                  data: OdsRtSzdnSnapshotFlowStationcaptureAddcode,
                                  trailBo: TrailBo) -> TrailBo:
        """收费站抓拍数据转换。"""
        # 【Java→Python】String.valueOf(...) → _javaStr(...)，null 语义保持 "null"
        trailBo.setPointUuid(_javaStr(data.getBigId()))
        trailBo.setPlatenumber(data.getPlatenumber())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getSnapshottime()))
        trailBo.setLocationCode(data.getDeviceip())
        trailBo.setStationCapture(data)
        trailBo.setIpType("stationip")
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def convertFromFeeRecord(self, data: OdsLwzxsfsjFeeRecords01, trailBo: TrailBo) -> TrailBo:
        """卡口流水数据转换。"""
        trailBo.setPointUuid(data.getBigId())
        trailBo.setPlatenumber(data.getVehicleplate())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getTranstime()))
        trailBo.setFeeRecord(data)
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def convertFromFeeStationEnter(self,
                                   data: OdsLwzxsfsjFeeStationEnter01,
                                   trailBo: TrailBo) -> TrailBo:
        """收费站入口数据转换。"""
        trailBo.setPointUuid(_javaStr(data.getBigId()))
        trailBo.setPlatenumber(data.getVehicleid())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getEntime()))
        trailBo.setLocationCode(data.getEntolllaneid())
        trailBo.setDirectionIn(True)  # 标记为进入方向
        trailBo.setFeeStationEnter(data)
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def convertFromFeeStationExit(self,
                                  data: OdsLwzxsfsjFeeStationExit01,
                                  trailBo: TrailBo) -> TrailBo:
        """收费站出口数据转换。"""
        trailBo.setPointUuid(data.getBigId())
        trailBo.setPlatenumber(data.getExvehicleid())
        trailBo.setCaptureTime(DateUtils.parseDateToStr(
            DateUtils.YYYY_MM_DD_HH_MM_SS, data.getExtime()))
        trailBo.setLocationCode(data.getExtolllaneid())
        trailBo.setDirectionIn(False)  # 标记为驶出方向
        trailBo.setFeeStationExit(data)
        trailBo.setPointJosn(JSON.toJSONString(data))
        return trailBo

    def tryAppendToTrail(self, plateKey: str, newEvent: TrailBo) -> bool:
        """尝试将事件拼接到现有轨迹。

        思路：
        1. 从Redis获取该车牌的当前轨迹
        2. 判断新事件是否能拼接到当前轨迹
        3. 如果时间差超过7天，开启新轨迹链
        4. 更新轨迹并保存回Redis

        目的：实现轨迹的动态拼接和更新

        :param plateKey: 车牌标识
        :param newEvent: 新事件
        :return: 是否拼接成功
        """
        trailKey = self.REALTIME_TRAIL_KEY_PREFIX + plateKey

        try:
            # 步骤1：获取当前轨迹（裸强转 (TrailInfo) → 无需强转）
            currentTrail: Optional[TrailInfo] = self.redisTemplate.opsForValue().get(trailKey)

            if currentTrail is None or currentTrail.getTracks() is None:
                # 无现有轨迹，创建新轨迹
                log.info("[轨迹拼接] 无现有轨迹，创建新轨迹：plateKey=%s", plateKey)
                self.createNewTrail(plateKey, newEvent)
                return True

            # 步骤2：判断是否需要切割轨迹（时间差超过7天）
            needSplit = self.needSplitTrail(currentTrail, newEvent)

            if needSplit:
                log.info("[轨迹拼接] 时间差超过7天，开启新轨迹链：plateKey=%s", plateKey)
                self.createNewTrail(plateKey, newEvent)
                return True

            # 步骤3：拼接到现有轨迹
            self.appendToExistingTrail(currentTrail, newEvent)

            # 步骤4：保存更新后的轨迹
            self.redisTemplate.opsForValue().set(
                trailKey, currentTrail, self.REALTIME_TRAIL_TTL, TimeUnit.SECONDS)
            log.debug("[轨迹拼接] 成功拼接到现有轨迹：plateKey=%s, pointUuid=%s",
                      plateKey, newEvent.getPointUuid())

            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[轨迹拼接] 异常：plateKey=%s", plateKey)
            return False

    def needSplitTrail(self, currentTrail: TrailInfo, newEvent: TrailBo) -> bool:
        """判断是否需要切割轨迹。

        思路：比较新事件时间与轨迹起止时间的差值
        目的：超过7天则认为是新的行程

        :param currentTrail: 当前轨迹
        :param newEvent: 新事件
        :return: 是否需要切割
        """
        tracks: ZdataTrailTracks = currentTrail.getTracks()
        # 【Java→Python】captureTime 为字符串，parseDate 失败时返回 None，
        # 后者在 _epochMillis 处抛 AttributeError（等价 Java 的 NPE）
        eventTime: Optional[datetime] = DateUtils.parseDate(newEvent.getCaptureTime())

        if tracks.getEnterTime() is None or tracks.getExitTime() is None:
            return False

        # 计算与进入时间的差
        diffWithEnter = int(abs(_epochMillis(eventTime) - _epochMillis(tracks.getEnterTime())))
        # 计算与离开时间的差
        diffWithExit = int(abs(_epochMillis(eventTime) - _epochMillis(tracks.getExitTime())))

        # 任意一个差值超过7天，就需要切割
        return (diffWithEnter > MultiSourceDataFlowService.TRAIL_SPLIT_THRESHOLD
                or diffWithExit > MultiSourceDataFlowService.TRAIL_SPLIT_THRESHOLD)

    def createNewTrail(self, plateKey: str, newEvent: TrailBo) -> None:
        """创建新轨迹。

        思路：以新事件为起点，创建一条新的轨迹链
        目的：处理新行程的轨迹初始化
        """
        newTrail = TrailInfo()
        tracks = ZdataTrailTracks()

        # 生成轨迹UUID（去掉连字符）
        # 【Java→Python】String#replace 为全部替换 → str.replace 语义一致
        tracks.setUuid(UUID.randomUUID().toString().replace("-", ""))
        tracks.setPlateKey(plateKey)
        tracks.setType(0)  # 初始标记为不完整轨迹
        tracks.setPointCount(1)  # Java: 1L

        # 设置时间
        eventTime: Optional[datetime] = DateUtils.parseDate(newEvent.getCaptureTime())
        tracks.setEnterTime(eventTime)
        tracks.setExitTime(eventTime)

        # 初始化轨迹点列表
        trailList: List[TrailBo] = []
        trailList.append(newEvent)

        # 保存完整JSON
        tracks.setTrailPoints(JSON.toJSONString(trailList))

        newTrail.setTrailUuid(tracks.getUuid())
        newTrail.setTracks(tracks)
        newTrail.setTrailList(trailList)

        # 保存到Redis
        trailKey = self.REALTIME_TRAIL_KEY_PREFIX + plateKey
        self.redisTemplate.opsForValue().set(
            trailKey, newTrail, self.REALTIME_TRAIL_TTL, TimeUnit.SECONDS)

        log.info("[轨迹拼接] 创建新轨迹成功：plateKey=%s, trailUuid=%s",
                 plateKey, tracks.getUuid())

    def appendToExistingTrail(self, currentTrail: TrailInfo, newEvent: TrailBo) -> None:
        """拼接到现有轨迹。

        思路：
        1. 将新事件加入轨迹点列表
        2. 按时间重新排序
        3. 更新轨迹的起止时间和点数量
        4. 重新生成完整JSON

        目的：将新数据整合进现有轨迹，保持轨迹的完整性
        """
        tracks: ZdataTrailTracks = currentTrail.getTracks()
        trailList: Optional[List[TrailBo]] = currentTrail.getTrailList()

        if trailList is None:
            trailList = []

        # 添加新事件
        trailList.append(newEvent)

        # 按抓拍时间排序（List#sort 原地排序）
        trailList.sort(key=lambda p: p.getCaptureTime())

        # 更新轨迹信息
        tracks.setPointCount(len(trailList))  # Java: (long) trailList.size()

        # 更新起止时间
        firstTime: Optional[datetime] = DateUtils.parseDate(trailList[0].getCaptureTime())
        lastTime: Optional[datetime] = DateUtils.parseDate(
            trailList[len(trailList) - 1].getCaptureTime())

        # 【Java→Python】Date#before / Date#after → datetime 的大小比较
        if tracks.getEnterTime() is None or firstTime < tracks.getEnterTime():
            tracks.setEnterTime(firstTime)
        if tracks.getExitTime() is None or lastTime > tracks.getExitTime():
            tracks.setExitTime(lastTime)

        # 如果轨迹点数量足够，标记为完整轨迹
        if len(trailList) >= 3:
            tracks.setType(1)

        # 更新完整JSON
        tracks.setTrailPoints(JSON.toJSONString(trailList))

        currentTrail.setTrailList(trailList)

    def addToPendingQueue(self, plateKey: str, event: TrailBo) -> None:
        """将事件加入待处理队列。

        思路：使用Redis List存储待处理事件
        目的：暂存无法直接拼接的乱序数据，等待后续重处理
        """
        queueKey = self.PENDING_QUEUE_KEY_PREFIX + plateKey

        # 封装成待处理对象，记录重试次数
        pendingEvent = PendingEvent()
        pendingEvent.setEvent(event)
        pendingEvent.setRetryCount(0)
        pendingEvent.setCreateTime(datetime.now())  # 对应 new Date()

        # 加入Redis List（RLUSH；替身按 deepcopy 模拟序列化）
        self.redisTemplate.opsForList().rightPush(queueKey, pendingEvent)

        log.debug("[待处理队列] 加入队列：plateKey=%s, pointUuid=%s",
                  plateKey, event.getPointUuid())

    def processPendingQueue(self) -> None:
        """处理待处理队列（定时任务调用）。

        思路：定期从队列取出数据重试处理
        目的：解决乱序数据问题，保障轨迹完整性
        """
        log.info("[待处理队列] 开始处理")

        # 获取所有待处理队列的Key（Redis KEYS 支持 glob，无匹配返回空集）
        keys: Optional[set[str]] = self.redisTemplate.keys(
            self.PENDING_QUEUE_KEY_PREFIX + "*")

        if keys is None or len(keys) == 0:
            log.info("[待处理队列] 无待处理数据")
            return

        totalProcessed = 0

        for queueKey in keys:
            # 【Java→Python】String#replace 全部替换 → 同名的 str.replace
            plateKey = queueKey.replace(self.PENDING_QUEUE_KEY_PREFIX, "")

            # 取出队列中的所有数据（0 ~ -1 为全量）
            pendingEvents: Optional[List[Any]] = self.redisTemplate.opsForList().range(
                queueKey, 0, -1)

            if pendingEvents is None or len(pendingEvents) == 0:
                continue

            # 清空队列
            self.redisTemplate.delete(queueKey)

            for obj in pendingEvents:
                # 裸强转 (PendingEvent) obj → 直接使用
                pendingEvent: PendingEvent = obj

                # 尝试处理
                success = self.tryAppendToTrail(plateKey, pendingEvent.getEvent())

                if success:
                    totalProcessed += 1
                else:
                    # 处理失败，检查重试次数
                    pendingEvent.setRetryCount(pendingEvent.getRetryCount() + 1)

                    if pendingEvent.getRetryCount() < 3:
                        # 重新加入队列
                        self.redisTemplate.opsForList().rightPush(queueKey, pendingEvent)
                    else:
                        log.warning("[待处理队列] 超过最大重试次数，放弃：plateKey=%s, pointUuid=%s",
                                    plateKey, pendingEvent.getEvent().getPointUuid())

        log.info("[待处理队列] 处理完成，成功数：%s", totalProcessed)


# 【Java→Python】保持 Java 中 `MultiSourceDataFlowService.PendingEvent` 的访问路径
MultiSourceDataFlowService.PendingEvent = PendingEvent
