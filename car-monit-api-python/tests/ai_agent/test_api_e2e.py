# -*- coding: utf-8 -*-
"""AI Agent HTTP 端到端测试（云 runner 无需真实 LLM key）."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AI_AGENT_API_KEY", "")  # FakeModel
    monkeypatch.setenv("AI_AGENT_ACCESS_TOKEN", "test-access-token")


def test_query_requires_access_token():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ai/agent/query", json={"question": "hello"})
    assert r.status_code == 403


def test_query_returns_contract():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ai/agent/query", headers={"X-Agent-Key": "test-access-token"},
                    json={"question": "你好", "session_id": "s1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"answer", "tool_calls", "trace_id", "rounds"}
    assert isinstance(body["tool_calls"], list)


def test_query_validation_returns_400():
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/ai/agent/query", headers={"X-Agent-Key": "test-access-token"},
                    json={"question": ""})
    assert r.status_code == 400
