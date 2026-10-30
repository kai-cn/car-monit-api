# -*- coding: utf-8 -*-
"""org.elasticsearch.action.search.SearchScrollRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.search.SearchScrollRequest``。
本工程用法（LargeScaleQueryService.executeExportScroll）：
    SearchScrollRequest scrollRequest = new SearchScrollRequest(scrollId);
    scrollRequest.scroll(new Scroll(new TimeValue(5, TimeUnit.MINUTES)));
    scrollResp = client.scroll(scrollRequest, RequestOptions.DEFAULT);

【Java→Python】关键差异
1) Java 的构造器 ``SearchScrollRequest(String scrollId)`` 与无参构造器并存；
   Python 用默认参数 ``scroll_id=None`` 表达两个重载。
2) ``scrollId(String)`` 与 ``scroll(Scroll)`` 都是链式 setter，返回 ``this``；
   ``scrollId()``（无参）是 getter —— **同名不同签名**在 Python 里无法共存，
   因此 getter 保留 Java 侧真实使用的 ``scrollId()``，setter 改为 ``setScrollId``
   （本工程只用构造器传 id，没有用到 setter）。
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["SearchScrollRequest"]


class SearchScrollRequest(object):
    """``SearchScrollRequest`` 的替身（scrollId + Scroll）。"""

    def __init__(self, scroll_id: Optional[str] = None) -> None:
        self._scroll_id = scroll_id
        self._scroll: Optional[Any] = None

    # ------------------------------------------------------------------ 链式 setter
    def setScrollId(self, scroll_id: str) -> "SearchScrollRequest":
        """``scrollId(String)`` 链式 setter 的对应物（见文件头第 2 条）。"""
        self._scroll_id = scroll_id
        return self

    def scroll(self, scroll: Any) -> "SearchScrollRequest":
        """对应 ``scroll(Scroll scroll)``：返回 this。"""
        self._scroll = scroll
        return self

    # ------------------------------------------------------------------ getter
    def scrollId(self) -> Optional[str]:
        """对应 ``String scrollId()``。"""
        return self._scroll_id

    def getScroll(self) -> Optional[Any]:
        """Java 无公开此方法；替身用于求值（keepAlive 不做实际回收）。"""
        return self._scroll

    def __repr__(self) -> str:
        return "SearchScrollRequest(scrollId=%r, scroll=%r)" % (
            self._scroll_id, self._scroll)
