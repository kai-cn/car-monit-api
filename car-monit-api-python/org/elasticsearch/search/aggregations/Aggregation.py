# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.Aggregation

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.aggregations.Aggregation``。
本工程用法（LargeScaleQueryService.aggregationStats）：
    ParsedStringTerms terms = response.getAggregations().get("group_by_" + groupBy);
    ValueCount count = bucket.getAggregations().get("total_count");

【Java→Python】关键差异
1) Java 的 ``Aggregation`` 是**接口**（只有 ``getName()`` 与 ``getAggregations()``）；
   Python 用一个基类表达，``Terms`` / ``ValueCount`` 继承它。
2) Java 的 ``response.getAggregations().get(name)`` 是**泛型方法**，靠调用处的
   ``ParsedStringTerms terms = ...`` 做隐式强转；Python 无泛型擦除后的强转，
   ``get()`` 直接返回对应对象（类型由调用方保证），因此这里不需要 ``asInstanceOf``。
"""

from __future__ import annotations

__all__ = ["Aggregation"]


class Aggregation(object):
    """``Aggregation`` 接口的替身（聚合结果基类）。"""

    def __init__(self, name: str) -> None:
        self._name = name

    def getName(self) -> str:
        """对应 ``String getName()``：聚合名（即 ``AggregationBuilders.terms(name)`` 的 name）。"""
        return self._name

    def __repr__(self) -> str:
        return "%s(name=%r)" % (type(self).__name__, self._name)
