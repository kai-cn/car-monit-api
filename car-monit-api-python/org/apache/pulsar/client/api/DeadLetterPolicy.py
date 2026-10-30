# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.DeadLetterPolicy

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.DeadLetterPolicy`，
用法（PulsarConsumerConfig 中）：
    DeadLetterPolicy.builder()
        .maxRedeliverCount(maxRetryTimes)
        .deadLetterTopic(defaultTopic + "-DLQ")
        .build()

【Java→Python 关键差异】
1) Java 的 Builder 是**静态内部类** ``DeadLetterPolicy.Builder``；Python 没有内部类，
   这里用独立的 ``DeadLetterPolicyBuilder`` 类，由静态方法 ``builder()`` 返回。
2) 构建器是可变链式调用（每个 setter 返回 this）；Python 同样返回 self。
3) 所有字段都有默认值（Java 的 Builder 字段默认 0/null），这里用 None/0 对齐；
   ``build()`` 之后字段即“冻结”（Java 对象 Immutable，Python 也可再改，
   但业务代码不会改，保持只读约定）。
4) Java 的 ``getDeadLetterTopic()`` 在未显式设置时返回 "topic-DLQ"（运行时拼接）；
   替身返回 None，并在调用方（Consumer）里做同样的兜底拼接。
"""
from __future__ import annotations

from typing import Optional

__all__ = ["DeadLetterPolicy", "DeadLetterPolicyBuilder"]


class DeadLetterPolicy(object):
    """死信队列策略（对应 Java 的不可变值对象）。"""

    def __init__(self, max_redeliver_count: int = 0,
                 dead_letter_topic: Optional[str] = None,
                 retry_letter_topic: Optional[str] = None,
                 initial_subscription_name: Optional[str] = None) -> None:
        self.maxRedeliverCount = max_redeliver_count
        self.deadLetterTopic = dead_letter_topic
        self.retryLetterTopic = retry_letter_topic
        self.initialSubscriptionName = initial_subscription_name

    # ------------------------------------------------------------------ getter
    def getMaxRedeliverCount(self) -> int:
        return self.maxRedeliverCount

    def getDeadLetterTopic(self) -> Optional[str]:
        return self.deadLetterTopic

    def getRetryLetterTopic(self) -> Optional[str]:
        return self.retryLetterTopic

    def getInitialSubscriptionName(self) -> Optional[str]:
        return self.initialSubscriptionName

    # ------------------------------------------------------------------ builder
    @staticmethod
    def builder() -> "DeadLetterPolicyBuilder":
        return DeadLetterPolicyBuilder()

    def __str__(self) -> str:
        # Java 的 toString()（lombok @Builder 生成的是类名+字段，这里保持可读形式）
        return ("DeadLetterPolicy(maxRedeliverCount=%s, deadLetterTopic=%s)"
                % (self.maxRedeliverCount, self.deadLetterTopic))


class DeadLetterPolicyBuilder(object):
    """``DeadLetterPolicy.Builder`` 的替身。"""

    def __init__(self) -> None:
        self._max_redeliver_count: int = 0
        self._dead_letter_topic: Optional[str] = None
        self._retry_letter_topic: Optional[str] = None
        self._initial_subscription_name: Optional[str] = None

    def maxRedeliverCount(self, max_redeliver_count: int,
                          initial_subscription_name: Optional[str] = None) -> "DeadLetterPolicyBuilder":
        # Java 有两个重载：maxRedeliverCount(int) / maxRedeliverCount(int, String)
        self._max_redeliver_count = max_redeliver_count
        if initial_subscription_name is not None:
            self._initial_subscription_name = initial_subscription_name
        return self

    def deadLetterTopic(self, dead_letter_topic: str) -> "DeadLetterPolicyBuilder":
        self._dead_letter_topic = dead_letter_topic
        return self

    def retryLetterTopic(self, retry_letter_topic: str) -> "DeadLetterPolicyBuilder":
        self._retry_letter_topic = retry_letter_topic
        return self

    def build(self) -> DeadLetterPolicy:
        return DeadLetterPolicy(
            max_redeliver_count=self._max_redeliver_count,
            dead_letter_topic=self._dead_letter_topic,
            retry_letter_topic=self._retry_letter_topic,
            initial_subscription_name=self._initial_subscription_name,
        )
