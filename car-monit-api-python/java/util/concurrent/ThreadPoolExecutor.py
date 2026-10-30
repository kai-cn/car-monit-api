# -*- coding: utf-8 -*-
"""java.util.concurrent.ThreadPoolExecutor

【无 Java 源文件：JDK 类替身】（``java.util.concurrent.ThreadPoolExecutor``）

【Java→Python】为什么需要它
Java 的 ``ThreadPoolExecutor`` 有 4 个**静态内部类**作为拒绝策略：
``CallerRunsPolicy`` / ``AbortPolicy`` / ``DiscardPolicy`` / ``DiscardOldestPolicy``。
项目里唯一用到的是 ``new ThreadPoolExecutor.CallerRunsPolicy()``
（见 ThreadPoolConfig#taskExecutor）。

Python 的 ``concurrent.futures.ThreadPoolExecutor`` **没有**“拒绝策略”概念
（任务永远排队，不会拒绝），因此这里只提供策略对象本身，
由 ``ThreadPoolTaskExecutor.execute_with_policy`` 在“队列已满”时手动调用，
以贴近 Java 的行为。

其他线程池 API（execute/submit/shutdown/...）不在本替身中重复实现 ——
它们由 ``org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor`` 包装提供。

【optimization 包补充】``CompositeQueryOptimizationService`` 直接手写构造
``new ThreadPoolExecutor(core, max, 60L, SECONDS, new LinkedBlockingQueue<>(1000),
new CallerRunsPolicy())`` 并调用 ``submit(...)``，因此本替身继承 ``ExecutorService``，
把 ``core/max/keepAlive/unit/queue/threadFactory/handler`` 全部记录下来，
任务调度复用固定池。

【构造器签名】严格按 Java 的 7 参构造顺序：
``(corePoolSize, maximumPoolSize, keepAliveTime, unit, workQueue, threadFactory, handler)``。
Java 的重载（5 参无 threadFactory/handler、6 参无 handler）在 Python 里用默认值表达；
如果只想传 handler 而不传 threadFactory，请用关键字 ``handler=...``。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from java.util.concurrent.ExecutorService import ExecutorService

__all__ = ["CallerRunsPolicy", "ThreadPoolExecutor"]


class CallerRunsPolicy:
    """``ThreadPoolExecutor.CallerRunsPolicy``：队列满时由**提交任务的线程**直接执行。"""

    def rejectedExecution(self, task: Callable[[], Any], executor: Any) -> None:
        if not executor.isShutdown():
            task()


class ThreadPoolExecutor(ExecutorService):
    """``ThreadPoolExecutor`` 的替身：记录构造参数 + 复用固定池调度。

    【Java→Python】Java 的语义：
    - 核心线程数满后任务进 ``workQueue``，队列满且达到 max 时交给 ``handler``；
    Python 没有「核心/最大线程数 + 拒绝策略」这套机制，替身把
    **maximumPoolSize 当作固定线程数**，并保存 ``workQueue``/``handler``
    供调用方或测试断言构造参数是否与原代码一致（行为上不触发 CallerRunsPolicy）。
    """

    CallerRunsPolicy = CallerRunsPolicy

    def __init__(self, core_pool_size: int, maximum_pool_size: int,
                 keep_alive_time: float = 60, unit: Any = None,
                 work_queue: Any = None, thread_factory: Any = None,
                 handler: Any = None) -> None:
        # 【Java→Python】以 maximumPoolSize 作为实际并发上限（见类注释）
        super().__init__(maximum_pool_size, thread_factory)
        self._core_pool_size = max(1, int(core_pool_size))
        self._maximum_pool_size = max(1, int(maximum_pool_size))
        self._keep_alive_time = keep_alive_time
        self._unit = unit
        self._work_queue = work_queue
        self._thread_factory = thread_factory
        self._handler = handler

    # ------------------------------------------------------------------ 参数查询
    def getCorePoolSize(self) -> int:
        return self._core_pool_size

    def getMaximumPoolSize(self) -> int:
        return self._maximum_pool_size

    def getKeepAliveTime(self, unit: Any = None) -> int:
        """对应 ``getKeepAliveTime(TimeUnit)``。

        【Java→Python】Java 会按目标单位换算；本工程只传入 ``60L + SECONDS``
        且从不读取该值，替身直接返回构造时传入的原始数值（不换算）。
        """
        return int(self._keep_alive_time)

    def getQueue(self) -> Optional[Any]:
        return self._work_queue

    def getRejectedExecutionHandler(self) -> Optional[Any]:
        return self._handler

    def getThreadFactory(self) -> Optional[Any]:
        """对应 ``getThreadFactory()``。"""
        return self._thread_factory

    def __repr__(self) -> str:
        return ("ThreadPoolExecutor(core=%d, max=%d, keepAlive=%s, queue=%r)" %
                (self._core_pool_size, self._maximum_pool_size,
                 self._keep_alive_time, self._work_queue))
