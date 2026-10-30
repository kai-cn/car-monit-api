# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.ConsumerBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.ConsumerBuilder<T>`，
由 ``PulsarClient.newConsumer(Schema)`` 返回，PulsarConsumerConfig 全部用链式调用：
    client.newConsumer(Schema.STRING)
          .topic(defaultTopic)
          .subscriptionName(subscriptionName)
          .subscriptionType(SubscriptionType.Shared)
          .subscriptionInitialPosition(SubscriptionInitialPosition.Latest)
          .receiverQueueSize(receiverQueueSize)
          .ackTimeout(ackTimeoutMs, TimeUnit.MILLISECONDS)
          .ackTimeoutTickTime(1, TimeUnit.SECONDS)
          .deadLetterPolicy(...)
          .enableRetry(true)
          .consumerName("...")
          .subscribe();

【Java→Python 关键差异】
1) 每个方法在 Java 里返回 ``ConsumerBuilder<T>``（this），Python 同样返回 self，
   因此链式写法可原样保留。
2) `subscribe()` 在 Java 中是**阻塞**网络调用并抛受检异常 ``PulsarClientException``；
   Python 无受检异常，直接返回 ``Consumer`` 替身（内部无网络）。
3) Java 的 ``ackTimeout(long, TimeUnit)`` 有两个重载（带/不带 tick 时间），
   Python 用默认参数 ``tick_time=None`` 合并。
4) 构建完成的 Consumer 会保留本构建器里的订阅参数（topic/subscription/type），
   供 ``Consumer.getTopic()`` 等方法读取。
"""
from __future__ import annotations

from typing import Any, Optional

from org.apache.pulsar.client.api.Consumer import Consumer
from org.apache.pulsar.client.api.DeadLetterPolicy import DeadLetterPolicy
from org.apache.pulsar.client.api.Schema import Schema
from org.apache.pulsar.client.api.SubscriptionInitialPosition import SubscriptionInitialPosition
from org.apache.pulsar.client.api.SubscriptionType import SubscriptionType

__all__ = ["ConsumerBuilder"]


class ConsumerBuilder(object):
    """`ConsumerBuilder<T>` 的替身（字段与 Java 同名，便于逐行对照）。"""

    def __init__(self, client: Any = None, schema: Optional[Schema] = None) -> None:
        self._client = client
        self._schema = schema
        self._topic: str = ""
        self._topics: list[str] = []
        self._subscription_name: str = ""
        self._subscription_type: SubscriptionType = SubscriptionType.Exclusive
        self._subscription_initial_position: SubscriptionInitialPosition = \
            SubscriptionInitialPosition.Latest
        self._receiver_queue_size: int = 1000
        self._ack_timeout_ms: int = 0
        self._ack_timeout_tick_time_ms: int = 1000
        self._dead_letter_policy: Optional[DeadLetterPolicy] = None
        self._enable_retry: bool = False
        self._consumer_name: Optional[str] = None

    # ------------------------------------------------------------------ 链式配置
    def topic(self, topic_name: str) -> "ConsumerBuilder":
        self._topic = topic_name
        return self

    def topics(self, topic_names: Any) -> "ConsumerBuilder":
        # Java 的 topics(Iterable<String>) 是可变参数/集合重载
        self._topics = list(topic_names)
        return self

    def subscriptionName(self, subscription_name: str) -> "ConsumerBuilder":
        self._subscription_name = subscription_name
        return self

    def subscriptionType(self, subscription_type: SubscriptionType) -> "ConsumerBuilder":
        self._subscription_type = subscription_type
        return self

    def subscriptionInitialPosition(self,
                                    position: SubscriptionInitialPosition) -> "ConsumerBuilder":
        self._subscription_initial_position = position
        return self

    def receiverQueueSize(self, receiver_queue_size: int) -> "ConsumerBuilder":
        self._receiver_queue_size = receiver_queue_size
        return self

    def ackTimeout(self, timeout: int, unit: Any, tick_time: Optional[int] = None) -> "ConsumerBuilder":
        """等价 `ackTimeout(long, TimeUnit)` / `ackTimeout(long, TimeUnit, long)`。

        【Java→Python】Java 用重载区分“是否指定 tick 时间”，Python 用默认参数合并，
        因此调用 ``ackTimeout(60000, TimeUnit.MILLISECONDS)`` 与 Java 完全一致。
        """
        # 【Java→Python】Java 的 ackTimeout 参数是 long；TimeUnit 替身用 float 系数换算，
        # 故用 int(...) 回收成整数，避免后续与 int 比较时出现 60000.0 这类值。
        self._ack_timeout_ms = int(unit.toMillis(timeout)) if unit is not None else timeout
        if tick_time is not None:
            self._ack_timeout_tick_time_ms = tick_time
        return self

    def ackTimeoutTickTime(self, tick_time: int, unit: Any) -> "ConsumerBuilder":
        self._ack_timeout_tick_time_ms = int(unit.toMillis(tick_time)) if unit is not None else tick_time
        return self

    def deadLetterPolicy(self, policy: DeadLetterPolicy) -> "ConsumerBuilder":
        self._dead_letter_policy = policy
        return self

    def enableRetry(self, retry: bool) -> "ConsumerBuilder":
        self._enable_retry = retry
        return self

    def consumerName(self, consumer_name: str) -> "ConsumerBuilder":
        self._consumer_name = consumer_name
        return self

    # ------------------------------------------------------------------ 构建
    def subscribe(self) -> Consumer:
        """等价 `subscribe()`：Java 抛受检 PulsarClientException，Python 直接返回。"""
        return Consumer(
            topic=self._topic or "persistent://public/default/default",
            subscription_name=self._subscription_name or "default",
            subscription_type=self._subscription_type,
        )
