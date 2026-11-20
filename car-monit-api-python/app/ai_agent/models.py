# -*- coding: utf-8 -*-
"""AI Agent DTO（Pydantic v2）.

【Java→Python 差异】
Java: ``class AgentQueryRequest { @NotBlank String question; ... }`` + Lombok
Python: ``class AgentQueryRequest(BaseModel)`` —— Field 约束即 Bean Validation，
``model_dump()`` 等价 Jackson 序列化。Pydantic v2 的 ``Literal`` 等价 Java enum。

所有响应字段在两个框架分支（LangGraph / LangChain）完全一致，便于 A/B 对比。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TrafficTable = Literal["snapshot", "fee", "trail"]


class AgentQueryRequest(BaseModel):
    """自然语言问数请求。

    * ``question``：用户问题，1–2000 字符（防超长 prompt 注入）；
    * ``session_id``：会话 ID，对应 LangGraph ``thread_id`` / LangChain ``thread_id``；
    * ``tables``：允许 Agent 访问的表白名单（默认三张），工具层据此过滤。
    """

    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    tables: list[TrafficTable] = Field(default_factory=lambda: ["snapshot", "fee", "trail"])


class ToolCallRecord(BaseModel):
    """一次工具调用的可观测记录（**不含**完整返回数据，防止 PII 泄露）。

    Java 对照：一次 ``@Tool`` 调用审计日志行（操作名 + 参数摘要 + 成功标志）。
    """

    name: str
    args: dict[str, Any]
    ok: bool
    result_preview: str = Field(default="", max_length=300)


class AgentQueryResponse(BaseModel):
    """统一响应体：两个分支对外完全一致。"""

    answer: str
    tool_calls: list[ToolCallRecord]
    trace_id: str
    rounds: int


class AgentAnswer(BaseModel):
    """LLM 结构化输出（中间 DTO，不直接出现在 HTTP 响应）。

    LangChain 分支把它作为 ``response_format``；LangGraph 分支在 call_model 节点里
    用同样结构约束模型输出。``confidence`` 仅记 trace 日志（跨分支裁定 L8/R8）。
    """

    answer: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
