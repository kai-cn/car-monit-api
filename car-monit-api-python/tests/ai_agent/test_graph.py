# -*- coding: utf-8 -*-
"""LangGraph 图流转测试：验证官方 StateGraph + ToolNode 路径真正执行."""
from __future__ import annotations

from langchain_core.messages import AIMessage

from app.ai_agent.graph import build_graph, get_graph
from app.ai_agent.tools import TOOLS


def _tool_call_msg(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1", "type": "tool_call"}])


def test_graph_uses_tool_node():
    """注入 tool_calls 后，ToolNode 必须执行工具并把 ToolMessage 追加到 state。"""
    from app.ai_agent import graph as graph_module

    original = graph_module._build_model
    graph_module._build_model = lambda: type(
        "M", (), {"bind_tools": lambda self, tools: self,
                  "invoke": lambda self, messages: _tool_call_msg(
                      "query_snapshot", {"start_time": "2025-06-01", "end_time": "2025-06-02"})}
    )()
    try:
        g = build_graph()
        state = g.invoke({"messages": [("user", "查询快照")], "trace_id": "t1",
                          "tool_calls_count": 0, "error": None})
        assert state["tool_calls_count"] >= 1
        assert any(getattr(m, "type", "") == "tool" for m in state["messages"])
    finally:
        graph_module._build_model = original


def test_graph_singleton_survives_calls():
    assert get_graph() is get_graph()


def test_max_rounds_guard():
    """超过 max_rounds 后 call_model 写 error，不再调用 LLM。"""
    from app.ai_agent import graph as graph_module

    state = {"messages": [], "trace_id": "t", "tool_calls_count": 999, "error": None}
    result = graph_module.call_model(state)
    assert result.get("error") == "tool_rounds_exceeded"
