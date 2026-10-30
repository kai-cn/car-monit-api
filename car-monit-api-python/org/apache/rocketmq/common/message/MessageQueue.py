# -*- coding: utf-8 -*-
"""org.apache.rocketmq.common.message.MessageQueue

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.common.message.MessageQueue``。
本工程只在 ``RocketMqProducer`` 的日志里用到：
    result.getMessageQueue().getQueueId()

【Java→Python】关键差异
1) Java 的 ``MessageQueue`` 是 ``Comparable<MessageQueue>`` 且重写了
   ``equals/hashCode``；替身保留同样的三元组（topic/brokerName/queueId）
   与相等性语义，便于断言与排序。
2) Java 的 ``toString()`` 输出 ``MessageQueue [topic=..., brokerName=..., queueId=...]``；
   替身按同样格式输出（日志可对照）。
3) 该对象由 broker 在 ``SendResult`` 中返回，生产者代码不会主动 new。
"""

from __future__ import annotations

from typing import Any

__all__ = ["MessageQueue"]


class MessageQueue(object):
    """``MessageQueue`` 的替身。"""

    def __init__(self, topic: str = "", broker_name: str = "",
                 queue_id: int = 0) -> None:
        self._topic = topic
        self._broker_name = broker_name
        self._queue_id = queue_id

    # ------------------------------------------------------------------ getter
    def getTopic(self) -> str:
        return self._topic

    def getBrokerName(self) -> str:
        return self._broker_name

    def getQueueId(self) -> int:
        return self._queue_id

    # ------------------------------------------------------------------ 对象语义
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MessageQueue):
            return NotImplemented
        return (self._topic, self._broker_name, self._queue_id) == \
               (other._topic, other._broker_name, other._queue_id)

    def __hash__(self) -> int:
        return hash((self._topic, self._broker_name, self._queue_id))

    def __str__(self) -> str:
        return ("MessageQueue [topic=%s, brokerName=%s, queueId=%d]" %
                (self._topic, self._broker_name, self._queue_id))

    def __repr__(self) -> str:
        return self.__str__()
