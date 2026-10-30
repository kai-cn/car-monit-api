# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.Consumer

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.Consumer<T>`，
由 `PulsarConsumerConfig` 通过
    client.newConsumer(Schema.STRING).topic(...).subscriptionName(...)...subscribe()
创建。业务代码（SnapshotFlowPulsarConsumer / DebeziumReadonlyPulsarConsumer）用到：
    Message<String> msg = consumer.receive();          // 阻塞接收
    consumer.acknowledge(msg);                          // 手动确认（= Kafka commitSync）
    consumer.acknowledgeAsync(msg);                     // 异步确认（= Kafka commitAsync）
    consumer.negativeAcknowledge(msg);                  // 负确认 → Broker 立即重投
    consumer.close();

【Java→Python 关键差异】
1) Java 的 `receive()` 在网络线程池里阻塞等待 Broker 推送；这里用 `queue.Queue` 模拟，
   每 50ms 轮询一次以便及时响应 `close()`（Python 的 Queue.get 无法被外部中断）。
2) Java 的 `receive()` 在 consumer 关闭后抛 `PulsarClientException`；替身同样抛
   RuntimeError（消息里带 `org.apache.pulsar.client.api.PulsarClientException` 前缀），
   使消费循环的 catch 分支行为保持一致。
3) `receive(timeout, unit)` 在 Java 中超时抛 `PulsarClientException.TimeoutException`；
   替身抛 RuntimeError（带 `PulsarClientException$TimeoutException` 前缀）。
4) `acknowledgeAsync` 在 Java 返回 `CompletableFuture<Void>`；替身返回已完成的
   CompletableFuture（本工程只把它当语句调用，不等待）。
5) 真实 Broker 会在负确认后**重新投递**同一条消息；替身只记录到 `negativeAckedMessages()`，
   需要重投时由测试显式再 enqueue（避免“一直重投”导致测试不可控）。
6) 提供 `enqueue(key, value)` 测试辅助方法：Java 侧没有，靠真实 Broker 投递。
"""
from __future__ import annotations

import queue
import time
from typing import Any, Dict, List, Optional

from java.util.concurrent.CompletableFuture import CompletableFuture
from org.apache.pulsar.client.api.Message import Message
from org.apache.pulsar.client.api.MessageId import MessageId

__all__ = ["Consumer"]


class Consumer(object):
    """`Consumer<T>` 的进程内替身（消息队列 + ack 记录）。"""

    def __init__(self,
                 topic: str = "persistent://public/default/default",
                 subscription_name: str = "default",
                 subscription_type: Any = None) -> None:
        self._topic = topic
        self._subscription_name = subscription_name
        self._subscription_type = subscription_type
        self._queue: "queue.Queue[Message]" = queue.Queue()
        self._connected = True
        self._closed = False
        # 模拟 broker 侧的 entry 自增（与 Producer 的 ledger/entry 概念对应）
        self._entry_id = 0
        self._ledger_id = 0
        self._acked: List[Message] = []
        self._negative_acked: List[Message] = []

    # ------------------------------------------------------------------ 元信息
    def getTopic(self) -> str:
        return self._topic

    def getSubscription(self) -> str:
        """等价 `getSubscription()`：订阅名（类比 Kafka group.id）。"""
        return self._subscription_name

    def getSubscriptionType(self) -> Any:
        return self._subscription_type

    def isConnected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------ 接收
    def receive(self, timeout: Optional[int] = None, unit: Any = None) -> Message:
        """等价 `receive()` / `receive(long, TimeUnit)`：阻塞接收下一条消息。"""
        deadline = None
        if timeout is not None:
            seconds = unit.toSeconds(timeout) if unit is not None else timeout
            deadline = time.time() + seconds

        while True:
            if self._closed and self._queue.empty():
                raise RuntimeError(
                    "org.apache.pulsar.client.api.PulsarClientException: Consumer 已关闭")
            try:
                return self._queue.get(timeout=0.05)
            except queue.Empty:
                if deadline is not None and time.time() >= deadline:
                    raise RuntimeError(
                        "org.apache.pulsar.client.api.PulsarClientException$TimeoutException: "
                        "接收消息超时")

    def receiveAsync(self) -> CompletableFuture:
        """等价 `receiveAsync()`：返回 `CompletableFuture<Message<T>>`。"""
        return CompletableFuture.supplyAsync(lambda: self.receive())

    # ------------------------------------------------------------------ 确认
    def acknowledge(self, msg: Message) -> None:
        """等价 `acknowledge(Message)`：手动确认（= Kafka commitSync 的语义）。"""
        self._acked.append(msg)

    def acknowledgeAsync(self, msg: Message) -> CompletableFuture:
        """等价 `acknowledgeAsync(Message)`：异步确认（= Kafka commitAsync）。"""
        self._acked.append(msg)
        return CompletableFuture(value=None)

    def acknowledgeCumulative(self, msg: Message) -> None:
        """等价 `acknowledgeCumulative(Message)`：累积确认到该消息为止。"""
        self._acked.append(msg)

    def negativeAcknowledge(self, msg: Message) -> None:
        """等价 `negativeAcknowledge(Message)`：负确认 → Broker 稍后重投。"""
        self._negative_acked.append(msg)

    def redeliverUnacknowledgedMessages(self) -> None:
        """等价 `redeliverUnacknowledgedMessages()`：要求 Broker 重投未确认消息。"""
        return None

    def close(self) -> None:
        """等价 `close()`：关闭消费者并释放与 Broker 的连接。"""
        self._closed = True
        self._connected = False

    # ------------------------------------------------------------------ 测试辅助
    def enqueue(self, key: Optional[str], value: Any,
                properties: Optional[Dict[str, str]] = None,
                event_time: int = 0) -> Message:
        """投递一条消息（Java 侧由 Broker 投递，替身用此方法模拟）。"""
        self._entry_id += 1
        message = Message(
            key=key,
            value=value,
            message_id=MessageId(ledger_id=self._ledger_id, entry_id=self._entry_id),
            topic_name=self._topic,
            properties=properties,
            event_time=event_time,
        )
        self._queue.put(message)
        return message

    def ackedMessages(self) -> List[Message]:
        """查看已确认消息（Java 没有此方法，仅替身用于校验）。"""
        return list(self._acked)

    def negativeAckedMessages(self) -> List[Message]:
        """查看被负确认的消息（Java 没有此方法，仅替身用于校验）。"""
        return list(self._negative_acked)
