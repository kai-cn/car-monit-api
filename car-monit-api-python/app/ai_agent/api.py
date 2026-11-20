# -*- coding: utf-8 -*-
"""AI Agent HTTP 端点（LangChain 分支，对外契约与 LangGraph 分支一致）.

【Java 开发者导读】
等价 ``@RestController`` + ``@PreAuthorize`` + ``@PostMapping``。
LangChain 的 agent.invoke() 返回一个 dict（Graph state），内含：
* ``structured_response``: AgentAnswer（response_format 约束的 Pydantic 对象）
* ``rounds`` / ``tool_records``: middleware.after_agent 写回的字段（审阅 L1）

审阅 B2：错误走全局 handler（Spring 错误体），参数错 400、令牌错 403、LLM 错 503。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai_agent.agent import get_agent, get_middleware
from app.ai_agent.auth import verify_agent_key
from app.ai_agent.models import AgentQueryRequest, AgentQueryResponse, ToolCallRecord
from app.ai_agent.settings import get_agent_settings
from app.ai_agent.tools import TOOLS, confirm_export

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/agent", tags=["ai-agent"])


class ConfirmRequest(BaseModel):
    confirm_token: str = Field(min_length=1, max_length=128)


def _extract_result(result: dict[str, Any]) -> AgentQueryResponse:
    """从 agent.invoke() 结果构造统一响应（与 LangGraph 分支字段一致）。"""
    structured = result.get("structured_response")
    answer = getattr(structured, "answer", "") if structured is not None else ""
    if not answer:
        for msg in reversed(result.get("messages") or []):
            content = getattr(msg, "content", "")
            if content:
                answer = str(content)
                break

    records: list[ToolCallRecord] = []
    for item in (result.get("tool_records") or []):
        preview = str(item.get("result_preview", ""))[:300]
        records.append(ToolCallRecord(
            name=str(item.get("name", "tool")),
            args=item.get("args") or {},
            ok=bool(item.get("ok", False)),
            result_preview=preview,
        ))
    return AgentQueryResponse(
        answer=answer or "(no answer)", tool_calls=records,
        trace_id=str(result.get("trace_id") or ""),
        rounds=int(result.get("rounds") or 0),
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
    settings = get_agent_settings()
    return {"status": "UP", "model": settings.model,
            "llm_mode": "fake" if not settings.api_key else "live"}


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(body: AgentQueryRequest, _: None = Depends(verify_agent_key)) -> AgentQueryResponse:
    """POST /ai/agent/query —— 自然语言问数（与 LangGraph 分支同契约）."""
    settings = get_agent_settings()
    trace_id = uuid.uuid4().hex
    thread_id = body.session_id or trace_id
    middleware = get_middleware()
    if middleware is not None:
        middleware.reset()  # 单例 agent：防止上一次请求的审计记录串到本次
    try:
        result = get_agent().invoke(
            {"messages": [{"role": "user", "content": body.question}],
             "trace_id": trace_id, "rounds": 0, "tool_records": []},
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": settings.max_rounds * 2 + 2,
            },
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[AI Agent] invoke 失败 trace=%s", trace_id)
        raise StarletteHTTPException(status_code=503, detail="ai agent unavailable") from exc
    response = _extract_result(result)
    response.trace_id = trace_id  # API 层生成，覆盖 middleware 可能未写入的情况（审阅 R7）
    return response


@router.post("/confirm")
def confirm_agent_export(body: ConfirmRequest, _: None = Depends(verify_agent_key)) -> dict[str, Any]:
    """POST /ai/agent/confirm —— 写操作二次确认（审阅 R4/L5）。"""
    return confirm_export(body.confirm_token)
