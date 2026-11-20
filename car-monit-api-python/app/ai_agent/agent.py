# -*- coding: utf-8 -*-
"""LangChain v1 create_agent 工厂（本分支核心）.

【Java 开发者导读】
LangChain v1 的心智模型::

    Agent = Model + Harness
    Harness = system_prompt + tools + middleware

``create_agent`` 是官方工厂方法（等价 Spring 的 ``@Bean`` 工厂）：
底层已用 LangGraph 构建好工具调用循环，本分支**不重写图**，
只通过 ``state_schema`` / ``middleware`` 扩展可观测字段（审阅 L1）。

与 LangGraph 分支的对照：
* LangGraph 分支显式写 ``StateGraph`` / ``ToolNode`` / 条件边（可控工作流）；
* LangChain 分支声明式装配 model/tools/middleware（快速生产化）。

两个分支对外 HTTP 契约一致（``AgentQueryResponse``）。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from typing_extensions import TypedDict

from app.ai_agent.fake_model import FakeAgentModel
from app.ai_agent.middleware import TraceMiddleware
from app.ai_agent.models import AgentAnswer
from app.ai_agent.settings import get_agent_settings
from app.ai_agent.tools import SYSTEM_PROMPT, TOOLS

log = logging.getLogger(__name__)


class AgentRuntimeState(AgentState):
    """扩展 LangChain 内置 AgentState（审阅 L1：让 invoke 结果可见自定义字段）.

    Java 对照：继承框架基类 ``AbstractAgentContext`` 并追加 trace_id/rounds 字段。
    """

    trace_id: str
    rounds: int
    tool_records: list[dict[str, Any]]


# 进程级单例（审阅 B3/L3）
_AGENT: Any = None
_CHECKPOINTER: Any = None
_MIDDLEWARE: TraceMiddleware | None = None


def _build_model() -> Any:
    """api_key 为空 → FakeAgentModel（CI 无 key）；非空 → ChatOpenAI（OpenAI 兼容）。"""
    settings = get_agent_settings()
    if not settings.api_key:
        return FakeAgentModel(responses=["I have no tools to call."])
    model = settings.model.split(":", 1)[-1] if ":" in settings.model else settings.model
    return ChatOpenAI(
        model=model, api_key=settings.api_key, base_url=settings.base_url or None,
        timeout=settings.timeout_sec, max_retries=2,
    )


def build_agent(checkpointer: Any = None) -> Any:
    """按官方 create_agent 契约构造 agent（不使用已弃用的 create_react_agent）。"""
    settings = get_agent_settings()
    middleware = TraceMiddleware(max_rounds=settings.max_rounds)
    return create_agent(
        model=_build_model(),
        tools=list(TOOLS),
        system_prompt=SYSTEM_PROMPT,
        response_format=AgentAnswer,
        state_schema=AgentRuntimeState,
        middleware=[middleware],
        checkpointer=checkpointer or InMemorySaver(),
    )


def get_agent() -> Any:
    """进程级单例 agent（审阅 L3，与 LangGraph 分支 get_graph 对等）。"""
    global _AGENT, _CHECKPOINTER, _MIDDLEWARE
    if _AGENT is None:
        settings = get_agent_settings()
        _CHECKPOINTER = InMemorySaver()
        _MIDDLEWARE = TraceMiddleware(max_rounds=settings.max_rounds)
        _AGENT = create_agent(
            model=_build_model(), tools=list(TOOLS), system_prompt=SYSTEM_PROMPT,
            response_format=AgentAnswer, state_schema=AgentRuntimeState,
            middleware=[_MIDDLEWARE], checkpointer=_CHECKPOINTER,
        )
    return _AGENT


def get_middleware() -> TraceMiddleware | None:
    """供 API 层 reset buffer / 读取 tool_records（单例 agent 的配套访问器）。"""
    return _MIDDLEWARE
