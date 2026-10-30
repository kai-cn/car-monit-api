# -*- coding: utf-8 -*-
"""java.util.concurrent.Executors

【无 Java 源文件：框架类替身】
Java 侧来自 JDK 的线程池工厂：
    Executors.newFixedThreadPool(n)
    Executors.newFixedThreadPool(n, threadFactory)
    Executors.newSingleThreadExecutor()
    Executors.newCachedThreadPool()

【Java→Python 关键差异】
1) Java 的 `newCachedThreadPool` 是“按需创建、空闲 60s 回收”的无界池；
   Python 没有等价物，这里用 `ThreadPoolExecutor` 的语义近似：固定一个较大的上限
   （默认 64）复用之 —— 本工程里只在没显式传 executor 的 CompletableFuture 中使用。
2) Java 的 `ThreadFactory` 接口只有 `newThread(Runnable r)`；Python 侧仍保留同名方法，
   但返回值必须是 `threading.Thread`（否则被忽略，退回默认线程命名）。
"""
from __future__ import annotations

from typing import Any, Optional

from java.util.concurrent.ExecutorService import ExecutorService

__all__ = ["Executors", "ThreadFactory"]


class ThreadFactory(object):
    """`java.util.concurrent.ThreadFactory` 的替身基类。

    子类实现 `newThread(target)`，返回一个 `threading.Thread`（必须在外部 start）。
    """

    def newThread(self, target: Any) -> Any:  # pragma: no cover - 由子类实现
        raise NotImplementedError("ThreadFactory.newThread 需由子类实现")


class Executors(object):
    """线程池工厂（静态方法集合）。"""

    @staticmethod
    def newFixedThreadPool(core_pool_size: int, thread_factory: Optional[ThreadFactory] = None) -> ExecutorService:
        return ExecutorService(core_pool_size, thread_factory)

    @staticmethod
    def newSingleThreadExecutor(thread_factory: Optional[ThreadFactory] = None) -> ExecutorService:
        return ExecutorService(1, thread_factory)

    @staticmethod
    def newCachedThreadPool(thread_factory: Optional[ThreadFactory] = None) -> ExecutorService:
        # FastAPI 场景下不会真的用到 64 并发；仅作 CompletableFuture 的默认执行器
        return ExecutorService(64, thread_factory)

    @staticmethod
    def newScheduledThreadPool(core_pool_size: int, thread_factory: Optional[ThreadFactory] = None) -> ExecutorService:
        """`ScheduledExecutorService` 的替身：本工程只用它的 submit 能力。"""
        return ExecutorService(core_pool_size, thread_factory)
