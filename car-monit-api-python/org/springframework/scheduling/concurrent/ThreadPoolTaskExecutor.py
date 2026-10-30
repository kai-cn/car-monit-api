# -*- coding: utf-8 -*-
"""org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor

【无 Java 源文件：框架类替身】（``org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor``）

【Java→Python】关键差异
1) Spring 的 ``ThreadPoolTaskExecutor`` 是 ``ThreadPoolExecutor`` 的**配置包装**：
   setter 只记属性，``afterPropertiesSet()``（或 XML/JavaConfig 的 ``initialize()``）
   时才真正创建线程池。本替身保持同样节奏：setter 只赋值，``initialize()`` 建池。
2) ``corePoolSize`` / ``maxPoolSize`` / ``queueCapacity`` 三参数模型在
   ``concurrent.futures.ThreadPoolExecutor`` 里只有一个 ``max_workers``：
   Python 侧保留全部 setter（数值用于对照与日志），真正生效的是 maxPoolSize
   （Java 中任务超过 core 后靠队列 + max 扩容，Python 直接在 max_workers 处封顶）。
3) ``execute(Runnable)`` / ``submit(Callable)`` 都映射到 ``ThreadPoolExecutor.submit``；
   ``execute`` 按 Java 语义返回 None。
4) ``CallerRunsPolicy`` 在 Python 线程池里不存在，因此额外提供
   ``execute_with_policy``：队列已满（``_work_queue.qsize() >= queueCapacity``）时
   交给 ``rejectedExecutionHandler``（Java 的拒绝策略对象）处理。
5) ``setWaitForTasksToCompleteOnShutdown(true)`` + ``setAwaitTerminationSeconds(n)``
   → ``shutdown(wait=True)`` + 等待逻辑。
6) 本文件原先内嵌在 ``com.ruoyi.common.config.ThreadPoolConfig`` 中，
   现在按 Java 的真实包路径拆出，使 Controller/Task 的 import 与 Java 逐字对应。
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

__all__ = ["ThreadPoolTaskExecutor"]

log = logging.getLogger(__name__)


class ThreadPoolTaskExecutor:
    """Spring ``ThreadPoolTaskExecutor`` 的轻量替身。

    【Java→Python】Java 的 setter 返回 void，这里全部返回 None 以保持一致；
    真正的线程池对象在 ``initialize()`` 时创建（对应 Spring 的 afterPropertiesSet）。
    """

    def __init__(self) -> None:
        self.corePoolSize = 1
        self.maxPoolSize = 1
        self.queueCapacity = 0
        self.keepAliveSeconds = 60
        self.threadNamePrefix = ""
        self.rejectedExecutionHandler: Optional[Any] = None
        self.waitForTasksToCompleteOnShutdown = False
        self.awaitTerminationSeconds = 0
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ setter
    def setCorePoolSize(self, core_pool_size: int) -> None:
        self.corePoolSize = core_pool_size

    def setMaxPoolSize(self, max_pool_size: int) -> None:
        self.maxPoolSize = max_pool_size

    def setQueueCapacity(self, queue_capacity: int) -> None:
        self.queueCapacity = queue_capacity

    def setKeepAliveSeconds(self, keep_alive_seconds: int) -> None:
        self.keepAliveSeconds = keep_alive_seconds

    def setThreadNamePrefix(self, thread_name_prefix: str) -> None:
        self.threadNamePrefix = thread_name_prefix

    def setRejectedExecutionHandler(self, handler: Any) -> None:
        self.rejectedExecutionHandler = handler

    def setWaitForTasksToCompleteOnShutdown(self, wait: bool) -> None:
        self.waitForTasksToCompleteOnShutdown = wait

    def setAwaitTerminationSeconds(self, seconds: int) -> None:
        self.awaitTerminationSeconds = seconds

    # ------------------------------------------------------------------ 生命周期
    def initialize(self) -> None:
        """对应 Spring 容器的 init-method；重复调用是幂等的。"""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=max(1, self.maxPoolSize),
                    thread_name_prefix=self.threadNamePrefix,
                )

    def _ensure(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self.initialize()
        return self._executor  # type: ignore[return-value]

    def submit(self, task: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        """等价于 ``execute(Runnable)`` / ``submit(Callable)``（返回 Future 便于取结果）。"""
        return self._ensure().submit(task, *args, **kwargs)

    def execute(self, task: Callable[[], Any]) -> None:
        """对应 ``execute(Runnable)``：无返回值。"""
        self._ensure().submit(task)

    def execute_with_policy(self, task: Callable[[], Any]) -> None:
        """带 CallerRunsPolicy 的提交方式：队列满时由调用线程执行。

        【Java→Python】ThreadPoolExecutor 无队列容量可观测接口，
        这里用 ``_work_queue.qsize() >= queueCapacity`` 近似判断“队列已满”。
        """
        executor = self._ensure()
        queue = getattr(executor, "_work_queue", None)
        if queue is not None and self.queueCapacity > 0 and queue.qsize() >= self.queueCapacity:
            if self.rejectedExecutionHandler is not None:
                self.rejectedExecutionHandler.rejectedExecution(task, self)
            else:
                task()
            return
        executor.submit(task)

    def isShutdown(self) -> bool:
        return self._executor is None

    def shutdown(self) -> None:
        """对应 ``setWaitForTasksToCompleteOnShutdown(true)`` 的优雅关闭。"""
        if self._executor is None:
            return
        if self.waitForTasksToCompleteOnShutdown:
            self._executor.shutdown(wait=True)
        else:
            self._executor.shutdown(wait=False)
        if self.awaitTerminationSeconds > 0:
            self._await_termination(self.awaitTerminationSeconds)
        self._executor = None

    def _await_termination(self, seconds: int) -> None:
        # Python 的 shutdown(wait=True) 已阻塞至全部完成；
        # 若提前返回（wait=False），此处的语义退化为“不再额外等待”，原样注释保留。
        log.debug("awaitTerminationSeconds=%s", seconds)
