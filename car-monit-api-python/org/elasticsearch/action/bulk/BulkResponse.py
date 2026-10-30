# -*- coding: utf-8 -*-
"""org.elasticsearch.action.bulk.BulkResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.bulk.BulkResponse`。

本工程用法（LargeScaleDataSyncService 的 BulkProcessor.Listener）：
    if (response.hasFailures()) {
        long failed = Arrays.stream(response.getItems())
                .filter(BulkItemResponse::isFailed).count();
        ...
    }

【Java→Python 关键差异】
1) `getItems()` 在 Java 返回 `BulkItemResponse[]`（数组，有 `.length`）；
   Python 返回 `List[BulkItemResponse]`（用 `len(...)`）。
2) 真实响应还带 took / ingestTook 等耗时字段，本工程未使用，不实现。
"""
from __future__ import annotations

from typing import List

from org.elasticsearch.action.bulk.BulkItemResponse import BulkItemResponse

__all__ = ["BulkResponse"]


class BulkResponse(object):
    """`BulkResponse` 的替身（仅保存 items）。"""

    def __init__(self, items: List[BulkItemResponse]) -> None:
        self._items: List[BulkItemResponse] = list(items or [])

    def hasFailures(self) -> bool:
        """对应 `hasFailures()`：是否存在失败子项。"""
        return any(item.isFailed() for item in self._items)

    def getItems(self) -> List[BulkItemResponse]:
        """对应 `getItems()`（Java 数组 → Python list）。"""
        return list(self._items)

    def __repr__(self) -> str:
        return "BulkResponse(items=%d, failures=%d)" % (
            len(self._items), sum(1 for item in self._items if item.isFailed()))
