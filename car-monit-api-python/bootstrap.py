# -*- coding: utf-8 -*-
"""Import path bootstrap for the Python runtime layer.

The ported business code keeps the Java package layout verbatim::

    com/...                                  framework shims
    java/...                                 java.lang / java.util shims
    pro-base-common/src/main/java/com/...    pro-base-common
    pro-business-api/src/main/java/com/...   pro-business-api

Python needs those roots on ``sys.path`` before ``import com.ruoyi...``
can work, exactly like Maven puts both module output directories on the
classpath of the Spring Boot application.

This module is imported by:
  * ``run.py``            (the entry point)
  * ``app/__init__.py``   (defensive: tests and tools import ``app.*`` first)
  * ``conftest.py``       (pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PACKAGE_ROOTS = (
    ROOT / "pro-base-common" / "src" / "main" / "java",
    ROOT / "pro-business-api" / "src" / "main" / "java",
    ROOT,
)


def setup_sys_path() -> None:
    """Register the Java-mirrored package roots (idempotent)."""
    # reversed() keeps ROOT as the highest priority entry
    for path in reversed(PACKAGE_ROOTS):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)


setup_sys_path()
