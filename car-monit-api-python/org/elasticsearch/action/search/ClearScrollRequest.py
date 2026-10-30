# -*- coding: utf-8 -*-
"""org.elasticsearch.action.search.ClearScrollRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.search.ClearScrollRequest``。
本工程用法（LargeScaleQueryService.executeExportScroll 的 finally）：
    ClearScrollRequest clearScrollRequest = new ClearScrollRequest();
    clearScrollRequest.addScrollId(scrollId);
    client.clearScroll(clearScrollRequest, RequestOptions.DEFAULT);

【Java→Python】关键差异
1) Java 内部维护 ``List<String> scrollIds``；``addScrollId(String)`` 追加、无返回值
   （**不是链式**），``getScrollIds()`` 返回列表。
2) ``scrollId(String...)`` 是“**覆盖**式”设置（先清空再 addAll），与 ``addScrollId``
   语义不同；本工程只用 ``addScrollId``，替身两个都提供以免误用。
"""

from __future__ import annotations

from typing import List

__all__ = ["ClearScrollRequest"]


class ClearScrollRequest(object):
    """``ClearScrollRequest`` 的替身（待清理的 scrollId 列表）。"""

    def __init__(self) -> None:
        self._scroll_ids: List[str] = []

    # ------------------------------------------------------------------ setter
    def addScrollId(self, scroll_id: str) -> None:
        """对应 ``void addScrollId(String scrollId)``：追加（无返回值）。"""
        self._scroll_ids.append(scroll_id)

    def scrollId(self, *scroll_ids: str) -> None:
        """对应 ``void scrollId(String... scrollIds)``：**覆盖**设置。"""
        self._scroll_ids = list(scroll_ids)

    # ------------------------------------------------------------------ getter
    def getScrollIds(self) -> List[str]:
        """对应 ``List<String> getScrollIds()``。"""
        return list(self._scroll_ids)

    def __repr__(self) -> str:
        return "ClearScrollRequest(scrollIds=%r)" % (self._scroll_ids,)
