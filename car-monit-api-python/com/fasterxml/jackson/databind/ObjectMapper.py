# -*- coding: utf-8 -*-
"""com.fasterxml.jackson.databind.ObjectMapper / JsonNode

【无 Java 源文件：框架类替身】
Java 侧来自 jackson-databind jar：
    com.fasterxml.jackson.databind.ObjectMapper
    com.fasterxml.jackson.databind.JsonNode

本工程用法（EsIndexManageService.ilmPolicyExists）：
    JsonNode node = OBJECT_MAPPER.readTree(body);
    return node.has(policyName);

【Java→Python 关键差异】
1) Jackson 的 `ObjectMapper` 是重量级线程安全对象（`private static final`），
   内部维护 Serializer/Deserializer 缓存；Python 侧直接用内置 `json` 模块，
   替身只保留“调用形态”，无状态、无需缓存。
2) `readTree(String)` 返回 `JsonNode`（树模型）。Python 的 `json.loads` 得到
   dict/list，因此 `JsonNode` 是一个**轻量包装器**，把 dict 的 key 访问
   （`node.has(name)` / `node.get(name)`）呈现为 Jackson 风格的方法。
3) **本工程只用到 `has(String)`**；`get` / `path` / `asText` 按需补充，
   未实现的 Jackson 能力不臆造。
4) Jackson 在解析失败时抛 `JsonProcessingException`（受检异常），
   替身抛内置 `ValueError`（原代码用 `catch (Exception e)` 兜住，等价）。
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

__all__ = ["ObjectMapper", "JsonNode"]


class JsonNode(object):
    """``JsonNode`` 的替身：包装 dict / list / 标量。"""

    def __init__(self, value: Any) -> None:
        self._value = value

    # ------------------------------------------------------------------ 访问
    def has(self, field_name: str) -> bool:
        """对应 ``has(String fieldName)``：字段存在（**值为 null 也算存在**）。"""
        if isinstance(self._value, dict):
            return field_name in self._value
        return False

    def get(self, field_name: str) -> Optional["JsonNode"]:
        """对应 ``get(String)``：不存在返回 None。"""
        if isinstance(self._value, dict) and field_name in self._value:
            return JsonNode(self._value[field_name])
        return None

    def path(self, field_name: str) -> "JsonNode":
        """对应 ``path(String)``：不存在返回 MissingNode（这里用 None 值节点近似）。"""
        return self.get(field_name) or JsonNode(None)

    def isMissingNode(self) -> bool:
        return self._value is None and getattr(self, "_missing", False)

    def asText(self) -> str:
        if self._value is None:
            return "null"
        if isinstance(self._value, str):
            return self._value
        return json.dumps(self._value, ensure_ascii=False)

    def asInt(self, default_value: int = 0) -> int:
        try:
            return int(self._value)
        except (TypeError, ValueError):
            return default_value

    def asBoolean(self, default_value: bool = False) -> bool:
        if isinstance(self._value, bool):
            return self._value
        return default_value

    def isArray(self) -> bool:
        return isinstance(self._value, list)

    def size(self) -> int:
        if isinstance(self._value, (dict, list)):
            return len(self._value)
        return 0

    def elements(self) -> List["JsonNode"]:
        """对应 ``elements()``：数组/对象的值迭代器。"""
        if isinstance(self._value, list):
            return [JsonNode(item) for item in self._value]
        if isinstance(self._value, dict):
            return [JsonNode(item) for item in self._value.values()]
        return []

    def toString(self) -> str:
        """对应 ``toString()``：JSON 文本。"""
        return json.dumps(self._value, ensure_ascii=False, default=str)

    def __repr__(self) -> str:
        return "JsonNode(%r)" % (self._value,)


class ObjectMapper(object):
    """``ObjectMapper`` 的替身（只实现本工程用到的 ``readTree`` / ``writeValueAsString``）。"""

    def readTree(self, content: str) -> JsonNode:
        """对应 ``readTree(String content)``；解析失败抛 ValueError。"""
        return JsonNode(json.loads(content))

    def writeValueAsString(self, value: Any) -> str:
        """对应 ``writeValueAsString(Object value)``。"""
        return json.dumps(value, ensure_ascii=False, default=str)

    def __repr__(self) -> str:
        return "ObjectMapper()"
