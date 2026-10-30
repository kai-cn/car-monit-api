# -*- coding: utf-8 -*-
"""org.elasticsearch.action.search.ClearScrollResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.search.ClearScrollResponse``。
本工程用法（LargeScaleQueryService.executeExportScroll 的 finally）：
    client.clearScroll(clearScrollRequest, RequestOptions.DEFAULT);

【Java→Python】关键差异
1) Java 侧该返回值**被丢弃**（只用于确认清理成功，失败会抛异常）；
   替身仍返回本对象，保证 ``client.clearScroll(...)`` 的返回类型与 Java 一致。
2) ``isSucceeded()`` 对应 ``RestStatus.OK`` 判定；``getNumFreed()`` 是实际释放的
   上下文个数（替身里就是被删掉的游标数）。
"""

from __future__ import annotations

__all__ = ["ClearScrollResponse"]


class ClearScrollResponse(object):
    """``ClearScrollResponse`` 的替身（清理结果）。"""

    def __init__(self, succeeded: bool = True, num_freed: int = 1) -> None:
        self._succeeded = bool(succeeded)
        self._num_freed = int(num_freed)

    # ------------------------------------------------------------------ getter
    def isSucceeded(self) -> bool:
        """对应 ``boolean isSucceeded()``。"""
        return self._succeeded

    def getNumFreed(self) -> int:
        """对应 ``int getNumFreed()``：释放的 search context 数量。"""
        return self._num_freed

    def __repr__(self) -> str:
        return "ClearScrollResponse(succeeded=%r, numFreed=%d)" % (
            self._succeeded, self._num_freed)
