# -*- coding: utf-8 -*-
"""org.elasticsearch.client.indices.CreateIndexRequest

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.client.indices.CreateIndexRequest``。
本工程用法（EsIndexManageService.createIndexIfAbsent）：
    CreateIndexRequest createReq = new CreateIndexRequest(indexName);
    createReq.source(settings, XContentType.JSON);
    if (attachIlm) {
        createReq.settings("{\\"index.lifecycle.name\\":\\"...\\"}", XContentType.JSON);
    }
    CreateIndexResponse resp = esClient.indices().create(createReq, RequestOptions.DEFAULT);

【Java→Python 关键差异】
1) Java 的 ``source(String source, XContentType xContentType)`` 是把整段
   settings+mappings JSON 作为建索引请求体；替身保存字符串原文，
   由 ``IndicesClient.create`` 登记到进程内“集群元数据”。
2) Java 有 ``settings(String, XContentType)`` / ``settings(Map<String,?>)`` /
   ``mapping(...)`` / ``alias(...)`` 等多个重载；本工程只用“JSON 字符串”版本。
3) Java 的链式方法返回 ``this``；替身保持一致。
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["CreateIndexRequest"]


class CreateIndexRequest(object):
    """``CreateIndexRequest`` 的替身（索引名 + source JSON + settings JSON）。"""

    def __init__(self, index: str) -> None:
        self._index = index
        #: 建索引请求体（settings + mappings）
        self._source: Optional[str] = None
        self._source_type: Any = None
        #: 单独的 settings 片段（挂载 ILM 时使用）
        self._settings: Optional[str] = None
        self._settings_type: Any = None

    # ------------------------------------------------------------------ 链式 setter
    def source(self, source: str, xcontent_type: Any = None) -> "CreateIndexRequest":
        """对应 ``source(String source, XContentType xContentType)``。"""
        self._source = source
        self._source_type = xcontent_type
        return self

    def settings(self, settings: str, xcontent_type: Any = None) -> "CreateIndexRequest":
        """对应 ``settings(String source, XContentType xContentType)``。"""
        self._settings = settings
        self._settings_type = xcontent_type
        return self

    # ------------------------------------------------------------------ getter
    def index(self) -> str:
        """对应 ``index()``。"""
        return self._index

    def getSource(self) -> Optional[str]:
        """Java 无公开 ``getSource``；替身供 ``IndicesClient.create`` 读取。"""
        return self._source

    def getSettings(self) -> Optional[str]:
        return self._settings

    def __repr__(self) -> str:
        return "CreateIndexRequest(index=%r)" % (self._index,)
