# -*- coding: utf-8 -*-
"""Spring Boot error body (``BasicErrorController`` equivalent).

Migrated from: (no Java source -- Spring Boot's default error handling)

The Java project has **no** ``@ControllerAdvice``, so every uncaught exception
reaches Spring Boot's ``BasicErrorController`` and produces::

    {
      "timestamp": "2026-10-22T02:11:33.123+00:00",
      "status": 500,
      "error": "Internal Server Error",
      "path": "/base/gantry/list"
    }

``server.error.include-message`` defaults to ``never``, therefore the
``message`` key is absent -- that is reproduced here on purpose.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.web.responses import JacksonResponse

__all__ = ["error_body", "error_response", "HTTP_REASONS"]

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
    # server.error.include-message=never -> the key only appears for
    # explicitly enabled configurations (never in this project).
    if message:
        body["message"] = message
    body["path"] = path
    return body


def error_response(status: int, path: str, message: Optional[str] = None) -> JacksonResponse:
    return JacksonResponse(status_code=status, content=error_body(status, path, message))
