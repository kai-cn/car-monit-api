# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.ThreadPoolConfig

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/ThreadPoolConfig.java

【Java→Python】整体说明
1) Spring 的 ``@Configuration`` + ``@Bean("threadTaskExecutor")`` → 本模块提供
   ``ThreadPoolConfig.taskExecutor()`` 工厂方法，由启动代码调用后
   通过 ``SpringUtils.register_bean("threadTaskExecutor", executor)`` 注入容器替身。
2) ``ThreadPoolTaskExecutor`` 与 ``ThreadPoolExecutor.CallerRunsPolicy`` 都是**框架替身**，
   已按 Java 的真实包路径拆分到
   ``org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor`` 与
   ``java.util.concurrent.ThreadPoolExecutor``，因此下面的 import 与 Java 逐字对应。
3) ``Runtime.getRuntime().availableProcessors()`` → ``os.cpu_count() or 1``。
4) ``CallerRunsPolicy``（队列满后由调用线程自己执行）→ Python 线程池没有拒绝策略：
   ``submit`` 在 max_workers 满时只会排队；替身里的 ``execute_with_policy``
   用 ``queueCapacity`` 近似判断“队列已满则由调用线程执行”。
5) ``setWaitForTasksToCompleteOnShutdown`` + ``setAwaitTerminationSeconds`` →
   ``shutdown(wait=True)`` + ``_await_termination(seconds)``。
6) Java 里 Spring 容器会在 Bean 初始化阶段调用 ``afterPropertiesSet()``；
   Python 侧显式调用 ``executor.initialize()``（替身中 define 的等价动作）。
"""
from __future__ import annotations

import os

from java.util.concurrent.ThreadPoolExecutor import ThreadPoolExecutor
from org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor import ThreadPoolTaskExecutor

__all__ = ["ThreadPoolConfig"]


class ThreadPoolConfig:
    """线程池配置。"""

    def taskExecutor(self) -> ThreadPoolTaskExecutor:
        executor = ThreadPoolTaskExecutor()
        core_pool_size = (os.cpu_count() or 1) * 2
        executor.setCorePoolSize(core_pool_size)
        executor.setMaxPoolSize(core_pool_size * 3)
        # 使用 SynchronousQueue 确保立即拒绝超额任务（Java 注释原样保留；
        # Python 线程池没有可替换队列，queueCapacity 仅用于 execute_with_policy 判断）
        executor.setQueueCapacity(1000)
        executor.setKeepAliveSeconds(60)
        executor.setThreadNamePrefix("ThreadTask-")
        executor.setRejectedExecutionHandler(ThreadPoolExecutor.CallerRunsPolicy())
        # 重要修改！
        executor.setWaitForTasksToCompleteOnShutdown(True)
        executor.setAwaitTerminationSeconds(60)
        # Java: Spring 容器在初始化 Bean 时调用 afterPropertiesSet()
        executor.initialize()
        return executor
