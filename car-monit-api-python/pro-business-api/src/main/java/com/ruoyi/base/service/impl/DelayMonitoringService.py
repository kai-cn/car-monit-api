# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DelayMonitoringService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DelayMonitoringService.java
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from java.lang.System import System
from java.util.concurrent.ConcurrentHashMap import ConcurrentHashMap
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate
from org.springframework.scheduling.annotation.Scheduled import Scheduled

__all__ = ["DelayMonitoringService"]

log = logging.getLogger(__name__)


class DelayMonitoringService(object):
    """延迟监控服务

    【Java→Python】
    1) `@Service` → 普通类；`@Autowired` 字段 → 构造器参数；`@PostConstruct init()` →
       构造末尾显式调用（Spring 容器本来会在依赖注入完成后自动调用）。
    2) `@Value("${monitoring.device-report-threshold-ms:5000}")` 等 5 个配置项 →
       通过 `Environment.value("${...}", int)` 解析（支持 application.yml + 环境变量覆盖）。
    3) `private static final String XXX_PREFIX` → **类属性**（Python 没有“静态常量”语法，
       类属性同样只有一份，且可以通过 self.XXX 访问，调用处无需改写）。
    4) `ConcurrentHashMap<String, Long>` → `ConcurrentHashMap`（见该替身注释）：
       Java 的 `put/remove` 返回值语义完全保留；`Long` 与 `int` 在 Python 中统一为 int。
    5) `System.currentTimeMillis()` → `java.lang.System` 替身，返回毫秒 int。
    """

    # ==================== Redis Key 常量 ====================

    DEVICE_DELAY_PREFIX = "monitoring:delay:device:"
    MESSAGE_DELAY_PREFIX = "monitoring:delay:message:"
    PROCESS_DELAY_PREFIX = "monitoring:delay:process:"
    E2E_DELAY_PREFIX = "monitoring:delay:e2e:"
    ALERT_COUNT_PREFIX = "monitoring:alert:count:"

    def __init__(self,
                 redisTemplate: Optional[RedisTemplate] = None,
                 environment: Optional[Environment] = None) -> None:
        self.redisTemplate = redisTemplate or defaultRedisTemplate()

        # ==================== 配置参数（@Value） ====================
        env = environment or Environment()
        self.deviceReportThresholdMs = env.value("${monitoring.device-report-threshold-ms:5000}", int)
        self.messageTransferThresholdMs = env.value("${monitoring.message-transfer-threshold-ms:3000}", int)
        self.dataProcessThresholdMs = env.value("${monitoring.data-process-threshold-ms:10000}", int)
        self.endToEndThresholdMs = env.value("${monitoring.end-to-end-threshold-ms:30000}", int)
        self.statsWindowMinutes = env.value("${monitoring.stats-window-minutes:10}", int)

        # ==================== 本地缓存 ====================
        # 【Java→Python】`final` 字段 → 在 __init__ 里赋值一次的实例属性（Python 无 final）
        self.messageProduceTimes = ConcurrentHashMap()
        self.messageConsumeTimes = ConcurrentHashMap()
        self.deviceCaptureTimes = ConcurrentHashMap()

        # ==================== 线程池 ====================
        self.statsExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    # ------------------------------------------------------------------ 生命周期
    def init(self) -> None:
        """@PostConstruct：初始化线程池并打印阈值配置。"""
        self.statsExecutor = Executors.newFixedThreadPool(2)
        log.info("[延迟监控] 初始化完成，设备上报阈值: %dms, 消息传输阈值: %dms, 数据处理阈值: %dms, 端到端阈值: %dms",
                 self.deviceReportThresholdMs, self.messageTransferThresholdMs,
                 self.dataProcessThresholdMs, self.endToEndThresholdMs)

    # ==================== 设备上报延迟监控 ====================

    def recordDeviceCaptureTime(self, dataId: str, captureTime: int) -> None:
        """记录设备采集时间

        :param dataId: 数据ID
        :param captureTime: 设备采集时间戳
        """
        self.deviceCaptureTimes.put(dataId, captureTime)

    def recordServiceReceiveTime(self, dataId: str, deviceId: str) -> int:
        """记录服务接收时间并计算上报延迟

        【Java→Python】`Long captureTime = map.remove(dataId)` 可能为 null，
        因此下面的 `if captureTime != null` 是**必要**的判空（Python 用 is not None）。
        """
        captureTime = self.deviceCaptureTimes.remove(dataId)  # Map.remove 返回旧值
        receiveTime = System.currentTimeMillis()

        if captureTime is not None:
            delay = receiveTime - captureTime

            # 记录到Redis
            key = self.DEVICE_DELAY_PREFIX + deviceId + ":" + self.formatDate(datetime.now())
            self.redisTemplate.opsForList().rightPush(key, delay)
            self.redisTemplate.expire(key, 2, TimeUnit.DAYS)

            # 检查是否超过阈值
            if delay > self.deviceReportThresholdMs:
                self.triggerAlert("DEVICE_REPORT_DELAY", deviceId, delay, self.deviceReportThresholdMs)

            log.debug("[延迟监控] 设备上报延迟: deviceId=%s, dataId=%s, delay=%dms", deviceId, dataId, delay)
            return delay

        return -1

    # ==================== 消息传输延迟监控 ====================

    def recordMessageProduceTime(self, messageId: str) -> None:
        """记录消息生产时间

        :param messageId: 消息ID
        """
        self.messageProduceTimes.put(messageId, System.currentTimeMillis())

    def recordMessageConsumeTime(self, messageId: str) -> int:
        """记录消息消费时间并计算传输延迟"""
        produceTime = self.messageProduceTimes.remove(messageId)
        consumeTime = System.currentTimeMillis()

        if produceTime is not None:
            delay = consumeTime - produceTime

            # 记录到Redis
            key = self.MESSAGE_DELAY_PREFIX + self.formatDate(datetime.now())
            self.redisTemplate.opsForList().rightPush(key, delay)
            self.redisTemplate.expire(key, 2, TimeUnit.DAYS)

            # 检查是否超过阈值
            if delay > self.messageTransferThresholdMs:
                self.triggerAlert("MESSAGE_TRANSFER_DELAY", messageId, delay, self.messageTransferThresholdMs)

            log.debug("[延迟监控] 消息传输延迟: messageId=%s, delay=%dms", messageId, delay)
            return delay

        return -1

    # ==================== 数据处理延迟监控 ====================

    def recordProcessStartTime(self, messageId: str) -> None:
        """记录消息消费开始时间"""
        self.messageConsumeTimes.put(messageId, System.currentTimeMillis())

    def recordProcessEndTime(self, messageId: str) -> int:
        """记录数据写入完成时间并计算处理延迟"""
        consumeTime = self.messageConsumeTimes.remove(messageId)
        endTime = System.currentTimeMillis()

        if consumeTime is not None:
            delay = endTime - consumeTime

            # 记录到Redis
            key = self.PROCESS_DELAY_PREFIX + self.formatDate(datetime.now())
            self.redisTemplate.opsForList().rightPush(key, delay)
            self.redisTemplate.expire(key, 2, TimeUnit.DAYS)

            # 检查是否超过阈值
            if delay > self.dataProcessThresholdMs:
                self.triggerAlert("DATA_PROCESS_DELAY", messageId, delay, self.dataProcessThresholdMs)

            log.debug("[延迟监控] 数据处理延迟: messageId=%s, delay=%dms", messageId, delay)
            return delay

        return -1

    # ==================== 端到端延迟监控 ====================

    def calculateEndToEndDelay(self, dataId: str, captureTime: int, storageTime: int, deviceId: str) -> int:
        """计算端到端延迟：从设备采集到最终存储的完整延迟"""
        delay = storageTime - captureTime

        # 记录到Redis
        key = self.E2E_DELAY_PREFIX + deviceId + ":" + self.formatDate(datetime.now())
        self.redisTemplate.opsForList().rightPush(key, delay)
        self.redisTemplate.expire(key, 2, TimeUnit.DAYS)

        # 检查是否超过阈值
        if delay > self.endToEndThresholdMs:
            self.triggerAlert("END_TO_END_DELAY", deviceId, delay, self.endToEndThresholdMs)

        log.debug("[延迟监控] 端到端延迟: deviceId=%s, dataId=%s, delay=%dms", deviceId, dataId, delay)
        return delay

    # ==================== 告警触发 ====================

    def triggerAlert(self, alertType: str, targetId: str, actualDelay: int, threshold: int) -> None:
        """触发告警（检查告警频率，避免频繁告警）

        【Java→Python】`(Long) lastAlertObj` 这个**强制类型转换**在 Python 中
        改为 `int(...)`：RedisTemplate 替身用 deepcopy 存取，取出的类型是 int，
        但为了还原“Java 强转失败会抛 ClassCastException”，这里对不可转换的值同样抛错。
        """
        # 检查告警频率（每分钟最多告警1次）
        alertKey = self.ALERT_COUNT_PREFIX + alertType + ":" + targetId
        lastAlertObj = self.redisTemplate.opsForValue().get(alertKey)

        if lastAlertObj is not None:
            lastAlertTime = int(lastAlertObj)  # Java: (Long) lastAlertObj
            if System.currentTimeMillis() - lastAlertTime < 60000:
                # 1分钟内已告警过，跳过
                return

        # 更新告警时间
        self.redisTemplate.opsForValue().set(alertKey, System.currentTimeMillis(), 1, TimeUnit.MINUTES)

        # 发送告警
        # 【Java→Python】String.format("[%s] ... %d ...") → Python 的 % 格式化；
        # Java 的 %d 只接受整数，这里传入的也是 int（delay/threshold 均为 long）。
        alertMessage = "[%s] 延迟超过阈值！目标: %s, 实际延迟: %dms, 阈值: %dms" % (
            alertType, targetId, actualDelay, threshold)

        log.error("[延迟监控告警] %s", alertMessage)
        # TODO: 集成告警系统

    # ==================== 统计报告 ====================

    @Scheduled(fixedRate=600000)  # 每10分钟（Spring 由容器调度，见 Scheduled 替身注释）
    def generateStatsReport(self) -> None:
        """定时生成统计报告

        【Java→Python】`statsExecutor.submit(() -> {...})` → `submit(闭包)`；
        注意闭包内异常必须自行捕获，否则会被存进 Future 而**不会打印**
        （Java 里未捕获异常同样只进 Future，这里显式 try/except 并记录日志）。
        """
        def task() -> None:
            try:
                stats = self.calculateStats()
                log.info("[延迟监控统计] 设备上报: avg=%dms, max=%dms | 消息传输: avg=%dms, max=%dms | "
                         "数据处理: avg=%dms, max=%dms | 端到端: avg=%dms, max=%dms",
                         stats.device_report_avg, stats.device_report_max,
                         stats.message_transfer_avg, stats.message_transfer_max,
                         stats.data_process_avg, stats.data_process_max,
                         stats.end_to_end_avg, stats.end_to_end_max)
            except Exception:  # noqa: BLE001 - 与 Java catch (Exception e) 一致
                log.exception("[延迟监控] 生成统计报告异常")

        self.statsExecutor.submit(task)

    def calculateStats(self) -> "DelayMonitoringService.DelayStats":
        """计算延迟统计数据"""
        stats = DelayMonitoringService.DelayStats()

        # 计算设备上报延迟统计
        deviceDelays = self.getDelays(self.DEVICE_DELAY_PREFIX)
        stats.setDeviceReportAvg(self.calculateAvg(deviceDelays))
        stats.setDeviceReportMax(self.calculateMax(deviceDelays))

        # 计算消息传输延迟统计
        messageDelays = self.getDelays(self.MESSAGE_DELAY_PREFIX)
        stats.setMessageTransferAvg(self.calculateAvg(messageDelays))
        stats.setMessageTransferMax(self.calculateMax(messageDelays))

        # 计算数据处理延迟统计
        processDelays = self.getDelays(self.PROCESS_DELAY_PREFIX)
        stats.setDataProcessAvg(self.calculateAvg(processDelays))
        stats.setDataProcessMax(self.calculateMax(processDelays))

        # 计算端到端延迟统计
        e2eDelays = self.getDelays(self.E2E_DELAY_PREFIX)
        stats.setEndToEndAvg(self.calculateAvg(e2eDelays))
        stats.setEndToEndMax(self.calculateMax(e2eDelays))

        return stats

    def getDelays(self, prefix: str) -> List[int]:
        """获取延迟数据列表

        【Java→Python】`values.forEach(v -> delays.add((Long) v))` → 循环 + int 转换；
        Java 的 `redisTemplate.keys(pattern)` 可能返回 null（Java 判空），这里同样判 None。
        """
        delays: List[int] = []
        today = self.formatDate(datetime.now())

        keys = self.redisTemplate.keys(prefix + "*:" + today)
        if keys is not None:
            for key in keys:
                values = self.redisTemplate.opsForList().range(key, 0, -1)
                if values is not None:
                    for value in values:
                        delays.append(int(value))  # Java: (Long) v

        return delays

    def calculateAvg(self, values: List[int]) -> int:
        """计算平均值

        【Java→Python】`stream().mapToLong(...).average()` 返回 double，
        `(long) ...` 是**向零截断**；Python 的 `int()` 对正数同样是截断。
        空集合返回 0（Java 的 orElse(0)）。
        """
        if not values:
            return 0
        return int(sum(values) / len(values))

    def calculateMax(self, values: List[int]) -> int:
        """计算最大值（空集合返回 0）。"""
        if not values:
            return 0
        return max(values)

    def formatDate(self, date: datetime) -> str:
        """格式化日期为 yyyyMMdd

        【Java→Python】Java 原文用的是**已废弃**的 `date.getYear() + 1900` /
        `getMonth() + 1` / `getDate()`，等价于 `strftime("%Y%m%d")`；
        注意 Java 的月份从 0 开始，Python 的 `%m` 从 1 开始，这里用 strftime 避免 ±1 陷阱。
        """
        return date.strftime("%Y%m%d")

    # ------------------------------------------------------------------ 内部类
    @dataclass
    class DelayStats(JavaBean):
        """延迟统计数据

        【Java→Python】`@Data public static class DelayStats` → 嵌套 `@dataclass` +
        继承 `JavaBean`：既保留 `getXxx()/setXxx()` 的 Java 调用写法，
        又提供 dataclass 的字段默认值（Java 的 long 默认 0）。
        """

        device_report_avg: int = 0  # Java: private long deviceReportAvg;
        device_report_max: int = 0  # Java: private long deviceReportMax;
        message_transfer_avg: int = 0  # Java: private long messageTransferAvg;
        message_transfer_max: int = 0  # Java: private long messageTransferMax;
        data_process_avg: int = 0  # Java: private long dataProcessAvg;
        data_process_max: int = 0  # Java: private long dataProcessMax;
        end_to_end_avg: int = 0  # Java: private long endToEndAvg;
        end_to_end_max: int = 0  # Java: private long endToEndMax;
