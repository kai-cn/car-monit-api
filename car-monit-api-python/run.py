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

    # P0-2：shim 模式下打印醒目横幅，防止“替身假成功”被误当生产环境使用。
    from app.runtime import runtime_mode

    if runtime_mode() != "prod":
        print("=" * 74)
        print("⚠  CAR_MONIT_RUNTIME=shim（开发/测试模式）")
        print("⚠  Kafka / Pulsar / RocketMQ / ES / Redis 写 / JdbcTemplate / Forest")
        print("⚠  均为进程内替身：操作返回“成功”但数据不会离开本进程。")
        print("⚠  生产部署必须设置 CAR_MONIT_RUNTIME=prod（假成功将被拒绝并抛错）。")
        print("=" * 74, flush=True)

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
