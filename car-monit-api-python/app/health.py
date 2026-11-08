# -*- coding: utf-8 -*-
"""``/health`` endpoint -- migration-only addition.

There is **no** Java counterpart (the project does not depend on Actuator and
exposes no health endpoint). It is added so the migrated service can be
verified after ``pip install`` without touching the business API surface.

Contract:
* always HTTP 200 while the process is alive;
* ``status`` is ``UP`` when every registered probe succeeds, ``DEGRADED``
  otherwise -- a failing GaussDB/Redis/ES must not make the container
  restart-loop, exactly like Spring Boot without Actuator health groups.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import platform
import sys
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

__all__ = ["HealthRegistry", "degraded_probe", "health_registry", "health_verbose"]

STARTED_AT = _dt.datetime.now(tz=_dt.timezone.utc)


def health_verbose() -> bool:
    """P0-6：``/health`` 是否携带 ``config`` 细节（含中间件地址）。

    默认仅 shim（开发）模式携带；prod 模式需显式 ``CAR_MONIT_HEALTH_VERBOSE=true``
    （Java 侧没有 /health 端点，这是 Python 侧新增的生产收敛，不是契约变更）。
    """
    value = (os.environ.get("CAR_MONIT_HEALTH_VERBOSE") or "").strip().lower()
    if value:
        return value in ("1", "true", "yes", "on")
    from app.runtime import runtime_mode

    return runtime_mode() != "prod"


def degraded_probe(name: str, backend_factory: Callable[[], Any]) -> Callable[[], Any]:
    """M6：把真实适配器的 ``degraded`` 状态接进健康检查。

    * 后端不存在（未配置 URL）→ ``{"mode": "shim"}``，UP；
    * 后端是内存实现（无 ``degraded`` 属性）→ ``{"mode": "memory"}``，UP；
    * 真实后端处于熔断降级 → 抛 ``RuntimeError``（组件 DOWN，readiness 503）。
    """

    def probe() -> Any:
        backend = backend_factory()
        if backend is None:
            return {"mode": "shim"}
        if not hasattr(backend, "degraded"):
            return {"mode": "memory"}
        if bool(backend.degraded):
            raise RuntimeError("%s 熔断降级中（真实服务不可用，已回落进程内替身）" % name)
        return {"mode": "real"}

    probe.__name__ = "%s_probe" % name
    return probe


class HealthRegistry:
    """Registry of lazy connectivity probes (DB / Redis / ES / MQ)."""

    def __init__(self) -> None:
        self._probes: dict[str, Callable[[], Any]] = {}

    def register(self, name: str, probe: Callable[[], Any]) -> None:
        self._probes[name] = probe

    def unregister(self, name: str) -> None:
        self._probes.pop(name, None)

    def run(self) -> dict[str, Any]:
        components: dict[str, Any] = {}
        status = "UP"
        for name, probe in self._probes.items():
            try:
                detail = probe()
                components[name] = {"status": "UP", "detail": detail}
            except Exception as error:  # noqa: BLE001 - health must never raise
                status = "DEGRADED"
                components[name] = {"status": "DOWN", "error": f"{type(error).__name__}: {error}"}
                log.warning("health probe %s failed: %s", name, error)
        return {"status": status, "components": components}


health_registry = HealthRegistry()


def health_payload(extra: Optional[dict] = None) -> dict[str, Any]:
    from app import __version__
    from app.runtime import runtime_mode

    result = health_registry.run()
    payload: dict[str, Any] = {
        "status": result["status"],
        "app": "car-monit-api",
        "version": __version__,
        "runtime": runtime_mode(),  # P0-6：shim/prod 可见，防止替身被误当生产
        "javaVersion": "1.8",
        "springBootVersion": "2.4.5",
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "startedAt": STARTED_AT.isoformat(timespec="seconds"),
        "uptimeSeconds": int((_dt.datetime.now(tz=_dt.timezone.utc) - STARTED_AT).total_seconds()),
        "components": result["components"],
    }
    if extra:
        payload.update(extra)
    return payload
