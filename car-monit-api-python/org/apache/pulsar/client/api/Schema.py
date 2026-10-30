# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.Schema

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.Schema<T>` 及其
静态常量 `Schema.STRING` / `Schema.BYTES` / `Schema.JSON`。
本工程只用到 ``client.newConsumer(Schema.STRING)`` 这一处。

【Java→Python 关键差异】
1) Java 的 ``Schema.STRING`` 是 ``Schema<String>`` 的**单例实例**，内部持有
   ``SchemaInfo``（type=STRING，无 schema 定义）。Python 用类实例模拟，
   并把 ``getSchemaInfo()`` 的结果简化为 dict。
2) Java 还有 ``Schema.AVRO(Class)`` / ``Schema.JSON(Class)`` 等**静态工厂**；
   它们的名字与同名的类属性冲突（Python 无法让类属性与静态方法同名），
   因此替身命名为 ``_json`` / ``_avro``，并在模块级导出 ``JSON`` / ``AVRO``
   两个等价函数：`from ...Schema import JSON; JSON(Foo)` 与 Java 写法一一对应。
3) 真实 Schema 参与编解码（``encode``/``decode`` 返回字节）；替身只做
   ``dict`` ↔ JSON 的转换，供 Consumer/Producer 替身内部使用。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

__all__ = ["Schema", "SchemaType", "JSON", "AVRO"]


class SchemaType(object):
    """`SchemaType` 枚举的字符串常量替身（Java 是 enum）。"""

    NONE = "NONE"
    STRING = "STRING"
    JSON = "JSON"
    BYTES = "BYTES"
    AVRO = "AVRO"


class Schema(object):
    """`Schema<T>` 的替身（仅承载 schema 类型信息 + 编解码）。"""

    # 【Java→Python】类属性模拟 Java 静态单例：STRING/BYTES 各一个实例
    STRING: "Schema"
    BYTES: "Schema"

    def __init__(self, schema_type: str = SchemaType.NONE) -> None:
        self.type = schema_type

    # ------------------------------------------------------------------ 元信息
    def getSchemaInfo(self) -> Dict[str, Any]:
        return {"type": self.type, "schema": None}

    def getSchema(self) -> str:
        """等价 `getSchema()`：返回 schema 定义字符串（STRING 为 ""）。"""
        return ""

    def clone(self) -> "Schema":
        return Schema(self.type)

    # ------------------------------------------------------------------ 编解码
    def encode(self, message: Any) -> bytes:
        """等价 `encode(T)`：STRING → UTF-8 字节；其它 → JSON 字节。"""
        if message is None:
            return b""
        if self.type == SchemaType.STRING:
            return str(message).encode("utf-8")
        return json.dumps(message, ensure_ascii=False, default=str).encode("utf-8")

    def decode(self, bytes_: Optional[bytes]) -> Any:
        """等价 `decode(byte[])`。"""
        if not bytes_:
            return None
        text = bytes_.decode("utf-8")
        if self.type == SchemaType.STRING:
            return text
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text

    # ------------------------------------------------------------------ 静态工厂
    @staticmethod
    def _json(schema_class: Any = None) -> "Schema":
        # 对应 Java 的 `Schema.JSON(Class<T>)`：类型信息由调用方传入，替身不参与反射
        return Schema(SchemaType.JSON)

    @staticmethod
    def _avro(schema_class: Any = None) -> "Schema":
        return Schema(SchemaType.AVRO)


# Java 静态字段：`public static final Schema<String> STRING = new StringSchema();`
Schema.STRING = Schema(SchemaType.STRING)
Schema.BYTES = Schema(SchemaType.BYTES)

# 模块级导出：等价 Java 的 `Schema.JSON(...)` / `Schema.AVRO(...)` 静态工厂
JSON = Schema._json
AVRO = Schema._avro
