# -*- coding: utf-8 -*-
"""One-command launcher: ``python run.py``.

Equivalent to ``java -jar pro-business-api.jar``.

Environment variables (all optional):
    CAR_MONIT_HOST        bind address          (default 0.0.0.0, like Tomcat)
    CAR_MONIT_PORT        bind port            (default server.port = 9901)
    CAR_MONIT_RELOAD      true -> uvicorn --reload (development only)
    CAR_MONIT_LOG_LEVEL   INFO / DEBUG          (default INFO)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import bootstrap  # noqa: F401  (must run before importing app.*)

from app.logging_config import configure_logging
from app.settings import settings


def main() -> None:
    import uvicorn

    level = os.environ.get("CAR_MONIT_LOG_LEVEL", "INFO")
    configure_logging(level)

    reload_enabled = os.environ.get("CAR_MONIT_RELOAD", "false").strip().lower() in ("1", "true", "yes", "on")
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("CAR_MONIT_HOST", "0.0.0.0"),
        port=int(os.environ.get("CAR_MONIT_PORT", settings.server_port)),
        reload=reload_enabled,
        reload_dirs=[str(Path(__file__).resolve().parent / "app")] if reload_enabled else None,
        log_level=level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    sys.exit(main())
