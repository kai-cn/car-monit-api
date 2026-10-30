# -*- coding: utf-8 -*-
"""org.apache.kafka.common.serialization.JsonSerializer

【无 Java 源文件：框架类替身】
Java 侧来自 kafka-clients jar：`org.springframework.kafka.support.serializer.JsonSerializer`，
KafkaProducerConfig 用 ``configProps.put(VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class)``
把 Java 对象序列化为 JSON 字节。

【Java→Python 关键差异】
1) 真实 JsonSerializer 依赖 Jackson ObjectMapper，会写入 ``__TypeId__`` 等 header
   以便消费端按原类型反序列化；Python 侧用 fastjson2 替身（``JSON.toJSONString``）
   生成同样的 JSON 文本，但**不写类型 header**（Python 对象无稳定全限定名）。
2) Java 的 `serialize` 返回 ``byte[]``；Python 返回 UTF-8 ``bytes``，保持类型一致。
3) Java 构造器可传 ObjectMapper / 是否写类型头；Python 侧保留开关字段用于对照，
   不改变行为。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from com.alibaba.fastjson2.JSON import JSON

__all__ = ["JsonSerializer"]


class JsonSerializer(object):
    """`JsonSerializer<T>` 的替身。"""

    def __init__(self, add_type_info_headers: bool = True) -> None:
        self.addTypeInfoHeaders = add_type_info_headers
        self.encoding = "UTF-8"

    def configure(self, configs: Optional[Dict[str, Any]] = None, is_key: bool = False) -> None:
        return None

    def serialize(self, topic: str, data: Optional[Any]) -> Optional[bytes]:
        """等价 `serialize(String, T)`：null → null；否则 fastjson2 输出 UTF-8 字节。"""
        if data is None:
            return None
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            # 已是 JSON 字符串时 Jackson 也会再包一层引号；为了与业务“发字符串”场景
            # 保持一致，这里原样透传（并在注释中标注差异）。
            return data.encode(self.encoding)
        # 【Java→Python】Python 没有 Jackson，用 fastjson2 替身；对不认识的对象退化为
        # json.dumps(default=str)，避免直接抛序列化异常。
        try:
            return JSON.toJSONString(data).encode(self.encoding)
        except Exception:
            return json.dumps(data, ensure_ascii=False, default=str).encode(self.encoding)

    def close(self) -> None:
        return None
