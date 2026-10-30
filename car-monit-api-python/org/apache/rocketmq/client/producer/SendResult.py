# -*- coding: utf-8 -*-
"""org.apache.rocketmq.client.producer.SendResult

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.client.producer.SendResult``。
本工程用法（RocketMqProducer.sendBatchMessages）：
    SendResult result = producer.send(message);
    if ("SEND_OK".equals(result.getSendStatus().name())) {
        log.debug(..., result.getMsgId(), result.getMessageQueue().getQueueId());
    } else {
        log.error(..., result.getMsgId(), result.getSendStatus());
    }

【Java→Python】关键差异
1) Java 的 ``SendResult`` 有多个构造器；替身只实现本工程用到的字段
   （sendStatus / msgId / messageQueue / queueOffset / transactionId）。
2) ``getMessageQueue()`` 在 Java 里可能返回 **null**（部分构造器不设置），
   原代码直接 ``.getQueueId()`` 存在 NPE 风险；替身总是返回一个 MessageQueue，
   以保持“发送成功路径可跑通”，并在 RocketMqProducer.py 中注明该差异。
3) ``getSendStatus()`` 返回 ``SendStatus`` 枚举；Python 取名字要用 ``.name``。
4) Java 的 ``toString()`` 输出多字段拼接；替身给出相似的字符串便于日志对照。
"""

from __future__ import annotations

from typing import Optional

from org.apache.rocketmq.client.producer.SendStatus import SendStatus
from org.apache.rocketmq.common.message.MessageQueue import MessageQueue

__all__ = ["SendResult"]


class SendResult(object):
    """``SendResult`` 的替身。"""

    def __init__(self, send_status: SendStatus, msg_id: Optional[str] = None,
                 message_queue: Optional[MessageQueue] = None,
                 queue_offset: int = 0,
                 transaction_id: Optional[str] = None) -> None:
        self._send_status = send_status
        self._msg_id = msg_id
        self._message_queue = message_queue or MessageQueue()
        self._queue_offset = queue_offset
        self._transaction_id = transaction_id

    # ------------------------------------------------------------------ getter
    def getSendStatus(self) -> SendStatus:
        return self._send_status

    def getMsgId(self) -> Optional[str]:
        return self._msg_id

    def getMessageQueue(self) -> MessageQueue:
        return self._message_queue

    def getQueueOffset(self) -> int:
        return self._queue_offset

    def getTransactionId(self) -> Optional[str]:
        return self._transaction_id

    def __str__(self) -> str:
        return ("SendResult [sendStatus=%s, msgId=%s, messageQueue=%s, "
                "queueOffset=%d]" % (self._send_status, self._msg_id,
                                     self._message_queue, self._queue_offset))

    def __repr__(self) -> str:
        return self.__str__()
