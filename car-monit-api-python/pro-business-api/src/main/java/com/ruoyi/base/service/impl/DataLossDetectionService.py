# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DataLossDetectionService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataLossDetectionService.java

数据丢失检测服务（原注释保留）：
1. 检测设备上报数据与数据库实际存储数据之间的差异
2. 识别丢失的数据记录
3. 支持按时间窗口、设备维度进行检测
4. 生成检测报告并触发补偿机制

检测机制：
- 基于消息ID的完整性校验
- 时间窗口内的数据完整性统计
- 设备上报频率分析
- 数据连续性检测（缺失序列号检测）

【Java→Python 本文件重点差异】
1) `@Slf4j`/`@Service`/`@Value`/`@PostConstruct` → logging + 普通类 + Environment + 显式 init()，
   与 DataReliabilityService / DelayMonitoringService 同一套约定。
2) `@Autowired OdsRtSzdnSnapshotFlowAddcodeMapper` → 构造注入，缺省 `Mapper()`（进程内表）。
   `@Autowired DataReliabilityService` → 缺省 `DataReliabilityService()`；**跨 Service 共享状态**
   需要显式传入同一个实例（Spring 里是同一个单例 Bean）。
3) `LambdaQueryWrapper.between(...)` + `.select(...)`：
   - `Entity::getSnapshottime` 方法引用 → `lambda r: r.snapshottime`（不能用 `Entity.snapshottime`，
     dataclass 带默认值的字段类属性就是 None）；
   - SQL 的列投影（只查 bigId）在内存表中无法复现“其它字段为 null”，替身只记录列名，
     本类只用 `getBigId()`，因此结果一致。
4) `List.stream().map(...).collect(Collectors.toSet())` → 集合推导式（同一个 bag 语义）。
5) `Set.removeAll` → Python 的 `set - set`（返回新集合；原集合不变的含义在注释中说明）。
6) `String.format("%.2f", x)` → `format(x, ".2f")`：Java 用**默认 Locale**（如德语环境会输出
   "12,34"），Python 固定用 "."，这是可见差异，已在调用处注明。
7) `new Date(timestamp)` → `datetime.fromtimestamp(timestamp / 1000)`；
   `DateUtils.addMinutes/addHours` 在替身里用 `timedelta` 实现，语义一致。
8) 嵌套 `@Data DetectionResult` → `@dataclass(JavaBean)`；`isPassed()` 是**手写方法**，
   Python 侧同样手写（JavaBean 的 `__getattr__` 不会覆盖已定义的方法）。
9) 【原文疑似缺陷，按“一比一”保留】`@Scheduled(fixedRateString =
   "${detection.interval-minutes:30}000")` 只给分钟数补了 3 个 0 → **30000ms = 30 秒**，
   而不是 30 分钟。为保持与 Java 完全一致的行为，Python 版原样保留，不做“修正”。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper import LambdaQueryWrapper
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.base.service.impl.DataReliabilityService import DataReliabilityService
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.utils.DateUtils import DateUtils
from java.util.UUID import UUID
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate
from org.springframework.scheduling.annotation.Scheduled import Scheduled

__all__ = ["DataLossDetectionService", "DetectionResult"]

log = logging.getLogger(__name__)


@dataclass
class DetectionResult(JavaBean):
    """检测结果（Java 侧为 `public static class DetectionResult`）。

    【Java→Python】
    - `@Data` → `@dataclass` + JavaBean：字段 snake_case，`getLostRate()` 等仍可用；
    - `int`/`double` 基本类型 → Python int/float，默认 0/0.0（**不能**是 None，
      否则 `lossRate > threshold` 在 Java 里是 0.0 比较、Python 会 TypeError）；
    - `Set<String>` → `set`，Java 里默认 null，这里保留 None（与 Java 一致：
      未 set 前 `getLostMessageIds()` 返回 null）。
    """

    start_time: Optional[datetime] = None          # 检测开始时间
    end_time: Optional[datetime] = None            # 检测结束时间
    reported_count: int = 0                        # 上报消息总数
    stored_count: int = 0                          # 数据库存储数量
    lost_count: int = 0                            # 丢失数量
    loss_rate: float = 0.0                         # 丢失率（百分比）
    lost_message_ids: Optional[Set[str]] = None    # 丢失的消息ID列表
    duplicate_count: int = 0                       # 重复数量
    duplicate_message_ids: Optional[Set[str]] = None  # 重复的消息ID列表

    def isPassed(self) -> bool:
        """是否检测通过（手写方法，Java 侧也是手写而非 Lombok 生成）。

        【Java→Python】Java 的 `double == 0` 与 Python 的 `float == 0` 语义一致
        （lossRate 由整数除法得到，不存在 0.0 与 -0.0 的判定差异）。
        """
        return self.loss_rate == 0 and self.duplicate_count == 0


class DataLossDetectionService(object):
    """数据丢失检测服务。"""

    # ==================== Redis Key 常量 ====================
    REPORTED_MSG_PREFIX = "detection:reported:"        # 上报消息ID集合前缀
    REPORT_PREFIX = "detection:report:"                # 检测报告前缀
    DEVICE_COUNT_PREFIX = "detection:device:count:"    # 设备上报计数前缀

    def __init__(self,
                 snapshotFlowMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 reliabilityService: Optional[DataReliabilityService] = None,
                 environment: Optional[Environment] = None) -> None:
        """等价的字段注入 + 配置注入 + @PostConstruct。"""
        self.snapshotFlowMapper = snapshotFlowMapper or OdsRtSzdnSnapshotFlowAddcodeMapper()
        self.redisTemplate = redisTemplate or defaultRedisTemplate()
        # 【Java→Python】Spring 注入的是**同一个** DataReliabilityService 单例；
        # Python 缺省新建一个（Redis/Kafka 仍是进程级单例，只有内存 State 不共享）。
        self.reliabilityService = reliabilityService or DataReliabilityService()

        # ==================== 配置参数 ====================
        env = environment or Environment()
        # 检测窗口大小（分钟）
        self.windowSizeMinutes = env.value("${detection.window-size-minutes:60}", int)
        # 检测间隔（分钟）——注意：只被 @Scheduled 的字符串使用（见文件头第 9 条）
        self.intervalMinutes = env.value("${detection.interval-minutes:30}", int)
        # 丢失率告警阈值（百分比）
        # 【Java→Python】`private double` → Python float；Environment 用 float 转换
        #（Java 的 `@Value` 靠 ConversionService 把 "5" 转成 5.0）。
        self.lossThresholdPercent = env.value("${detection.loss-threshold-percent:5}", float)

        # ==================== 线程池 ====================
        self.detectionExecutor: Optional[ExecutorService] = None  # @PostConstruct 中创建

        self.init()  # @PostConstruct

    def init(self) -> None:
        """等价 `@PostConstruct public void init()`。"""
        # 【Java→Python】daemon 线程池：避免 Python 解释器退出时被工作线程卡住
        self.detectionExecutor = Executors.newFixedThreadPool(4)
        log.info("[数据丢失检测] 初始化完成，窗口大小: %s分钟, 检测间隔: %s分钟, 告警阈值: %s%%",
                 self.windowSizeMinutes, self.intervalMinutes, self.lossThresholdPercent)

    def recordReportedMessage(self, messageId: str, deviceId: str, timestamp: int) -> None:
        """记录上报的消息ID。

        思路：设备上报数据时，将消息ID记录到Redis集合中
        用于后续与数据库数据进行对比

        :param messageId: 消息ID
        :param deviceId: 设备ID
        :param timestamp: 上报时间戳（毫秒）
        """
        # 按小时分组存储，便于后续按时间窗口查询
        # 【Java→Python】`new Date(timestamp)` → `datetime.fromtimestamp(timestamp/1000)`；
        # Java 的 Date 精度到毫秒，Python datetime 保留微秒（此处只格式化到小时，无影响）。
        report_time = datetime.fromtimestamp(timestamp / 1000.0)
        hourKey = self.REPORTED_MSG_PREFIX + DateUtils.formatHour(report_time)
        self.redisTemplate.opsForSet().add(hourKey, messageId)
        self.redisTemplate.expire(hourKey, 48, TimeUnit.HOURS)

        # 设备上报计数
        deviceKey = self.DEVICE_COUNT_PREFIX + deviceId + ":" + DateUtils.formatDate(report_time)
        # INCRBY 在 key 不存在时按 0 处理 → 与 Java 的 increment(deviceKey) 一致
        self.redisTemplate.opsForValue().increment(deviceKey)
        self.redisTemplate.expire(deviceKey, 2, TimeUnit.DAYS)

    @Scheduled(fixedRateString="${detection.interval-minutes:30}000")
    def scheduledDetection(self) -> None:
        """定时检测任务。

        思路：定期检测指定时间窗口内的数据完整性
        1. 获取窗口内上报的消息ID集合
        2. 查询数据库中同一窗口内的数据
        3. 对比找出丢失的数据
        4. 生成检测报告

        【Java→Python】`fixedRateString` 见文件头第 9 条（30000ms = 30 秒，原代码即如此）。
        由 `app.scheduler` 在启动时登记；单独调试也可用 `startScheduledTasks(service)`。
        """

        def _detection_task() -> None:
            try:
                # 计算检测窗口时间范围（当前时间 - 窗口大小）
                endTime = datetime.now()
                startTime = DateUtils.addMinutes(endTime, -self.windowSizeMinutes)

                log.info("[数据丢失检测] 开始检测，时间窗口: %s ~ %s", startTime, endTime)

                # 执行检测
                result = self.detectDataLoss(startTime, endTime)

                # 生成报告
                self.generateReport(result, startTime, endTime)

                # 如果丢失率超过阈值，发送告警
                if result.getLossRate() > self.lossThresholdPercent:
                    self.sendAlert(result)

            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                # Java: log.error("[数据丢失检测] 定时检测异常", e) —— 带堆栈
                log.exception("[数据丢失检测] 定时检测异常")

        self.detectionExecutor.submit(_detection_task)

    def detectDataLoss(self, startTime: datetime, endTime: datetime) -> DetectionResult:
        """执行数据丢失检测。

        思路：
        1. 获取窗口内所有上报的消息ID
        2. 查询数据库中同一窗口的数据
        3. 对比找出丢失的数据

        :param startTime: 开始时间
        :param endTime: 结束时间
        :return: 检测结果
        """
        result = DetectionResult()
        result.setStartTime(startTime)
        result.setEndTime(endTime)

        # 1. 获取窗口内上报的消息ID集合
        reportedMessageIds = self.getReportedMessageIds(startTime, endTime)
        result.setReportedCount(len(reportedMessageIds))
        log.debug("[数据丢失检测] 窗口内上报消息数: %s", len(reportedMessageIds))

        # 2. 查询数据库中同一窗口的数据
        dbRecords = self.queryDatabaseRecords(startTime, endTime)
        result.setStoredCount(len(dbRecords))
        log.debug("[数据丢失检测] 数据库存储记录数: %s", len(dbRecords))

        # 3. 提取数据库中的消息ID
        # Java: dbRecords.stream().map(OdsRtSzdnSnapshotFlowAddcode::getBigId).collect(Collectors.toSet())
        # 【Java→Python】Stream → 集合推导式：两者都是“把每行映射成 bigId 去重”。
        # 注意 Java 的 toSet 允许 null 元素（HashSet 可存 null），Python set 也可以。
        storedMessageIds = {record.getBigId() for record in dbRecords}

        # 4. 找出丢失的消息ID（上报了但未存储）
        # Java: new HashSet<>(reported) + removeAll(stored)
        # 【Java→Python】`-` 生成新集合，等效于“先复制再去差”；不改动 reportedMessageIds。
        lostMessageIds = set(reportedMessageIds) - storedMessageIds
        result.setLostCount(len(lostMessageIds))
        result.setLostMessageIds(lostMessageIds)

        # 5. 计算丢失率
        # 【Java→Python】Java `(double) lost / reported * 100` 是浮点除法；
        # Python 的 `/` 同样是真除法（不是 `//`），无需显式 cast。
        reportedCount = result.getReportedCount()
        lossRate = ((float(result.getLostCount()) / reportedCount) * 100
                    if reportedCount > 0 else 0)
        result.setLossRate(lossRate)

        # 6. 检测重复数据
        duplicateIds = self.findDuplicateRecords(dbRecords)
        result.setDuplicateCount(len(duplicateIds))
        result.setDuplicateMessageIds(duplicateIds)

        # 【Java→Python】`String.format("%.2f", lossRate)` → `format(lossRate, ".2f")`；
        # Java 受默认 Locale 影响（可能出现 "12,34"），Python 固定小数点，属可见差异。
        log.info("[数据丢失检测] 检测完成: 上报=%s, 存储=%s, 丢失=%s, 重复=%s, 丢失率=%s%%",
                 result.getReportedCount(), result.getStoredCount(),
                 result.getLostCount(), result.getDuplicateCount(),
                 format(lossRate, ".2f"))

        return result

    def getReportedMessageIds(self, startTime: datetime, endTime: datetime) -> Set[str]:
        """获取窗口内上报的消息ID集合。"""
        messageIds: Set[str] = set()

        # 遍历窗口内的每个小时
        # 【Java→Python】Java 的 Date 是可变对象，`current = DateUtils.addHours(current, 1)`
        # 返回**新对象**；Python 的 datetime 不可变，写法相同且天然安全。
        current = startTime
        while current < endTime:  # Java: current.before(endTime)
            hourKey = self.REPORTED_MSG_PREFIX + DateUtils.formatHour(current)
            ids = self.redisTemplate.opsForSet().members(hourKey)
            if ids is not None:
                # Java: ids.forEach(id -> messageIds.add((String) id));
                messageIds.update(ids)
            current = DateUtils.addHours(current, 1)

        return messageIds

    def queryDatabaseRecords(self, startTime: datetime, endTime: datetime) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """查询数据库中指定时间窗口的数据。"""
        wrapper = LambdaQueryWrapper()
        # Java: wrapper.between(OdsRtSzdnSnapshotFlowAddcode::getSnapshottime, startTime, endTime);
        # 【Java→Python】方法引用 → lambda（不能写 Entity.snapshottime，拿到的是 None）。
        wrapper.between(lambda r: r.snapshottime, startTime, endTime)
        # Java: wrapper.select(OdsRtSzdnSnapshotFlowAddcode::getBigId);
        # 替身只记录投影列；返回的仍是完整实体副本，本类只用 bigId，故语义一致。
        wrapper.select(lambda r: r.big_id)
        return self.snapshotFlowMapper.selectList(wrapper)

    def findDuplicateRecords(self, records: List[OdsRtSzdnSnapshotFlowAddcode]) -> Set[str]:
        """找出重复记录。"""
        seen: Set[str] = set()
        duplicates: Set[str] = set()

        for record in records:
            bigId = record.getBigId()
            # Java: seen.contains(bigId) → Python 的 `in`
            if bigId in seen:
                duplicates.add(bigId)
            else:
                seen.add(bigId)

        return duplicates

    def generateReport(self, result: DetectionResult, startTime: datetime, endTime: datetime) -> None:
        """生成检测报告。"""
        # Java: UUID.randomUUID().toString().substring(0, 8) → Python 切片 [0:8]
        reportId = UUID.randomUUID().toString()[0:8]
        reportKey = self.REPORT_PREFIX + reportId

        # Java: Map<String, Object> report = new HashMap<>(); ...
        # 【Java→Python】HashMap 无序、dict 保持插入顺序；Redis 存的是序列化后的
        # 映射（无序），取出的内容语义一致。Date 值直接存 datetime 对象。
        report: Dict[str, Any] = {}
        report["reportId"] = reportId
        report["startTime"] = startTime
        report["endTime"] = endTime
        report["reportedCount"] = result.getReportedCount()
        report["storedCount"] = result.getStoredCount()
        report["lostCount"] = result.getLostCount()
        report["duplicateCount"] = result.getDuplicateCount()
        report["lossRate"] = result.getLossRate()
        report["generatedTime"] = datetime.now()  # Java: new Date()

        self.redisTemplate.opsForValue().set(reportKey, report, 7, TimeUnit.DAYS)

        log.info("[数据丢失检测] 生成报告: reportId=%s", reportId)

    def sendAlert(self, result: DetectionResult) -> None:
        """发送告警通知。"""
        # Java:
        # String.format("数据丢失率超过阈值！时间窗口: %s ~ %s, 上报: %d, 存储: %d, 丢失: %d, 丢失率: %.2f%%", ...)
        # 【Java→Python】`%s` 对 Date 调用 Date.toString()（"EEE MMM dd HH:mm:ss zzz yyyy"），
        # Python 的 str(datetime) 是 "yyyy-MM-dd HH:mm:ss.ffffff"，格式不同但信息等价；
        # `%d` → `%d`、`%.2f` → `%.2f`、`%%` → `%%`（PyQt 风格的 % 格式化与 Java 基本一致）。
        alertMessage = ("数据丢失率超过阈值！时间窗口: %s ~ %s, 上报: %d, 存储: %d, 丢失: %d, 丢失率: %.2f%%"
                        % (result.getStartTime(), result.getEndTime(),
                           result.getReportedCount(), result.getStoredCount(),
                           result.getLostCount(), result.getLossRate()))

        log.error("[数据丢失检测告警] %s", alertMessage)
        # TODO: 集成告警系统

    def triggerCompensation(self, result: DetectionResult) -> None:
        """触发补偿拉取。

        思路：根据检测结果，对丢失的数据进行补偿拉取

        :param result: 检测结果
        """
        if result.getLostCount() == 0:
            return

        log.info("[数据丢失检测] 触发补偿拉取，丢失消息数: %s", result.getLostCount())

        # 逐个处理丢失的消息
        # 【Java→Python】`Set<String>` 的迭代顺序在 Java（HashSet）与 Python（set）都未定义，
        # 这里不排序，保持“无序处理”的原语义。
        for messageId in result.getLostMessageIds():
            try:
                # 尝试从缓存获取消息内容并重发
                # 【Java→Python】跨类引用常量：Java 是 DataReliabilityService.MSG_CONTENT_PREFIX，
                # Python 侧类属性直接可见（public static final）。
                messageJson = self.redisTemplate.opsForValue().get(
                    DataReliabilityService.MSG_CONTENT_PREFIX + messageId)

                if messageJson is not None:
                    # 重新发送消息
                    self.reliabilityService.retrySend(messageId)
                else:
                    log.warning("[数据丢失检测] 丢失消息内容已过期: messageId=%s", messageId)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.exception("[数据丢失检测] 补偿拉取异常: messageId=%s", messageId)

    def getDeviceReportStats(self, deviceId: Optional[str], date: datetime) -> Dict[str, int]:
        """获取设备上报统计。

        :param deviceId: 设备ID（可选，为空则返回所有设备）
        :param date: 日期
        :return: 统计数据（deviceId → 上报次数）
        """
        # 【Java→Python】Java `Map<String, Long>` → Python `Dict[str, int]`（int 无溢出概念）。
        stats: Dict[str, int] = {}

        if deviceId is not None:
            key = self.DEVICE_COUNT_PREFIX + deviceId + ":" + DateUtils.formatDate(date)
            count = self.redisTemplate.opsForValue().get(key)
            # Java: Long count = (Long) ...; stats.put(deviceId, count != null ? count : 0L);
            stats[deviceId] = int(count) if count is not None else 0
        else:
            # 获取所有设备的统计
            keys = self.redisTemplate.keys(self.DEVICE_COUNT_PREFIX + "*:" + DateUtils.formatDate(date))
            if keys is not None:
                for key in keys:
                    # Java: key.substring(DEVICE_COUNT_PREFIX.length(), key.lastIndexOf(":"))
                    # 【Java→Python】lastIndexOf(":") 对应 `rindex(":")`；
                    # 若 key 中没有 ":"，Java 抛 StringIndexOutOfBoundsException，
                    # Python 的 rindex 抛 ValueError —— 两者都会中断（本方法不捕获）。
                    devId = key[len(self.DEVICE_COUNT_PREFIX):key.rindex(":")]
                    count = self.redisTemplate.opsForValue().get(key)
                    stats[devId] = int(count) if count is not None else 0

        return stats


# 【Java→Python】Java 中是 DataLossDetectionService.DetectionResult 的嵌套访问路径。
DataLossDetectionService.DetectionResult = DetectionResult
