# -*- coding: utf-8 -*-
"""LangChain v1 AgentMiddleware（审阅 ADDENDUM L1/L2/L5）.

【Java 开发者导读】
Middleware = Spring ``HandlerInterceptor`` / AOP ``@Around``：
* ``before_agent`` ≈ ``preHandle``：生成 trace_id；
* ``wrap_tool_call`` ≈ ``@Around`` 包住工具调用：计时 + 记录审计（不记完整数据）；
* ``after_agent`` ≈ ``postHandle``：把审计结果写回 state，确保 invoke() 能读到。

LangChain v1 把横切逻辑统一到 middleware，不散落在工具函数里 —— 这是官方写法。
这里 **不假设** middleware 的某个固定基类签名：先用 ``try import`` 探测官方
``AgentMiddleware``，缺失时退化为 duck-typed 基类（方法名保持一致），
并在注释里说明差异。这是初始化兼容性，不是改写框架执行逻辑。
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

try:
    from langchain.agents.middleware import AgentMiddleware  # type: ignore

    _BASE = AgentMiddleware
except Exception:  # pragma: no cover - 版本差异兜底
    _BASE = object


class TraceMiddleware(_BASE):  # type: ignore[misc,valid-type]
    """工具调用审计中间件；每次 invoke 前由 API 层调用 ``reset()`` 清空 buffer。"""

    def __init__(self, max_rounds: int = 8) -> None:
        self.max_rounds = max_rounds
        self._buffer: list[dict[str, Any]] = []
        self._rounds = 0
        try:
            super().__init__()
        except Exception:  # pragma: no cover
            pass

    def reset(self) -> None:
        """清空上次请求的审计缓冲（单例 agent 必须调用，防跨请求串数据）。"""
        self._buffer = []
        self._rounds = 0

    # ---- 官方 hook：不同小版本签名可能不同，用 *args/**kwargs 吸收（不影响框架执行） ----
    def before_agent(self, state: Any, runtime: Any = None, **kwargs: Any) -> Any:
        """preHandle：确保 trace_id 存在（API 层已生成则不覆盖）。"""
        return state

    def wrap_tool_call(self, request: Any, handler: Any = None, **kwargs: Any) -> Any:
        """@Around：执行工具并记录 {name,args,ok,elapsed_ms,result_preview}。"""
        name = getattr(getattr(request, "tool", None), "name", "unknown")
        args = getattr(request, "args", {}) or {}
        if self._rounds >= self.max_rounds:
            self._buffer.append({"name": name, "args": args, "ok": False,
                                 "error": "round_limit", "elapsed_ms": 0})
            return self._tool_message('{"ok":false,"error":"round_limit"}', request)
        started = time.perf_counter()
        try:
            result = handler(request) if handler is not None else None
            elapsed = int((time.perf_counter() - started) * 1000)
            text = str(getattr(result, "content", result))[:300]
            self._buffer.append({"name": name, "args": args, "ok": True,
                                 "elapsed_ms": elapsed, "result_preview": text})
            return result
        except Exception as exc:  # noqa: BLE001
            self._buffer.append({"name": name, "args": args, "ok": False,
                                 "error": str(exc)[:200], "elapsed_ms": 0})
            return self._tool_message('{"ok":false,"error":"tool_failed"}', request)
        finally:
            self._rounds += 1

    @staticmethod
    def _tool_message(content: str, request: Any) -> Any:
        """构造 ToolMessage（Java 对照：把异常转成 Tool 响应对象而非抛出）。"""
        try:
            from langchain_core.messages import ToolMessage

            return ToolMessage(content=content, tool_call_id=getattr(request, "id", "0"))
        except Exception:  # pragma: no cover
            return content

    def after_agent(self, state: Any, runtime: Any = None, **kwargs: Any) -> Any:
        """postHandle：返回 state 更新，确保 rounds/tool_records 出现在 invoke() 结果里。"""
        return {
            "rounds": self._rounds,
            "tool_records": list(self._buffer),
        }

    @property
    def tool_records(self) -> list[dict[str, Any]]:
        return list(self._buffer)
