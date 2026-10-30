# -*- coding: utf-8 -*-
"""org.elasticsearch.client.Response

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch-rest-client jar：
``org.elasticsearch.client.Response`` / ``Response.StatusLine`` / ``HttpEntity``。
本工程用法（EsIndexManageService 的 ILM 管理）：
    Response response = esClient.getLowLevelClient().performRequest(request);
    int status = response.getStatusLine().getStatusCode();
    String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);

【Java→Python 关键差异】
1) Java 的 ``Response`` 由真实 HTTP 层构造，包含 ``StatusLine``（含状态码、
   协议版本）与 ``HttpEntity``（可读流）。替身只保留**状态码 + 文本 body**。
2) ``getEntity()`` 在 Java 返回 ``HttpEntity``（可能为 null）；
   替身返回 ``_HttpEntity``（Python 私有类），其 ``text`` 属性供
   ``EntityUtils.toString`` 直接读取 —— 见 ``org/apache/http/util/EntityUtils.py``。
3) ``close()`` 在 Java 里释放连接；替身无连接，空实现。
"""

from __future__ import annotations

from typing import Optional

__all__ = ["Response", "StatusLine", "HttpEntity"]


class StatusLine(object):
    """``Response.StatusLine`` 的替身（只保留 HTTP 状态码）。"""

    def __init__(self, status_code: int, reason_phrase: str = "") -> None:
        self._status_code = int(status_code)
        self._reason_phrase = reason_phrase

    def getStatusCode(self) -> int:
        """对应 ``getStatusCode()``。"""
        return self._status_code

    def getReasonPhrase(self) -> str:
        return self._reason_phrase

    def __repr__(self) -> str:
        return "StatusLine(%d)" % self._status_code


class _HttpEntity(object):
    """``org.apache.http.HttpEntity`` 的最小替身。

    【Java→Python】Java 的 entity 是字节流；替身直接保存**已解码文本**，
    因为替身构造响应时就知道 body 是 JSON 字符串，无需再做字节→字符转换。
    """

    def __init__(self, text: str) -> None:
        self.text = text
        #: 同时提供 bytes 视图，兼容按 content 读取的调用方
        self.content = text.encode("utf-8")


class Response(object):
    """``Response`` 的替身（状态行 + 实体）。"""

    def __init__(self, status_line: StatusLine,
                 entity: Optional[_HttpEntity] = None) -> None:
        self._status_line = status_line
        self._entity = entity

    def getStatusLine(self) -> StatusLine:
        """对应 ``getStatusLine()``。"""
        return self._status_line

    def getEntity(self) -> Optional[_HttpEntity]:
        """对应 ``getEntity()``。"""
        return self._entity

    def close(self) -> None:
        """对应 ``close()``：替身无连接资源，空实现。"""
        return None

    def __repr__(self) -> str:
        return "Response(status=%d)" % self._status_line.getStatusCode()


# 【Java→Python】下划线开头的 `_HttpEntity` 是模块内部实现；对外暴露
# `HttpEntity` 名称（与 Java 的 `org.apache.http.HttpEntity` 呼应），
# 使 ``from ...Response import HttpEntity`` 这种写法更自然。
HttpEntity = _HttpEntity
