# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.Message

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.Message<T>`。
业务代码（SnapshotFlowPulsarConsumer / DebeziumReadonlyPulsarConsumer）用到：
    MessageId messageId = msg.getMessageId();
    String dataId = msg.getKey();
    String messageJson = msg.getValue();
    msg.getProperties();          // 注释里提到，类似 Kafka header
    msg.getEventTime();           // 注释里提到，事件时间戳

【Java→Python 关键差异】
1) Java 的 Message 由 broker 投递产生，是**一次性的只读视图**（`getData()` 每次可能重新解码）；
   Python 替身是普通对象，字段在构造时固定，可反复读取。
2) Java 的 `getValue()` 会按 Schema 反序列化（本项目 Schema.STRING → 直接返回字符串）；
   替身原样保存 enqueue 时传入的值（本工程恒为 JSON 字符串）。
3) `getEventTime()` 在没有事件时间时返回 0（Java 同样是 long 0），不返回 null。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from org.apache.pulsar.client.api.MessageId import MessageId

__all__ = ["Message"]


class Message(object):
    """`Message<T>` 的进程内替身。"""

    def __init__(self,
                 key: Optional[str] = None,
                 value: Any = None,
                 message_id: Optional[MessageId] = None,
                 topic_name: str = "persistent://public/default/default",
                 properties: Optional[Dict[str, str]] = None,
                 event_time: int = 0,
                 publish_time: int = 0) -> None:
        self._key = key
        self._value = value
        # 【Java→Python】Java 的 getMessageId() 一定非 null（broker 分配）；
        # 替身缺省补一个 0:0，避免调用方拿到 None。
        self._message_id = message_id if message_id is not None else MessageId()
        self._topic_name = topic_name
        self._properties = dict(properties or {})
        self._event_time = event_time
        self._publish_time = publish_time

    # ------------------------------------------------------------------ 元数据
    def getMessageId(self) -> MessageId:
        """等价 `getMessageId()`：broker 分配的唯一标识（对应 Kafka 的 offset）。"""
        return self._message_id

    def getKey(self) -> Optional[str]:
        """等价 `getKey()`：消息路由键（生产者侧 `newMessage().key(...)` 设置的 dataId）。"""
        return self._key

    def getValue(self) -> Any:
        """等价 `getValue()`：消息载荷（Schema.STRING → 字符串）。"""
        return self._value

    def getData(self) -> bytes:
        """等价 `getData()`：原始字节。"""
        value = self._value
        if isinstance(value, bytes):
            return value
        return ("" if value is None else str(value)).encode("utf-8")

    def getTopicName(self) -> str:
        return self._topic_name

    def getProperties(self) -> Dict[str, str]:
        """等价 `getProperties()`：附加属性（类比 Kafka header）。"""
        return dict(self._properties)

    def getProperty(self, name: str) -> Optional[str]:
        return self._properties.get(name)

    def getEventTime(self) -> int:
        """等价 `getEventTime()`：事件时间（毫秒），未设置时为 0。"""
        return self._event_time

    def getPublishTime(self) -> int:
        """等价 `getPublishTime()`：broker 发布时间（毫秒）。"""
        return self._publish_time

    # ------------------------------------------------------------------ 对象语义
    def __str__(self) -> str:
        # Pulsar 的 MessageImpl#toString：{topic} : {messageId} : {value}
        return "%s : %s : %s" % (self._topic_name, self._message_id, self._value)

    def __repr__(self) -> str:
        return "Message(%s)" % self.__str__()
