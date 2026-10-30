# -*- coding: utf-8 -*-
"""org.elasticsearch.search.SearchHits

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.SearchHits``。
本工程用法（EsQueryService.parseEsResponse）：
    if (response.getHits() != null && response.getHits().getHits() != null) {
        for (SearchHit hit : response.getHits().getHits()) { ... }
    }

【Java→Python】关键差异
1) Java 的 ``getHits()`` 返回 **数组** ``SearchHit[]``；Python 返回 ``list``。
   ``for (SearchHit hit : hits)`` → ``for hit in hits``，空数组判空 → ``if hits:``。
2) Java 的 ``getTotalHits()`` 返回 ``TotalHits`` 对象，字段为 ``value``（long）与
   ``relation``（``EQUAL_TO`` / ``GREATER_THAN_OR_EQUAL_TO``）。optimization 包的
   ``GaussEsConsistencyService`` / ``UnifiedQueryService`` 会写 ``.value``，
   所以替身返回 ``TotalHits``（**int 的子类**）：既能当 int 用（``== 5`` / ``int(x)``），
   也支持 ``.value`` / ``.relation`` 属性访问，两种写法都不用改。
3) ``getMaxScore()`` 同理，未使用。
"""

from __future__ import annotations

from typing import List

from org.elasticsearch.search.SearchHit import SearchHit

__all__ = ["SearchHits"]


class TotalHits(int):
    """``TotalHits`` 的替身：int 子类 + ``value`` / ``relation`` 属性。

    【Java→Python】JS/Java 侧写 ``getTotalHits().value``；Python 若直接返回 int，
    访问 ``.value`` 会 AttributeError。继承 int 后两种写法同时成立。
    """

    @property
    def value(self) -> int:
        return int(self)

    @property
    def relation(self) -> str:
        # 本工程不做 max_result_window 截断，总数恒为精确值
        return "EQUAL_TO"

    def toString(self) -> str:
        return "TotalHits[%d, %s]" % (self.value, self.relation)


class SearchHits(object):
    """``SearchHits`` 的替身（命中列表 + 总数）。"""

    def __init__(self, hits: List[SearchHit], total_hits: int = 0) -> None:
        self._hits = list(hits)
        self._total_hits = total_hits if total_hits else len(self._hits)

    # ------------------------------------------------------------------ getter
    def getHits(self) -> List[SearchHit]:
        """对应 ``SearchHit[] getHits()``：Python 返回 list（可能为空列表）。"""
        return list(self._hits)

    def getTotalHits(self) -> TotalHits:
        """对应 ``TotalHits getTotalHits()``；返回 int 子类（见 TotalHits 说明）。"""
        return TotalHits(self._total_hits)

    def getMaxScore(self) -> float:
        return 1.0 if self._hits else 0.0

    def __len__(self) -> int:
        # Python 独有：让 len(hits) 可用；Java 用 getHits().length
        return len(self._hits)

    def __repr__(self) -> str:
        return "SearchHits(total=%d)" % self._total_hits
