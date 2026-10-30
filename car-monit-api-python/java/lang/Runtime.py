# -*- coding: utf-8 -*-
"""java.lang.Runtime

【无 Java 源文件：JDK 类替身】
业务代码只用到一个静态方法：`Runtime.getRuntime().availableProcessors()`。

【Java→Python 关键差异】
1) Java 的 `Runtime` 是 JVM 级单例、通过 `getRuntime()` 获取；
   Python 没有 JVM，这里保留单例 + 同名方法，便于与 Java 源码逐行对照。
2) `availableProcessors()` → `os.cpu_count()`（逻辑核心数，与 JVM 的返回值语义一致）；
   极端情况下 `os.cpu_count()` 返回 None，按 Java 规范最小为 1 处理。
3) 不提供 `exec`/`gc`/`halt` 等本工程未使用、且在 Python 中语义危险的方法。
"""
from __future__ import annotations

import os
from typing import Optional

__all__ = ["Runtime"]


class Runtime(object):
    """`java.lang.Runtime` 的最小替身（仅保留 availableProcessors）。"""

    _INSTANCE: Optional["Runtime"] = None

    @staticmethod
    def getRuntime() -> "Runtime":
        if Runtime._INSTANCE is None:
            Runtime._INSTANCE = Runtime()
        return Runtime._INSTANCE

    def availableProcessors(self) -> int:
        # Java 保证返回值 >= 1
        return os.cpu_count() or 1
