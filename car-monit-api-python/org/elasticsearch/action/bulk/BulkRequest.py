# -*- coding: utf-8 -*-
"""org.elasticsearch.action.bulk.BulkRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.bulk.BulkRequest`。

本工程用法（BulkProcessor 内部，业务代码不直接构造）：
    request.numberOfActions()   // 批次条数
    client.bulkAsync(request, RequestOptions.DEFAULT, listener)

【Java→Python 关键差异】
1) Java 的 `BulkRequest.add(IndexRequest)` 存在多个重载（Index/Update/Delete），
   本工程只写入 IndexRequest，故只实现该重载。
2) `numberOfActions()` 返回 int；Python 返回 int（列表长度）。
3) `requests()` 在 Java 中返回 `List<DocWriteRequest<?>>`，供底层客户端序列化；
   替身用它把 action 列表交给 RestHighLevelClient.bulkAsync 逐条落库。
"""
from __future__ import annotations

from typing import Any, List

__all__ = ["BulkRequest"]


class BulkRequest(object):
    """`BulkRequest` 的替身（仅收集 IndexRequest）。"""

    def __init__(self) -> None:
        self._actions: List[Any] = []

    def add(self, request: Any) -> "BulkRequest":
        """对应 `add(IndexRequest)`：链式返回 this。"""
        self._actions.append(request)
        return self

    def numberOfActions(self) -> int:
        """对应 `numberOfActions()`：本批次条数。"""
        return len(self._actions)

    def requests(self) -> List[Any]:
        """对应 `requests()`：返回动作列表（Java 为 DocWriteRequest 列表）。"""
        return list(self._actions)

    def __repr__(self) -> str:
        return "BulkRequest(actions=%d)" % len(self._actions)
