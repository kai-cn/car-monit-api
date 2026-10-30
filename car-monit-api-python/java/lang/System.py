# -*- coding: utf-8 -*-
"""java.lang.System

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：`java.lang.System`。业务代码用到：
    System.currentTimeMillis()
    System.nanoTime()
    System.getProperty("line.separator")
    System.getenv(name)
    System.exit(code)          （本工程未使用，保留以便对照）

【Java→Python 关键差异】
1) `System.currentTimeMillis()` 返回**毫秒级 long**；Python 的 `time.time()` 是秒（float），
   这里 `int(time.time() * 1000)` 还原，并保持“同一毫秒内多次调用值相同”的近似语义
   （Java 在毫秒内也返回相同值）。
2) `System.nanoTime()` 是**单调时钟**（不受系统时间调整影响）；Python 对应用
   `time.monotonic_ns()`，不要用 `time.time_ns()`（会受时钟回拨影响）。
3) `System.getProperty("java.io.tmpdir")` 之类 JVM 属性在 Python 中不存在，这里仅支持
   少量映射，未知属性返回默认值（与 Java 的“不存在返回 null”一致）。
"""
from __future__ import annotations

import os
import time
from typing import Optional

__all__ = ["System"]


class System(object):
    """`java.lang.System` 的静态方法子集。"""

    @staticmethod
    def currentTimeMillis() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def nanoTime() -> int:
        return time.monotonic_ns()

    @staticmethod
    def getenv(name: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(name, default)

    @staticmethod
    def getProperty(name: str, default: Optional[str] = None) -> Optional[str]:
        # 【Java→Python】只做最常用的几个属性映射，其余按 Java 语义返回 null/default
        mapping = {
            "line.separator": os.linesep,
            "file.separator": os.sep,
            "path.separator": os.pathsep,
            "os.name": os.name,
            "user.dir": os.getcwd(),
            "java.io.tmpdir": os.environ.get("TEMP") or "/tmp",
        }
        return mapping.get(name, default)

    @staticmethod
    def exit(status: int = 0) -> None:
        """等价 `System.exit(status)`：Python 用 sys.exit（抛 SystemExit）。"""
        import sys

        sys.exit(status)
