# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.metrics.ValueCountAggregationBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.metrics.ValueCountAggregationBuilder``。
本工程用法（LargeScaleQueryService.aggregationStats）：
    AggregationBuilders.count("total_count").field(countField == null ? "_id" : countField)

【Java→Python】关键差异
1) ``AggregationBuilders.count(name)`` 在 Java 里返回
   ``ValueCountAggregationBuilder``（``count`` 只是带 ``ValuesSourceType.ANY`` 的快捷工厂）。
   本替身由 ``AggregationBuilders.count`` 直接 new 本类，类型一致。
2) ``field(String)`` 在 Java 返回 ``this``（链式）；替身一致。
3) ES 的 ``value_count`` 统计**非空值**的个数：
   ``_id`` 恒存在 ⇒ 等于桶内文档数；其余字段 ⇒ 值为 ``null``/缺失的文档不计入。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from org.elasticsearch.search.aggregations.AggregationBuilder import (
    AggregationBuilder,
    field_value,
)
from org.elasticsearch.search.aggregations.metrics.ValueCount import ValueCount

__all__ = ["ValueCountAggregationBuilder"]


class ValueCountAggregationBuilder(AggregationBuilder):
    """``ValueCountAggregationBuilder`` 的替身（value_count 聚合）。"""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        #: 计数字段；None 表示未设置（Java 侧 field() 之前为 null）
        self._field: Optional[str] = None

    # ------------------------------------------------------------------ 链式 setter
    def field(self, field: str) -> "ValueCountAggregationBuilder":
        """对应 ``field(String field)``：返回 this。"""
        self._field = field
        return self

    # ------------------------------------------------------------------ getter
    def getField(self) -> Optional[str]:
        return self._field

    # ------------------------------------------------------------------ 求值
    def aggregate(self, documents: List[Dict[str, Any]]) -> ValueCount:
        """统计字段非空的文档数。

        【Java→Python】ES 在服务端算；替身在本地算。
        ``_id``（文档主键）恒存在，所以按 ES 语义等价于 ``len(documents)``。
        """
        if self._field is None or self._field == "_id":
            return ValueCount(self.getName(), len(documents))
        count = sum(1 for document in documents
                    if field_value(document, self._field) is not None)
        return ValueCount(self.getName(), count)

    def __repr__(self) -> str:
        return "ValueCountAggregationBuilder(name=%r, field=%r)" % (
            self.getName(), self._field)
