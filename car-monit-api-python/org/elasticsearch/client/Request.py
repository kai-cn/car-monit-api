# -*- coding: utf-8 -*-
"""org.elasticsearch.client.Request

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch-rest-client jar：``org.elasticsearch.client.Request``。
本工程用法（EsIndexManageService 的 ILM 管理，走**低层 REST 客户端**）：
    Request request = new Request("PUT", "/_ilm/policy/" + policyName);
    request.setJsonEntity(policyJson);
    Response response = esClient.getLowLevelClient().performRequest(request);

【Java→Python 关键差异】
1) Java 的 ``Request(String method, String endpoint)`` 保存 HTTP 方法与路径
   （路径可含查询串）；替身只保存这两个字符串 + JSON 请求体。
2) ``setJsonEntity(String json)`` 会同时设置 ``Content-Type: application/json``；
   替身只保存字符串（没有真实 HTTP 层，无需头信息）。
3) Java 的 ``Request`` 还有 ``addParameter`` / ``setEntity`` / ``setOptions`` 等，
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Optional

__all__ = ["Request"]


class Request(object):
    """``Request`` 的替身（method + endpoint + JSON body）。"""

    def __init__(self, method: str, endpoint: str) -> None:
        self._method = method
        self._endpoint = endpoint
        self._json_entity: Optional[str] = None

    # ------------------------------------------------------------------ 链式 setter
    def setJsonEntity(self, json_entity: str) -> "Request":
        """对应 ``setJsonEntity(String jsonEntity)``。"""
        self._json_entity = json_entity
        return self

    # ------------------------------------------------------------------ getter
    def getMethod(self) -> str:
        """对应 ``getMethod()``：HTTP 方法（GET/PUT/POST/DELETE）。"""
        return self._method

    def getEndpoint(self) -> str:
        """对应 ``getEndpoint()``：请求路径（可能含查询串）。"""
        return self._endpoint

    def getJsonEntity(self) -> Optional[str]:
        """Java 无公开此方法；替身供 ``RestClient.performRequest`` 读取请求体。"""
        return self._json_entity

    def __repr__(self) -> str:
        return "Request(method=%r, endpoint=%r)" % (self._method, self._endpoint)
