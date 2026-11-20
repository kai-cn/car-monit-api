# -*- coding: utf-8 -*-
"""Agent 端点鉴权（审阅 ADDENDUM R1，fail-closed）.

【Java 开发者导读】
本 Python 项目**没有** Spring Security / interceptor chain，不能假设 Bearer token 自动注入。
所以 Agent 端点用显式 API Key 守卫，等价 Java 的：
    @PreAuthorize("@agentGuard.hasAccess(#key)")

安全语义（fail-closed）：
* ``AI_AGENT_ACCESS_TOKEN`` 未配置 → 503（服务不可用），**不静默放行**；
* 令牌不匹配 → 403（常量时间比较 ``hmac.compare_digest``，防时序侧信道）；
* 与 LLM 密钥 ``AI_AGENT_API_KEY`` 完全分离。

响应体由 app/main.py 的全局异常处理器转成 Spring 错误体（``error_response``），
不在本模块手写 ``{"detail": ...}``（审阅 B2）。
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import Header
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


def verify_agent_key(x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")) -> None:
    """FastAPI 依赖：校验 Agent 访问令牌。

    Java 对照：``HandlerInterceptor.preHandle`` 返回 false → 403，
    这里通过抛 ``StarletteHTTPException`` 交给全局 handler 统一转 Spring 错误体。
    """
    expected = (os.getenv("AI_AGENT_ACCESS_TOKEN") or "").strip()
    if not expected:
        # 服务未配置 = 禁止所有调用（不因为"默认开放"导致数据泄露）
        log.warning("[AI Agent] AI_AGENT_ACCESS_TOKEN 未配置，拒绝请求（fail-closed）")
        raise StarletteHTTPException(status_code=503, detail="agent access token not configured")
    supplied = (x_agent_key or "").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        log.warning("[AI Agent] 访问令牌校验失败")
        raise StarletteHTTPException(status_code=403, detail="forbidden")
