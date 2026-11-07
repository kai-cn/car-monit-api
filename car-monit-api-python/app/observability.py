# -*- coding: utf-8 -*-
"""P1-3 可观测性基础：请求 ID、访问日志与 ``/metrics`` 指标（零新依赖）。

背景（docs/迁移审阅报告.md Q8）：此前无访问日志、无请求 ID、无指标，
故障只能翻应用日志；``uvicorn.access`` 被禁用后连行级访问记录都没有。

实现（刻意不引入 prometheus-client 等新库，符合"一比一迁移不加依赖"约束）：
* ``X-Request-ID``：沿用入站值或生成 uuid，回写响应头并注入 ``request.state``，
  业务日志可用 ``getattr(request.state, "request_id", None)`` 关联；
* 访问日志：每个请求一行（方法/路径/状态/耗时/rid），logger 名 ``app.access``；
* ``/metrics``：Prometheus 文本格式的基础计数器（requests/errors/耗时），
  状态码分布。真实 Prometheus 接入属 P2 可观测性完善范围。
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("app.access")

__all__ = ["REQUEST_ID_HEADER", "next_request_id", "record_request",
           "metrics_text", "request_context_middleware"]

#: 请求 ID 的 HTTP 头（入站沿用 / 出站回写）
REQUEST_ID_HEADER = "X-Request-ID"

_lock = threading.Lock()
_requests_total = 0
_errors_total = 0  # 5xx
_seconds_sum = 0.0
_seconds_max = 0.0
_status_counts: dict[int, int] = {}


def next_request_id() -> str:
    return uuid.uuid4().hex


def record_request(status: int, duration: float) -> None:
    """记录一次请求（线程安全）。"""
    global _requests_total, _errors_total, _seconds_sum, _seconds_max
    with _lock:
        _requests_total += 1
        if status >= 500:
            _errors_total += 1
        _seconds_sum += duration
        if duration > _seconds_max:
            _seconds_max = duration
        _status_counts[status] = _status_counts.get(status, 0) + 1


def metrics_text() -> str:
    """Prometheus 文本格式的指标快照。"""
    with _lock:
        lines = [
            "# TYPE app_requests_total counter",
            "app_requests_total %d" % _requests_total,
            "# TYPE app_errors_total counter",
            "app_errors_total %d" % _errors_total,
            "# TYPE app_request_seconds summary",
            "app_request_seconds_count %d" % _requests_total,
            "app_request_seconds_sum %.6f" % _seconds_sum,
            "# TYPE app_request_seconds_max gauge",
            "app_request_seconds_max %.6f" % _seconds_max,
        ]
        for status in sorted(_status_counts):
            lines.append("app_responses_total{status=\"%d\"} %d"
                         % (status, _status_counts[status]))
        return "\n".join(lines) + "\n"


async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """请求上下文中间件：请求 ID + 访问日志 + 指标采样。"""
    request_id = request.headers.get(REQUEST_ID_HEADER) or next_request_id()
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - started
        record_request(500, duration)
        log.error("%s %s -> 500 (%.1fms) rid=%s",
                  request.method, request.url.path, duration * 1000, request_id,
                  exc_info=True)
        raise
    duration = time.perf_counter() - started
    response.headers[REQUEST_ID_HEADER] = request_id
    record_request(response.status_code, duration)
    log.info("%s %s -> %s (%.1fms) rid=%s",
             request.method, request.url.path, response.status_code,
             duration * 1000, request_id)
    return response
