# -*- coding: utf-8 -*-
"""AI Agent HTTP 端点（LangGraph 分支）.

【Java 开发者导读】
等价 ``@RestController``：
* ``APIRouter(prefix="/ai/agent")`` ≈ ``@RequestMapping("/ai/agent")``
* ``Depends(verify_agent_key)`` ≈ ``@PreAuthorize("@agentGuard.hasAccess(...)")``
* 抛 ``StarletteHTTPException`` → app/main.py 全局 handler → Spring 错误体

审阅 B2：错误契约与项目对齐——参数错 400（全局 handler）、令牌错 403、
LLM/state.error 503（HTTP + Spring 错误体），正常 200 + AgentQueryResponse。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai_agent.auth import verify_agent_key
from app.ai_agent.graph import get_graph
from app.ai_agent.models import AgentQueryRequest, AgentQueryResponse, ToolCallRecord
from app.ai_agent.settings import get_agent_settings
from app.ai_agent.tools import TOOLS, confirm_export

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/agent", tags=["ai-agent"])


class ConfirmRequest(BaseModel):
    """导出二次确认请求（审阅 R4：写操作 must confirm）。"""

    confirm_token: str = Field(min_length=1, max_length=128)


def _extract_result(state: dict[str, Any]) -> AgentQueryResponse:
    """从图最终 state 构造统一响应（不含完整工具返回，防 PII 泄露）。"""
    messages = state.get("messages") or []
    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "content", ""):
            answer = str(msg.content)
            break
    records: list[ToolCallRecord] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        preview = str(getattr(msg, "content", ""))[:300]
        try:
            import json

            parsed = json.loads(preview)
            keys = [k for k in ("ok", "count", "taskId", "status", "error") if k in parsed]
            preview = ", ".join(f"{k}={parsed[k]}" for k in keys)[:300]
        except Exception:  # noqa: BLE001
            pass
        records.append(ToolCallRecord(
            name=getattr(msg, "name", "tool") or "tool",
            args={}, ok='"ok": false' not in preview, result_preview=preview,
        ))
    return AgentQueryResponse(
        answer=answer or "(no answer)", tool_calls=records,
        trace_id=str(state.get("trace_id") or ""),
        rounds=int(state.get("tool_calls_count") or 0),
    )


@router.get("/tools")
def list_tools(_: None = Depends(verify_agent_key)) -> dict[str, Any]:
    """工具目录（Java 参考分支 G2：可枚举、可校验、可授权）.

    只返回工具名/描述/风险级别，不暴露实现细节。
    """
    risks = {"submit_export": "write-confirm", "export_status": "read",
             "query_snapshot": "read-masked", "group_stats": "read", "es_status": "read"}
    return {
        "tools": [{"name": t.name, "description": t.description,
                   "risk": risks.get(t.name, "read")} for t in TOOLS]
    }


@router.get("/health")
def agent_health(_: None = Depends(verify_agent_key)) -> dict[str, Any]:
    """Agent 健康探针：不需要真实 LLM key（无 key 时 FakeModel 可用）。"""
    from app.ai_agent.settings import get_agent_settings

    settings = get_agent_settings()
    return {"status": "UP", "model": settings.model,
            "llm_mode": "fake" if not settings.api_key else "live"}


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(body: AgentQueryRequest, _: None = Depends(verify_agent_key)) -> AgentQueryResponse:
    """自然语言问数入口（POST /ai/agent/query）."""
    settings = get_agent_settings()
    trace_id = uuid.uuid4().hex
    thread_id = body.session_id or trace_id
    try:
        state = get_graph().invoke(
            {
                "messages": [HumanMessage(content=body.question)],
                "trace_id": trace_id,
                "tool_calls_count": 0,
                "error": None,
            },
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": settings.max_rounds * 2 + 2,
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[AI Agent] graph 执行失败 trace=%s", trace_id)
        raise StarletteHTTPException(status_code=503, detail="ai agent unavailable") from exc
    if state.get("error"):
        log.warning("[AI Agent] state.error trace=%s error=%s", trace_id, state["error"])
        raise StarletteHTTPException(status_code=503, detail="ai agent unavailable")
    return _extract_result(state)


@router.post("/confirm")
def confirm_agent_export(body: ConfirmRequest, _: None = Depends(verify_agent_key)) -> dict[str, Any]:
    """导出二次确认：消费一次性 confirm_token 真正提交导出任务。"""
    return confirm_export(body.confirm_token)
