# -*- coding: utf-8 -*-
"""Spring Boot error body (``BasicErrorController`` equivalent).

Migrated from: (no Java source -- Spring Boot's default error handling)

The Java project has **no** ``@ControllerAdvice``, so every uncaught exception
reaches Spring Boot's ``BasicErrorController`` and produces::

    {
      "timestamp": "2026-10-22T02:11:33.123+00:00",
      "status": 500,
      "error": "Internal Server Error",
      "message": "",
      "path": "/base/gantry/list"
    }

【实测修正】早先按 ``server.error.include-message=never`` 推断“无 message 键”，
与真实 Java 进程的输出不符：实测 404/500 响应体**始终带** ``"message": ""``
（Tomcat 会把 ``javax.servlet.error.message`` 置为空串，Spring 因此写入了空消息）。
现改为无条件输出该键，保证与 Java 逐字节一致。
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.web.responses import JacksonResponse

__all__ = ["error_body", "error_response", "HTTP_REASONS",
           "basic_error_endpoint_body", "basic_error_endpoint_response"]

HTTP_REASONS = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    408: "Request Timeout",
    409: "Conflict",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

_UTC = ZoneInfo("UTC")


def error_body(status: int, path: str, message: Optional[str] = None) -> dict[str, Any]:
    """Build the ``BasicErrorAttributes`` map in its declaration order."""
    now = _dt.datetime.now(tz=_UTC)
    body: dict[str, Any] = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}+00:00",
        "status": status,
        "error": HTTP_REASONS.get(status, "Error"),
    }
    # 【实测修正】真实 Java 进程的 404/500 响应体里 message 键始终存在，
    # 取值为空串（不是 null，也不是缺键）—— 逐字节对齐时少这 13 个字节就不一致。
    body["message"] = "" if message is None else message
    body["path"] = path
    return body


def error_response(status: int, path: str, message: Optional[str] = None) -> JacksonResponse:
    return JacksonResponse(status_code=status, content=error_body(status, path, message))


# --------------------------------------------------------------------------- /error
#: Spring ``DefaultErrorAttributes.addStatus`` 在拿不到 ``ERROR_STATUS_CODE``
#: 属性时写入的占位值（源码里就是字面量 999，配套 error="None"）。
SPRING_ERROR_STATUS_NONE = 999


def basic_error_endpoint_body() -> dict[str, Any]:
    """直接访问 ``/error`` 时 ``BasicErrorController`` 返回的响应体。

    【实测】直接 GET/POST/... ``/error`` 时，Java 进程固定回：

        HTTP 500
        {"timestamp": "2026-10-31T05:10:16.194+00:00",
         "status": 999, "error": "None", "message": ""}

    三处与普通 404/500 不同，必须逐字对齐：

    1) ``status`` 是 999 而不是 HTTP 状态码：请求没有走错误派发，
       ``ERROR_STATUS_CODE`` 属性为 null，Spring 写入了占位值 999 + ``error="None"``；
    2) HTTP 状态码仍是 500（``BasicErrorController`` 兜底）；
    3) **没有 ``path`` 键**：``ERROR_REQUEST_URI`` 同样为 null。

    ``message`` 键依旧存在且为空串，与其它错误响应保持一致。
    """
    now = _dt.datetime.now(tz=_UTC)
    return {
        # 键顺序与 Java LinkedHashMap 的插入顺序一致
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}+00:00",
        "status": SPRING_ERROR_STATUS_NONE,
        "error": "None",
        "message": "",
    }


def basic_error_endpoint_response() -> JacksonResponse:
    """``GET/POST/... /error``：Java 侧固定回 HTTP 500。"""
    return JacksonResponse(status_code=500, content=basic_error_endpoint_body())
