# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.KafkaProducerService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/KafkaProducerService.java

Kafka生产者服务类（原注释保留）：

功能说明：
- 实现消息发送到Kafka的核心逻辑
- 集成数据可靠性保障服务，确保消息不丢失
- 实现后台重试任务，处理发送失败的消息
- 确保数据零丢失

可靠性保障机制：
1. 消息持久化：发送前先入库，确保消息不丢失
2. 异步确认：注册回调处理发送结果
3. 自动重试：失败消息自动重试，支持指数退避
4. 死信处理：超过重试次数进入死信队列
5. 幂等性：基于消息ID去重
6. 超时检测：未确认消息自动触发补偿

【Java→Python 本文件重点差异】
1) `@Service` + 5 个 `@Autowired` → 构造器可选参数；**缺省时按 Spring 单例关系组装**：
   `KafkaTemplate`/`RedisTemplate` 取进程级单例；`DataReliabilityService` 复用本类的
   `KafkaTemplate` 与 `KafkaMessageRecordMapper`（Spring 里它们本来就是同一个 Bean，
   否则死信记录与重试任务各看一张“表”）。
2) `@Value("${kafka.topic.snapshot-flow:...}")` / `@Value("${kafka.max-retry-count:10}")`
   → `Environment.value(..., str/int)`。
3) `@PostConstruct init()` → `__init__` 末尾显式调用；`init()` 里立刻 `startRetryTask()`，
   等价 Spring 启动即开始补偿。
4) `JSON.parse(json)` → JSON 替身的 `parse`（返回 JSONObject/JSONArray/基本类型）；
   `data instanceof JSONObject` → `isinstance(data, JSONObject)`，判空写法不变。
5) 匿名内部类 `new ListenableFutureCallback<...>(){...}` → 模块级 `_KafkaRecordCallback`
   （持有 service + record），成功/失败两条链路与 Java 逐行对应。
6) `Thread.sleep(30000)` 的无限重试循环 → daemon 线程池里的 `while True`：
   Java 线程池线程默认非守护，JVM 退出时会由 shutdown hook 结束；Python 必须用 daemon，
   否则进程无法退出（替身 Executors 已统一使用 daemon 线程）。
7) `catch (Exception e)` 里再 `catch (InterruptedException ie) { interrupt(); break; }`
   的两层结构原样保留：`java.lang.Thread` 替身用线程本地中断标志复现该语义。
8) `value.toString()` → `str(value)`：Java 对嵌套 JSONObject 输出 JSON（双引号），
   Python 的 str(dict) 输出单引号字典 —— 该值只作为“设备ID”字符串，正常数据为标量。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.KafkaMessageRecord import KafkaMessageRecord
from com.ruoyi.base.mapper.KafkaMessageRecordMapper import KafkaMessageRecordMapper
from com.ruoyi.base.service.impl.DataLossDetectionService import DataLossDetectionService
from com.ruoyi.base.service.impl.DataReliabilityService import DataReliabilityService
from com.ruoyi.base.service.impl.DelayMonitoringService import DelayMonitoringService
from java.lang.System import System
from java.lang.Thread import InterruptedException, Thread
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from org.springframework.core.env.Environment import Environment
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate, defaultKafkaTemplate
from org.springframework.util.concurrent.ListenableFutureCallback import ListenableFutureCallback

__all__ = ["KafkaProducerService"]

log = logging.getLogger(__name__)


class _KafkaRecordCallback(ListenableFutureCallback):
    """`sendMessage` 中的匿名内部类 `new ListenableFutureCallback<SendResult<...>>(){...}`。

    【Java→Python】Java 匿名内部类可直接访问外部类的 3 个注入字段与 `record` 参数；
    Python 用持有 `service + record` 的具名回调类还原，回调里的每一步（更新状态、
    通知可靠性服务）都与源码一一对应。
    """

    def __init__(self, service: "KafkaProducerService", record: KafkaMessageRecord) -> None:
        self._service = service
        self._record = record

    def onSuccess(self, result: Any) -> None:
        """发送成功回调：更新数据库状态为成功，记录发送时间和 offset。"""
        log.info("[Kafka生产者] 消息发送成功: dataId=%s, offset=%s",
                 self._record.getDataId(), result.getRecordMetadata().offset())
        # 更新数据库状态为1（成功），并记录发送时间
        # 【Java→Python】`new Date()` → `datetime.now()`
        self._service.kafkaMessageRecordMapper.updateStatusById(
            self._record.getId(), 1, datetime.now())

        # 通知可靠性服务Kafka已确认
        # 【Java→Python】注意原代码传的是 **dataId** 而不是 messageId（Java 侧即如此），
        # 因此可靠性服务的 pendingMessages 里通常查不到该 key；保持原样不做“修正”。
        self._service.reliabilityService.handleKafkaAck(
            self._record.getDataId(), result.getRecordMetadata().offset())

    def onFailure(self, ex: BaseException) -> None:
        """发送失败回调：更新数据库状态为失败，记录错误信息，增加重试次数。"""
        # 【Java→Python】Java 的 `ex.getMessage()` → Python 的 str(ex)
        message = str(ex)
        log.error("[Kafka生产者] 消息发送失败: dataId=%s, error=%s",
                  self._record.getDataId(), message)
        # 增加重试次数，记录错误信息，状态设为2（失败）
        self._service.kafkaMessageRecordMapper.incrementRetryCount(self._record.getId(), message)

        # 通知可靠性服务发送失败
        self._service.reliabilityService.handleSendFailure(self._record.getDataId(), message)


class KafkaProducerService(object):
    """Kafka生产者服务（`@Service` 单例语义由调用方保证）。"""

    def __init__(self,
                 kafkaTemplate: Optional[KafkaTemplate] = None,
                 kafkaMessageRecordMapper: Optional[KafkaMessageRecordMapper] = None,
                 reliabilityService: Optional[DataReliabilityService] = None,
                 lossDetectionService: Optional[DataLossDetectionService] = None,
                 delayMonitoringService: Optional[DelayMonitoringService] = None,
                 environment: Optional[Environment] = None) -> None:
        # 注入KafkaTemplate，用于发送消息
        self.kafkaTemplate = kafkaTemplate or defaultKafkaTemplate()
        # 注入消息记录Mapper，用于持久化消息状态
        self.kafkaMessageRecordMapper = kafkaMessageRecordMapper or KafkaMessageRecordMapper()

        # 注入数据可靠性服务，用于集成可靠性保障机制
        # 【Java→Python】缺省时把本类的 KafkaTemplate/Mapper 传进去，还原“同一个单例 Bean”
        self.reliabilityService = reliabilityService or DataReliabilityService(
            kafkaTemplate=self.kafkaTemplate,
            kafkaMessageRecordMapper=self.kafkaMessageRecordMapper)
        # 注入数据丢失检测服务，用于记录上报消息（共享同一个可靠性服务）
        self.lossDetectionService = lossDetectionService or DataLossDetectionService(
            reliabilityService=self.reliabilityService)
        # 注入延迟监控服务，用于监控消息延迟
        self.delayMonitoringService = delayMonitoringService or DelayMonitoringService()

        # 从配置文件读取主题名称，默认值为 ods-rt-szdn-snapshot-flow
        env = environment or Environment()
        self.snapshotFlowTopic = env.value(
            "${kafka.topic.snapshot-flow:ods-rt-szdn-snapshot-flow}", str)
        # 从配置文件读取最大重试次数，默认值为 10
        # 【Java→Python】`Integer` 包装类型 → int（配置缺失时由默认值兜底，不会为 null）
        self.maxRetryCount = env.value("${kafka.max-retry-count:10}", int)

        # 重试任务线程池（@PostConstruct 中创建）
        self.retryExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    def init(self) -> None:
        """初始化方法。

        思路：在Bean初始化后自动执行，启动后台重试线程
        目的：确保应用启动后立即开始处理失败消息的重试
        """
        # 创建单线程池，用于执行后台重试任务
        self.retryExecutor = Executors.newSingleThreadExecutor()
        # 启动重试任务
        self.startRetryTask()
        log.info("[Kafka生产者服务] 初始化完成，集成可靠性保障机制")

    def sendSnapshotFlowData(self, data: Any, dataId: str) -> str:
        """发送抓拍流水数据到Kafka（集成可靠性保障）。

        思路：
        1. 记录消息生产时间（用于延迟监控）
        2. 调用可靠性服务发送消息（包含持久化、校验、超时检测）
        3. 记录上报消息ID（用于数据丢失检测）

        目的：实现消息的高可靠性发送，确保数据不丢失

        :param data: 业务数据对象
        :param dataId: 业务数据ID（作为Kafka消息的key）
        :return: 消息ID
        """
        # 1. 记录消息生产时间（用于延迟监控）
        self.delayMonitoringService.recordMessageProduceTime(dataId)

        # 2. 调用可靠性服务发送消息
        messageId = self.reliabilityService.sendReliableMessage(data, dataId, self.snapshotFlowTopic)

        # 3. 记录上报消息ID（用于数据丢失检测）
        self.lossDetectionService.recordReportedMessage(
            messageId, self.extractDeviceId(data), System.currentTimeMillis())

        log.info("[Kafka生产者] 发送消息: dataId=%s, messageId=%s", dataId, messageId)
        return messageId

    def sendMessage(self, record: KafkaMessageRecord) -> None:
        """发送消息到Kafka（内部方法）。

        思路：
        1. 使用KafkaTemplate发送异步消息
        2. 注册回调函数，处理发送成功和失败的情况
        3. 成功时更新数据库状态为成功
        4. 失败时更新数据库状态为失败并记录错误

        目的：实现异步发送和状态更新

        :param record: 消息记录实体
        """
        # 发送异步消息到Kafka
        # 参数说明：
        # - topic: 目标主题
        # - key: dataId，确保相同dataId的消息发送到同一个分区，保证顺序
        # - value: 消息内容，从JSON反序列化为对象
        # 【Java→Python】`JSON.parse` 返回 Object（对象→JSONObject/数组→JSONArray），
        # 与 fastjson2 的返回类型对应；替身的 send 同步完成，回调随之立即触发。
        future = self.kafkaTemplate.send(
            record.getTopic(), record.getDataId(), JSON.parse(record.getMessageJson()))

        # 注册回调函数，处理异步发送结果
        future.addCallback(_KafkaRecordCallback(self, record))

    def startRetryTask(self) -> None:
        """启动后台重试任务。

        思路：
        1. 无限循环，定期查询失败消息
        2. 每次查询一批失败消息进行重试
        3. 两次重试之间休眠30秒
        4. 发生异常时休眠60秒后继续

        目的：自动处理发送失败的消息，确保最终送达
        """

        def _retry_loop() -> None:
            # 【Java→Python】`while (true)` → `while True`；线程是 daemon，
            # 解释器退出时自动结束（Java 由 JVM shutdown 结束线程池）。
            while True:
                try:
                    # 查询待重试的失败消息
                    # 参数：maxRetryCount-最大重试次数，100-每批最多100条
                    failedRecords = self.kafkaMessageRecordMapper.selectFailedRecords(
                        self.maxRetryCount, 100)

                    # 如果有待重试的消息，则逐个发送
                    if failedRecords is not None and len(failedRecords) > 0:
                        log.info("[Kafka生产者] 开始重试 %s 条消息", len(failedRecords))
                        for record in failedRecords:
                            self.sendMessage(record)

                    # 休眠30秒后再次查询
                    Thread.sleep(30000)
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    # Java: log.error("[Kafka生产者] 重试任务异常", e) —— 带堆栈
                    log.exception("[Kafka生产者] 重试任务异常")
                    try:
                        # 发生异常时，休眠60秒后继续
                        Thread.sleep(60000)
                    except InterruptedException:
                        # 如果被中断，退出循环
                        Thread.currentThread().interrupt()
                        break

        self.retryExecutor.submit(_retry_loop)

    def extractDeviceId(self, data: Any) -> str:
        """从数据对象中提取设备ID。

        思路：根据不同的数据类型提取设备标识字段
        目的：用于数据丢失检测中的设备维度统计

        :param data: 数据对象
        :return: 设备ID（提取不到时为 "unknown"）
        """
        # 【Java→Python】`data instanceof JSONObject` → isinstance；
        # 普通 dict 不算 JSONObject（与 Java 一致：只有 JSON.parse 出来的才是 JSONObject）。
        if isinstance(data, JSONObject):
            json_obj = data
            # 尝试从多个可能的字段中提取设备ID
            possibleFields = ["deviceId", "deviceid", "device_ip", "deviceIp", "gantrycode", "gantryId"]
            for field in possibleFields:
                value = json_obj.get(field)
                if value is not None:
                    # Java: value.toString() —— 标量时与 str() 一致
                    return str(value)
        return "unknown"

    def sendBatchSnapshotFlowData(self, dataList: List[Any]) -> None:
        """批量发送消息。

        思路：批量发送多条消息，提高发送效率
        目的：减少网络开销，提高吞吐量

        :param dataList: 数据列表
        """
        log.info("[Kafka生产者] 批量发送消息: count=%s", len(dataList))

        for data in dataList:
            try:
                dataId = self.extractDataId(data)
                if dataId is not None:
                    self.sendSnapshotFlowData(data, dataId)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.exception("[Kafka生产者] 批量发送异常")

    def extractDataId(self, data: Any) -> Optional[str]:
        """从数据对象中提取数据ID。"""
        if isinstance(data, JSONObject):
            json_obj = data
            possibleFields = ["bigId", "id", "uuid", "dataId"]
            for field in possibleFields:
                value = json_obj.get(field)
                if value is not None:
                    return str(value)
        # Java: return null; —— 提取不到返回 null，调用方据此跳过该条
        return None
