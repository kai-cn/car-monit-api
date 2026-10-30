# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.SubscriptionInitialPosition

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.SubscriptionInitialPosition`，
enum 取值 ``Earliest`` / ``Latest``（仅对**首次**订阅生效）。

【Java→Python 关键差异】
1) Java enum → Python ``enum.Enum``；``Latest`` 等价 Kafka 的
   ``auto.offset.reset=latest``，``Earliest`` 等价 ``earliest``。
2) 与 SubscriptionType 相同：Java 的 ``name()`` 是方法，Python 的 ``.name`` 是属性。
"""
from __future__ import annotations

from enum import Enum

__all__ = ["SubscriptionInitialPosition"]


class SubscriptionInitialPosition(Enum):
    """首次订阅时的消费起始位置。"""

    Earliest = "Earliest"
    Latest = "Latest"

    def __str__(self) -> str:
        return self.name
