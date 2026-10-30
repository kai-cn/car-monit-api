# -*- coding: utf-8 -*-
"""java.util.concurrent.RecursiveTask

【无 Java 源文件：JDK 类替身】
Java 的 `ForkJoinTask` / `RecursiveTask<V>` 是 ForkJoinPool 的分治任务基类：
子类实现 `compute()`，内部通过 `fork()` 提交子任务、`join()` 等待结果。

【Java→Python 关键差异】
1) Python 没有 work-stealing 的 ForkJoin 框架。这里的替身**串行执行**：
   `fork()` 立即在当前线程调用 `compute()` 并缓存结果，`join()` 直接返回缓存值。
   分治的**切分结构与合并顺序**与 Java 完全一致，只是失去并行加速。
2) `RecursiveTask` 在 Java 中属于 `ForkJoinTask`，`compute()` 是 protected；
   Python 无访问修饰符，统一作为公开方法由子类覆写。
3) `invoke()` 在 Java 中可由池或任务自身调用；替身保留该方法便于逐行对照。
"""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

__all__ = ["RecursiveTask"]

T = TypeVar("T")


class RecursiveTask(Generic[T]):
    """`java.util.concurrent.RecursiveTask<V>` 的串行替身。"""

    def __init__(self) -> None:
        self._forked: bool = False
        self._forkedResult: Optional[Any] = None

    def fork(self) -> "RecursiveTask[T]":
        """提交子任务（替身：立即串行计算并缓存结果）。"""
        self._forked = True
        self._forkedResult = self.compute()
        return self

    def join(self) -> T:
        """等待并取得子任务结果（未 fork 时等价于直接 compute）。"""
        if not self._forked:
            self._forked = True
            self._forkedResult = self.compute()
        return self._forkedResult

    def invoke(self) -> T:
        """在当前线程执行任务；Java 的 `ForkJoinPool#invoke(task)` 语义相同。"""
        return self.compute()

    def compute(self) -> T:  # pragma: no cover - 由子类实现
        raise NotImplementedError("RecursiveTask.compute 需由子类实现")
