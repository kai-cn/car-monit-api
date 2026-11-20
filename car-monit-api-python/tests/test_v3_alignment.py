# -*- coding: utf-8 -*-
"""Java V3 对齐回归测试（端点可见性 + 核心契约）。

运行::

    .venv\\Scripts\\python.exe -m pytest tests/test_v3_alignment.py -q

【Java→Python 差异】Java 侧对应的是 JUnit 测试
``service/v3/query/*Test.java`` 与 ``docs/v3/review/04-reproduction-guide.md`` 的手工 curl；
Python 侧用 pytest 直接驱动 Controller 实例，避免启动完整 Spring/FastAPI 上下文。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Java V3 新增的 25 条端点（24 条 V3 Controller + 1 条 LargeScaleQueryController）
EXPECTED_NEW_ROUTES = {
    ("POST", "/api/v3/traffic/list"),
    ("GET", "/api/v3/export/capabilities"),
    ("POST", "/api/v3/export/display"),
    ("POST", "/api/v3/export/full"),
    ("GET", "/api/v3/export/status/{taskId}"),
    ("POST", "/api/v3/export/cancel/{taskId}"),
    ("GET", "/api/v1/bigscreen/stats/escape"),
    ("GET", "/api/v1/bigscreen/stats/audit"),
    ("GET", "/api/v1/bigscreen/stats/income"),
    ("GET", "/api/v1/bigscreen/stats/warning-top"),
    ("GET", "/api/v1/bigscreen/warning/list"),
    ("POST", "/api/v3/es/bootstrap"),
    ("GET", "/api/v3/es/status"),
    ("GET", "/api/v3/es/readiness"),
    ("POST", "/api/v3/es/activate"),
    ("POST", "/api/v3/es/car-warning/bootstrap"),
    ("POST", "/api/v3/sync/car-warning/backfill"),
    ("POST", "/api/v3/sync/dws/backfill"),
    ("POST", "/api/v3/sync/car-warning/outbox/poll"),
    ("POST", "/api/v3/sync/backfill"),
    ("GET", "/api/v3/sync/backfill/status/{taskId}"),
    ("POST", "/api/v3/sync/reconcile"),
    ("POST", "/api/v3/sync/outbox/relay"),
    ("POST", "/api/v3/sync/reconcile/orphans"),
    ("GET", "/api/v1/large/export/download/{taskId}"),
}


def _routes():
    spec = importlib.util.spec_from_file_location("v3_generated", ROOT / "app/routes/generated.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ROUTES


def test_v3_route_table_complete():
    """生成表覆盖 Java V3 全部新增端点，且总数与 Java 分支一致。"""
    routes = _routes()
    assert len(routes) == 110
    assert len({r["controller"] for r in routes}) == 29
    actual = {(r["http"], r["path"]) for r in routes}
    missing = EXPECTED_NEW_ROUTES - actual
    assert not missing, f"缺失 V3 端点: {sorted(missing)}"


def test_traffic_query_v3_deep分页_keeps_pit():
    from com.ruoyi.base.controller.v3.TrafficQueryV3Controller import TrafficQueryV3Controller

    controller = TrafficQueryV3Controller()
    body = {
        "table": "snapshot", "startTime": "2025-06-01", "endTime": "2025-06-02",
        "searchAfter": ["2025-06-01", "abc"], "pitId": "pit-1", "needTotal": True,
    }
    response = controller.list(body)
    assert response["code"] == 200
    assert response["hasMore"] is False
    # Java P1-4：深分页必须保留 PIT；needTotal 即便为 true 也要被 deep 覆盖成 False 的反向逻辑
    # （Java: needTotal = !deep && api.isNeedTotal()）
    assert response["pitId"] == "pit-1"


def test_export_v3_submit_status_cancel_hides_file_path():
    from com.ruoyi.base.controller.v3.ExportV3Controller import ExportV3Controller

    controller = ExportV3Controller()
    capabilities = controller.capabilities()
    assert capabilities["modes"] == ["display", "full"]
    assert capabilities["multiValueSupported"] is True

    submitted = controller.submitDisplay({"table": "snapshot"})
    assert submitted["code"] == 200
    task_id = submitted["data"]["taskId"]
    assert "filePath" not in submitted["data"], "filePath 是服务端绝对路径，不得暴露"

    status = controller.status(task_id)
    assert status["code"] == 200
    assert status["data"]["mode"] == "display"

    assert controller.status("not-exist")["code"] == 404
    assert controller.cancel(task_id)["code"] == 200
    assert controller.cancel(task_id)["code"] == 200  # Java 幂等：已取消再取消仍 true
    assert controller.cancel("not-exist")["code"] == 404


def test_warning_v3_capture_type_sentinel_stripping():
    from com.ruoyi.base.controller.v3.BigScreenWarningV3Controller import BigScreenWarningV3Controller

    controller = BigScreenWarningV3Controller()
    capture_types: list[str] = []
    value = controller.stripCaptureTypeSentinel("GantryCapture, gantry-1", capture_types)
    assert value == "gantry-1"
    assert capture_types == ["GantryCapture"]

    with pytest.raises(Exception) as exc_info:
        controller.parseCaptureTypes("BadCapture")
    assert "captureType 非法" in str(exc_info.value)


def test_admin_v3_engine_activate_fails_closed():
    from com.ruoyi.base.controller.v3.TrafficAdminV3Controller import TrafficAdminV3Controller

    controller = TrafficAdminV3Controller()
    status = controller.esStatus()
    assert status["code"] == 200
    assert set(status["indices"]) == {"snapshot", "fee", "trail"}
    assert status["indices"]["snapshot"]["readAlias"].endswith("-read")

    # ES 未就绪时 activate(es) 保持 legacy 并返回 409（Java 契约）
    activation = controller.activate("es")
    assert activation["code"] == 409
    assert activation["activeEngine"] == "legacy"
    assert controller.activate("legacy")["code"] == 200

    assert controller.backfill("snapshot", "2025-06-01", "2025-06-02")["code"] == 200
    task_id = controller.backfill("fee", "2025-06-01", "2025-06-02")["taskId"]
    assert controller.backfillStatus(task_id)["code"] == 200
    assert controller.backfillStatus("not-exist")["code"] == 404


def test_large_download_endpoint_contract():
    from com.ruoyi.base.controller.LargeScaleQueryController import LargeScaleQueryController

    controller = LargeScaleQueryController()
    assert controller.downloadExport("missing")["code"] == 404

    submitted = controller.submitExport(
        type="snapshot", startTime="2025-06-01", endTime="2025-06-02", mode="display", body={})
    assert submitted["code"] == 200
    assert submitted["mode"] == "display"
    task_id = submitted["taskId"]
    # Java: 新任务 status=RUNNING，未完成下载返回 409
    assert controller.downloadExport(task_id)["code"] == 409
    assert controller.getExportStatus(task_id)["code"] == 200


def test_internal_guard_prefixes():
    from app.middleware.internal_guard import PROTECTED_PREFIXES, _is_protected

    assert _is_protected("/api/v3/es/status")
    assert _is_protected("/api/v1/large/export/submit")
    assert not _is_protected("/api/v1/large/snapshot")
    assert not _is_protected("/health")
