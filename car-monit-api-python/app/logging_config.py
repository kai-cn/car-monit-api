# -*- coding: utf-8 -*-
"""Logging configuration (``logback-spring.xml`` equivalent).

Migrated from: pro-business-api/src/main/resources/logback-spring.xml

Java appender  : ConsoleAppender + RollingFileAppender
File           : ../logs/pro-business-api-%d{yyyy-MM-dd}.%i.log
Rotation       : 10MB per file, 30 days history
Pattern        : %d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{50}:%L - %msg%n
Levels         : root INFO, package "web" DEBUG
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

__all__ = ["configure_logging"]

LOG_DIR = Path(os.environ.get("CAR_MONIT_LOG_DIR", Path(__file__).resolve().parent.parent / "logs"))
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 30
CONSOLE_FORMAT = "%(asctime)s.%(msecs)03d [%(threadName)s] %(levelname)-5s %(name)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Install console + rotating file handlers (idempotent)."""
    root = logging.getLogger()
    if getattr(root, "_car_monit_configured", False):
        return

    formatter = logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)

    handlers: list[logging.Handler] = [console]
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "pro-business-api.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except OSError as error:  # read-only filesystem: console only, like a failed appender
        logging.getLogger(__name__).warning("file appender disabled: %s", error)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in handlers:
        root.addHandler(handler)

    # logging.level.web=DEBUG in application.yml
    logging.getLogger("web").setLevel(logging.DEBUG)
    # uvicorn would otherwise duplicate every access log line
    logging.getLogger("uvicorn.access").disabled = True

    root._car_monit_configured = True  # type: ignore[attr-defined]
