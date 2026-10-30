# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DataReliabilityService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataReliabilityService.java

数据上报可靠性保障服务（原注释保留）：
1. 解决设备数据上报不及时问题：超时检测、补偿拉取、延迟告警
2. 解决数据丢失问题：消息持久化、多重确认、幂等性保障、断点续传
3. 数据完整性校验：MD5校验、数据签名、去重机制

核心机制：
- 消息三重确认机制（生产端、Kafka、消费端）
- 超时检测与自动补偿
- 幂等性保障（基于消息ID去重）
- 数据完整性校验（MD5哈希校验）
- 延迟监控与告警

【Java→Python 本文件重点差异】
1) `@Slf4j` → 模块级 `log = logging.getLogger(__name__)`；
   slf4j 的 `{}` 占位符 → Python logging 的 `%s`（惰性格式化语义一致）。
2) `@Service` → 普通类（容器语义由调用方负责）；三个 `@Autowired` 字段 →
   构造器可选参数，缺省值用**进程级单例**（KafkaTemplate/RedisTemplate 在 Spring 里是单例 Bean），
   这样多个 Service 共享同一份“Kafka/Redis”状态，与原系统行为一致。
3) 四个 `@Value("${k:d}")` → `Environment().value("${k:d}", long/int)`：解析顺序
   环境变量 > application.yml > 默认值；缺少默认值且配置缺失时抛 KeyError（等价启动失败）。
4) `@PostConstruct init()` → 在 `__init__` 末尾**显式调用** `self.init()`
   （Python 没有容器生命周期回调）。
5) 两个 `@Scheduled` → 装饰器只写元数据；真正的周期执行由 `app.scheduler`
   在启动时登记（等价 Spring 的 `ScheduledAnnotationBeanPostProcessor`）。
   其中 `fixedRateString = "${...:60}000"` 的“占位符 + 字面量”写法由装饰器解析。
6) **匿名内部类** `new ListenableFutureCallback<SendResult<...>>(){...}` →
   模块级 `_KafkaSendCallback`（持有 service + messageId），回调行为逐行一致。
7) 嵌套 `@Data` 类 → `@dataclass` + `JavaBean`：字段用 snake_case，但 `getMessageId()`
   `setMessageId()` 等 Java 写法由 JavaBean 动态提供，因此方法体可以**逐字保留**。
8) 枚举 `MessageStatus`：Java 的 `name()`/`valueOf()` 是 Enum 自带 API；
   Python 的 Enum 只有 `.name` 属性。这里在枚举里定义 `def name(self)` 覆盖
   `DynamicClassAttribute`，并补 `valueOf/values`，使 `MessageStatus.SENT.name()`、
   `MessageStatus.valueOf("SENT")` 与 Java 完全一致（同时重写 `__str__` 让日志输出同 Java）。
9) `MessageDigest.getInstance("MD5")` + 逐字节 `String.format("%02x", b)` →
   `hashlib.md5(...).hexdigest()`。Java 的 `%02x` 对 `byte` 会先按无符号扩展（Formatter
   对 Byte 的特殊处理），因此两者输出**逐位一致**；`NoSuchAlgorithmException`（受检异常）
   在 Python 中不存在，保留 `except ValueError`（FIPS 模式禁用 md5 时抛此错）。
10) `Thread.sleep(...)` / `InterruptedException` / `Thread.currentThread().interrupt()` →
   `java.lang.Thread` 替身：Python 的 sleep 不能被中断，替身用线程本地“中断标志”
   还原“置位后下一次 sleep 立即抛 InterruptedException”的语义。
11) `long delay = (long) Math.pow(2, retryCount) * 1000;` →
   `int(math.pow(2, retryCount)) * 1000`：Java 先截断 double 再乘，Python `int()` 同样向零截断
   （**不能**写成 `2 ** n` 就以为等价 —— 这里刻意保留 Math.pow 的两步语义）。
12) `switch (status)` 在 Java 里若 status 为 null 会立即抛 NullPointerException；
   Python 的 if/elif 对 None 只是“都不匹配”，因此显式补 NPE 分支后再走 case 链。
13) Java 字符串拼接 `"x" + null` 得到 `"null"`；Python 的 `str(None)` 是 `"None"`，
   故统一走 `_javaStr()`。
14) `dataId.hashCode()` → `javaStringHashCode()`：Python 内置 `hash()` 每进程随机加盐，
   且算法不同，不能替代（会影响消息ID的可复现性）。
"""
from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.KafkaMessageRecord import KafkaMessageRecord
from com.ruoyi.base.mapper.KafkaMessageRecordMapper import KafkaMessageRecordMapper
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.utils.DateUtils import DateUtils
from java.lang.String import javaStringHashCode
from java.lang.System import System
from java.lang.Thread import InterruptedException, Thread
from java.util.UUID import UUID
from java.util.concurrent.ConcurrentHashMap import ConcurrentHashMap
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate, defaultKafkaTemplate
from org.springframework.scheduling.annotation.Scheduled import Scheduled
from org.springframework.util.concurrent.ListenableFutureCallback import ListenableFutureCallback

__all__ = [
    "DataReliabilityService",
    "MessageStatus",
    "ReliableMessageWrapper",
    "MessageMeta",
]

log = logging.getLogger(__name__)


def _javaStr(value: Any) -> str:
    """等价 Java 的 `"" + value`：null 拼成 "null"，枚举拼成 name()。

    【Java→Python】Python 的 `str(None)` 是 "None"、`str(枚举)` 默认是
    "MessageStatus.PENDING"，都与 Java 的 `String.valueOf` 不同；日志与告警文案
    依赖这个差异，故统一收敛到本函数。
    """
    if value is None:
        return "null"
    return str(value)


# ==================== 内部类（Java 的 public static class / enum） ====================

class MessageStatus(Enum):
    """消息状态枚举（Java 侧为 DataReliabilityService.MessageStatus）。

    【Java→Python】Java 枚举自带 `name()`、`valueOf(String)`、`values()`；
    Python 的 Enum 只有 `.name`/`.value` 属性与 `Enum['NAME']` 索引。
    这里补齐三个 Java API，使业务代码里的 `MessageStatus.PENDING.name()` 原样可用。
    注意：`name` 已被定义成方法，JSON 替身序列化枚举时要兼容“属性/方法”两种形态。
    """

    PENDING = "PENDING"        # 待发送
    SENT = "SENT"              # 已发送到Kafka
    CONFIRMED = "CONFIRMED"    # 消费端已确认
    DEAD = "DEAD"              # 死信（无法重试）

    def name(self) -> str:  # type: ignore[override]
        """等价 Java 的 `Enum.name()`（返回枚举常量名）。"""
        return self._name_

    def __str__(self) -> str:
        # 等价 Java `Enum.toString()` → name()；否则日志里会出现 "MessageStatus.PENDING"
        return self._name_

    @staticmethod
    def valueOf(name: str) -> "MessageStatus":
        """等价 `MessageStatus.valueOf(String)`：名称非法时抛 IllegalArgumentException。"""
        try:
            return MessageStatus[name]
        except KeyError:
            # 【Java→Python】Java 抛 IllegalArgumentException，Python 对应 ValueError
            raise ValueError(
                "No enum constant DataReliabilityService.MessageStatus." + _javaStr(name)
            )

    @staticmethod
    def values() -> List["MessageStatus"]:
        """等价 `MessageStatus.values()`。"""
        return list(MessageStatus)


@dataclass
class ReliableMessageWrapper(JavaBean):
    """可靠消息包装体。

    包含消息元数据和业务数据，用于完整性校验和幂等性保障。

    【Java→Python】`@Data` → `@dataclass` + JavaBean：
    - 字段 snake_case，但 `getMessageId()/setMessageId()` 仍可用；
    - `Object data` → `Any`（保存原始业务对象，序列化交给 JSON 替身）；
    - `long timestamp` / `int version` 是**基本类型**，Java 默认 0 → Python 默认 0
      （不能写 None，否则序列化结果与 Java 不同）。
    """

    message_id: Optional[str] = None      # 消息唯一ID
    data_id: Optional[str] = None         # 业务数据ID
    checksum: Optional[str] = None        # 数据MD5校验值
    operation_type: Optional[str] = None  # 操作类型：INSERT、UPDATE、DELETE
    data: Any = None                      # 业务数据
    timestamp: int = 0                    # 发送时间戳
    version: int = 0                      # 版本号


@dataclass
class MessageMeta(JavaBean):
    """消息元数据（Java 侧为 private static class，Python 无访问修饰符）。

    【Java→Python】`kafkaOffset = -1`、`retryCount = 0` 是字段初始化器，
    Java 在构造时执行；dataclass 默认值语义相同。
    """

    message_id: Optional[str] = None
    data_id: Optional[str] = None
    topic: Optional[str] = None
    checksum: Optional[str] = None
    status: Optional[MessageStatus] = None
    create_time: int = 0
    kafka_offset: int = -1
    retry_count: int = 0
    error: Optional[str] = None

    def incrementRetryCount(self) -> None:
        # `retryCount++`：Python 没有自增运算符，self.retry_count += 1 语义相同
        self.retry_count += 1


class _KafkaSendCallback(ListenableFutureCallback):
    """`sendToKafka` 中的匿名内部类 `new ListenableFutureCallback<SendResult<...>>(){...}`。

    【Java→Python】Java 匿名内部类可以直接捕获 `messageId`（effectively final）并调用
    外部类的 `handleKafkaAck/handleSendFailure`；Python 没有匿名内部类，改用
    “持有宿主对象 + messageId”的具名回调类，回调逻辑与 Java 逐行对应。
    """

    def __init__(self, service: "DataReliabilityService", message_id: str) -> None:
        self._service = service
        self._message_id = message_id

    def onSuccess(self, result: Any) -> None:
        # Kafka确认收到消息
        self._service.handleKafkaAck(self._message_id, result.getRecordMetadata().offset())

    def onFailure(self, ex: BaseException) -> None:
        # Kafka发送失败，立即重试。
        # 【Java→Python】Java 取 `ex.getMessage()`（无消息时为 null）；Python 用 str(ex)
        #（无消息时为空串）—— 该值只写入日志/死信记录，不影响控制流。
        self._service.handleSendFailure(self._message_id, str(ex))


# ==================== 服务实现 ====================

class DataReliabilityService(object):
    """数据上报可靠性保障服务（等价 Java 的 `@Service` 单例 Bean，由调用方保证单例）。"""

    # ==================== Redis Key 常量 ====================
    # 【Java→Python】`private static final String` → 类属性；`public static final`
    # 仍是类属性（Python 无访问修饰符，靠命名约定）。
    MSG_STATUS_PREFIX = "reliability:msg:status:"      # 消息状态前缀：pending/sent/confirmed
    MSG_CONTENT_PREFIX = "reliability:msg:content:"    # 消息内容缓存前缀（public）
    TIMEOUT_QUEUE = "reliability:timeout:queue"        # 超时消息队列
    DEVICE_HEARTBEAT_PREFIX = "reliability:device:heartbeat:"  # 设备心跳前缀
    LATENCY_STATS_PREFIX = "reliability:latency:stats:"        # 延迟统计前缀

    def __init__(self,
                 kafkaTemplate: Optional[KafkaTemplate] = None,
                 kafkaMessageRecordMapper: Optional[KafkaMessageRecordMapper] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 environment: Optional[Environment] = None) -> None:
        """等价的字段注入 + 配置注入 + @PostConstruct。

        【Java→Python】
        1) `@Autowired private KafkaTemplate<String, Object> kafkaTemplate;` → 构造参数；
           缺省用 `defaultKafkaTemplate()`（进程级单例，等价 Spring 容器里的唯一 Bean）。
        2) `@Autowired KafkaMessageRecordMapper` → 缺省 `KafkaMessageRecordMapper()`；
           MyBatis 代理在同一进程内也只有一个“表”，需要共享数据时应显式传入同一实例。
        3) `@Autowired RedisTemplate` → 缺省 `defaultRedisTemplate()`（与 RedisCache 共用同一份内存库）。
        4) `@Value(...)` 字段 → `Environment().value(占位符, 目标类型)`；
           Java 的 `long`/`int` 在 Python 都是 int，但**显式传类型**以还原 Spring 的类型转换。
        """
        self.kafkaTemplate = kafkaTemplate or defaultKafkaTemplate()
        self.kafkaMessageRecordMapper = kafkaMessageRecordMapper or KafkaMessageRecordMapper()
        self.redisTemplate = redisTemplate or defaultRedisTemplate()

        # ==================== 配置参数 ====================
        env = environment or Environment()
        # 消息超时时间（毫秒），超过此时间未确认视为上报不及时
        self.messageTimeoutMs = env.value("${reliability.message-timeout-ms:30000}", int)
        # 最大重试次数
        self.maxRetryCount = env.value("${reliability.max-retry-count:5}", int)
        # 补偿拉取间隔（秒）——只被 @Scheduled 的 fixedRateString 使用
        self.compensationIntervalSeconds = env.value("${reliability.compensation-interval-seconds:60}", int)
        # 延迟告警阈值（毫秒）
        self.alertThresholdMs = env.value("${reliability.alert-threshold-ms:10000}", int)

        # ==================== 线程池 ====================
        # Java 只声明字段，实际在 @PostConstruct init() 中创建；这里先占位 None，
        # 保证 __init__ 期间若被反射访问也不会 AttributeError。
        self.retryExecutor: Optional[ExecutorService] = None        # 重试执行器
        self.compensationExecutor: Optional[ExecutorService] = None  # 补偿执行器

        # 本地缓存：存储待确认消息，用于快速查找（final 字段 → 构造时创建一次）
        self.pendingMessages: ConcurrentHashMap = ConcurrentHashMap()

        self.init()  # @PostConstruct

    def init(self) -> None:
        """等价 `@PostConstruct public void init()`。

        【Java→Python】容器在依赖注入完成后调用；Python 在 `__init__` 末尾显式调用。
        线程池使用 daemon 线程：否则 1 小时的延迟清理任务会让解释器无法退出
        （Java 的 ExecutorService 默认非守护线程，但 JVM 有 shutdown hook 兜底）。
        """
        self.retryExecutor = Executors.newFixedThreadPool(4)
        self.compensationExecutor = Executors.newFixedThreadPool(2)
        log.info("[可靠性服务] 初始化完成，消息超时时间: %sms, 最大重试次数: %s",
                 self.messageTimeoutMs, self.maxRetryCount)

    # ==================== 核心方法：消息发送与确认 ====================

    def sendReliableMessage(self, data: Any, dataId: str, topic: str) -> str:
        """发送可靠消息（带完整性校验和超时检测）。

        思路：
        1. 生成唯一消息ID
        2. 计算数据MD5校验值
        3. 本地缓存消息元数据
        4. Redis缓存消息内容（用于重试）
        5. 发送到Kafka并注册回调
        6. 设置超时定时器

        :param data: 业务数据对象
        :param dataId: 业务数据ID
        :param topic: Kafka主题
        :return: 消息ID
        """
        # 1. 生成唯一消息ID
        messageId = self.generateMessageId(dataId)

        # 2. 计算数据MD5校验值
        checksum = self.calculateChecksum(data)

        # 3. 构建消息包装体
        # 【Java→Python】setXxx() 由 JavaBean 动态提供并返回 self；这里保留链式前的
        # 独立语句，便于与源码逐行对照。
        wrapper = ReliableMessageWrapper()
        wrapper.setMessageId(messageId)
        wrapper.setDataId(dataId)
        wrapper.setChecksum(checksum)
        wrapper.setOperationType("INSERT")
        wrapper.setData(data)
        wrapper.setTimestamp(System.currentTimeMillis())
        wrapper.setVersion(1)

        # 4. 缓存消息元数据到本地
        meta = MessageMeta()
        meta.setMessageId(messageId)
        meta.setDataId(dataId)
        meta.setTopic(topic)
        meta.setChecksum(checksum)
        meta.setCreateTime(System.currentTimeMillis())
        meta.setStatus(MessageStatus.PENDING)
        self.pendingMessages.put(messageId, meta)

        # 5. 缓存消息内容到Redis（用于重试和幂等校验）
        messageJson = JSON.toJSONString(wrapper)
        self.redisTemplate.opsForValue().set(
            self.MSG_CONTENT_PREFIX + messageId, messageJson, 24, TimeUnit.HOURS)

        # 6. 更新消息状态为待发送
        self.redisTemplate.opsForValue().set(
            self.MSG_STATUS_PREFIX + messageId, MessageStatus.PENDING.name(), 24, TimeUnit.HOURS)

        # 7. 发送到Kafka
        self.sendToKafka(wrapper, topic, messageId)

        # 8. 启动超时检测定时器
        self.scheduleTimeoutCheck(messageId)

        log.info("[可靠性服务] 发送可靠消息: messageId=%s, dataId=%s, topic=%s", messageId, dataId, topic)
        return messageId

    def sendToKafka(self, wrapper: ReliableMessageWrapper, topic: str, messageId: str) -> None:
        """发送到Kafka并处理回调。"""
        # 【Java→Python】原代码是 6 行匿名内部类，这里等价为单行注册回调对象。
        # `send()` 在替身里同步完成，ListenableFuture 会立即回调（与 Spring 语义一致）。
        self.kafkaTemplate.send(topic, wrapper.getDataId(), wrapper).addCallback(
            _KafkaSendCallback(self, messageId))

    def handleKafkaAck(self, messageId: str, offset: int) -> None:
        """处理Kafka确认。"""
        meta = self.pendingMessages.get(messageId)
        if meta is not None:
            meta.setStatus(MessageStatus.SENT)
            meta.setKafkaOffset(offset)
            self.redisTemplate.opsForValue().set(
                self.MSG_STATUS_PREFIX + messageId, MessageStatus.SENT.name())
            log.debug("[可靠性服务] Kafka确认消息: messageId=%s, offset=%s", messageId, offset)

    def handleSendFailure(self, messageId: str, error: Optional[str]) -> None:
        """处理发送失败。"""
        meta = self.pendingMessages.get(messageId)
        if meta is not None:
            meta.incrementRetryCount()
            log.warning("[可靠性服务] 消息发送失败: messageId=%s, retryCount=%s, error=%s",
                        messageId, meta.getRetryCount(), _javaStr(error))

            if meta.getRetryCount() < self.maxRetryCount:
                # 重试发送
                # 【Java→Python】Java lambda 捕获 messageId（effectively final）；
                # Python 闭包同样按引用捕获，messageId 是方法参数（每次调用独立），安全。
                self.retryExecutor.submit(lambda: self.retrySend(messageId))
            else:
                # 超过最大重试次数，加入死信队列
                self.markAsDeadLetter(messageId, error)

    def retrySend(self, messageId: str) -> None:
        """重试发送。"""
        try:
            # 从Redis获取消息内容
            messageJson = self.redisTemplate.opsForValue().get(self.MSG_CONTENT_PREFIX + messageId)
            if messageJson is None:
                log.error("[可靠性服务] 重试失败：消息内容已过期: messageId=%s", messageId)
                return

            wrapper = JSON.parseObject(messageJson, ReliableMessageWrapper)
            # 【Java→Python】`pendingMessages.get(messageId).getTopic()` 若 meta 不存在，
            # Java 抛 NPE（被下方 catch 记录为“重试异常”）；Python 抛 AttributeError，
            # 同样落入 except，行为一致。
            topic = self.pendingMessages.get(messageId).getTopic()

            # 退避重试：指数退避策略
            meta = self.pendingMessages.get(messageId)
            # Java: long delay = (long) Math.pow(2, meta.getRetryCount()) * 1000;
            # 先截断 double 再乘 1000；Python int() 同样向零截断（Math.pow 恒为正 → 等价 floor）。
            delay = int(math.pow(2, meta.getRetryCount())) * 1000
            Thread.sleep(delay)

            # 重新发送
            self.sendToKafka(wrapper, topic, messageId)
            log.info("[可靠性服务] 重试消息: messageId=%s, retryCount=%s, delay=%sms",
                     messageId, meta.getRetryCount(), delay)

        except Exception as e:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 【Java→Python】Java 只记录 e.getMessage()（NPE 时为 null）；
            # 这里保留同样的文案，traceback 由 log.error 的异常信息补充。
            log.error("[可靠性服务] 重试异常: messageId=%s, error=%s", messageId, str(e))

    def markAsDeadLetter(self, messageId: str, error: Optional[str]) -> None:
        """标记为死信消息。"""
        meta = self.pendingMessages.remove(messageId)
        if meta is not None:
            meta.setStatus(MessageStatus.DEAD)
            meta.setError(error)
            self.redisTemplate.opsForValue().set(
                self.MSG_STATUS_PREFIX + messageId, MessageStatus.DEAD.name())

            # 记录到死信表
            record = KafkaMessageRecord()
            record.setDataId(meta.getDataId())
            record.setTopic(meta.getTopic())
            record.setStatus(3)  # 死信状态
            record.setRetryCount(meta.getRetryCount())
            record.setCreateTime(datetime.now())  # Java: new Date()
            record.setMessageJson(self.redisTemplate.opsForValue().get(self.MSG_CONTENT_PREFIX + messageId))
            self.kafkaMessageRecordMapper.insert(record)

            log.error("[可靠性服务] 消息进入死信队列: messageId=%s, dataId=%s, error=%s",
                      messageId, meta.getDataId(), _javaStr(error))

            # 发送告警通知
            self.sendAlert("DEAD_LETTER", "消息进入死信队列: " + messageId + ", 错误: " + _javaStr(error))

    def confirmConsumption(self, messageId: str, consumerType: str) -> None:
        """消费端确认（三重确认的最后一步）。

        思路：消费端成功处理消息后调用此方法确认
        1. 更新消息状态为已确认
        2. 清理本地缓存和Redis缓存
        3. 记录延迟统计

        :param messageId: 消息ID
        :param consumerType: 消费端类型（如：MySQL、ES、Redis）
        """
        meta = self.pendingMessages.remove(messageId)
        if meta is not None:
            latency = System.currentTimeMillis() - meta.getCreateTime()
            meta.setStatus(MessageStatus.CONFIRMED)

            # 更新Redis状态
            self.redisTemplate.opsForValue().set(
                self.MSG_STATUS_PREFIX + messageId, MessageStatus.CONFIRMED.name())

            # 记录延迟统计
            self.recordLatency(consumerType, latency)

            # 清理缓存（延迟清理，确保不会误删）
            self.scheduleCacheCleanup(messageId)

            log.info("[可靠性服务] 消费端确认: messageId=%s, consumer=%s, latency=%sms",
                     messageId, consumerType, latency)

            # 延迟超过阈值时发送告警
            if latency > self.alertThresholdMs:
                self.sendAlert("HIGH_LATENCY",
                               "消息处理延迟过高: " + messageId + ", 延迟: " + str(latency) + "ms")

    # ==================== 超时检测与补偿机制 ====================

    def scheduleTimeoutCheck(self, messageId: str) -> None:
        """启动超时检测定时器。"""
        # 【Java→Python】Java 的 lambda 实现 Runnable，sleep 后检查状态；
        # Python 用内部函数承接（捕获 messageId 与 self）。
        def _timeout_task() -> None:
            try:
                Thread.sleep(self.messageTimeoutMs)

                # 检查消息状态
                statusStr = self.redisTemplate.opsForValue().get(self.MSG_STATUS_PREFIX + messageId)
                status = MessageStatus.valueOf(statusStr) if statusStr is not None else None

                # 如果状态不是已确认，则视为超时
                # 【Java→Python】`null != CONFIRMED` 在 Java 为 true（null 视为“未确认”）；
                # Python 的 `None != MessageStatus.CONFIRMED` 同样为 True。
                if status != MessageStatus.CONFIRMED:
                    self.handleMessageTimeout(messageId, status)
            except InterruptedException:
                # 与 Java 一致：捕获中断后**重新置位**中断标志，把中断传递给上层
                Thread.currentThread().interrupt()

        self.retryExecutor.submit(_timeout_task)

    def handleMessageTimeout(self, messageId: str, currentStatus: Optional[MessageStatus]) -> None:
        """处理消息超时。"""
        log.warning("[可靠性服务] 消息超时: messageId=%s, 当前状态=%s", messageId, currentStatus)

        # 添加到超时队列，等待补偿处理
        self.redisTemplate.opsForList().rightPush(self.TIMEOUT_QUEUE, messageId)

        # 发送超时告警
        self.sendAlert("MESSAGE_TIMEOUT",
                       "消息超时未确认: " + messageId + ", 状态: " + _javaStr(currentStatus))

    @Scheduled(fixedRateString="${reliability.compensation-interval-seconds:60}000")
    def compensationTask(self) -> None:
        """定时补偿任务（处理超时消息）。

        思路：定期扫描超时队列，进行补偿拉取或重试

        【Java→Python】`fixedRateString = "${reliability.compensation-interval-seconds:60}000"`
        的语义：先解析占位符（得到 "60"），再拼上字面量 "000" → 60000ms。
        装饰器只写元数据：由 `app.scheduler` 在启动时登记；单独调试时也可用
        `startScheduledTasks(service)` 只启这一个 Bean。
        注意：方法体本身只是“丢给线程池”，因此调度线程不会被业务阻塞。
        """

        def _compensation_task() -> None:
            try:
                # 批量获取超时消息
                # 【Java→Python】Redis 的 LRANGE 是闭区间：range(0, 50) 返回 51 条，
                # 与 Java 端一致（原代码本意就是“含第 50 个下标”）。
                timeoutMessages = self.redisTemplate.opsForList().range(self.TIMEOUT_QUEUE, 0, 50)
                if timeoutMessages is None or len(timeoutMessages) == 0:
                    return

                log.info("[可靠性服务] 补偿任务处理: %s 条超时消息", len(timeoutMessages))

                for obj in timeoutMessages:
                    messageId = obj  # Java: String messageId = (String) obj;

                    # 从队列中移除
                    self.redisTemplate.opsForList().remove(self.TIMEOUT_QUEUE, 1, messageId)

                    # 获取消息状态
                    statusStr = self.redisTemplate.opsForValue().get(self.MSG_STATUS_PREFIX + messageId)
                    status = MessageStatus.valueOf(statusStr) if statusStr is not None else None

                    # 根据状态进行不同的补偿处理
                    # 【Java→Python】`switch (status)` 在 status 为 null 时会**先**抛
                    # NullPointerException（不会进入 default），随后被外层 catch 记录并
                    # 中止本轮循环（注意：此时该 messageId 已从队列移除，与 Java 相同）。
                    # Python 的 if/elif 对 None 只会落到 else，故先显式抛 NPE。
                    if status is None:
                        raise TypeError("java.lang.NullPointerException: switch 的目标枚举 status 为 null")
                    if status == MessageStatus.PENDING:
                        # 未发送成功，重新发送
                        self.retrySend(messageId)
                    elif status == MessageStatus.SENT:
                        # 已发送但未确认，通知消费端重新处理或重新发送
                        self.resendMessage(messageId)
                    elif status == MessageStatus.CONFIRMED:
                        # 已确认，无需处理
                        pass
                    elif status == MessageStatus.DEAD:
                        # 死信，跳过
                        pass
                    else:
                        log.warning("[可靠性服务] 未知状态: messageId=%s, status=%s", messageId, status)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                # Java: log.error("[可靠性服务] 补偿任务异常", e) —— 带堆栈
                log.exception("[可靠性服务] 补偿任务异常")

        self.compensationExecutor.submit(_compensation_task)

    def resendMessage(self, messageId: str) -> None:
        """重新发送消息（用于超时补偿）。"""
        try:
            messageJson = self.redisTemplate.opsForValue().get(self.MSG_CONTENT_PREFIX + messageId)
            if messageJson is None:
                log.error("[可靠性服务] 重发失败：消息内容已过期: messageId=%s", messageId)
                return

            wrapper = JSON.parseObject(messageJson, ReliableMessageWrapper)
            meta = MessageMeta()
            meta.setMessageId(messageId)
            meta.setDataId(wrapper.getDataId())
            # Java: pendingMessages.getOrDefault(messageId, new MessageMeta()).getTopic()
            # 缺省对象的所有字段都是 null → topic 为 null，send 时 topic 也是 null。
            meta.setTopic(self.pendingMessages.getOrDefault(messageId, MessageMeta()).getTopic())
            meta.setChecksum(wrapper.getChecksum())
            meta.setCreateTime(System.currentTimeMillis())
            meta.setStatus(MessageStatus.PENDING)
            self.pendingMessages.put(messageId, meta)

            # 重新发送
            # 【Java→Python】这里**没有**注册回调（原代码即为如此），
            # 因此该消息不会收到 ack/failure；保持原样以免改变业务行为。
            self.kafkaTemplate.send(meta.getTopic(), wrapper.getDataId(), wrapper)
            log.info("[可靠性服务] 重发消息: messageId=%s", messageId)

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[可靠性服务] 重发异常: messageId=%s", messageId)

    # ==================== 设备心跳检测（解决上报不及时问题） ====================

    def updateDeviceHeartbeat(self, deviceId: str) -> None:
        """更新设备心跳。

        思路：设备每次上报数据时调用此方法更新心跳时间
        用于检测设备是否离线或上报延迟

        :param deviceId: 设备ID
        """
        self.redisTemplate.opsForValue().set(
            self.DEVICE_HEARTBEAT_PREFIX + deviceId, System.currentTimeMillis(), 5, TimeUnit.MINUTES)

    @Scheduled(fixedRate=300000)  # 每5分钟检测一次
    def checkOfflineDevices(self) -> None:
        """检测离线设备。

        思路：定期检查设备心跳，超过阈值未上报视为离线
        """
        try:
            # 获取所有设备心跳key
            keys = self.redisTemplate.keys(self.DEVICE_HEARTBEAT_PREFIX + "*")
            if keys is None or len(keys) == 0:
                return

            now = System.currentTimeMillis()
            offlineThreshold = 5 * 60 * 1000  # 5分钟

            for key in keys:
                heartbeatTimeObj = self.redisTemplate.opsForValue().get(key)
                if heartbeatTimeObj is None:
                    continue

                # Java: long heartbeatTime = (Long) heartbeatTimeObj;
                # 【Java→Python】Redis 取出的是 Object，Java 用强转拆箱；
                # Python 用 int() 还原（非数字时抛 ValueError/TypeError，同样进入 catch）。
                heartbeatTime = int(heartbeatTimeObj)
                # Java: key.substring(DEVICE_HEARTBEAT_PREFIX.length())
                deviceId = key[len(self.DEVICE_HEARTBEAT_PREFIX):]

                if now - heartbeatTime > offlineThreshold:
                    # 设备离线
                    # 【Java→Python】`(now - heartbeatTime) / 1000` 是 long/long：
                    # Java 向零截断，Python 的 `//` 向下取整（负值不同）。两者都是正数
                    # 时结果相同；为保持语义，统一写成 int(... / ...)。
                    log.warning("[可靠性服务] 设备离线: deviceId=%s, 上次心跳: %sms前",
                                deviceId, int((now - heartbeatTime) / 1000))
                    self.sendAlert("DEVICE_OFFLINE", "设备离线: " + deviceId)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[可靠性服务] 设备离线检测异常")

    # ==================== 数据完整性校验 ====================

    def calculateChecksum(self, data: Any) -> str:
        """计算数据MD5校验值。

        思路：对数据内容进行哈希计算，用于验证数据完整性
        防止数据在传输过程中被篡改

        :param data: 数据对象
        :return: MD5校验值
        """
        try:
            jsonStr = JSON.toJSONString(data)
            # 【Java→Python】Java 的 MessageDigest + StringBuilder("%02x") 与
            # hashlib.md5(...).hexdigest() 输出完全一致（都是 32 位小写十六进制）：
            # - Java 的 `%02x` 对 byte 会先做无符号扩展（Formatter 对 Byte 的特殊处理），
            #   所以负数字节也输出 2 位，不会出现 "ffffff82" 这种 8 位串；
            # - Python 的 bytes → hex 天然是 0..255 的两位十六进制。
            return hashlib.md5(jsonStr.encode("utf-8")).hexdigest()  # noqa: S324 - 仅作完整性校验
        except ValueError:
            # 【Java→Python】Java 捕获 NoSuchAlgorithmException（受检异常）；
            # Python 的 hashlib 在算法被禁用（如 FIPS 模式）时抛 ValueError，
            # 这是唯一对应的分支，保留原有的“随机串兜底”行为。
            log.exception("[可靠性服务] MD5计算异常")
            return UUID.randomUUID().toString().replace("-", "")

    def verifyChecksum(self, data: Any, expectedChecksum: str) -> bool:
        """验证数据完整性。

        :param data: 数据对象
        :param expectedChecksum: 预期的校验值
        :return: 是否完整
        """
        actualChecksum = self.calculateChecksum(data)
        # Java: actualChecksum.equals(expectedChecksum) → Python 的 ==（None 安全）
        valid = actualChecksum == expectedChecksum
        if not valid:
            log.warning("[可靠性服务] 数据完整性校验失败: expected=%s, actual=%s",
                        expectedChecksum, actualChecksum)
        return valid

    # ==================== 幂等性保障 ====================

    def isMessageProcessed(self, messageId: str) -> bool:
        """检查消息是否已处理（幂等性校验）。

        思路：基于消息ID进行去重
        使用Redis的SETNX实现分布式锁和去重

        :param messageId: 消息ID
        :return: 是否已处理
        """
        # Java: Boolean exists = redisTemplate.hasKey(...); return exists != null && exists;
        # 【Java→Python】hasKey 在替身里直接返回 bool（Java 是 Boolean，可能为 null），
        # `bool(...)` 保留“null → false”的语义。
        exists = self.redisTemplate.hasKey(self.MSG_STATUS_PREFIX + messageId)
        return bool(exists)

    def markMessageProcessed(self, messageId: str) -> None:
        """标记消息为已处理。

        :param messageId: 消息ID
        """
        self.redisTemplate.opsForValue().set(
            self.MSG_STATUS_PREFIX + messageId, MessageStatus.CONFIRMED.name(), 24, TimeUnit.HOURS)

    # ==================== 工具方法 ====================

    def generateMessageId(self, dataId: str) -> str:
        """生成唯一消息ID。

        格式：timestamp-random-uuid前8位-dataIdHash
        """
        # 【Java→Python】
        # 1) Java 的 `long + "-" + ...` 会自动把数字转十进制字符串；Python 必须显式 str()。
        # 2) `System.nanoTime() % 1000000`：Java 的 % 结果符号随被除数；本替身的 nanoTime
        #    恒为非负（time.monotonic_ns），故 Python 的 % 与 Java 结果一致。
        # 3) `UUID.randomUUID().toString().substring(0, 8)` → `[0:8]`（Python 切片左闭右开，
        #    与 Java 的 substring(begin, end) 语义相同）。
        # 4) `dataId.hashCode()` → javaStringHashCode：Java 固定算法；Python 内置 hash
        #    每进程加盐且算法不同，用于消息ID会破坏可复现性。
        return (str(System.currentTimeMillis()) + "-"
                + str(System.nanoTime() % 1000000) + "-"
                + UUID.randomUUID().toString()[0:8] + "-"
                + str(javaStringHashCode(dataId) if dataId is not None else 0))

    def scheduleCacheCleanup(self, messageId: str) -> None:
        """延迟清理缓存。"""

        def _cleanup_task() -> None:
            try:
                # 延迟1小时清理，确保不会被误删
                Thread.sleep(3600000)
                self.redisTemplate.delete(self.MSG_CONTENT_PREFIX + messageId)
                self.redisTemplate.delete(self.MSG_STATUS_PREFIX + messageId)
                log.debug("[可靠性服务] 清理消息缓存: messageId=%s", messageId)
            except InterruptedException:
                # 与 Java 一致：恢复中断标志
                Thread.currentThread().interrupt()

        self.retryExecutor.submit(_cleanup_task)

    def recordLatency(self, consumerType: str, latency: int) -> None:
        """记录延迟统计。"""
        # 记录到Redis，用于监控分析
        # 【Java→Python】DateUtils.formatDate(new Date()) → formatDate(datetime.now())；
        # 替身输出 "yyyy-MM-dd"，与 Java 的 SimpleDateFormat 一致。
        key = self.LATENCY_STATS_PREFIX + consumerType + ":" + DateUtils.formatDate(datetime.now())
        self.redisTemplate.opsForList().rightPush(key, latency)
        # 保留最近1000条记录（LTRIM 是闭区间，-1000..-1 即最后 1000 个元素）
        self.redisTemplate.opsForList().trim(key, -1000, -1)

    def sendAlert(self, alertType: str, message: str) -> None:
        """发送告警通知。

        实际项目中可扩展为邮件、短信、钉钉等多种方式
        """
        log.error("[告警] [%s] %s", alertType, message)
        # TODO: 集成告警系统（钉钉、企业微信、邮件等）


# ==================== 嵌套类型的访问路径兼容 ====================
# 【Java→Python】Java 中它们是 DataReliabilityService.MessageStatus / .ReliableMessageWrapper /
# .MessageMeta；Python 无法在类体内定义“之后才引用”的嵌套类型也能工作，但模块级定义
# 更利于 import，因此在类创建后补上同名属性，保持 Java 的访问写法不变。
DataReliabilityService.MessageStatus = MessageStatus
DataReliabilityService.ReliableMessageWrapper = ReliableMessageWrapper
DataReliabilityService.MessageMeta = MessageMeta
