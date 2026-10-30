# -*- coding: utf-8 -*-
"""org.elasticsearch.action.index.IndexResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.action.index.IndexResponse``。
本工程用法（DataProcessService）：
    IndexResponse response = esClient.index(request, RequestOptions.DEFAULT);
    log.debug(..., response.getResult());

【Java→Python】关键差异
1) Java 的 ``getResult()`` 返回 ``DocWriteResponse.Result`` **枚举**
   （CREATED / UPDATED / DELETED / NOT_FOUND / NOOP）；日志里 ``{}`` 打印枚举名。
   替身直接用字符串 ``"CREATED"`` / ``"UPDATED"``，打印结果与 Java 完全一致。
2) ``getVersion()`` 在 Java 里是乐观锁版本号（新建为 1，覆盖 +1）；替身同样自增。
3) ``getShardInfo()`` / ``getSeqNo()`` 等本工程未使用，不实现。
"""

from __future__ import annotations

__all__ = ["IndexResponse"]


class IndexResponse(object):
    """``IndexResponse`` 的替身（result 用字符串模拟枚举名）。"""

    def __init__(self, index: str, doc_id: str, result: str,
                 version: int = 1) -> None:
        self._index = index
        self._id = doc_id
        self._result = result
        self._version = version

    # ------------------------------------------------------------------ getter
    def getIndex(self) -> str:
        return self._index

    def getId(self) -> str:
        return self._id

    def getResult(self) -> str:
        """``CREATED``（首次写入）/ ``UPDATED``（同 id 覆盖）。"""
        return self._result

    def getVersion(self) -> int:
        return self._version

    def __repr__(self) -> str:
        return "IndexResponse(index=%r, id=%r, result=%r, version=%d)" % (
            self._index, self._id, self._result, self._version)
