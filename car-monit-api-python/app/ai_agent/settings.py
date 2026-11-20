# -*- coding: utf-8 -*-
"""AI Agent 配置（两个框架分支共用语义）.

【Java→Python 差异】
Java: ``@ConfigurationProperties(prefix="ai.agent")`` + ``@Value("${AI_AGENT_MODEL:...}")``
Python: ``os.getenv`` + ``dataclass(frozen=True)``。每次 ``get_agent_settings()`` 重新读 env，
便于测试用 ``monkeypatch.setenv`` 隔离（等价 Java ``@RefreshScope`` 的测试替身）。

安全关键点：
* ``access_token`` 是 **Agent HTTP 端点访问令牌**（fail-closed），空 = 拒绝所有请求；
* ``api_key`` 是 **LLM 供应商密钥**，空 = 使用 FakeAgentModel（仅测试）。
两个密钥职责不同，**绝不能混用**。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    """Agent 运行配置（不可变对象，等价 Java 的 immutable config bean）。"""

    model: str
    api_key: str
    base_url: str
    access_token: str
    max_rounds: int
    timeout_sec: float


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (ValueError, TypeError):
        return default


def _read_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)).strip())
    except (ValueError, TypeError):
        return default


def get_agent_settings() -> AgentSettings:
    """从环境变量构造配置；不缓存，保证测试可 monkeypatch。"""
    rounds = max(1, _read_int("AI_AGENT_MAX_ROUNDS", 8))
    return AgentSettings(
        model=(os.getenv("AI_AGENT_MODEL", "openai:gpt-4o-mini").strip() or "openai:gpt-4o-mini"),
        api_key=(os.getenv("AI_AGENT_API_KEY") or "").strip(),
        base_url=(os.getenv("AI_AGENT_BASE_URL") or "").strip(),
        access_token=(os.getenv("AI_AGENT_ACCESS_TOKEN") or "").strip(),
        max_rounds=rounds,
        timeout_sec=max(1.0, _read_float("AI_AGENT_TIMEOUT_SEC", 30.0)),
    )
