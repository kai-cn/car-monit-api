# -*- coding: utf-8 -*-
"""LangChain create_agent 调用链测试."""
from __future__ import annotations

from langchain_core.messages import AIMessage

from app.ai_agent.agent import build_agent, get_agent
from app.ai_agent.middleware import TraceMiddleware


def test_agent_is_singleton():
    assert get_agent() is get_agent()


def test_trace_middleware_reset_and_after_agent():
    mw = TraceMiddleware(max_rounds=2)
    mw.reset()
    assert mw.tool_records == []
    result = mw.after_agent(state={}, runtime=None)
    assert result["rounds"] == 0
    assert result["tool_records"] == []


def test_agent_build_with_fake_model():
    """无 key 时 create_agent 用 FakeAgentModel，不依赖外部 API。"""
    import os

    old = os.environ.pop("AI_AGENT_API_KEY", None)
    try:
        agent = build_agent()
        assert agent is not None
    finally:
        if old is not None:
            os.environ["AI_AGENT_API_KEY"] = old
