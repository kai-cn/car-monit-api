# -*- coding: utf-8 -*-
"""org.apache.kafka.common.serialization.StringSerializer

【无 Java 源文件：框架类替身】
Java 侧来自 kafka-clients jar：`org.apache.kafka.common.serialization.StringSerializer`，
在 KafkaProducerConfig 里以 ``configProps.put(KEY_SERIALIZER_CLASS_CONFIG,
StringSerializer.class)`` 的形式登记（登记的是 **Class 对象**，Kafka 用反射实例化）。

【Java→Python 关键差异】
1) Python 没有 Class 交给 Kafka 反射实例化的机制，因此这里既保留 ``.class`` 语义
   （模块级属性 ``StringSerializer`` 本身就是类对象，登记即等价），
   又实现 `serialize` / `deserialize` 供替身工厂直接调用。
2) Java 的 `serialize(String topic, String data)` 对 null 返回 **null**；
   `deserialize` 对 null 返回 null，空数组返回 ""（不是 null）——照此实现。
3) Java 实现 `Serializer<String>`（含 `configure`/`close` 默认方法），
   Python 侧保留同名方法为空操作。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["StringSerializer"]


class StringSerializer(object):
    """`StringSerializer` 的替身：UTF-8 编解码。"""

    def __init__(self, encoding: str = "UTF-8") -> None:
        self.encoding = encoding

    def configure(self, configs: Optional[Dict[str, Any]] = None, is_key: bool = False) -> None:
        # 对应 Java 的默认方法 configure(Map, boolean)：StringSerializer 无额外配置
        return None

    def serialize(self, topic: str, data: Optional[str]) -> Optional[bytes]:
        """等价 `serialize(String, String)`：null → null。"""
        if data is None:
            return None
        return str(data).encode(self.encoding)

    def deserialize(self, topic: str, data: Optional[bytes]) -> Optional[str]:
        """等价 `deserialize(String, byte[])`：null → null；空数组 → ""。"""
        if data is None:
            return None
        return bytes(data).decode(self.encoding)

    def close(self) -> None:
        return None
