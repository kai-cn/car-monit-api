# -*- coding: utf-8 -*-
"""java.util.concurrent.atomic.AtomicLong

【无 Java 源文件：框架类替身】同名 re-export：
`AtomicLong` 与 `AtomicInteger` 在本工程里只有“整数计数”一种用法，实现完全一致，
放在 AtomicInteger.py 中，避免两份重复代码（Java 侧两者是并列的独立类）。
"""
from java.util.concurrent.atomic.AtomicInteger import AtomicLong  # noqa: F401

__all__ = ["AtomicLong"]
