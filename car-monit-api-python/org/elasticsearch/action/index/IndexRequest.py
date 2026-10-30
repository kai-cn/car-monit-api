# -*- coding: utf-8 -*-
"""org.elasticsearch.action.index.IndexRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.action.index.IndexRequest``。
本工程用法（DataProcessService）：
    new IndexRequest(ES_INDEX)
            .id(data.getId().toString())
            .source(JSON.toJSONString(data), XContentType.JSON);

【Java→Python】关键差异
1) Java 的 ``id()`` / ``source()`` 是**链式方法**（返回 this），替身保持一致。
2) Java 有多个 ``source(...)`` 重载（String / byte[] / Map / XContentBuilder，
   带或不带 XContentType）；Python 无重载，这里用 ``source(content, content_type=None)``
   单方法表达，并按类型分派：str 原样保存，bytes 按 UTF-8 解码，
   dict/其他对象交给 ``str(...)``（真实 fastjson 调用方总传 String，不会走到这里）。
3) 真实请求还带路由/刷新策略/版本号等；本工程只用 index + id + source，其余不实现。
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["IndexRequest"]


class IndexRequest(object):
    """``IndexRequest`` 的替身（仅保存 index / id / source）。"""

    def __init__(self, index: str) -> None:
        self._index = index
        self._id: Optional[str] = None
        self._source: Optional[str] = None
        self._content_type: Optional[str] = None

    # ------------------------------------------------------------------ 链式 setter
    def id(self, doc_id: Optional[str]) -> "IndexRequest":
        """对应 ``id(String id)``。"""
        self._id = None if doc_id is None else str(doc_id)
        return self

    def source(self, content: Any,
               content_type: Optional[Any] = None) -> "IndexRequest":
        """对应 ``source(String source, XContentType contentType)`` 等重载。"""
        if isinstance(content, bytes):
            self._source = content.decode("utf-8")
        elif isinstance(content, str):
            self._source = content
        else:
            # 真实 fastjson 只会传 String；这里宽松处理 Map 等类型
            from com.alibaba.fastjson2.JSON import JSON
            self._source = JSON.toJSONString(content)
        self._content_type = content_type
        return self

    # ------------------------------------------------------------------ getter
    def index(self) -> str:
        return self._index

    def getId(self) -> Optional[str]:
        return self._id

    def getSource(self) -> Optional[str]:
        return self._source

    def __repr__(self) -> str:
        return "IndexRequest(index=%r, id=%r, source=%r)" % (
            self._index, self._id, self._source)
