# -*- coding: utf-8 -*-
"""com.ruoyi.base.config.SchedulingConfig

源文件：pro-business-api/src/main/java/com/ruoyi/base/config/SchedulingConfig.java

定时任务配置类

功能说明：
1. 启用 Spring 定时任务功能
2. 配置定时任务线程池，避免任务阻塞
3. 设置合理的线程池大小和队列容量

设计思路：
- 使用专用线程池执行定时任务，避免影响主线程
- 设置适当的线程数，根据任务类型调整
- 配置线程名称前缀，便于日志追踪

【Java→Python】整体说明
1) ``@Configuration`` + ``@EnableScheduling`` → Python 无容器/无注解：
   - ``@EnableScheduling`` 的语义（注册 ScheduledAnnotationBeanPostProcessor）
     在替身里等价于「启动时调用一次 ``SchedulingConfig().configureTasks(...)``」；
   - 本类的 ``__init__`` 主动创建 ``ScheduledTaskRegistrar`` 并调用
     ``configureTasks``，模拟 Spring 容器 refresh 时的回调时机（Java 由容器调用）。
2) ``implements SchedulingConfigurer`` → 继承 ``SchedulingConfigurer``（ABC），
   ``@Override configureTasks(...)`` 用 ``@abstractmethod`` 的实现在子类中还原。
   注意：Java 写错方法名会编译失败；Python 漏实现则**实例化时**抛 TypeError。
3) ``ThreadPoolTaskScheduler`` → 替身类（见 org.springframework.scheduling.concurrent），
   内部用 ``ThreadPoolExecutor`` + 守护循环模拟定时调度。
4) ``log.info("[定时任务配置] 线程池初始化完成，线程数: {}", ...)``：
   SLF4J 用 ``{}`` 占位符（**位置**绑定），Python logging 用 ``%s``（**惰性格式化**）——
   两者都必须用“参数传入”而不是 f-string 拼接，否则日志级别关闭时仍会做字符串拼接。
5) ``scheduler.getPoolSize()`` 在 Java 里返回**存活线程数**（线程懒创建，此刻通常是 0）；
   Python 替身返回配置值 10（差异已在替身类注释中标注）。
"""
from __future__ import annotations

import logging

from org.springframework.scheduling.annotation.SchedulingConfigurer import SchedulingConfigurer
from org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler import ThreadPoolTaskScheduler
from org.springframework.scheduling.config.ScheduledTaskRegistrar import ScheduledTaskRegistrar

log = logging.getLogger(__name__)

__all__ = ["SchedulingConfig"]


class SchedulingConfig(SchedulingConfigurer):
    """定时任务配置。"""

    def __init__(self) -> None:
        # 【Java→Python】Java 由容器在 refresh 阶段创建本 Bean 并调用 configureTasks；
        # Python 无容器，这里显式建一个登记表并调用，等价“容器启动时执行一次”。
        # 真正的任务登记与启动在 ``app/scheduler``（start_scheduler）：它复用本对象的
        # taskRegistrar 里的 ThreadPoolTaskScheduler，扫描 @Scheduled 方法后调用
        # ScheduledTaskRegistrar#afterPropertiesSet 排期。
        self.taskRegistrar = ScheduledTaskRegistrar()
        self.configureTasks(self.taskRegistrar)

    def configureTasks(self, taskRegistrar: ScheduledTaskRegistrar) -> None:
        """配置定时任务线程池。

        思路：
        1. 创建 ThreadPoolTaskScheduler 作为定时任务执行器
        2. 设置线程池大小为 10，可根据实际任务数量调整
        3. 设置线程名称前缀为 "scheduler-"，便于日志追踪
        4. 配置等待任务完成后再关闭线程池

        :param taskRegistrar: 任务注册器
        """
        scheduler = ThreadPoolTaskScheduler()

        # 设置线程池大小
        scheduler.setPoolSize(10)

        # 设置线程名称前缀
        scheduler.setThreadNamePrefix("scheduler-")

        # 设置等待所有任务完成后再关闭线程池
        scheduler.setWaitForTasksToCompleteOnShutdown(True)

        # 设置等待时间（秒）
        scheduler.setAwaitTerminationSeconds(60)

        # 初始化线程池
        # 【Java→Python】Java 里 initialize() 之后线程池已创建但线程懒启动；
        # Python 替身同样在此处创建 ThreadPoolExecutor（线程仍按需创建）。
        scheduler.initialize()

        # 将线程池设置到任务注册器
        taskRegistrar.setTaskScheduler(scheduler)

        # 【Java→Python】SLF4J 的 "{}" → logging 的 "%s"（参数化日志，非 f-string）
        log.info("[定时任务配置] 线程池初始化完成，线程数: %s", scheduler.getPoolSize())

    # ------------------------------------------------------------------ 兼容容器语义
    def shutdown(self) -> None:
        """对应容器关闭时 ``ThreadPoolTaskScheduler`` 的 destroy（Java 由 Spring 调用）。

        【Java→Python】Java 里 @Bean 的 destroyMethod 由容器自动触发；
        Python 需要显式调用（例如进程退出钩子）。
        """
        scheduler = self.taskRegistrar.getTaskScheduler()
        if scheduler is not None and hasattr(scheduler, "shutdown"):
            scheduler.shutdown()
