# -*- coding: utf-8 -*-
"""内部端点守卫（V3 新增）。

Java 事实源：``InternalEndpointGuardConfig.java``（``pro-business-api`` 的 ``config`` 包）。

【Java→Python 差异 / why this is a decorator, not a Servlet Filter】
* Java 用 ``OncePerRequestFilter`` + ``FilterRegistrationBean`` 按 URL 模式注册；
  Python/FastAPI 没有 Filter 链，这里用 ``@app.middleware("http")`` 函数式中间件，
  在 ``app/main.py`` 注册。执行时机等价：在路由分发之前。
* Java 的常量时间比较用 ``MessageDigest.isEqual(byte[], byte[])``；Python 用
  ``hmac.compare_digest``（同样是常量时间，防止时序侧信道）。
* Java 未配置令牌时 ``isAllowedRemoteAddr`` 只放行 127.0.0.1 / 0:0:0:0:0:0:0:1；
  Python 用 ``request.client.host``，并额外把 ``::1`` 纳入（Java InetAddress 的等价表示）。
* 环境变量名与 Java 配置属性一一对应：``traffic.security.internal-token`` →
  ``TRAFFIC_SECURITY_INTERNAL_TOKEN``。
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Awaitable, Callable

from fastapi import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger(__name__)

#: Java: ``InternalEndpointGuardConfig.PROTECTED_PREFIXES``
PROTECTED_PREFIXES = ("/api/v3/", "/api/v1/large/export/")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "0:0:0:0:0:0:0:1"})
#: ASGI ``TestClient`` 的合成 host（进程内直连，无真实网络跳）。
# 【Java→Python 差异】Java 的 MockMvc/Servlet 测试同样不经过真实 socket，
# ``isAllowedRemoteAddr`` 看到的是 127.0.0.1；Starlette TestClient 则填 "testclient"。
# 若不纳入，CI 的 smoke_all_routes 会把本该等价的调用误判成 403（云 runner 实测发现）。
IN_PROCESS_HOSTS = frozenset({"testclient"})


def _configured_token() -> str:
    """Java: ``@Value("${traffic.security.internal-token:}")``。"""
    return (os.getenv("TRAFFIC_SECURITY_INTERNAL_TOKEN")
            or os.getenv("TRAFFIC__SECURITY__INTERNAL_TOKEN") or "").strip()


def _is_protected(path: str) -> bool:
    # Java 用 AntPathMatcher ``/api/v3/**``；前缀匹配对本项目所有端点等价。
    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)


async def internal_endpoint_guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """拒绝未授权的内部端点调用；放行时把请求交给下游中间件/路由。"""
    if not _is_protected(request.url.path):
        return await call_next(request)

    token = _configured_token()
    if token:
        supplied = request.headers.get("X-Internal-Token", "")
        if not hmac.compare_digest(supplied, token):
            log.warning("[内部守卫] 403 path=%s host=%s", request.url.path,
                        request.client.host if request.client else "?")
            return JSONResponse(status_code=403, content={"code": 403, "msg": "forbidden"})
    else:
        host = request.client.host if request.client else ""
        if host not in LOOPBACK_HOSTS and host not in IN_PROCESS_HOSTS:
            log.warning("[内部守卫] 未配置 token 且非回环来源 -> 403 path=%s host=%s",
                        request.url.path, host)
            return JSONResponse(status_code=403, content={"code": 403, "msg": "forbidden"})
    return await call_next(request)
