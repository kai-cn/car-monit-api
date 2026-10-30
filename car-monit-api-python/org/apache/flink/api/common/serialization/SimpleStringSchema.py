# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.serialization.SimpleStringSchema

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.serialization.SimpleStringSchema``。
本工程用法（VehicleTrackFlinkJob.createCDCDataStream / createRawDataStream）：
    FlinkKafkaConsumer<String> consumer =
            new FlinkKafkaConsumer<>(CDC_TOPIC, new SimpleStringSchema(), props);

【Java→Python】关键差异（对应源码里的 [修复3]）
1) 原工程曾自定义了一个同名的 SimpleStringSchema（放在业务包里），
   源码注释 “[修复3] 自定义 SimpleStringSchema ->
   org.apache.flink.api.common.serialization.SimpleStringSchema” 说明后来
   改为使用 Flink 官方类。替身按官方类建模，**不再**在业务包下放同名类。
2) Java 的 ``deserialize(byte[])`` 返回 String；``serialize(String)`` 返回 byte[]。
   Python 用 ``bytes`` ↔ ``str``：反序列化按 UTF-8 解码（对应 Java 的
   ``new String(message, StandardCharsets.UTF_8)``）。
3) ``getProducedType()`` 在 Java 里返回 ``TypeInformation<String>``；
   替身返回 ``Types.STRING`` 以便断言。
"""
from __future__ import annotations

from typing import Any, Optional

from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation
from org.apache.flink.api.common.typeinfo.Types import Types

__all__ = ["SimpleStringSchema"]


class SimpleStringSchema(object):
    """``SimpleStringSchema`` 的替身（Kafka value 的 String 编解码）。"""

    def __init__(self) -> None:
        #: Java 侧无此字段；替身记录解码后的字符集，便于断言
        self.charset = "UTF-8"

    def serialize(self, element: Optional[str]) -> Optional[bytes]:
        """对应 ``byte[] serialize(String element)``。"""
        if element is None:
            return None
        return element.encode(self.charset)

    def deserialize(self, message: Optional[bytes]) -> Optional[str]:
        """对应 ``String deserialize(byte[] message)``。"""
        if message is None:
            return None
        if isinstance(message, str):
            # Python 侧测试时可能直接喂字符串，宽松接受
            return message
        return bytes(message).decode(self.charset)

    def getProducedType(self) -> TypeInformation:
        """对应 ``TypeInformation<String> getProducedType()``。"""
        return Types.STRING

    def __repr__(self) -> str:
        return "SimpleStringSchema(charset=%s)" % self.charset
