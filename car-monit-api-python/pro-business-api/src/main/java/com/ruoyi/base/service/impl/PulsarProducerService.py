# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.PulsarProducerService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/PulsarProducerService.java

Pulsar 消息发送服务（原注释保留）

功能说明：
- 将门架抓拍流水数据发送到 Pulsar 消息队列
- 完全等价替换原 KafkaProducerService 功能

可靠性保障机制（与 Kafka 版一一对应）：
1. 消息先入库再发送（status=0 待发送）
2. 异步发送并通过回调更新状态
3. 后台定时线程扫描待重试记录并重发
4. 超过最大重试次数（默认 10 次）停止重试，需要人工介入

Pulsar 与 Kafka API 区别：
- KafkaTemplate.send()  <=>  Producer.newMessage().sendAsync()
- ListenableFuture       <=>  CompletableFuture<MessageId>
- ProducerRecord(key,value) <=> newMessage().key(dataId).value(json)
- MessageId（Pulsar原生）  <=>  offset + partition（Kafka概念）

【Java→Python 本文件重点差异】
1) 原类上的 `@Service` 是**被注释掉的**（`//@Service`），即 Java 侧 Spring 根本不会创建
   这个 Bean；且工程里也没有 `Producer<String>` Bean 的定义。两者叠加导致该类实际
   “不可注入、不可运行”。Python 侧为了可单测/可运行，按 `@Service` 语义正常构造，
   并在 `snapshotFlowProducer=None` 时按 defaultTopic 直连创建一个 Producer 替身。
2) `@Autowired private Producer<String>` / `PulsarMessageRecordMapper`
   → 构造器可选参数；Mapper 缺省 new 一个（Spring 单例由调用方保证）。
3) `@Value("${spring.pulsar.topic:...}")` / `@Value("${spring.pulsar.max-retry-count:10}")`
   → `Environment.value(..., str/int)`。Java 的字段声明顺序是 producer→mapper→topic→retry，
   Python 必须先解析 topic 才能造出默认 Producer，故调整了赋值顺序（仅影响构造，不影响行为）。
4) `@PostConstruct init()` → `__init__` 末尾显式调用；
   `@PreDestroy destroy()` → 普通方法（Python 无容器生命周期回调，需调用方在退出时显式 destroy）。
5) **异步回调的执行线程不同**：Java 的 `sendAsync()` 立即返回，`thenAccept`/`exceptionally`
   由 Pulsar IO 线程稍后触发；Python 替身的 CompletableFuture 在调用 `thenAccept` 时就
   `join()` 等待结果（见 java/util/concurrent/CompletableFuture.py 头注释），因此
   `sendMessage()` 在替身里是**同步阻塞**的。代码写法（先 thenAccept 再 exceptionally）
   与 Java 完全一致，语义上依旧“成功只走成功回调、失败只走失败回调”。
6) 匿名 lambda `messageId -> {...}` / `ex -> {...}` → 函数体内的局部 `def`（Python 的
   lambda 只能写表达式，多语句回调必须用 def），闭包捕获 `record` 的方式与 Java 一致。
7) `UUID.randomUUID().toString().replace("-", "")` → `UUID` 替身的同名方法。
8) `errorMsg.length()` / `errorMsg.substring(0, 500)` → `len()` / 切片 `[0:500]`。
9) `ex.getMessage()` → 模块内 `_messageOf(ex)`（`str(ex)`）；Java 的 getMessage() 可能为
   null，而 Python 的 str(ex) 永远返回字符串（无消息时为空串），差异已在该函数注释中说明。
10) `new Date()` → `datetime.now()`；`Date` → `datetime`。
11) `while (!Thread.currentThread().isInterrupted())` + `catch (InterruptedException)`：
    Java 用线程中断标志退出；`java.lang.Thread` 替身用线程本地中断标志复现。
    注意 catch 顺序必须保持“先 InterruptedException 后 Exception”（子类在前）。
12) 日志占位符 `{}` → logging 的 `%s`；`log.error(msg, e)` → `log.exception(msg)` /
    `log.error(msg, exc_info=True)`（带堆栈）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.PulsarMessageRecord import PulsarMessageRecord
from com.ruoyi.base.mapper.PulsarMessageRecordMapper import PulsarMessageRecordMapper
from java.lang.Thread import InterruptedException, Thread
from java.util.UUID import UUID
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit
from org.apache.pulsar.client.api.MessageId import MessageId
from org.apache.pulsar.client.api.Producer import Producer
from org.apache.pulsar.client.api.TypedMessageBuilder import TypedMessageBuilder
from org.springframework.core.env.Environment import Environment

__all__ = ["PulsarProducerService"]

log = logging.getLogger(__name__)


def _messageOf(error: BaseException) -> Optional[str]:
    """等价 Java 的 `Throwable#getMessage()`。

    【Java→Python】Java 的 getMessage() 可能返回 null（如无参构造的异常），
    Python 的 `str(ex)` 始终返回字符串（无消息时是 ""）。这里保留 `str(ex)`：
    落库的 error_msg 从 null 变成 ""，只影响“是否为空”的可读性，不影响重试判定
    （重试次数由 retry_count 驱动）。
    """
    return str(error)


class PulsarProducerService(object):
    """Pulsar 消息发送服务。

    【Java→Python】Java 侧 `//@Service` 是注释掉的，本类在 Spring 中并不会被实例化；
    Python 侧按正常服务类实现，并保留“可独立构造”的默认依赖。
    """

    def __init__(self,
                 snapshotFlowProducer: Optional[Producer] = None,
                 pulsarMessageRecordMapper: Optional[PulsarMessageRecordMapper] = None,
                 environment: Optional[Environment] = None) -> None:
        env = environment or Environment()

        # --- @Value 注入的配置（Java 声明顺序在后，但默认 Producer 需要先知道 topic） ---
        # 主题名，默认 persistent://public/default/ods-rt-szdn-snapshot-flow
        self.defaultTopic: str = env.value(
            "${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}", str)
        # 最大重试次数，默认 10
        self.maxRetryCount: int = env.value("${spring.pulsar.max-retry-count:10}", int)

        # 注入 Pulsar 生产者：用于发送消息
        # 【Java→Python】Java 里由 `@Autowired` 从容器取（但工程未定义该 Bean）；
        # 缺省时按主题直接创建一个 Producer 替身，保证“开箱可运行”。
        self.snapshotFlowProducer: Producer = (
            snapshotFlowProducer if snapshotFlowProducer is not None else Producer(self.defaultTopic))
        # 注入消息记录 Mapper：用于持久化消息状态
        self.pulsarMessageRecordMapper: PulsarMessageRecordMapper = (
            pulsarMessageRecordMapper or PulsarMessageRecordMapper())

        # 重试任务线程池（@PostConstruct 中创建）
        self.retryExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    def init(self) -> None:
        """服务初始化：启动后台重试线程（`@PostConstruct`）。"""
        # 创建单线程池：只允许一个重试任务串行执行，避免重复重发
        self.retryExecutor = Executors.newSingleThreadExecutor()
        # 启动重试任务
        self.startRetryTask()
        log.info("[PulsarProducer] 初始化完成，主题=%s, 最大重试=%s",
                 self.defaultTopic, self.maxRetryCount)

    def destroy(self) -> None:
        """服务销毁：优雅关闭线程池和 Producer（`@PreDestroy`）。

        【Java→Python】Python 没有 Bean 销毁回调；替身线程池全是 daemon 线程，
        进程退出不会因此卡住，但**不会自动关闭 Producer**。需要时请在退出流程显式调用。
        """
        log.info("[PulsarProducer] 正在关闭...")
        if self.retryExecutor is not None:
            self.retryExecutor.shutdownNow()
        try:
            if self.snapshotFlowProducer is not None and self.snapshotFlowProducer.isConnected():
                self.snapshotFlowProducer.close()
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # Java: log.error("[PulsarProducer] 关闭 Producer 异常", e)
            log.exception("[PulsarProducer] 关闭 Producer 异常")

    def sendSnapshotFlowData(self, data: Any, dataId: str) -> str:
        """发送单条抓拍流水数据。

        步骤：
        1. 构建标准消息格式 JSON：{ "operationType": "INSERT", "data": {...} }
        2. 消息记录入库（status=0 待发送），生成 UUID 主键
        3. 调用 sendMessage() 异步发送，通过 CompletableFuture 回调更新数据库状态

        :param data: 业务数据对象（OdsRtSzdnSnapshotFlowAddcode）
        :param dataId: 业务数据ID（用作 Pulsar Message 的 key）
        :return: dataId
        """
        try:
            # 1. 构建标准消息 JSON 格式
            messageObj = JSONObject()
            messageObj.put("operationType", "INSERT")
            # 【Java→Python】`Object data` 由 fastjson2 反射序列化为 JSON；
            # JSON 替身的 _serialize 对 dataclass 实体按字段输出并转回 camelCase，
            # 与 fastjson 默认的“实体→JSON 对象”行为一致。
            messageObj.put("data", data)
            messageJson = messageObj.toJSONString()

            # 2. 先入库：status=0 待发送
            record = PulsarMessageRecord()
            # 【Java→Python】UUID 去掉 "-" → 32 位纯十六进制字符串（与 Java 输出一致）
            record.setId(UUID.randomUUID().toString().replace("-", ""))
            record.setDataId(dataId)
            record.setTopic(self.defaultTopic)
            record.setMessageJson(messageJson)
            record.setStatus(0)
            record.setRetryCount(0)
            record.setCreateTime(datetime.now())
            self.pulsarMessageRecordMapper.insert(record)

            # 3. 异步发送
            self.sendMessage(record)

            log.info("[PulsarProducer] 消息已提交发送: dataId=%s, recordId=%s",
                     dataId, record.getId())
            return dataId

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # Java: log.error("[PulsarProducer] 发送异常: dataId={}", dataId, e)
            log.exception("[PulsarProducer] 发送异常: dataId=%s", dataId)
            # 【Java→Python】Java 在 catch 里依然返回 dataId（不抛给上层），保持不变
            return dataId

    def sendMessage(self, record: PulsarMessageRecord) -> None:
        """实际发送消息到 Pulsar（内部方法，Java 为 private）。

        sendAsync() 返回 CompletableFuture<MessageId>，注册 thenAccept / exceptionally 回调：
        - 成功回调：UPDATE status=1，记录 messageId 和 sendTime
        - 失败回调：UPDATE status=2，retry_count+1，记录 errorMsg
        """
        # 构建消息：key=dataId（路由一致性） value=JSON
        messageBuilder: TypedMessageBuilder = self.snapshotFlowProducer.newMessage() \
            .key(record.getDataId()) \
            .value(record.getMessageJson())

        # 异步发送
        future = messageBuilder.sendAsync()

        # 成功回调（Java 的 lambda `messageId -> {...}`）
        def _onSuccess(messageId: MessageId) -> None:
            # 更新状态=1，记录 MessageId 与发送时间
            self.pulsarMessageRecordMapper.updateStatusById(
                record.getId(), 1, datetime.now(), messageId.toString())
            log.info("[PulsarProducer] 发送成功: dataId=%s, messageId=%s",
                     record.getDataId(), messageId)

        # 失败回调（Java 的 lambda `ex -> {...; return null;}`）
        def _onFailure(ex: BaseException) -> None:
            errorMsg = _messageOf(ex)
            # 截断超长错误信息到 500 字符（数据库列长度限制）
            if errorMsg is not None and len(errorMsg) > 500:
                errorMsg = errorMsg[0:500]
            # 累加重试次数并置 status=2（待重试），写入 errorMsg
            self.pulsarMessageRecordMapper.incrementRetryCount(record.getId(), errorMsg)
            log.error("[PulsarProducer] 发送失败: dataId=%s, error=%s",
                      record.getDataId(), errorMsg)
            return None

        # 【Java→Python】两行顺序与 Java 一致：先注册成功回调，再注册失败回调。
        # CompletableFuture 替身里 thenAccept 会阻塞到发送结束；失败时它内部吞掉异常
        # 并返回异常阶段，因此随后的 exceptionally 仍能拿到原始异常并执行失败回调。
        future.thenAccept(_onSuccess)
        future.exceptionally(_onFailure)

    def startRetryTask(self) -> None:
        """后台重试任务：每 30 秒扫描待重试记录。

        思路：
        1. 查询 status IN (0, 2) AND retry_count < maxRetryCount 的记录（最多 100 条）
        2. 逐条调用 sendMessage() 重新发送
        3. 休眠 30 秒后进入下一轮
        """
        def _retryLoop() -> None:
            # Java: while (!Thread.currentThread().isInterrupted())
            while not Thread.currentThread().isInterrupted():
                try:
                    failedRecords: List[PulsarMessageRecord] = \
                        self.pulsarMessageRecordMapper.selectFailedRecords(
                            self.maxRetryCount, 100)

                    if failedRecords is not None and len(failedRecords) > 0:
                        log.info("[PulsarProducer] 开始重试 %s 条消息", len(failedRecords))
                        for record in failedRecords:
                            self.sendMessage(record)

                    # 休眠 30 秒（Java: TimeUnit.SECONDS.sleep(30)）
                    TimeUnit.SECONDS.sleep(30)

                except InterruptedException:
                    # 注意：必须先捕获 InterruptedException（它是 Exception 的子类）
                    log.info("[PulsarProducer] 重试任务收到中断信号，退出")
                    # 恢复中断标志，与 Java 的 Thread.currentThread().interrupt() 一致
                    Thread.currentThread().interrupt()
                    break
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    # Java: log.error("[PulsarProducer] 重试任务异常，等待 60s 后继续", e)
                    log.exception("[PulsarProducer] 重试任务异常，等待 60s 后继续")
                    try:
                        TimeUnit.SECONDS.sleep(60)
                    except InterruptedException:
                        Thread.currentThread().interrupt()
                        break

        # 【Java→Python】retryExecutor 在 init() 中创建；替身线程池为 daemon 线程。
        self.retryExecutor.submit(_retryLoop)

    def isProducerHealthy(self) -> bool:
        """健康检查：Producer 是否正常连接。"""
        return self.snapshotFlowProducer is not None and self.snapshotFlowProducer.isConnected()
