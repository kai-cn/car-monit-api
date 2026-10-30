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
from app.settings import settings
from app.web.binding import BindingError
from app.web.errors import error_response
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
    """MyBatis' ``SqlSessionFactoryBean`` + ``MapperScannerConfigurer``.

    Until this runs, every mapper answers from the in-memory implementation
    written by the port -- which silently returns ``[]`` instead of querying
    GaussDB, the exact divergence a migration must not hide.
    """
    try:
        from app.db.registry import install_mappers

        report = install_mappers()
    except Exception as error:  # noqa: BLE001 - keep serving, report loudly
        log.exception("mapper registry failed to install")
        return f"failed: {error}"
    for item in report.missing_statements:
        log.error("mapper method without statement: %s", item)
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
        except Exception as error:  # noqa: BLE001 - 与 Spring 一致：Bean 起不来就启动失败
            scheduler_note = f"failed: {error}"

    elapsed = time.perf_counter() - started
    log.info("Starting %s v%s (Python %s)", APP_NAME, __version__, os.sys.version.split()[0])
    log.info("Tomcat started on port(s): %s (http) with context path '%s'",
             os.environ.get("CAR_MONIT_PORT", settings.server_port), settings.context_path)
    log.info("MyBatis: %s", mapper_note)
    log.info("Scheduler: %s", scheduler_note)
    log.info("Started %s in %.2f seconds", APP_NAME, elapsed)
    yield
    log.info("Shutting down %s", APP_NAME)
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
