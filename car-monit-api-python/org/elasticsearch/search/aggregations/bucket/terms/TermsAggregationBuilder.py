# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.bucket.terms.TermsAggregationBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.bucket.terms.TermsAggregationBuilder``。
本工程用法（LargeScaleQueryService.aggregationStats）：
    AggregationBuilders.terms("group_by_" + groupBy)
            .field(groupBy + ".keyword")
            .size(topN)
            .subAggregation(...)

【Java→Python】关键差异（**排序与 size 截断语义**）
1) ES 的 terms 聚合默认 ``order: doc_count desc``，**计数相同时按 key 升序**；
   同时 ``missing`` 值默认**不进桶**。替身逐条复刻这两点，见 :meth:`aggregate`。
2) ``size(int)`` 在 Java 里是 **top-N 桶数**（不是返回文档数），默认 10；
   ``sum_other_doc_count`` 记录被截断掉的桶的文档总数 —— 替身同样写入，
   这样才能与真实 ES 的 ``getSumOtherDocCount()`` 对齐。
3) ``field(String)`` / ``size(int)`` 在 Java 返回 ``this``；替身一致。
4) Java 的 ``size`` 与 ``SearchSourceBuilder#size(int)`` 同名但语义完全不同
   （前者=桶数，后者=文档数），迁移时不要混用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from org.elasticsearch.search.aggregations.AggregationBuilder import (
    AggregationBuilder,
    field_value,
)
from org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms import (
    ParsedStringTerms,
)
from org.elasticsearch.search.aggregations.bucket.terms.Terms import Terms

__all__ = ["TermsAggregationBuilder"]

#: ES terms 聚合的默认 top-N 桶数
_DEFAULT_SIZE = 10


def _order_key(key: Any) -> Tuple[int, Any]:
    """构造“计数相同时按 key 升序”的比较键。

    【Java→Python】ES 内部对字符串用字节序、对数字用数值序；Python 混用 str/int
    无法比较，所以用 (类型档位, 值) 两段式键：数字（含布尔）在前按数值比，
    字符串在后按字典序比。同一字段的真实取值类型是一致的，档位只用于兜底。
    """
    if isinstance(key, bool):
        return (0, int(key))
    if isinstance(key, (int, float)):
        return (0, key)
    return (1, str(key))


class TermsAggregationBuilder(AggregationBuilder):
    """``TermsAggregationBuilder`` 的替身（terms 分桶聚合）。"""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        #: 分桶字段；None 表示未设置
        self._field: Optional[str] = None
        #: top-N 桶数（ES 默认 10）
        self._size: int = _DEFAULT_SIZE

    # ------------------------------------------------------------------ 链式 setter
    def field(self, field: str) -> "TermsAggregationBuilder":
        """对应 ``field(String field)``：返回 this。"""
        self._field = field
        return self

    def size(self, size: int) -> "TermsAggregationBuilder":
        """对应 ``size(int size)``：**top-N 桶数**（不是文档数），返回 this。"""
        self._size = int(size)
        return self

    # ------------------------------------------------------------------ getter
    def getField(self) -> Optional[str]:
        return self._field

    def getSize(self) -> int:
        return self._size

    # ------------------------------------------------------------------ 求值
    def aggregate(self, documents: List[Dict[str, Any]]) -> ParsedStringTerms:
        """对全部命中文档分桶。

        【Java→Python】ES 在服务端分桶；替身按 ``field_value`` 在本地分组。
        语义对齐点：① 缺失/None 值不进桶；② 计数倒序、同计数按 key 升序；
        ③ 截断到 ``size``，被截断的文档数累加到 ``sum_other_doc_count``。
        """
        groups: Dict[Any, List[Dict[str, Any]]] = {}
        for document in documents:
            value = field_value(document, self._field)
            if value is None:
                # ES terms 聚合默认不把 missing 值放进桶
                continue
            groups.setdefault(value, []).append(document)

        ordered = sorted(groups.items(),
                         key=lambda item: (-len(item[1]), _order_key(item[0])))
        buckets: List[Terms.Bucket] = []
        other_doc_count = 0
        for position, (key, bucket_documents) in enumerate(ordered):
            if position >= self._size:
                other_doc_count += len(bucket_documents)
                continue
            buckets.append(Terms.Bucket(
                key, len(bucket_documents),
                self._subAggregations(bucket_documents)))

        terms = ParsedStringTerms(self.getName(), buckets)
        terms.setSumOtherDocCount(other_doc_count)
        return terms

    def __repr__(self) -> str:
        return "TermsAggregationBuilder(name=%r, field=%r, size=%d)" % (
            self.getName(), self._field, self._size)
