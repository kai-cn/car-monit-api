# -*- coding: utf-8 -*-
"""启动自检脚本 / Startup smoke test.

用法 / Usage::

    # 1) 进程内自检（不需要先启服务，最快，适合 CI）
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

    # 2) 对已经启动的服务做真实 HTTP 自检（等价于人工点接口）
    .venv\\Scripts\\python.exe run.py                 # 另一个窗口
    .venv\\Scripts\\python.exe scripts\\smoke_test.py --live http://127.0.0.1:9901

自检内容（都是"迁移是否等价"的硬指标，不是业务功能测试）：
    1. ``/health`` 返回 200 且结构完整
    2. 路由数量 = 110（29 个 Controller；Java V3 新增 5 个 Controller / 25 个 handler）
    3. ``TableDataInfo`` 契约：``{total, rows, code, msg}``
    4. ``AjaxResult`` 契约：``{code, msg, data?}``
    5. ``UnifiedQueryController#list`` 的**裸 Map** 契约：
       ``{code, message, dataSource, pageNum, pageSize, data}``
       （Java 返回 ``Map<String, Object>``，**不是** ``TableDataInfo``，没有 rows）
    6. 统一查询 + 异步导出（submit → poll → COMPLETED）
    7. 错误体契约：``{timestamp, status, error, path}`` 且 ``message`` 为空串
       （实测 Java 进程始终输出该键、值为 ""，见 app/web/errors.py 的实测修正注记）

两种模式的探针差异（刻意设计，不是缺陷）：
    IN-PROCESS 不进入 ASGI lifespan，Mapper 保持内存实现、调度器不启动，
    因此 ``/health`` 的 ``components`` 只有 ``config``；只有在 ``--live`` 模式下
    才会断言 ``db`` / ``scheduler`` 探针存在。

退出码 / Exit code: 0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# P0-2：自检固定 shim 模式（替身可用）；prod 模式守卫由 tests/test_v2_p0.py 覆盖。
os.environ.setdefault("CAR_MONIT_RUNTIME", "shim")
# M2：进程内自检必须隔离真实中间件（`--live` 模式只发 HTTP，不受影响）。
for _backend_env in ("CAR_MONIT_REDIS_URL", "CAR_MONIT_ES_URL",
                     "CAR_MONIT_KAFKA_URL"):
    os.environ.pop(_backend_env, None)
for _env_name in list(os.environ):
    if _env_name.startswith(("CAR_MONIT_DB_", "CAR_MONIT_JSON_",
                             "CAR_MONIT_TEST_")):
        os.environ.pop(_env_name, None)

# P1-4：导出用例的前置条件——
# 1) 导出目录指向临时目录（默认 /data/export 在 CI/开发机常不可写）；
# 2) 内存 ES 里预置目标索引与一条样例文档（否则 index_not_found -> 任务 FAILED）。
import tempfile as _tempfile

os.environ.setdefault("OPTIMIZATION_EXPORT_DIR",
                      _tempfile.mkdtemp(prefix="car-monit-export-"))


def _seed_es() -> None:
    # P2-3：改经业务链路（EsIndexManageService + IndexRequest）种子化——
    # shim 模式写进程内替身；设了 CAR_MONIT_ES_URL 时写真实集群（同一条代码路径）。
    from tools.smoke_seed import seed_es_via_business_chain

    seed_es_via_business_chain()


_seed_es()

START = "2025-06-01 00:00:00"
END = "2025-06-02 00:00:00"

# 【Java V3 对齐】master 24 Controller / 85 handler → V3 29 Controller / 110 handler
EXPECTED_ROUTES = 110


class Reporter:
    """收集 PASS/FAIL，最后统一输出，避免一有失败就中断。"""

    def __init__(self) -> None:
        self.failures: list[tuple[str, Any]] = []
        self.passed = 0

    def check(self, label: str, ok: bool, detail: Any = "") -> bool:
        if ok:
            self.passed += 1
            print("  PASS  " + label)
        else:
            self.failures.append((label, detail))
            print("  FAIL  " + label)
            if detail not in ("", None):
                print("        " + json.dumps(detail, ensure_ascii=False, default=str)[:400])
        return ok


def section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 62 - len(title)))


class InProcessClient:
    """不启动 uvicorn，直接打 ASGI app。

    刻意不使用 ``with``：``TestClient`` 只在上下文管理器内触发生命周期，
    因此 Mapper 保持内存实现，自检不依赖 GaussDB / Kafka / ES。
    """

    def __init__(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app  # noqa: F401  (import 即注册路由)

        self._client = TestClient(app, raise_server_exceptions=False)

    def get(self, path: str, params: Optional[dict] = None):
        return self._client.get(path, params=params)

    def post(self, path: str, params: Optional[dict] = None, json_body: Any = None):
        return self._client.post(path, params=params, json=json_body)

    def close(self) -> None:
        """TestClient 无需关闭；保留接口与 LiveClient 一致。"""


class LiveClient:
    """对已经在跑的服务发真实 HTTP 请求（``--live`` 模式）。"""

    def __init__(self, base_url: str) -> None:
        import httpx

        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)

    def get(self, path: str, params: Optional[dict] = None):
        return self._client.get(path, params=params)

    def post(self, path: str, params: Optional[dict] = None, json_body: Any = None):
        return self._client.post(path, params=params, json=json_body)

    def close(self) -> None:
        self._client.close()


def _json(response) -> Any:
    try:
        return response.json()
    except Exception:  # noqa: BLE001 - 非 JSON 响应原样返回文本
        return response.text[:200]


def check_health(client, reporter: Reporter, live: bool) -> Optional[str]:
    """Return the ``db`` probe status (``None`` when no db probe is registered)."""
    section("/health")
    response = client.get("/health")
    reporter.check("GET /health -> 200", response.status_code == 200, response.status_code)
    body = _json(response)
    if not isinstance(body, dict):
        reporter.check("body 为 JSON 对象", False, body)
        return None
    for key in ("status", "app", "version", "components"):
        reporter.check("health 含字段 %r" % key, key in body, list(body))

    components = body.get("components") or {}
    # config 是 ``payload.update(extra)`` 注入的**顶层**字段（app/health.py），
    # 不在 components 里，与 lifespan 无关，两种模式都必须有。
    reporter.check("health 含顶层 config（settings.describe()）", "config" in body, sorted(body))

    if live:
        # 真实启动会走 lifespan：db / scheduler 探针必须注册上
        reporter.check("health.components 含 db 探针", "db" in components, sorted(components))
        reporter.check("health.components 含 scheduler 探针",
                       "scheduler" in components, sorted(components))
    else:
        # 进程内模式刻意绕过 lifespan（见 InProcessClient 说明），
        # 因此只有 config —— 打印出来即可，不作为失败项。
        print("        note: in-process 跳过 lifespan，探针 = %s" % sorted(components))

    db_status = (components.get("db") or {}).get("status")
    if db_status is not None:
        # GaussDB 不通时整体是 DEGRADED —— 自检不算失败，但要显式打印出来
        print("        note: db probe = %s" % db_status)
    return db_status


def check_tabledatainfo(client, reporter: Reporter, db_status: Optional[str]) -> None:
    section("TableDataInfo 契约（分页列表）")
    response = client.get("/base/fwqjcxx/list")
    body = _json(response)
    if db_status is not None and db_status != "UP":
        # 只在 ``--live`` + GaussDB 不可达时走到这里。此时接口必然 500，
        # 但必须表现为 Spring BasicErrorController 的错误体，
        # 而不是 Python traceback / 裸 500。
        expected_err = {"timestamp", "status", "error", "path"}
        reporter.check("db probe DOWN -> /base/fwqjcxx/list 为 Spring 500 错误体",
                       response.status_code == 500
                       and isinstance(body, dict) and expected_err <= set(body),
                       body if not isinstance(body, dict) else sorted(body))
        print("        note: GaussDB 探针 DOWN，列表体契约改由进程内模式覆盖")
        return

    expected = {"total", "rows", "code", "msg"}
    reporter.check("GET /base/fwqjcxx/list 返回 %s" % sorted(expected),
                   isinstance(body, dict) and expected <= set(body),
                   body if not isinstance(body, dict) else sorted(body))
    if isinstance(body, dict):
        reporter.check("rows 为数组", isinstance(body.get("rows"), list), type(body.get("rows")).__name__)
        reporter.check("code = 200", str(body.get("code")) == "200", body.get("code"))


def check_routes(reporter: Reporter) -> None:
    section("路由清单 / route inventory")
    from app.routes.generated import ROUTES

    controllers = {route["controller"] for route in ROUTES}
    reporter.check("路由数 = %d" % EXPECTED_ROUTES,
                   len(ROUTES) == EXPECTED_ROUTES, len(ROUTES))
    reporter.check("Controller 数 = 24", len(controllers) == 24, len(controllers))
    paths = [route["path"] for route in ROUTES]
    reporter.check("无重复 path+verb",
                   len({(r["path"], r["http"]) for r in ROUTES}) == len(paths))


def check_ajaxresult(client, reporter: Reporter) -> None:
    section("AjaxResult 契约（单对象 / 状态查询）")
    body = _json(client.get("/base/fwqjcxx/1"))
    reporter.check("GET /base/fwqjcxx/1 为 JSON 对象", isinstance(body, dict), body)
    body = _json(client.get("/progressive/scale-level"))
    reporter.check("/progressive/scale-level code = 200",
                   isinstance(body, dict) and str(body.get("code")) == "200", body)
    levels = (body or {}).get("data") or {}
    reporter.check("scale-level 覆盖 3 张表", len(levels) == 3, levels)


def check_unified_query(client, reporter: Reporter) -> None:
    section("统一查询 + 异步导出")
    params = {"startTime": START, "endTime": END}
    body = _json(client.get("/api/v1/unified/snapshot/list", params=params))
    reporter.check("GET /api/v1/unified/snapshot/list -> JSON",
                   isinstance(body, dict), body)
    if isinstance(body, dict):
        # UnifiedQueryController#list 返回 Map<String, Object>，逐字对齐 Java，
        # 注意它 **不是** TableDataInfo：没有 rows / total，字段名是 message 而非 msg。
        expected = {"code", "message", "dataSource", "pageNum", "pageSize", "data"}
        reporter.check("list 响应字段 = %s" % sorted(expected),
                       expected <= set(body), sorted(body))
        reporter.check("list code = 200", str(body.get("code")) == "200", body.get("code"))
        reporter.check("list data 为数组",
                       isinstance(body.get("data"), list),
                       type(body.get("data")).__name__)
        reporter.check("list dataSource = snapshot",
                       body.get("dataSource") == "snapshot", body.get("dataSource"))
        reporter.check("list **不含** rows（Java 返回 Map，不是 TableDataInfo）",
                       "rows" not in body, sorted(body))

    submitted = _json(client.post("/api/v1/unified/snapshot/export/submit",
                                  params=params, json_body={}))
    task_id = (submitted or {}).get("taskId")
    reporter.check("导出 submit 返回 taskId", bool(task_id), submitted)
    if not task_id:
        return

    status: dict = {}
    for _ in range(100):
        status = _json(client.get("/api/v1/unified/export/status/%s" % task_id)) or {}
        if status.get("status") in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)
    reporter.check("导出任务 COMPLETED", status.get("status") == "COMPLETED", status)
    reporter.check("导出结果含 filePaths 数组",
                   isinstance(status.get("filePaths"), list), status.get("filePaths"))


def check_error_contract(client, reporter: Reporter) -> None:
    section("错误体契约（BasicErrorController 复刻）")
    response = client.get("/__definitely_not_a_route__")
    reporter.check("未知路径 -> 404", response.status_code == 404, response.status_code)
    body = _json(response)
    expected = {"timestamp", "status", "error", "path"}
    reporter.check("错误体字段 = %s" % sorted(expected),
                   isinstance(body, dict) and expected <= set(body),
                   body if not isinstance(body, dict) else sorted(body))
    reporter.check("错误体 message 为空串（实测 Java 始终输出该键）",
                   isinstance(body, dict) and body.get("message") == "", body)
    reporter.check("status 字段 = 404", str((body or {}).get("status")) == "404",
                   (body or {}).get("status"))


def main() -> int:
    live_url = None
    if "--live" in sys.argv:
        index = sys.argv.index("--live")
        if index + 1 >= len(sys.argv):
            print("--live 需要一个 URL，例如 --live http://127.0.0.1:9901")
            return 2
        live_url = sys.argv[index + 1]

    reporter = Reporter()
    if live_url:
        print("模式 / mode : LIVE  %s" % live_url)
        client = LiveClient(live_url)
    else:
        print("模式 / mode : IN-PROCESS (ASGI, 内存后端)")
        client = InProcessClient()

    try:
        db_status = check_health(client, reporter, live=bool(live_url))
        if not live_url:
            check_routes(reporter)
        check_tabledatainfo(client, reporter, db_status)
        check_ajaxresult(client, reporter)
        check_unified_query(client, reporter)
        check_error_contract(client, reporter)
    finally:
        client.close()

    section("结果 / result")
    print("  passed : %d" % reporter.passed)
    print("  failed : %d" % len(reporter.failures))
    for label, _ in reporter.failures:
        print("    - " + label)
    return 0 if not reporter.failures else 1


if __name__ == "__main__":
    exit_code = main()
    # 导出/同步线程池的 worker 不是 daemon（与 Java 侧一致），
    # 解释器不会自己退出，自检脚本必须强制结束。
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
