# -*- coding: utf-8 -*-
"""LangGraph v1 显式状态图（本分支核心）.

【Java 开发者导读 —— StateGraph 是什么？】
把它想成 Java 工作流引擎（Activiti/Flowable）的类型安全版本：
* ``AgentState`` = 工作流上下文对象（WorkflowContext），每次节点执行后合并更新；
* ``add_node`` = 注册一个处理步骤（Java: ``TaskDelegate``）；
* ``add_conditional_edges`` = 网关条件分支（Java: ``ExclusiveGateway``）；
* ``ToolNode`` = 官方提供的"执行工具并把结果写回消息列表"节点；
* ``checkpointer`` = 流程实例状态持久化（Java: 数据库流程变量表）。

图结构（与 SPEC §2.4 一致）::

    START → agent ─┬─ tool_calls & rounds<max → tools → agent
                   └─ otherwise               → END

【官方写法】
使用 ``langgraph.graph.StateGraph`` / ``langgraph.prebuilt.ToolNode`` /
``langgraph.checkpoint.memory.InMemorySaver`` 原生命名，不封装/改写框架 API。
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.ai_agent.fake_model import FakeAgentModel
from app.ai_agent.settings import get_agent_settings
from app.ai_agent.state import AgentState
from app.ai_agent.tools import SYSTEM_PROMPT, TOOLS

log = logging.getLogger(__name__)


# 进程级单例（审阅 B3：每次请求新建 saver 会让 thread_id 失效）
_CHECKPOINTER: InMemorySaver | None = None
_GRAPH: Any = None


def _build_model() -> Any:
    """根据配置构造 LLM（Java 对照：``@Bean ChatModel``）。

    ``api_key`` 为空 → FakeAgentModel（CI/本地无密钥场景）；
    非空 → ChatOpenAI（OpenAI 兼容接口，可指向豆包/通义/DeepSeek 的 base_url）。
    """
    settings = get_agent_settings()
    if not settings.api_key:
        return FakeAgentModel(responses=["I have no tools to call."])
    model = settings.model.split(":", 1)[-1] if ":" in settings.model else settings.model
    return ChatOpenAI(
        model=model, api_key=settings.api_key, base_url=settings.base_url or None,
        timeout=settings.timeout_sec, max_retries=2,
    )


def call_model(state: AgentState) -> dict[str, Any]:
    """节点：调用绑定了工具的 LLM，输出 AIMessage（可能含 tool_calls）。

    Java 对照：``@Service`` 里的 ``chatModel.call(prompt)``，
    异常写 state.error 而不是抛出（等价把异常转成 Result 对象）。
    """
    try:
        model = _build_model().bind_tools(list(TOOLS))
        settings = get_agent_settings()
        rounds = int(state.get("tool_calls_count") or 0)
        if rounds >= settings.max_rounds:
            return {"error": "tool_rounds_exceeded"}
        response = model.invoke(list(state.get("messages") or []))
        return {"messages": [response], "tool_calls_count": rounds + 1}
    except Exception as exc:  # noqa: BLE001
        log.exception("[AI Agent] call_model 失败 trace=%s", state.get("trace_id"))
        return {"error": str(exc)[:300]}


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """条件边：有 tool_calls → tools 节点；否则结束（审阅 B5 循环保护）。"""
    if state.get("error"):
        return "__end__"
    messages = state.get("messages") or []
    if not messages:
        return "__end__"
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None) or []
    settings = get_agent_settings()
    if tool_calls and int(state.get("tool_calls_count") or 0) <= settings.max_rounds:
        return "tools"
    return "__end__"


def build_graph(checkpointer: Any = None) -> Any:
    """构造并编译 StateGraph（官方 API，不改写框架写法）。"""
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(list(TOOLS)))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue,
                                   {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer)


def get_graph() -> Any:
    """进程级单例（审阅 B3）；生产可把 InMemorySaver 换成 PostgresSaver。"""
    global _CHECKPOINTER, _GRAPH
    if _GRAPH is None:
        _CHECKPOINTER = InMemorySaver()
        _GRAPH = build_graph(checkpointer=_CHECKPOINTER)
    return _GRAPH
