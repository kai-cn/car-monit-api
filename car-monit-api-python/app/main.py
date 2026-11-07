# -*- coding: utf-8 -*-
"""Application entry point.

Migrated from: pro-business-api/src/main/java/com/ruoyi/EcBusinessApiApplication.java

Startup order mirrors Spring Boot:

1. ``@SpringBootApplication``            -> create the FastAPI application
2. environment / application.yml         -> ``app.settings`` (lazy, same file)
3. ``@EnableScheduling`` + ApplicationRunner -> ``app.scheduler`` (Phase 2c, done)
4. DispatcherServlet + @RestController   -> ``app.routes`` (Phase 2b)
5. Tomcat on port 9901, context path ''  -> uvicorn on ``server.port``

Differences that are deliberate and documented:
* ``/health`` and ``/docs`` exist only in the Python port (verification aid);
* there is no Spring Security / interceptor chain, matching the Java project
  where ``SecurityInterceptor`` and ``WebConfig`` are entirely commented out.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.health import health_payload
from app.logging_config import configure_logging
from app.routes import register_routes
from app.runtime import runtime_mode, startup_fail_fast
from app.settings import settings
from app.web.binding import BindingError
from app.web.errors import basic_error_endpoint_response, error_response
from app.web.responses import JacksonResponse

configure_logging(os.environ.get("CAR_MONIT_LOG_LEVEL", "INFO"))

log = logging.getLogger(__name__)

APP_NAME = "EcBusinessApiApplication"


def _register_health_probes() -> None:
    """Attach connectivity probes once the adapters exist (Phase 2b/2d)."""
    try:
        from app.db.engine import get_database

        database = get_database()
        from app.health import health_registry

        health_registry.register("db", database.ping)
    except Exception as error:  # noqa: BLE001
        log.debug("database probe not registered: %s", error)


def _install_persistence() -> str:
    """MyBatis' ``SqlSessionFactoryBean`` + ``MapperScannerConfigurer``。

    P0-5 起与 Spring 一致地 fail-fast（此前只记日志继续跑，报告 B5）：

    * install 抛错（含 P0-1 的 0-XML 守卫）→ 启动失败；
    * ``failed_files`` / 白名单**外**的缺失 statement → 启动失败；
    * 白名单内的 6 个缺失 statement → WARNING + TODO(V2/决策①)（Java 侧同样缺失，
      见 ``app/db/registry.KNOWN_MISSING_STATEMENTS``）；
    * 逃生口：``CAR_MONIT_STARTUP_FAIL_FAST=false`` 恢复旧的仅日志行为。
    """
    from app.db.registry import KNOWN_MISSING_STATEMENTS, install_mappers

    try:
        report = install_mappers()
    except Exception as error:  # noqa: BLE001
        if startup_fail_fast():
            raise
        log.exception("mapper registry failed to install (fail-fast disabled)")
        return f"failed: {error}"

    whitelisted = [item for item in report.missing_statements
                   if item in KNOWN_MISSING_STATEMENTS]
    unexpected = [item for item in report.missing_statements
                  if item not in KNOWN_MISSING_STATEMENTS]
    for item in whitelisted:
        log.warning("mapper method without statement (whitelisted, TODO 决策①): %s", item)
    if report.failed_files or unexpected:
        problem = ("mapper install incomplete: failed_files=%s unexpected_missing=%s"
                   % (report.failed_files, unexpected))
        if startup_fail_fast():
            raise RuntimeError(problem)
        log.error("%s (fail-fast disabled)", problem)
    return report.summary()


@asynccontextmanager
async def lifespan(_: FastAPI):
    started = time.perf_counter()
    mapper_note = _install_persistence()
    _register_health_probes()

    scheduler_note = "disabled"
    if settings.scheduler_enabled:
        try:
            from app.scheduler import start_scheduler

            count = start_scheduler()
            scheduler_note = f"{count} task(s)"
        except Exception as error:  # noqa: BLE001
            # P0-5：与 Spring 一致——Bean 起不来容器就启动失败（此前只记日志）
            if startup_fail_fast():
                raise
            scheduler_note = f"failed: {error}"

    # P0-3：@Service#@PostConstruct 的后台 Bean（默认关闭，TODO 决策②③，见 app/beans.py）
    from app.beans import start_beans

    beans_note = start_beans()

    elapsed = time.perf_counter() - started
    log.info("Starting %s v%s (Python %s)", APP_NAME, __version__, os.sys.version.split()[0])
    log.info("Runtime mode: %s (CAR_MONIT_RUNTIME)", runtime_mode())
    log.info("Tomcat started on port(s): %s (http) with context path '%s'",
             os.environ.get("CAR_MONIT_PORT", settings.server_port), settings.context_path)
    log.info("MyBatis: %s", mapper_note)
    log.info("Scheduler: %s", scheduler_note)
    log.info("Beans: %s", beans_note)
    log.info("Started %s in %.2f seconds", APP_NAME, elapsed)
    yield
    log.info("Shutting down %s", APP_NAME)
    try:
        from app.beans import shutdown_beans

        shutdown_beans()
    except Exception:  # noqa: BLE001 - best effort, like a Spring destroy callback
        pass
    try:
        from app.scheduler import shutdown_scheduler

        shutdown_scheduler()
    except Exception:  # noqa: BLE001 - best effort, like a Spring destroy callback
        pass


app = FastAPI(
    title="car-monit-api",
    description="Behavior-equivalent Python port of the Spring Boot 2.4.5 service.",
    version=__version__,
    lifespan=lifespan,
    default_response_class=JacksonResponse,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)


# --------------------------------------------------------------------- routes
@app.get("/health", tags=["migration"], summary="Liveness/readiness (migration-only)")
def health() -> dict[str, Any]:
    """No Java counterpart: added to verify the migration without business calls."""
    return health_payload({"config": settings.describe()})


_ROUTE_COUNT = register_routes(app)
log.info("Registered %s controller route(s)", _ROUTE_COUNT)

# P0-5：路由注册不完整 → 与 Spring 的容器 refresh 失败一致，直接抛错退出
# （此前仅记 error 日志继续跑，报告 B5）。逃生口同上：CAR_MONIT_STARTUP_FAIL_FAST=false。
_route_report = getattr(app.state, "route_report", None)
if _route_report is not None and startup_fail_fast():
    _route_problems = {name: getattr(_route_report, name) for name in (
        "unavailable", "skipped", "missing_methods",
        "signature_mismatches", "base_path_mismatches", "duplicates")}
    _route_problems = {name: values for name, values in _route_problems.items() if values}
    if _route_problems:
        raise RuntimeError(
            "route registration incomplete (Spring would fail startup): %s" % _route_problems)


# Java 侧这个路由来自 Spring Boot 自带的 ``BasicErrorController``（不是业务代码），
# 但 springfox 把它扫进了 api-docs，因此 /error 也属于需要对齐的接口面：
# 直接访问时不走错误派发，固定回 HTTP 500 + ``status:999 / error:"None"``。
@app.api_route("/error", methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
               include_in_schema=False)
def spring_basic_error_controller() -> JacksonResponse:
    """对应 ``BasicErrorController#error``（直接命中，无错误属性）。"""
    return basic_error_endpoint_response()


# ------------------------------------------------------------------- handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JacksonResponse:
    """Spring Boot ``BasicErrorController`` shape instead of ``{"detail": ...}``."""
    return error_response(exc.status_code, request.url.path)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JacksonResponse:
    """Spring answers a binding failure with 400, not FastAPI's 422."""
    log.debug("request validation failed for %s: %s", request.url.path, exc.errors())
    return error_response(400, request.url.path)


@app.exception_handler(BindingError)
async def binding_error_handler(request: Request, exc: BindingError) -> JacksonResponse:
    log.debug("binding failed for %s: %s", request.url.path, exc)
    return error_response(400, request.url.path)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JacksonResponse:
    """No ``@ControllerAdvice`` exists in the Java project -> 500 + log stack trace."""
    log.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return error_response(500, request.url.path)
