# -*- coding: utf-8 -*-
"""AI Agent 工具层单测（LangGraph / LangChain 两分支共用语义）."""
from __future__ import annotations

import json

import pytest

from app.ai_agent.tools import (
    confirm_export,
    export_status,
    group_stats,
    mask_car_no,
    query_snapshot,
    submit_export,
)


def _parse(result: str) -> dict:
    return json.loads(result)


def test_mask_car_no():
    """车牌进入 LLM 上下文前必须掩码（审阅 R4）。"""
    assert mask_car_no("") == "***"
    assert mask_car_no("赣A51234") == "赣A5***"
    assert mask_car_no("bad") == "***"


def test_query_snapshot_returns_structured_or_service_unavailable():
    result = _parse(query_snapshot.invoke({"start_time": "2025-06-01", "end_time": "2025-06-02",
                                           "car_no": "赣A51234", "limit": 5}))
    assert set(result) >= {"ok"}
    if result["ok"]:
        assert result["car_no_masked"].endswith("***")
        assert result["count"] >= 0
    else:
        assert result["error"] == "service_unavailable"


def test_query_snapshot_rejects_bad_time():
    result = _parse(query_snapshot.invoke({"start_time": "bad", "end_time": "2025-06-02"}))
    assert result["ok"] is False


def test_group_stats_validates_table():
    result = _parse(group_stats.invoke({"table": "invalid", "group_by": "section",
                                        "start_time": "2025-06-01", "end_time": "2025-06-02"}))
    assert result == {"ok": False, "error": "invalid_table"}


def test_submit_export_requires_confirm_and_confirm_rejects_bad_token():
    first = _parse(submit_export.invoke({"table": "snapshot", "start_time": "2025-06-01",
                                         "end_time": "2025-06-02", "mode": "display"}))
    assert first["ok"] is False and first["need_confirm"] is True
    assert confirm_export("not-exist")["ok"] is False
    # 确认后要么成功提交（返回 taskId），要么 Service 不可用时结构化失败；不得抛异常
    confirmed = confirm_export(first["confirm_token"])
    assert confirmed["ok"] in (True, False)


def test_export_status_not_found_or_unavailable():
    result = _parse(export_status.invoke({"task_id": "missing"}))
    assert result["ok"] is False
