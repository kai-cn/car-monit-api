# -*- coding: utf-8 -*-
"""java.util.concurrent.ExecutorService / java.util.concurrent.Future

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：
    java.util.concurrent.ExecutorService
    java.util.concurrent.Future
业务代码典型用法：
    ExecutorService executorService = Executors.newFixedThreadPool(4);
    executorService.submit(this::fullSync);          // Runnable
    Future<T> future = executorService.submit(callable);
    executorService.shutdown();
    executorService.awaitTermination(30, TimeUnit.SECONDS);

【Java→Python 关键差异】
1) Java 的线程池是**守护/非守护线程**可配的；本替身一律创建 `daemon=True` 的工作线程，
   这样主线程结束后进程可以立即退出 —— 与 Spring Boot 里 `newFixedThreadPool` 的
   @PostConstruct 后台任务 + `Thread.setDaemon(true)` 的实际生产表现一致，
   也避免 Python 在解释器退出时被非守护线程（concurrent.futures 的行为）卡住。
2) Java 的 `Future.get()` 抛 `ExecutionException`（包装原始异常）、超时抛 `TimeoutException`；
   Python 没有受检异常，这里直接**重抛原始异常**，超时抛 `TimeoutError`。
3) `submit(Runnable)` 与 `submit(Callable<T>)` 是两个重载，Python 用同一个
   `submit(fn, *args)` 表达（返回值统一为 Future）。
4) 任务队列用 `queue.Queue`；`shutdown()` 表示“不再接收新任务”，
   正在排队的任务仍会执行完（与 Java 语义一致）。
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable, Generic, List, Optional, TypeVar

T = TypeVar("T")

__all__ = ["Future", "ExecutorService", "RejectedExecutionException"]


class RejectedExecutionException(RuntimeError):
    """java.util.concurrent.RejectedExecutionException 的替身。"""


class Future(Generic[T]):
    """`java.util.concurrent.Future<T>` 的替身（一次性完成的异步结果）。"""

    def __init__(self) -> None:
        self._done = threading.Event()
        self._result: Optional[T] = None
        self._error: Optional[BaseException] = None
        self._cancelled = False

    # ------------------------------------------------------------------ 取值
    def get(self, timeout: Optional[int] = None, unit: Any = None) -> T:
        """阻塞取值：超时抛 TimeoutError，任务异常则重抛原始异常。"""
        seconds = None if timeout is None else unit.toSeconds(timeout)
        if not self._done.wait(seconds):
            raise TimeoutError("future 等待超时")
        if self._cancelled:
            raise RuntimeError("java.util.concurrent.CancellationException")
        if self._error is not None:
            raise self._error
        return self._result  # type: ignore[return-value]

    def join(self) -> T:
        """`CompletableFuture.join()` 的语义：等待并返回，异常时重抛。"""
        return self.get()

    # ------------------------------------------------------------------ 状态
    def isDone(self) -> bool:
        return self._done.is_set()

    def isCancelled(self) -> bool:
        return self._cancelled and not self._done.is_set()

    def cancel(self, may_interrupt_if_running: bool = True) -> bool:
        """取消任务：已开始执行的任务在 Python 里无法安全中断，返回 False（尽力而为）。"""
        if self._done.is_set():
            return False
        self._cancelled = True
        self._done.set()
        return True

    # ------------------------------------------------------------------ 内部
    def _setResult(self, value: T) -> None:
        self._result = value
        self._done.set()

    def _setException(self, error: BaseException) -> None:
        self._error = error
        self._done.set()


class ExecutorService(object):
    """`java.util.concurrent.ExecutorService` 的替身（固定大小线程池）。"""

    _pool_seq = 0  # Java 的 pool-N-thread-M 里的 N

    def __init__(self, core_pool_size: int, thread_factory: Any = None) -> None:
        self._core_pool_size = max(1, int(core_pool_size))
        self._thread_factory = thread_factory
        self._tasks: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._shutdown = False
        self._pool_index = 0
        # 与 Java 默认线程名 pool-N-thread-M 对齐：N 为线程池全局序号
        ExecutorService._pool_seq += 1
        self._pool_number = ExecutorService._pool_seq

    # ------------------------------------------------------------------ 提交
    def submit(self, fn: Callable[..., Any], *args: Any) -> Future:
        """提交任务（等价 Runnable/Callable 两个重载）。"""
        with self._lock:
            if self._shutdown:
                raise RejectedExecutionException("线程池已 shutdown，拒绝新任务")
            future: Future = Future()
            self._tasks.put((fn, args, future))
            self._startWorkersIfNeeded()
        return future

    def execute(self, fn: Callable[..., Any], *args: Any) -> None:
        """等价 `execute(Runnable)`：无返回值，异常由工作线程吞掉并打印。"""
        self.submit(fn, *args)

    def invokeAll(self, fns: List[Callable[[], Any]]) -> List[Future]:
        """等价 invokeAll(Collection<Callable<T>>)：提交后等全部完成。"""
        futures = [self.submit(fn) for fn in fns]
        for future in futures:
            future.get()
        return futures

    # ------------------------------------------------------------------ 生命周期
    def shutdown(self) -> None:
        """不再接收新任务；排队中的任务继续执行完。"""
        with self._lock:
            self._shutdown = True
            for _ in self._workers:
                self._tasks.put(None)

    def shutdownNow(self) -> List[Any]:
        """清空未执行任务并终止工作线程，返回未执行的任务列表。"""
        pending: List[Any] = []
        while True:
            try:
                item = self._tasks.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                pending.append(item[0])
        with self._lock:
            self._shutdown = True
            for _ in self._workers:
                self._tasks.put(None)
        return pending

    def awaitTermination(self, timeout: int, unit: Any) -> bool:
        """等待所有工作线程结束；返回是否在超时前全部结束。"""
        deadline = None
        if unit is not None:
            deadline = time.time() + unit.toSeconds(timeout)
        for worker in list(self._workers):
            remaining = None if deadline is None else max(0.0, deadline - time.time())
            worker.join(remaining)
            if worker.is_alive():
                return False
        return True

    def isShutdown(self) -> bool:
        return self._shutdown

    def isTerminated(self) -> bool:
        return self._shutdown and all(not worker.is_alive() for worker in self._workers)

    # ------------------------------------------------------------------ 工作线程
    def _startWorkersIfNeeded(self) -> None:
        while len(self._workers) < self._core_pool_size:
            self._pool_index += 1
            worker = self._newThread(
                self._workerLoop, "pool-%d-thread-%d" % (self._pool_number, self._pool_index)
            )
            self._workers.append(worker)
            worker.start()

    def _newThread(self, target: Callable[[], None], default_name: str) -> threading.Thread:
        if self._thread_factory is not None:
            created = self._thread_factory.newThread(target)
            # Java 的 ThreadFactory 可以返回任意 Thread；Python 只能启动 threading.Thread
            if isinstance(created, threading.Thread):
                created.daemon = True
                return created
        return threading.Thread(target=target, name=default_name, daemon=True)

    def _workerLoop(self) -> None:
        while True:
            item = self._tasks.get()
            if item is None:
                return
            fn, args, future = item
            if future.isCancelled():
                continue
            try:
                future._setResult(fn(*args))
            except BaseException as error:  # noqa: BLE001  与 Java 一致：异常记录在 Future 里
                future._setException(error)
