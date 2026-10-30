# -*- coding: utf-8 -*-
"""org.elasticsearch.action.search.SearchRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.action.search.SearchRequest``。
本工程用法（EsQueryService）：
    SearchRequest searchRequest = new SearchRequest(ES_INDEX);
    searchRequest.source(sourceBuilder);
    SearchResponse response = esClient.search(searchRequest, RequestOptions.DEFAULT);

【Java→Python】关键差异
1) Java 的构造器 ``SearchRequest(String... indices)`` 是可变参数；Python 用 ``*indices``。
   另外还有 ``SearchRequest(SearchRequest)`` 拷贝构造器和无参构造器，本工程未使用。
2) ``source(SearchSourceBuilder)`` 返回 this；替身保存引用（不深拷贝）。
3) Java 还有 ``indicesOptions`` / ``routing`` / ``preference`` 等，本工程未使用。
4) ``scroll(Scroll)`` 由 LargeScaleQueryService 使用（导出走游标深翻页），
   链式返回 this；``getScroll()`` 供 ``RestHighLevelClient.search`` 判断
   “这是否是一个游标查询”，从而登记游标上下文。
"""

from __future__ import annotations

from typing import Any, List, Optional

__all__ = ["SearchRequest"]


class SearchRequest(object):
    """``SearchRequest`` 的替身（indices + SearchSourceBuilder）。"""

    def __init__(self, *indices: str) -> None:
        self._indices: List[str] = list(indices)
        self._source: Optional[Any] = None
        #: 游标存活配置；None 表示普通（非 scroll）查询
        self._scroll: Optional[Any] = None

    # ------------------------------------------------------------------ 链式 setter
    def source(self, source_builder: Any) -> "SearchRequest":
        """对应 ``source(SearchSourceBuilder source)``。"""
        self._source = source_builder
        return self

    def scroll(self, scroll: Any) -> "SearchRequest":
        """对应 ``scroll(Scroll scroll)``：返回 this。"""
        self._scroll = scroll
        return self

    # ------------------------------------------------------------------ getter
    def indices(self) -> List[str]:
        return list(self._indices)

    def getSource(self) -> Optional[Any]:
        return self._source

    def getScroll(self) -> Optional[Any]:
        """对应 ``Scroll getScroll()``：非游标查询返回 None（Java 返回 null）。"""
        return self._scroll

    def __repr__(self) -> str:
        return "SearchRequest(indices=%r, source=%r, scroll=%r)" % (
            self._indices, self._source, self._scroll)
