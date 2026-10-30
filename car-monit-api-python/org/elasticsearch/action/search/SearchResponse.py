# -*- coding: utf-8 -*-
"""org.elasticsearch.action.search.SearchResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.action.search.SearchResponse``。
本工程用法（EsQueryService.parseEsResponse）：
    SearchResponse response = esClient.search(searchRequest, RequestOptions.DEFAULT);
    response.getHits()...

【Java→Python】关键差异
1) Java 的 ``getHits()`` 返回 ``SearchHits``（一定非 null，空结果时 hits 长度为 0）；
   原代码里的 ``response.getHits() != null`` 属于**防御性冗余判断**，忠实保留。
2) ``getTook()`` / ``isTimedOut()``：真实 ES 的耗时/超时标记；替身只记录传入值。
3) ``getAggregations()`` / ``getScrollId()`` 由 LargeScaleQueryService 使用：
   - ``getAggregations()`` 在 Java 里**恒非 null**（无聚合时是空 ``Aggregations``），
     所以 ``size(0)`` 查询也能直接链式调用，不会 NPE；替身保持该语义。
   - ``getScrollId()`` 仅当请求设置了 ``scroll(...)`` 时非 null，
     普通查询返回 null（Java 也返回 null）。
"""

from __future__ import annotations

from typing import Optional

from org.elasticsearch.search.SearchHits import SearchHits
from org.elasticsearch.search.aggregations.Aggregations import Aggregations

__all__ = ["SearchResponse"]


class SearchResponse(object):
    """``SearchResponse`` 的替身（SearchHits + 聚合结果 + scrollId）。"""

    def __init__(self, hits: SearchHits, took: int = 0,
                 timed_out: bool = False,
                 aggregations: Optional[Aggregations] = None,
                 scroll_id: Optional[str] = None) -> None:
        self._hits = hits
        self._took = took
        self._timed_out = timed_out
        # 【Java→Python】Java 的 getAggregations() 恒非 null（无聚合时为空集合），
        # 这里同样默认构造一个空的 Aggregations，避免调用方多一层判空。
        self._aggregations = aggregations if aggregations is not None else Aggregations()
        self._scroll_id = scroll_id

    # ------------------------------------------------------------------ getter
    def getHits(self) -> SearchHits:
        return self._hits

    def getTook(self) -> int:
        return self._took

    def isTimedOut(self) -> bool:
        return self._timed_out

    def getAggregations(self) -> Aggregations:
        """对应 ``Aggregations getAggregations()``：无聚合时返回空容器（非 None）。"""
        return self._aggregations

    def getScrollId(self) -> Optional[str]:
        """对应 ``String getScrollId()``：非游标查询返回 None（Java 返回 null）。"""
        return self._scroll_id

    def __repr__(self) -> str:
        return "SearchResponse(%r, aggregations=%d, scrollId=%r)" % (
            self._hits, len(self._aggregations), self._scroll_id)
