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
import platform
import sys
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

__all__ = ["HealthRegistry", "health_registry"]

STARTED_AT = _dt.datetime.now(tz=_dt.timezone.utc)


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

    result = health_registry.run()
    payload: dict[str, Any] = {
        "status": result["status"],
        "app": "car-monit-api",
        "version": __version__,
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
