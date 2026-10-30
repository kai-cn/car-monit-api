# -*- coding: utf-8 -*-
"""org.elasticsearch.action.bulk.BulkItemResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.bulk.BulkItemResponse`。

本工程用法（LargeScaleDataSyncService 的 BulkProcessor.Listener）：
    Arrays.stream(response.getItems())
          .filter(BulkItemResponse::isFailed)
          .peek(item -> log.warn("... id={}, reason={}",
                  item.getId(), item.getFailureMessage()))
          .count();

【Java→Python 关键差异】
1) 真实的 `BulkItemResponse` 由 ES 响应 JSON 反序列化而来，字段包括 opType/index/id/
   failure 等；替身只保留本工程用到的 `isFailed/getId/getFailureMessage`。
2) Java 的 `getFailureMessage()` 在无失败时返回 null → Python 返回 None。
"""
from __future__ import annotations

from typing import Optional

__all__ = ["BulkItemResponse"]


class BulkItemResponse(object):
    """单条 bulk 子项的结果。"""

    def __init__(self, item_id: Optional[str] = None, failed: bool = False,
                 failure_message: Optional[str] = None) -> None:
        self._id = item_id
        self._failed = failed
        self._failure_message = failure_message

    def isFailed(self) -> bool:
        """对应 `isFailed()`：该子项是否失败。"""
        return self._failed

    def getId(self) -> Optional[str]:
        """对应 `getId()`：文档 _id。"""
        return self._id

    def getFailureMessage(self) -> Optional[str]:
        """对应 `getFailureMessage()`：失败原因（无失败时为 null）。"""
        return self._failure_message

    def __repr__(self) -> str:
        return "BulkItemResponse(id=%r, failed=%r, reason=%r)" % (
            self._id, self._failed, self._failure_message)
