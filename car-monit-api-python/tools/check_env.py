# -*- coding: utf-8 -*-
"""Print the interpreter and dependency status of the Python 3.12 runtime.

Usage:
    D:\\Python\\Python312\\python.exe tools\\check_env.py
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "SQLAlchemy"),
    ("psycopg", "psycopg"),
    ("redis", "redis"),
    ("elasticsearch", "elasticsearch"),
    ("httpx", "httpx"),
    ("apscheduler", "APScheduler"),
    ("yaml", "PyYAML"),
    ("orjson", "orjson"),
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
    print(f"missing     : {missing}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
