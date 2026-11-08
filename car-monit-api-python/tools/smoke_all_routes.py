# -*- coding: utf-8 -*-
"""Sweep every registered route through the ASGI app (in-process, in-memory backends).

Purpose: prove that all handler methods can be **reached and executed** without a
Python-level defect (``AttributeError`` / ``NameError`` / ``TypeError`` /
``ImportError``) introduced by the port.

The ASGI lifespan is deliberately *not* started (``TestClient`` is used without
``with``), so ``app.db.registry.install_mappers()`` never runs: every mapper answers
from its in-memory list.  No GaussDB query, no 800M-row scan, no Kafka connection.

Status codes are therefore **not** asserted -- only "no unexpected exception":

======  ==========  ====================================================
2xx     ok          the handler completed
400     binding     Spring answers the same (missing / unparsable value)
405     method      the path exists under another verb (never expected)
5xx     DEFECT      Python error in ported code -> traceback is printed
======  ==========  ====================================================

Run::

    .venv\\Scripts\\python.exe tools\\smoke_all_routes.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# P0-2：冒烟固定 shim 模式（替身可用）。
os.environ.setdefault("CAR_MONIT_RUNTIME", "shim")
# M2：冒烟必须隔离真实 ES/Kafka/Redis——否则开发机设了 CAR_MONIT_*_URL 时
# 会把种子文档写进真实集群（甚至污染业务索引）。集成测试走 tests/business。
for _backend_env in ("CAR_MONIT_REDIS_URL", "CAR_MONIT_ES_URL",
                     "CAR_MONIT_KAFKA_URL"):
    os.environ.pop(_backend_env, None)

# P1-4：targeted 导出用例的前置条件（同 scripts/smoke_test.py）。
import tempfile as _tempfile

os.environ.setdefault("OPTIMIZATION_EXPORT_DIR",
                      _tempfile.mkdtemp(prefix="car-monit-export-"))


def _seed_es() -> None:
    # P2-3：改经业务链路（EsIndexManageService + IndexRequest）种子化——
    # shim 模式写进程内替身；设了 CAR_MONIT_ES_URL 时写真实集群（同一条代码路径）。
    from tools.smoke_seed import seed_es_via_business_chain

    seed_es_via_business_chain()


_seed_es()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402  (importing registers every route)
from app.routes.generated import ROUTES  # noqa: E402

# A zero-length window keeps every "big table" call cheap in memory mode.
_START = "2025-06-01 00:00:00"
_END = "2025-06-02 00:00:00"

_SCALARS = {"int": "1", "decimal": "1", "float": "1.5", "bool": "true"}

# Path values that the handler itself validates (an unknown value would 400).
_PATH_OVERRIDES = {"ds": "snapshot"}


class _Recorder(logging.Handler):
    """Keep every ``log.*(..., exc_info=True)`` emitted while the sweep runs."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.entries: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.exc_info:
            self.entries.append((record.getMessage(),
                                 "".join(traceback.format_exception(*record.exc_info))))

    def take(self) -> list[tuple[str, str]]:
        entries, self.entries = self.entries, []
        return entries


def _path_value(param: dict) -> str:
    return _PATH_OVERRIDES.get(param["java_name"], _SCALARS.get(param["type"], "1"))


def _query_value(param: dict) -> str:
    name = (param.get("java_name") or "").lower()
    if "end" in name and ("time" in name or "date" in name):
        return _END
    if "time" in name or "date" in name:
        return _START
    return _SCALARS.get(param["type"], "1")


def _build(route: dict) -> tuple[str, dict | None, str | None, dict | None]:
    """Return ``(path, query, verb, json_body)`` for one route entry."""
    path = route["path"]
    query: dict[str, str] = {}
    body = None
    for param in route["params"]:
        source = param["source"]
        if source == "path":
            path = path.replace("{" + param["java_name"] + "}", _path_value(param))
        elif source == "param" and param["required"] and param["default"] is None:
            query[param["java_name"]] = _query_value(param)
        elif source == "body":
            body = {}
    return path, (query or None), route["http"], body


def _section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 66 - len(title)))


def _check(failures: list[str], label: str, ok: bool, detail: object = "") -> None:
    print("  %-4s %s" % ("ok" if ok else "FAIL", label))
    if not ok:
        failures.append(label)
        if detail:
            print("       " + json.dumps(detail, ensure_ascii=False, default=str)[:400])


def _targeted(client: TestClient, failures: list[str]) -> None:
    """Assert the payload shapes the sweep alone cannot see (status is always 200)."""
    _section("targeted: ProgressiveQueryController")
    payload = client.get("/progressive/scale-level").json()
    levels = payload.get("data") or {}
    _check(failures, "scale-level: AjaxResult code=200", str(payload.get("code")) == "200", payload)
    _check(failures, "scale-level: 3 张表", len(levels) == 3, levels)
    _check(failures, "scale-level: detectScaleLevel().name",
           all(str(name).startswith("LEVEL_") for name in levels.values()), levels)

    table = client.get("/progressive/snapshotflow/list",
                       params={"startTime": _START, "endTime": _END}).json()
    _check(failures, "snapshotflow/list: rows 为 list",
           isinstance(table.get("rows"), list), table)
    _check(failures, "snapshotflow/list: msg = '策略: ...'",
           str(table.get("msg", "")).startswith("策略: "), table.get("msg"))

    _section("targeted: LargeScaleQueryController")
    missing = client.get("/api/v1/large/export/status/no-such-task").json()
    _check(failures, "large export/status: 未知 taskId -> 404",
           str(missing.get("code")) == "404", missing)
    submitted = client.post("/api/v1/large/export/submit",
                            params={"startTime": _START, "endTime": _END}).json()
    _check(failures, "large export/submit: taskId", bool(submitted.get("taskId")), submitted)

    _section("targeted: UnifiedQueryController (submit -> poll)")
    uni = client.post("/api/v1/unified/snapshot/export/submit",
                      params={"startTime": _START, "endTime": _END}, json={}).json()
    task_id = uni.get("taskId")
    _check(failures, "unified submit: taskId", bool(task_id), uni)
    status: dict = {}
    for _ in range(100):
        status = client.get("/api/v1/unified/export/status/%s" % task_id).json()
        if status.get("status") in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)
    _check(failures, "unified status: code=200", str(status.get("code")) == "200", status)
    _check(failures, "unified status: COMPLETED", status.get("status") == "COMPLETED", status)
    _check(failures, "unified status: filePaths 为 list",
           isinstance(status.get("filePaths"), list), status)
    _check(failures, "unified status: costSeconds 为 int",
           isinstance(status.get("costSeconds"), int), status)

    _section("targeted: SysUtilController (nested bean binding)")
    trail = client.post("/base/sysutil/changeTrailInfo", json={
        "tracks": {"plateKey": "\u8d63A12345", "startLon": "115.123456",
                   "stratLat": "28.654321", "endLon": "115.5", "endLat": "28.9"},
        "trailList": [{"pointUuid": "p1", "captureTime": "2025-06-01 10:00:00"}],
    }).json()
    _check(failures, "changeTrailInfo: 返回 TrailInfo 对象", isinstance(trail, dict), trail)
    _check(failures, "changeTrailInfo: 嵌套 tracks 已绑定",
           (trail.get("tracks") or {}).get("startLonDec") == 115.123456, trail)
    _check(failures, "changeTrailInfo: trailList[0].isQuery = '1'",
           ((trail.get("trailList") or [{}])[0]).get("isQuery") == "1", trail)

    car = client.get("/base/sysutil/carTrackQueryByCarNo",
                     params={"carNo": "\u8d63A12345"}).json()
    _check(failures, "carTrackQueryByCarNo: rows 为 list", isinstance(car.get("rows"), list), car)
    trail_bo = client.get("/base/sysutil/getByTrailBo", params={
        "captureTime": "2025-06-01 10:00:00", "stateType": "gantryCapture",
        "pointUuid": "p1"}).json()
    _check(failures, "getByTrailBo: 返回 TrailBo 对象", isinstance(trail_bo, dict), trail_bo)


def main() -> int:
    recorder = _Recorder()
    logging.getLogger().addHandler(recorder)

    rows: list[tuple[str, str, int, str]] = []
    defects: list[tuple[str, str, int, str]] = []

    # No ``with``: TestClient only runs the lifespan inside a context manager,
    # so the mapper registry stays uninstalled (in-memory mode by design).
    client = TestClient(app, raise_server_exceptions=False)
    _section("sweep %d route(s)" % len(ROUTES))
    for route in ROUTES:
        path, query, verb, body = _build(route)
        recorder.take()
        if verb == "POST":
            response = client.post(path, params=query, json=body)
        else:
            response = client.get(path, params=query)
        captured = recorder.take()
        label = "%s %s" % (verb, path)
        status = response.status_code
        if status >= 500:
            tail = ""
            if captured:
                lines = [x for x in captured[-1][1].strip().splitlines() if x.strip()]
                tail = lines[-1]
            rows.append((label, route["controller"].rsplit(".", 1)[-1], status, tail))
            defects.append((label, route["controller"].rsplit(".", 1)[-1], status, tail))
        else:
            rows.append((label, route["controller"].rsplit(".", 1)[-1], status, ""))

    buckets: dict[str, int] = {}
    for _, _, status, _ in rows:
        key = "%d" % status
        buckets[key] = buckets.get(key, 0) + 1
    _section("status codes")
    print("  " + ", ".join("%s=%d" % (k, v) for k, v in sorted(buckets.items())))
    print("  routes=%d" % len(rows))

    _section("defects (5xx)")
    if not defects:
        print("  none")
    for label, controller, status, tail in defects:
        print("  %-52s %-26s %s" % (label, controller, status))
        print("      " + tail)

    _section("per controller")
    per: dict[str, list[int]] = {}
    for _, controller, status, _ in rows:
        per.setdefault(controller, []).append(status)
    for controller in sorted(per):
        statuses = per[controller]
        marks = " ".join("%d" % s for s in statuses)
        print("  %-46s n=%-2d %s" % (controller, len(statuses), marks))

    failures: list[str] = []
    _targeted(client, failures)

    _section("result")
    print("  routes   : %d, 5xx: %d" % (len(rows), len(defects)))
    print("  payload  : %d failure(s)" % len(failures))
    for label in failures:
        print("    - " + label)
    return 1 if (defects or failures) else 0


if __name__ == "__main__":
    exit_code = main()
    # The ported services own non-daemon worker threads (export / sync pools), so
    # the interpreter would never exit on its own -- a smoke run must not wait.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
