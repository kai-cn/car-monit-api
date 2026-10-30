# -*- coding: utf-8 -*-
"""java.util.concurrent.ForkJoinPool

【无 Java 源文件：JDK 类替身】
业务代码用法：
    ForkJoinPool pool = new ForkJoinPool(CORE_POOL_SIZE);
    List<TrailInfo> result = pool.invoke(task);
    pool.shutdown();

【Java→Python 关键差异】
1) Python 标准库没有 work-stealing 线程池。本替身**不做并行**：
   `invoke(task)` 直接调用 `task.compute()`，由 `RecursiveTask` 替身串行展开分治。
   分治结构与结果顺序与 Java 一致，仅缺少并行加速。
2) `parallelism` 参数只保留为非空校验用的属性（`getParallelism()`），不影响执行。
3) `shutdown()` 仅置标志位；`isShutdown()` / `isTerminated()` 返回该标志。
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["ForkJoinPool"]


class ForkJoinPool(object):
    """`java.util.concurrent.ForkJoinPool` 的串行替身。"""

    def __init__(self, parallelism: Optional[int] = None) -> None:
        # Java: new ForkJoinPool() 默认使用 CPU 核心数
        self._parallelism: int = parallelism if parallelism is not None else 1
        self._shutdown: bool = False

    def invoke(self, task: Any) -> Any:
        """同步执行任务并返回结果（Java: 提交后在当前线程等待）。"""
        if self._shutdown:
            raise RuntimeError("java.util.concurrent.RejectedExecutionException: pool is shut down")
        return task.compute()

    def submit(self, task: Any) -> Any:
        """`submit` 返回 ForkJoinTask；替身直接返回已计算完成的任务。"""
        if self._shutdown:
            raise RuntimeError("java.util.concurrent.RejectedExecutionException: pool is shut down")
        task.fork()
        return task

    def shutdown(self) -> None:
        self._shutdown = True

    def shutdownNow(self) -> None:
        self._shutdown = True

    def isShutdown(self) -> bool:
        return self._shutdown

    def isTerminated(self) -> bool:
        # 替身为同步执行：调用 shutdown 时必然已无任务在跑
        return self._shutdown

    def getParallelism(self) -> int:
        return self._parallelism
