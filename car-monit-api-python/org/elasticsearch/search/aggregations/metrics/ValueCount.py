# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.metrics.ValueCount

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.metrics.ValueCount``（接口）。
本工程用法（LargeScaleQueryService.aggregationStats）：
    ValueCount count = bucket.getAggregations().get("total_count");
    resultMap.put(bucket.getKeyAsString(), count.getValue());

【Java→Python】关键差异
1) ``getValue()`` 在 Java 返回 ``long`` → Python int。
2) ``getValueAsString()`` / ``value()``（聚合接口别名）本工程未使用，不实现。
3) ``AggregationBuilders.count(name)`` 在 7.x 里就是 ``value_count`` 聚合的快捷方式，
   语义为“统计该字段**非空**的文档数”（不是去重计数，去重是 cardinality）。
   替身的计数实现见 :class:`ValueCountAggregationBuilder`。
"""

from __future__ import annotations

from org.elasticsearch.search.aggregations.Aggregation import Aggregation

__all__ = ["ValueCount"]


class ValueCount(Aggregation):
    """``ValueCount`` 接口的替身（单值计数结果）。"""

    def __init__(self, name: str, value: int) -> None:
        super().__init__(name)
        self._value = int(value)

    # ------------------------------------------------------------------ getter
    def getValue(self) -> int:
        """对应 ``long getValue()``：字段非空的文档数。"""
        return self._value

    def getValueAsString(self) -> str:
        """对应 ``String getValueAsString()``（ES 用 ``Double.toString``，整数不带小数点）。"""
        return str(self._value)

    def __repr__(self) -> str:
        return "ValueCount(name=%r, value=%d)" % (self.getName(), self._value)
