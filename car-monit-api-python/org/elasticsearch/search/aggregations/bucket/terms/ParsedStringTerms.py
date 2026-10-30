# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms``。
本工程用法（LargeScaleQueryService.aggregationStats）：
    ParsedStringTerms terms = response.getAggregations().get("group_by_" + groupBy);
    for (Terms.Bucket bucket : terms.getBuckets()) { ... }

【Java→Python】关键差异
1) 真实 ES 里 ``ParsedStringTerms`` 是**响应反序列化产物**（继承 ``ParsedTerms``，
   桶类型为 ``ParsedStringTerms.ParsedBucket``，key 恒为 String）。
   替身里“解析”发生在进程内，``TermsAggregationBuilder.aggregate`` 直接返回
   本类实例，因此调用处的 ``ParsedStringTerms terms = ...`` 写法无需改动。
2) Java 侧的 ``getValueCountError()`` 本工程未使用；``getSumOtherDocCount()``
   记录被 ``size`` 截断掉的桶所覆盖的文档数，由 ``TermsAggregationBuilder.aggregate``
   求值后写入（初始 0）。
"""

from __future__ import annotations

from typing import List, Optional

from org.elasticsearch.search.aggregations.bucket.terms.Terms import Terms

__all__ = ["ParsedStringTerms"]


class ParsedStringTerms(Terms):
    """``ParsedStringTerms`` 的替身（key 为字符串的 terms 聚合结果）。"""

    def __init__(self, name: str,
                 buckets: Optional[List[Terms.Bucket]] = None) -> None:
        super().__init__(name, buckets)
        #: 未纳入 top-N 的桶所覆盖的文档数；-1 表示未统计（与 ES 默认一致）
        self._sum_other_doc_count: int = 0

    # ------------------------------------------------------------------ getter
    def getSumOtherDocCount(self) -> int:
        """对应 ``long getSumOtherDocCount()``：被 ``size`` 截断掉的文档数。"""
        return self._sum_other_doc_count

    def setSumOtherDocCount(self, count: int) -> None:
        """Java 无公开 setter（由 ``ParsedTerms`` 反序列化时赋值）；替身用于求值。"""
        self._sum_other_doc_count = int(count)

    def __repr__(self) -> str:
        return ("ParsedStringTerms(name=%r, buckets=%d, otherDocCount=%d)" %
                (self.getName(), len(self.getBuckets()), self._sum_other_doc_count))
