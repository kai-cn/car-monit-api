# -*- coding: utf-8 -*-
"""Print the interpreter and dependency status of the Python 3.12 runtime.

Usage:
    D:\\Python\\Python312\\python.exe tools/check_env.py

P1-4：检查清单与 requirements.txt 对齐（此前还检查 redis/elasticsearch/
APScheduler/PyYAML——它们只存在于开发机 venv、并未声明为依赖，导致
干净环境误报 MISS）。
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: requirements.txt 声明的运行时依赖（门禁对象）
REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "SQLAlchemy"),
    ("psycopg", "psycopg"),
    ("httpx", "httpx"),
    ("orjson", "orjson"),
    ("redis", "redis"),                  # P2：真实 Redis 适配
    ("elasticsearch", "elasticsearch"),  # P2：真实 ES 适配（7.x 客户端）
]

#: 开发机可能装了、但**不**是运行时依赖的包（仅提示，不计入缺失）
INFO_ONLY = [
    ("apscheduler", "APScheduler"),
    ("yaml", "PyYAML"),
]


def main() -> int:
    print(f"python      : {sys.version.split()[0]} ({platform.python_implementation()})")
    print(f"executable  : {sys.executable}")
    print(f"project root: {ROOT}")
    missing = 0
    for module_name, package_name in REQUIRED:
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "?")
            print(f"  OK   {package_name:<14} {version}")
        except Exception as error:  # noqa: BLE001
            missing += 1
            print(f"  MISS {package_name:<14} {type(error).__name__}: {error}")
    for module_name, package_name in INFO_ONLY:
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "?")
            print(f"  info {package_name:<14} {version}（未声明为依赖，仅本机存在）")
        except Exception:  # noqa: BLE001
            print(f"  --   {package_name:<14} 未安装（未声明为依赖，正常）")
    print(f"missing     : {missing}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
