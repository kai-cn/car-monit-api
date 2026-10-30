# -*- coding: utf-8 -*-
"""org.apache.rocketmq.common.message.MessageExt

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.common.message.MessageExt``。
它继承 ``Message``，额外携带消息在 broker 侧的元数据（msgId / 重试次数 / 队列等）。
本工程用法（RocketMqConsumer.onMessage）：
    String msgId = messageExt.getMsgId();
    int reconsumeTimes = messageExt.getReconsumeTimes();
    String body = new String(messageExt.getBody(), StandardCharsets.UTF_8);

【Java→Python】关键差异
1) Java 的 ``MessageExt extends Message``；Python 同样用继承表达，``getBody()``
   等方法直接复用父类。
2) **``new String(bytes, StandardCharsets.UTF_8)``** 是 Java 的“字节数组解码”写法，
   Python 对应 ``body.decode("utf-8")``（见 RocketMqConsumer.py）。
3) Java 的 ``msgId`` 是 broker 生成的全局唯一 id（32 位 hex）；
   ``reconsumeTimes`` 是**重投次数**（首次消费为 0），超过
   ``maxReconsumeTimes`` 后 broker 自动投递到死信队列（%DLQ%+consumerGroup）。
   替身只保存这两个字段的数值，不模拟投递流程。
4) Java 的 ``setStoreHost`` / ``getBornTimestamp`` / ``getStoreTimestamp`` 等
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Optional

from org.apache.rocketmq.common.message.Message import Message

__all__ = ["MessageExt"]


class MessageExt(Message):
    """``MessageExt`` 的替身（在 Message 基础上增加 broker 元数据）。"""

    def __init__(self, topic: str = "", body: Optional[bytes] = None,
                 msg_id: Optional[str] = None, reconsume_times: int = 0,
                 queue_id: int = 0) -> None:
        super().__init__(topic, None, None, body)
        self._msg_id = msg_id
        self._reconsume_times = reconsume_times
        self._queue_id = queue_id
        self._born_timestamp = 0
        self._store_timestamp = 0

    # ------------------------------------------------------------------ getter/setter
    def getMsgId(self) -> Optional[str]:
        return self._msg_id

    def setMsgId(self, msg_id: Optional[str]) -> None:
        self._msg_id = msg_id

    def getReconsumeTimes(self) -> int:
        return self._reconsume_times

    def setReconsumeTimes(self, reconsume_times: int) -> None:
        self._reconsume_times = int(reconsume_times)

    def getQueueId(self) -> int:
        return self._queue_id

    def setQueueId(self, queue_id: int) -> None:
        self._queue_id = int(queue_id)

    def getBornTimestamp(self) -> int:
        return self._born_timestamp

    def setBornTimestamp(self, timestamp: int) -> None:
        self._born_timestamp = int(timestamp)

    def getStoreTimestamp(self) -> int:
        return self._store_timestamp

    def setStoreTimestamp(self, timestamp: int) -> None:
        self._store_timestamp = int(timestamp)

    def __repr__(self) -> str:
        return ("MessageExt(topic=%r, msgId=%r, reconsumeTimes=%d, body.len=%d)" %
                (self.getTopic(), self._msg_id, self._reconsume_times,
                 len(self.getBody())))
