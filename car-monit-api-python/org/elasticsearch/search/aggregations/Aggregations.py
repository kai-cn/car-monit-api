# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.Aggregations

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.aggregations.Aggregations``。
本工程用法：
    - SearchResponse#getAggregations().get("group_by_" + groupBy)  （顶层桶）
    - Terms.Bucket#getAggregations().get("total_count")           （子聚合）

【Java→Python】关键差异
1) Java 的 ``get(String name)`` 签名是 ``<A extends Aggregation> A get(String name)``，
   内部就是 ``(A) asMap().get(name)``：**名字不存在时返回 null**（不抛异常）。
   替身同样返回 ``None``，与 Java 一致——调用方未判空时两者都在同一位置失败
   （Java 的 ``NullPointerException`` ↔ Python 的 ``AttributeError``）。
2) ``getAsMap()`` 返回不可变 Map；替身返回 dict 副本（调用方修改不影响内部状态）。
3) ``Aggregations.from(Map)`` 等静态工厂本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from org.elasticsearch.search.aggregations.Aggregation import Aggregation

__all__ = ["Aggregations"]


class Aggregations(object):
    """``Aggregations`` 的替身（名字 -> 聚合结果 的只读容器）。"""

    def __init__(self, aggregations: Optional[Dict[str, Aggregation]] = None) -> None:
        self._aggregations: Dict[str, Aggregation] = dict(aggregations or {})

    # ------------------------------------------------------------------ getter
    def get(self, name: str) -> Optional[Any]:
        """对应 ``<A extends Aggregation> A get(String name)``：不存在时返回 None。"""
        return self._aggregations.get(name)

    def getAsMap(self) -> Dict[str, Aggregation]:
        """对应 ``Map<String, Aggregation> getAsMap()``。"""
        return dict(self._aggregations)

    def __len__(self) -> int:
        # Python 独有：便于 ``if aggregations:`` 判空（Java 用 getAsMap().isEmpty()）
        return len(self._aggregations)

    def __repr__(self) -> str:
        return "Aggregations(%r)" % (sorted(self._aggregations),)
