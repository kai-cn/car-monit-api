# -*- coding: utf-8 -*-
"""Python runtime layer of the car-monit-api port.

Layout (mirrors the Spring Boot layering):

    app/main.py          EcBusinessApiApplication + Filter/Interceptor chain
    app/settings.py      application.yml access (@Value equivalent)
    app/web/             Spring MVC behaviour: binding, JSON, error body
    app/db/              MyBatis / MyBatis-Plus behaviour: XML SQL, paging, ids
    app/routes/          @RestController registration (24 controllers)
    app/scheduler/       @Scheduled tasks
    app/health.py        /health (migration-only, no Java counterpart)

Everything under ``com/``, ``java/``, ``org/`` and
``pro-{base-common,business-api}/src/main/java`` is the pre-existing 1:1
business port and is imported unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import bootstrap  # noqa: F401  (registers the Java-mirrored import roots)

__all__ = ["__version__"]

__version__ = "1.0.0"
