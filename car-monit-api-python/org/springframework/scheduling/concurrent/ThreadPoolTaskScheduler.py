# -*- coding: utf-8 -*-
"""org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler

【无 Java 源文件：框架类替身】
Java 侧来自 spring-context：`org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler`，
SchedulingConfig 里做初始化：
    ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
    scheduler.setPoolSize(10);
    scheduler.setThreadNamePrefix("scheduler-");
    scheduler.setWaitForTasksToCompleteOnShutdown(true);
    scheduler.setAwaitTerminationSeconds(60);
    scheduler.initialize();
    taskRegistrar.setTaskScheduler(scheduler);

`@Scheduled(cron = ...)` 最终经 `ScheduledTaskRegistrar` 落到
`schedule(Runnable, Trigger)`；`fixedRate` / `fixedDelay` 落到
`scheduleAtFixedRate` / `scheduleWithFixedDelay`。

【Java→Python 关键差异】
1) Spring 内部是 `ScheduledThreadPoolExecutor`（定时线程池：一个任务占一个池线程，
   按 Date / Trigger 反复调度）。Python 标准库没有等价物，替身用
   **队列 + poolSize 个守护工作线程**（`execute`/`submit`）+ **每个定时任务一条守护线程**
   （`schedule*`）来还原。定时任务不再占用工作线程，因此 poolSize 只约束
   `execute`/`submit` 的并发度 —— 本工程没有任何代码向 TaskScheduler 投递一次性任务，
   该差异不影响行为。
2) **执行异常后是否继续**：`@Scheduled` 走的是 `ReschedulingRunnable`，它用
   `LOG_AND_SUPPRESS_ERROR_HANDLER` 捕掉 Throwable 后**仍然重排下一次**。
   替身同样“记录后继续”；只有直接投给 `ScheduledExecutorService` 的周期任务
   才会因异常终止 —— 本工程没有这种用法。
3) **线程守护属性**：Spring 默认 `daemon=false`，JVM 靠 shutdown hook 与
   `System.exit` 收尾；Python 没有强制退出机制，非守护线程会让解释器**永远退不出**
   （定时任务正卡在等待下一次触发上）。因此替身默认 `daemon=True`
   （等价显式 `setDaemon(true)`），并保留 `setDaemon` 以对齐 Spring 的 setter。
4) `getPoolSize()` 在 Java 返回**存活线程数**（线程懒创建，初始为 0）；
   替身返回配置值 10，让启动日志有意义（差异已在方法注释中标明）。
5) `shutdown()` 在 Java 里 `ScheduledThreadPoolExecutor` 会**取消所有周期任务**
   （`continueExistingPeriodicTasksAfterShutdown` 默认 false），替身同样先
   `cancel()` 全部 `ScheduledFuture`，再按 `waitForTasksToCompleteOnShutdown` /
   `awaitTerminationSeconds` 决定是否等待。
6) 时间参数：Java 是 `java.util.Date` + 毫秒；Python 统一用 `datetime` + 毫秒（等价）。
   `schedule(Runnable, Trigger)` 与 `schedule(Runnable, Date)` 在 Java 是**重载**，
   Python 无重载，靠 `start_time` 的类型鸭子判定区分。
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future
from datetime import datetime
from typing import Any, Callable, List, Optional

from org.springframework.scheduling.support.CronTrigger import TriggerContext

log = logging.getLogger(__name__)

__all__ = ["ThreadPoolTaskScheduler", "ScheduledFuture"]


class ScheduledFuture(object):
    """``java.util.concurrent.ScheduledFuture`` 的最小替身。

    除了 ``cancel`` / ``isCancelled``，额外提供 ``wait(timeout)``：
    调度循环用它等待下一次触发，`cancel()` 会立即唤醒，因此 ``shutdown()``
    不必等满一个调度周期。
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._done = False
        self._cancelEvent = threading.Event()

    def cancel(self, may_interrupt_if_running: bool = False) -> bool:
        if self._cancelled or self._done:
            # Java 的 cancel 返回“是否成功取消”（已取消/已完成返回 false）
            return False
        self._cancelled = True
        self._cancelEvent.set()
        return True

    def isCancelled(self) -> bool:
        return self._cancelled

    def isDone(self) -> bool:
        return self._done or self._cancelled

    def markDone(self) -> None:
        """调度循环自然结束（Trigger 返回 null）时置位。"""
        self._done = True
        self._cancelEvent.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """等待 ``timeout`` 秒；返回 True 表示期间已被取消（调用方应退出循环）。"""
        self._cancelEvent.wait(timeout)
        return self._cancelled


class ThreadPoolTaskScheduler(object):
    """`ThreadPoolTaskScheduler` 的替身。"""

    def __init__(self) -> None:
        self.poolSize = 1
        self.threadNamePrefix = ""
        self.waitForTasksToCompleteOnShutdown = False
        self.awaitTerminationSeconds = 0
        self.removeOnCancelPolicy = False
        self.daemon = True
        self._queue: Optional[queue.Queue] = None
        self._workers: List[threading.Thread] = []
        self._loops: List[threading.Thread] = []
        self._futures: List[ScheduledFuture] = []
        self._stopped = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setter
    def setPoolSize(self, pool_size: int) -> None:
        self.poolSize = pool_size

    def setThreadNamePrefix(self, thread_name_prefix: str) -> None:
        self.threadNamePrefix = thread_name_prefix

    def setWaitForTasksToCompleteOnShutdown(self, wait: bool) -> None:
        self.waitForTasksToCompleteOnShutdown = wait

    def setAwaitTerminationSeconds(self, seconds: int) -> None:
        self.awaitTerminationSeconds = seconds

    def setRemoveOnCancelPolicy(self, remove_on_cancel: bool) -> None:
        self.removeOnCancelPolicy = remove_on_cancel

    def setDaemon(self, daemon: bool) -> None:
        """对应 `setDaemon(boolean)`（见文件头第 3 条：替身默认 True）。"""
        self.daemon = daemon

    def isDaemon(self) -> bool:
        return self.daemon

    # ------------------------------------------------------------------ 生命周期
    def initialize(self) -> None:
        """对应 Spring 的 ``afterPropertiesSet()`` / init-method（幂等）。"""
        with self._lock:
            if self._workers:
                return
            self._stopped.clear()
            self._queue = queue.Queue()
            self._workers = []
            for index in range(max(1, self.poolSize)):
                worker = threading.Thread(
                    target=self._workerLoop,
                    name="%s%s" % (self.threadNamePrefix, index + 1),
                    daemon=self.daemon,
                )
                worker.start()
                self._workers.append(worker)

    def _ensure(self) -> queue.Queue:
        if self._queue is None:
            self.initialize()
        return self._queue  # type: ignore[return-value]

    def getPoolSize(self) -> int:
        """【Java→Python】Java 返回存活线程数（懒创建，未跑任务时为 0）；
        替身返回配置值，让 SchedulingConfig 的启动日志能直接反映线程池大小。
        """
        return self.poolSize

    def getActiveCount(self) -> int:
        return sum(1 for worker in self._workers if worker.is_alive())

    def getScheduledThreadPoolExecutor(self) -> Any:
        """Java 返回底层 ``ScheduledThreadPoolExecutor``；替身没有该对象，返回自身。"""
        self._ensure()
        return self

    def shutdown(self) -> None:
        """对应 ``shutdown()``：先取消全部周期任务，再按配置等待收尾。"""
        self._stopped.set()
        with self._lock:
            futures = list(self._futures)
            loops = list(self._loops)
        for future in futures:
            future.cancel(False)

        deadline = None
        if self.waitForTasksToCompleteOnShutdown:
            deadline = time.monotonic() + max(0, self.awaitTerminationSeconds)

        for thread in loops + self._workers:
            if thread is threading.current_thread():
                continue
            timeout = None if deadline is None else max(0.0, deadline - time.monotonic())
            # waitForTasksToCompleteOnShutdown=false 时也短暂 join，避免线程泄漏
            thread.join(timeout=timeout if timeout is not None else 1.0)

        with self._lock:
            self._workers = []
            self._loops = []
            self._queue = None

    def _workerLoop(self) -> None:
        """工作线程：从队列取任务执行（等价线程池的 worker）。"""
        work_queue = self._queue
        while work_queue is not None:
            try:
                task = work_queue.get(block=True, timeout=0.1)
            except queue.Empty:
                if self._stopped.is_set() and work_queue.empty():
                    return
                continue
            try:
                task()
            except BaseException:  # noqa: BLE001 - 与线程池一致：单个任务异常不杀 worker
                log.exception("scheduler worker task failed")
            finally:
                work_queue.task_done()

    # ------------------------------------------------------------------ 提交
    def execute(self, task: Callable[[], Any]) -> None:
        """对应 ``execute(Runnable)``：无返回值。"""
        self._ensure().put(task)

    def submit(self, task: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        """对应 ``submit(Callable)``：返回 ``Future``。"""
        future: Future = Future()

        def _call() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(task(*args, **kwargs))
            except BaseException as error:  # noqa: BLE001 - 异常要回传给 Future
                future.set_exception(error)

        self.execute(_call)
        return future

    # ------------------------------------------------------------------ 调度
    def schedule(self, task: Callable[[], Any], start_time: Any = None) -> ScheduledFuture:
        """等价 ``schedule(Runnable, Date|Instant|Trigger)`` 的重载集合。

        【Java→Python】Java 靠重载区分第二参数；Python 用鸭子判定：
        - 带 ``next_execution_time`` 的对象 → 按 Trigger 反复调度（cron）
        - ``datetime`` → 到点执行一次
        - ``None`` → 立即执行一次
        """
        if start_time is not None and hasattr(start_time, "next_execution_time"):
            return self._scheduleTrigger(task, start_time)
        if isinstance(start_time, datetime):
            return self._startLoop(task, start_time.timestamp(), 0, False, once=True)
        return self._startLoop(task, None, 0, False, once=True)

    def scheduleAtFixedRate(self, task: Callable[[], Any],
                            start_time: Optional[datetime], period_ms: int) -> ScheduledFuture:
        """等价 ``scheduleAtFixedRate(Runnable, Date, long)``：固定频率（以开始时间为基准）。"""
        start_epoch = start_time.timestamp() if isinstance(start_time, datetime) else None
        return self._startLoop(task, start_epoch, period_ms, fixed_rate=True)

    def scheduleWithFixedDelay(self, task: Callable[[], Any],
                               start_time: Optional[datetime], delay_ms: int) -> ScheduledFuture:
        """等价 ``scheduleWithFixedDelay(Runnable, Date, long)``：上次结束后再等 delay。"""
        start_epoch = start_time.timestamp() if isinstance(start_time, datetime) else None
        return self._startLoop(task, start_epoch, delay_ms, fixed_rate=False)

    # ------------------------------------------------------------------ 内部
    def _newLoopThread(self, target: Callable[[], None], name: str) -> threading.Thread:
        thread = threading.Thread(target=target, name=name, daemon=self.daemon)
        with self._lock:
            self._loops.append(thread)
        thread.start()
        return thread

    def _runTask(self, task: Callable[[], Any], label: str) -> None:
        try:
            task()
        except BaseException:  # noqa: BLE001 - Spring: LOG_AND_SUPPRESS_ERROR_HANDLER
            log.exception("[Scheduled] 定时任务执行异常: %s", label)

    def _scheduleTrigger(self, task: Callable[[], Any], trigger: Any) -> ScheduledFuture:
        """等价 ``schedule(Runnable, Trigger)``：每轮由 Trigger 计算下一次时刻。"""
        future = ScheduledFuture()
        with self._lock:
            self._futures.append(future)
        context = TriggerContext()
        label = getattr(task, "__name__", "task")

        def _loop() -> None:
            while not future.isCancelled():
                next_time = trigger.next_execution_time(context)
                if next_time is None:
                    # Trigger 返回 null → 不再重排（CronExpression 8 年内无匹配）
                    future.markDone()
                    return
                wait_seconds = next_time.timestamp() - time.time()
                if wait_seconds > 0 and future.wait(wait_seconds):
                    return
                if future.isCancelled():
                    return
                actual = datetime.now()
                self._runTask(task, label)
                context.update(next_time, actual, datetime.now())

        self._newLoopThread(_loop, "%s%s" % (self.threadNamePrefix, label))
        return future

    def _startLoop(self, task: Callable[[], Any], start_epoch: Optional[float],
                   interval_ms: int, fixed_rate: bool,
                   once: bool = False) -> ScheduledFuture:
        """固定频率/固定延迟/一次性执行的循环。"""
        future = ScheduledFuture()
        with self._lock:
            self._futures.append(future)
        interval_seconds = max(interval_ms, 1) / 1000.0
        label = getattr(task, "__name__", "task")

        def _loop() -> None:
            # 等到首次执行时刻（Java 的 startTime 语义）
            if start_epoch is not None:
                wait = start_epoch - time.time()
                if wait > 0 and future.wait(wait):
                    return
            if once:
                self._runTask(task, label)
                future.markDone()
                return

            next_epoch = time.time()
            while not future.isCancelled():
                self._runTask(task, label)
                if fixed_rate:
                    # Java 的 PeriodicTrigger: 下一次 = 上次**计划**时刻 + 周期；
                    # 任务超时则立即补跑（ScheduledThreadPoolExecutor 视负延迟为 0）
                    next_epoch += interval_seconds
                    sleep_seconds = next_epoch - time.time()
                else:
                    sleep_seconds = interval_seconds
                if sleep_seconds > 0 and future.wait(sleep_seconds):
                    return
            future.markDone()

        self._newLoopThread(_loop, "%s%s" % (self.threadNamePrefix, label))
        return future
