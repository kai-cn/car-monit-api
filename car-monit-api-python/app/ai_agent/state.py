# -*- coding: utf-8 -*-
"""LangGraph 状态定义（审阅规格 SPEC §2.4）.

【Java 开发者导读】
TypedDict 是类型化的 Map/WorkflowContext：运行时就是 dict，但 mypy/IDE 知道字段类型。
``Annotated[list[AnyMessage], add_messages]`` 告诉 LangGraph：新消息是**追加**到列表，
而不是覆盖整个 messages 字段（等价 Java ``List.addAll`` 而非 ``set``）。
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


#: 默认工具轮次上限（唯一来源仍是 settings.max_rounds / AI_AGENT_MAX_ROUNDS）
MAX_TOOL_ROUNDS = 8


class AgentState(TypedDict):
    """Agent 执行上下文（Node 之间传递的状态）。"""

    messages: Annotated[list[AnyMessage], add_messages]
    trace_id: str
    tool_calls_count: int
    error: str | None
