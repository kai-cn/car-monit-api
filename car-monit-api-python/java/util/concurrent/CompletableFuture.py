# -*- coding: utf-8 -*-
"""java.util.concurrent.CompletableFuture

【无 Java 源文件：框架类替身】
Java 侧来自 JDK 8：`java.util.concurrent.CompletableFuture<T>`。
业务代码典型用法（HighPerformanceSyncService / TimeRangeParallelQueryExample）：
    CompletableFuture<List<OdsSzdnGantry>> f = CompletableFuture.supplyAsync(
            odsSzdnGantryService::getGantryRedis, executorService);
    CompletableFuture.allOf(f1, f2, f3).join();
    futures.stream().map(CompletableFuture::join).flatMap(List::stream)...

【Java→Python 关键差异】
1) Java 的 supplyAsync 把任务丢进 executor 后**立刻返回**，不阻塞；
   Python 侧同样：先 `ExecutorService.submit`，再用本类包装 Future。
   `executor` 为 None 时用进程级 commonPool 近似 ForkJoinPool.commonPool()。
2) `join()` 抛的是非受检的 CompletionException；`get()` 抛受检的
   ExecutionException/InterruptedException。这里两者都直接重抛原始异常，
   不做包装（Python 无受检异常，包装只会让栈更难读）。
3) `allOf` 在 Java 里返回 `CompletableFuture<Void>`；Python 用 join() 返回 None 表达。
   任一子任务异常时，allOf().join() 在 Java 里会抛 CompletionException；
   本替身按 java 实现“第一个异常即抛”，但其余任务不会被取消（Java 也不取消）。
4) `thenApply/thenAccept/exceptionally` 在 Java 里可能由完成线程或调用线程执行；
   这里统一在**调用线程**同步执行（简化，不影响本工程的用法）。
"""
from __future__ import annotations

from typing import Any, Callable, Generic, List, Optional, TypeVar

from java.util.concurrent.ExecutorService import ExecutorService, Future
from java.util.concurrent.Executors import Executors

T = TypeVar("T")

__all__ = ["CompletableFuture"]

# 等价 ForkJoinPool.commonPool()：进程级共享、惰性创建
_COMMON_POOL: Optional[ExecutorService] = None


def _commonPool() -> ExecutorService:
    global _COMMON_POOL
    if _COMMON_POOL is None:
        _COMMON_POOL = Executors.newCachedThreadPool()
    return _COMMON_POOL


class CompletableFuture(Generic[T]):
    """`CompletableFuture<T>` 的最小替身。"""

    def __init__(self, future: Optional[Future] = None, value: Any = None,
                 error: Optional[BaseException] = None) -> None:
        self._future = future
        self._value = value
        # 【Java→Python】Java 的 CompletableFuture 可以处于“异常完成”状态；
        # 这里用 _error 字段表达，使 thenAccept/thenApply 能“不当场抛、只沿链路传递异常”。
        self._error = error

    # ------------------------------------------------------------------ 创建
    @staticmethod
    def supplyAsync(fn: Callable[[], T], executor: Optional[ExecutorService] = None) -> "CompletableFuture[T]":
        pool = executor or _commonPool()
        return CompletableFuture(future=pool.submit(fn))

    @staticmethod
    def runAsync(fn: Callable[[], Any], executor: Optional[ExecutorService] = None) -> "CompletableFuture[None]":
        pool = executor or _commonPool()
        return CompletableFuture(future=pool.submit(fn))

    @staticmethod
    def completedFuture(value: T) -> "CompletableFuture[T]":
        return CompletableFuture(value=value)

    @staticmethod
    def allOf(*futures: "CompletableFuture[Any]") -> "CompletableFuture[None]":
        """等价 allOf(...)：全部完成后才完成（任一异常则抛出）。"""
        for future in futures:
            future.join()
        return CompletableFuture(value=None)

    @staticmethod
    def anyOf(*futures: "CompletableFuture[Any]") -> "CompletableFuture[Any]":
        """等价 anyOf(...)：返回第一个完成的（本替身简化为按顺序取第一个）。"""
        return CompletableFuture(value=futures[0].join() if futures else None)

    # ------------------------------------------------------------------ 取值
    def join(self) -> T:
        if self._error is not None:
            raise self._error
        if self._future is not None:
            return self._future.join()
        return self._value

    def get(self, timeout: Optional[int] = None, unit: Any = None) -> T:
        if self._error is not None:
            raise self._error
        if self._future is not None:
            return self._future.get(timeout, unit)
        return self._value

    def isDone(self) -> bool:
        if self._error is not None:
            return True
        return self._future.isDone() if self._future is not None else True

    # ------------------------------------------------------------------ 链式
    def thenApply(self, fn: Callable[[T], Any]) -> "CompletableFuture[Any]":
        """同步变换（对应 `future.thenApply(fn)`）。

        【Java→Python】源 future 异常完成时，Java 的 thenApply **不会**当场抛异常，
        而是返回一个同样异常完成的新阶段；因此这里捕获后转存为 _error。
        """
        try:
            return CompletableFuture(value=fn(self.join()))
        except BaseException as error:  # noqa: BLE001 - 对应 Java 的 Throwable
            return CompletableFuture(error=error)

    def thenAccept(self, fn: Callable[[T], Any]) -> "CompletableFuture[None]":
        """同步消费（对应 `future.thenAccept(fn)`）。

        【Java→Python】与 thenApply 同理：源 future 失败时不执行 fn、不抛异常，
        只把异常传给下游阶段。PulsarProducerService 正是靠这一语义，让
        `thenAccept(成功回调)` 与 `exceptionally(失败回调)` 各自只跑一个。
        """
        try:
            fn(self.join())
        except BaseException as error:  # noqa: BLE001
            return CompletableFuture(error=error)
        return CompletableFuture(value=None)

    def exceptionally(self, fn: Callable[[BaseException], Any]) -> "CompletableFuture[Any]":
        """异常兜底：正常则透传结果，异常则用 fn 的返回值作为结果。"""
        try:
            return CompletableFuture(value=self.join())
        except BaseException as error:  # noqa: BLE001 - 对应 Java 的 Throwable
            return CompletableFuture(value=fn(error))

    def whenComplete(self, fn: Callable[[Any, Optional[BaseException]], Any]) -> "CompletableFuture[Any]":
        """完成后回调（正常/异常都会执行）。"""
        try:
            value = self.join()
        except BaseException as error:  # noqa: BLE001
            fn(None, error)
            raise
        fn(value, None)
        return CompletableFuture(value=value)
