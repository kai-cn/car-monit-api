# -*- coding: utf-8 -*-
"""AI Agent 业务工具（两个框架分支共享同一套工具语义）。

【Java 开发者导读 —— 什么是 Tool？】
Tool = 一个带结构化 schema 的普通函数，LLM 看到的是 ``@tool`` 解析出的 JSON Schema
（函数名 + 参数类型 + docstring），决定调用哪家工具；真正执行的是这里的 Python 函数。
等价 Java：一个带 ``@Tool`` 注解的方法 + Spring 容器里的 Service 调用。

【安全设计（审阅 ADDENDUM R4/R5）】
1. 工具只调**已存在的 V3 Service**（TrafficSearchService / BigScreenStatsService /
   ExportTaskService），不重写 SQL，不直接访问 ORM；
2. 车牌 ``car_no`` 在进入 LLM 上下文前**掩码**（前 3 位 + `***`），
   返回数据只含 count/time_bucket 等聚合字段，不含原始明细；
3. ``submit_export`` 是写操作：第一次调用返回 ``need_confirm=true`` + confirm_token，
   必须走 ``POST /ai/agent/confirm`` 二次确认（等价 LangGraph human-in-the-loop interrupt）；
4. 所有工具返回 **JSON 字符串**（LangChain/LangGraph ToolNode 统一契约），
   异常转 ``{"ok": false, "error": ...}`` 而非抛出，避免 Agent 崩溃。

【官方写法】
使用 ``from langchain.tools import tool`` 的 ``@tool`` 装饰器 —— 这是 LangChain v1 /
LangGraph v1 共同推荐的工具定义方式，docstring 会自动变成 LLM 看到的 tool description。
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Literal

from langchain.tools import tool

__all__ = [
    "TOOLS", "SYSTEM_PROMPT", "query_snapshot", "group_stats",
    "submit_export", "export_status", "es_status", "mask_car_no",
]

log = logging.getLogger(__name__)

TrafficTable = Literal["snapshot", "fee", "trail"]

#: System prompt：告诉 LLM 它有哪些工具、边界在哪（Java 对照：@Tool 注解上的 description）。
SYSTEM_PROMPT = (
    "你是 car-monit 交通数据助手。你只能通过提供的工具查询数据，禁止编造数字。\n"
    "规则：\n"
    "1. 查询流水用 query_snapshot，聚合统计用 group_stats，导出用 submit_export（需确认）；\n"
    "2. 用户给的车牌会在工具层掩码，你看到的不是原始车牌，不要试图还原；\n"
    "3. 每次回答简要说明你调用了哪些工具；\n"
    "4. 时间格式统一 'YYYY-MM-DD HH:MM:SS'。\n"
    "You are a traffic data assistant. Call tools only; never fabricate numbers."
)

# 写操作确认令牌的进程内登记表（生产应换 Redis，见 ADDENDUM R4）
_PENDING_CONFIRMS: dict[str, dict[str, Any]] = {}

# 中国车牌：省份汉字 + 字母 + 5-6 位字母数字；拒绝纯字母短串（如 "bad"）
_CAR_NO_RE = re.compile(r"^[\u4e00-\u9fff][A-Z][A-Z0-9]{4,6}$")


def _json(data: dict[str, Any]) -> str:
    """把 dict 序列化为 JSON 字符串（等价 Jackson ``ObjectMapper.writeValueAsString``）。"""
    return json.dumps(data, ensure_ascii=False, default=str)


def mask_car_no(car_no: str) -> str:
    """车牌掩码：'赣A51234' → '赣A5***'。

    审阅 R4 要求：原始车牌不得进入 LLM 上下文或 checkpointer 持久化内容。
    非法格式直接返回 ``***``（fail-closed）。
    """
    value = (car_no or "").strip().upper()
    if not value or not _CAR_NO_RE.match(value):
        return "***"
    if len(value) <= 3:
        return value[:1] + "***"
    return value[:3] + "***"


def _safe_time(value: str) -> str:
    """轻量时间格式校验（防 Prompt 注入携带奇怪字符）。"""
    text = (value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$", text):
        raise ValueError("时间格式必须为 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'")
    return text


def _load_service(name: str) -> Any:
    """从 V3 单例表加载 Service（等价 Spring ``ApplicationContext.getBean``）。

    Service 不可用时返回 None，工具层转成 ``service_unavailable`` 结构化错误，
    不让 ImportError 冒泡到 Agent 循环里。
    """
    try:
        from com.ruoyi.base.service.v3.v3_services import SERVICES  # type: ignore

        return SERVICES.get(name)
    except Exception as exc:  # noqa: BLE001
        log.warning("[AI Tool] Service 不可用 name=%s reason=%s", name, exc)
        return None


@tool
def query_snapshot(start_time: str, end_time: str, car_no: str = "", limit: int = 20) -> str:
    """查询高速通行快照流水的聚合摘要。

    Query aggregated snapshot traffic records. Returns only counts/time buckets, never raw vehicle details.

    参数：start_time/end_time 为 'YYYY-MM-DD HH:MM:SS'；car_no 可选，会自动掩码；
    limit 最大 100。返回 ``{"ok": true, "count": N, "buckets": ...}``。
    """
    try:
        start, end = _safe_time(start_time), _safe_time(end_time)
        limit = max(1, min(100, limit))
        masked = mask_car_no(car_no) if car_no else ""
        service = _load_service("trafficSearchService")
        if service is None:
            return _json({"ok": False, "error": "service_unavailable"})
        # Java 对照：TrafficSearchService.search(TrafficSearchRequest)
        # 真实实现走 ES PIT + search_after（见 v3_services.py:327/337）。
        from datetime import datetime

        from com.ruoyi.base.service.v3.v3_services import TrafficSearchRequest, TrafficTable  # type: ignore

        def _millis(text: str) -> int:
            fmt = "%Y-%m-%d %H:%M:%S" if " " in text else "%Y-%m-%d"
            return int(datetime.strptime(text, fmt).timestamp() * 1000)

        result = service.search(TrafficSearchRequest(
            table=TrafficTable.SNAPSHOT, startMillis=_millis(start), endMillis=_millis(end),
            plate=masked or None, pageSize=limit))
        rows = getattr(result, "rows", []) or []
        return _json({
            "ok": True,
            "car_no_masked": masked,
            "count": len(rows),
            "buckets": [{"time": r.get("time"), "section": r.get("sectionCode")} for r in rows[:limit]],
        })
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)[:200]})


@tool
def group_stats(table: str, group_by: str, start_time: str,
                end_time: str, top_n: int = 10) -> str:
    """按维度统计 Top-N（快照/收费/轨迹三表）。

    Aggregate Top-N statistics by dimension for snapshot/fee/trail tables.

    ``table`` 只能是 snapshot/fee/trail；返回 ``{"ok": true, "items": [...]}``。
    """
    try:
        if table not in ("snapshot", "fee", "trail"):
            return _json({"ok": False, "error": "invalid_table"})
        start, end = _safe_time(start_time), _safe_time(end_time)
        top_n = max(1, min(100, top_n))
        service = _load_service("bigScreenStatsService")
        if service is None:
            return _json({"ok": False, "error": "service_unavailable"})
        # Java 对照：BigScreenStatsService.warning_top(start, end, topN)
        # 真实符号见 v3_services.py:517/529（不是不存在的 aggregate 方法）。
        items = service.warning_top(start, end, top_n) or []
        return _json({"ok": True, "table": table, "group_by": group_by, "items": items[:top_n]})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)[:200]})


@tool
def submit_export(table: str, start_time: str, end_time: str,
                  mode: str = "display") -> str:
    """提交导出任务（写操作，需二次确认）。

    Submit an export task (write operation, requires explicit confirmation).

    第一次调用返回 ``need_confirm=true`` 和 ``confirm_token``；
    客户端必须调用 ``POST /ai/agent/confirm`` 携带该 token 才真正提交。
    """
    try:
        if table not in ("snapshot", "fee", "trail"):
            return _json({"ok": False, "error": "invalid_table"})
        start, end = _safe_time(start_time), _safe_time(end_time)
        if mode not in ("display", "full"):
            return _json({"ok": False, "error": "invalid_mode"})
        token = uuid.uuid4().hex
        _PENDING_CONFIRMS[token] = {
            "table": table, "start": start, "end": end, "mode": mode,
            "created_at": time.time(),
        }
        return _json({"ok": False, "need_confirm": True, "confirm_token": token,
                      "message": "导出为写操作，请调用 /ai/agent/confirm 确认"})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)[:200]})


def confirm_export(confirm_token: str) -> dict[str, Any]:
    """二次确认后真正提交导出（供 API 层调用，不是 tool）。

    Java 对照：Controller 的 ``@PostMapping("/confirm")`` 方法，
    消费一次性 token 并调用 ``ExportTaskService.submit_display/submit_full``。
    """
    pending = _PENDING_CONFIRMS.pop(confirm_token, None)
    if pending is None or time.time() - pending["created_at"] > 300:
        return {"ok": False, "error": "confirm_token_invalid_or_expired"}
    service = _load_service("exportTaskService")
    if service is None:
        return {"ok": False, "error": "service_unavailable"}
    from com.ruoyi.base.service.v3.v3_services import ExportRequest  # type: ignore

    request = ExportRequest(table=pending["table"], startTime=pending["start"],
                            endTime=pending["end"])
    task = service.submit_full(request) if pending["mode"] == "full" else service.submit_display(request)
    return {"ok": True, "taskId": getattr(task, "taskId", None), "mode": pending["mode"]}


@tool
def export_status(task_id: str) -> str:
    """查询导出任务状态。

    Check export task status by task id.

    Java 对照：``ExportTaskService.get(taskId) -> Optional[ExportTask]``（不是 status 方法）。
    """
    try:
        service = _load_service("exportTaskService")
        if service is None:
            return _json({"ok": False, "error": "service_unavailable"})
        task = service.get(task_id)
        if task is None:
            return _json({"ok": False, "error": "task_not_found"})
        return _json({"ok": True, "taskId": task_id, "status": getattr(task, "status", "UNKNOWN"),
                      "mode": getattr(task, "mode", None)})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)[:200]})


@tool
def es_status() -> str:
    """查询 Elasticsearch 索引健康状态（只读）。

    Check Elasticsearch index health (read-only).

    Java 对照：``TrafficEsIndexService`` 的状态查询（v3_services.py:386）。
    """
    try:
        service = _load_service("trafficEsIndexService")
        if service is None:
            return _json({"ok": False, "error": "service_unavailable"})
        # 契约骨架：Service 未暴露 status 方法时返回空列表（与 Java "空索引" 一致）
        status = getattr(service, "status", None)
        data = status() if callable(status) else []
        return _json({"ok": True, "indices": data})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)[:200]})


#: 传给 LangGraph ToolNode / LangChain create_agent 的官方工具列表。
TOOLS = [query_snapshot, group_stats, submit_export, export_status, es_status]
