# -*- coding: utf-8 -*-
"""org.apache.rocketmq.common.message.Message

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.common.message.Message``。
本工程用法（RocketMqProducer.sendBatchMessages）：
    Message message = new Message(
            topic,
            "snapshot_flow",                    // tags
            data.getId().toString(),            // keys
            jsonData.getBytes(StandardCharsets.UTF_8));   // body

【Java→Python】关键差异
1) Java 的 ``Message(String topic, String tags, String keys, byte[] body)`` 是 4 参构造器；
   还有 ``Message(String topic, byte[] body)`` 等重载。Python 用一个构造器 + 默认值表达，
   参数顺序与 4 参版本一致（topic, tags, keys, body）。
2) **body 是字节数组**：Java ``String.getBytes(StandardCharsets.UTF_8)`` →
   Python ``jsonData.encode("utf-8")``；``getBody()`` 返回 ``bytes``，
   消费端用 ``body.decode("utf-8")`` 还原字符串。
3) Java 的 ``putUserProperty`` / ``setDelayTimeLevel`` / ``setWaitStoreMsgOK``
   等本工程未使用，不实现。
4) ``getKeys()`` 在 Java 里是逗号分隔多个 key 的字符串；替身原样保存。
"""

from __future__ import annotations

from typing import Optional

__all__ = ["Message"]


class Message(object):
    """``Message`` 的替身（topic + tags + keys + body）。"""

    def __init__(self, topic: str, tags: Optional[str] = None,
                 keys: Optional[str] = None, body: Optional[bytes] = None) -> None:
        self._topic = topic
        self._tags = tags
        self._keys = keys
        self._body = body if body is not None else b""

    # ------------------------------------------------------------------ getter/setter
    def getTopic(self) -> str:
        return self._topic

    def setTopic(self, topic: str) -> None:
        self._topic = topic

    def getTags(self) -> Optional[str]:
        return self._tags

    def setTags(self, tags: Optional[str]) -> None:
        self._tags = tags

    def getKeys(self) -> Optional[str]:
        return self._keys

    def setKeys(self, keys: Optional[str]) -> None:
        self._keys = keys

    def getBody(self) -> bytes:
        return self._body

    def setBody(self, body: bytes) -> None:
        self._body = body

    def __repr__(self) -> str:
        return ("Message(topic=%r, tags=%r, keys=%r, body.len=%d)" %
                (self._topic, self._tags, self._keys, len(self._body)))
