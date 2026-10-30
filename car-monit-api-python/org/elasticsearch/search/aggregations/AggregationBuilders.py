# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.AggregationBuilders

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.AggregationBuilders``。
本工程用法（LargeScaleQueryService.aggregationStats）：
    AggregationBuilders.terms("group_by_" + groupBy).field(groupBy + ".keyword").size(topN)
            .subAggregation(AggregationBuilders.count("total_count").field(...))

【Java→Python】关键差异
1) Java 的 ``AggregationBuilders`` 是**纯静态工厂**（私有构造器）；
   Python 用 ``@staticmethod`` 表达，调用写法完全一致。
2) Java 有上百个工厂方法（histogram/dateHistogram/avg/sum/cardinality/...）；
   本工程只用到 ``terms`` 与 ``count``，其余不实现。
3) ``count(String name)`` 在 7.x 里返回 ``ValueCountAggregationBuilder``
   （内部 ``new ValueCountAggregationBuilder(name, null, ValuesSourceType.ANY)``），
   等价于 ``new ValueCountAggregationBuilder(name)``；替身直接 new 该类。
"""

from __future__ import annotations

from org.elasticsearch.search.aggregations.bucket.terms.TermsAggregationBuilder import (
    TermsAggregationBuilder,
)
from org.elasticsearch.search.aggregations.metrics.ValueCountAggregationBuilder import (
    ValueCountAggregationBuilder,
)

__all__ = ["AggregationBuilders"]


class AggregationBuilders(object):
    """``AggregationBuilders`` 静态工厂替身。"""

    @staticmethod
    def terms(name: str) -> TermsAggregationBuilder:
        """对应 ``static TermsAggregationBuilder terms(String name)``。"""
        return TermsAggregationBuilder(name)

    @staticmethod
    def count(name: str) -> ValueCountAggregationBuilder:
        """对应 ``static ValueCountAggregationBuilder count(String name)``。"""
        return ValueCountAggregationBuilder(name)
