# -*- coding: utf-8 -*-
"""org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest``。
本工程用法（EsIndexManageService.dropIndex）：
    DeleteIndexRequest deleteReq = new DeleteIndexRequest(indexName);
    AcknowledgedResponse resp = esClient.indices().delete(deleteReq, RequestOptions.DEFAULT);

【Java→Python 关键差异】
1) Java 的 ``DeleteIndexRequest(String... indices)`` 是可变参数构造器；
   Python 用 ``*indices``。
2) Java 的 ``indices()`` 返回 String[]；Python 返回 list。
"""

from __future__ import annotations

from typing import List

__all__ = ["DeleteIndexRequest"]


class DeleteIndexRequest(object):
    """``DeleteIndexRequest`` 的替身（承载待删索引名）。"""

    def __init__(self, *indices: str) -> None:
        self._indices: List[str] = list(indices)

    def indices(self) -> List[str]:
        """对应 ``String[] indices()``。"""
        return list(self._indices)

    def __repr__(self) -> str:
        return "DeleteIndexRequest(indices=%r)" % (self._indices,)
