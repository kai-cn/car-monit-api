# -*- coding: utf-8 -*-
"""org.elasticsearch.client.indices.GetIndexRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.client.indices.GetIndexRequest``。
本工程用法（EsIndexManageService）：
    GetIndexRequest existsReq = new GetIndexRequest(indexName);
    if (esClient.indices().exists(existsReq, RequestOptions.DEFAULT)) { ... }

【Java→Python 关键差异】
1) Java 的 ``GetIndexRequest(String... indices)`` 是可变参数构造器；
   Python 用 ``*indices``，调用写法一致。
2) Java 的 ``indices()`` 返回 String[]；Python 返回 list。
3) 本工程只用 ``GetIndexRequest(String)`` 的单索引重载，其余
   （``indicesOptions`` / ``local`` / ``includeDefaults``）不需要。
"""

from __future__ import annotations

from typing import List

__all__ = ["GetIndexRequest"]


class GetIndexRequest(object):
    """``GetIndexRequest`` 的替身（承载索引名列表）。"""

    def __init__(self, *indices: str) -> None:
        self._indices: List[str] = list(indices)

    def indices(self) -> List[str]:
        """对应 ``String[] indices()``。"""
        return list(self._indices)

    def __repr__(self) -> str:
        return "GetIndexRequest(indices=%r)" % (self._indices,)
