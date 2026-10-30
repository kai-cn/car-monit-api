# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.AggregationBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.AggregationBuilder``（抽象类）。
本工程用法（LargeScaleQueryService.aggregationStats）：
    sourceBuilder.aggregation(AggregationBuilders.terms("group_by_" + groupBy)
            .field(groupBy + ".keyword")
            .size(topN)
            .subAggregation(AggregationBuilders.count("total_count")
                    .field(countField == null ? "_id" : countField))
    );

【Java→Python】关键差异（**整个 aggregation 替身的设计说明**）
1) 真实 ES 把 AggregationBuilder 序列化成 DSL，由**各分片并行聚合**后再 reduce；
   本替身没有网络层，改为在 ``RestHighLevelClient.search`` 里对**全部命中文档**
   逐条调用 ``builder.aggregate(documents)`` 在进程内计算（见该方法注释）。
   关键语义对齐点：聚合作用于**整个命中集合**，与 ``from`` / ``size`` 无关
   —— 这正是 ``size(0)`` 只取聚合、不取文档的前提。
2) ``subAggregation(AggregationBuilder)`` 在 Java 返回 ``this``（链式）；
   替身同样返回 ``this``，子聚合按**加入顺序**计算并放进桶的 ``Aggregations``。
3) ``getName()`` 在 Java 里是 ``public abstract String getName()``，指**聚合名**
   （注意与 ``Terms#getName()`` 同名但语义不同：前者是“配置的名字”，
   后者是“结果的名字”）。替身由构造器传入的 name 统一提供。
4) 真实 ES 的聚合字段用 doc_values；``.keyword`` / ``.ngram`` 是 **multi-field**
   （只存在于 mapping 的倒排索引里，``_source`` 中仍是裸字段名）。
   因此 ``field("platenumber.keyword")`` 取的是 ``_source["platenumber"]``，
   见 :func:`field_value`。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from org.elasticsearch.search.aggregations.Aggregation import Aggregation
from org.elasticsearch.search.aggregations.Aggregations import Aggregations

__all__ = ["AggregationBuilder", "field_value"]

#: ES multi-field 的后缀：``_source`` 中不含它们，取值时要剥掉
_MULTI_FIELD_SUFFIXES = (".keyword", ".ngram")


def field_value(document: Dict[str, Any], field: Optional[str]) -> Any:
    """从 ``_source`` 文档里取聚合字段的值（等价 ES 按 doc_values 取值）。

    【Java→Python】Java 侧没有这个方法——取值发生在 ES 服务端。替身必须在本地
    复刻 ES 的 multi-field 语义：``field("platenumber.keyword")`` 读的是
    ``_source["platenumber"]``。字段缺失时返回 ``None``（ES 的 ``missing`` 语义）。
    """
    if not field:
        return None
    for suffix in _MULTI_FIELD_SUFFIXES:
        if field.endswith(suffix):
            return document.get(field[:-len(suffix)])
    return document.get(field)


class AggregationBuilder(object):
    """``AggregationBuilder`` 抽象类的替身：名字 + 子聚合 + 本地求值。"""

    def __init__(self, name: str) -> None:
        self._name: str = name
        #: 子聚合构建器（按加入顺序）
        self._sub_aggregations: List["AggregationBuilder"] = []

    # ------------------------------------------------------------------ 链式 setter
    def subAggregation(self, builder: "AggregationBuilder") -> "AggregationBuilder":
        """对应 ``subAggregation(AggregationBuilder)``：返回 this。"""
        self._sub_aggregations.append(builder)
        return self

    # ------------------------------------------------------------------ getter
    def getName(self) -> str:
        """对应 ``public abstract String getName()``：聚合名。"""
        return self._name

    def getSubAggregations(self) -> List["AggregationBuilder"]:
        """Java 无公开此方法（内部有 ``factoriesBuilder``）；替身用于求值与断言。"""
        return list(self._sub_aggregations)

    # ------------------------------------------------------------------ 求值
    def aggregate(self, documents: List[Dict[str, Any]]) -> Aggregation:
        """在给定文档集合上计算聚合结果。

        【Java→Python】Java 无此方法（计算在 ES 服务端）。子类必须实现：
        返回的 ``Aggregation`` 要带上 ``self._sub_aggregations`` 的计算结果。
        """
        raise NotImplementedError("AggregationBuilder.aggregate 必须由子类实现")

    def _subAggregations(self, documents: List[Dict[str, Any]]) -> Aggregations:
        """计算全部子聚合（对应 DSL 里的 ``"aggs": {...}``）。"""
        return Aggregations({builder.getName(): builder.aggregate(documents)
                             for builder in self._sub_aggregations})

    def __repr__(self) -> str:
        return "%s(name=%r)" % (type(self).__name__, self._name)
