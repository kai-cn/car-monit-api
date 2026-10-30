# -*- coding: utf-8 -*-
"""org.springframework.scheduling.config.ScheduledTaskRegistrar

【无 Java 源文件：框架类替身】
Java 侧来自 spring-context：`org.springframework.scheduling.config.ScheduledTaskRegistrar`。
SchedulingConfig 只调用了两处：
    public void configureTasks(ScheduledTaskRegistrar taskRegistrar) { ... }
    taskRegistrar.setTaskScheduler(scheduler);

【Java→Python 关键差异】
1) Java 的 ScheduledTaskRegistrar 是 Spring 内部的“任务登记表”：容器把
   ``@Scheduled`` 注解解析成 Runnable/CronTask 后登记进来，最后由
   ``afterPropertiesSet()`` 用 taskScheduler 真正排期。
2) Python 没有注解扫描，本工程用 ``com.ruoyi.base.task`` 下的 Task 类 +
   显式调用（或者 ``SchedulingConfig`` 手动 register）来替代；因此本替身只保留
   **登记 + 使用 taskScheduler 排期** 的最小能力。
3) ``setTaskScheduler(TaskScheduler)`` 在 Java 里接收接口类型；Python 侧
   鸭子类型，直接接收 ``ThreadPoolTaskScheduler`` / ``ThreadPoolTaskExecutor``。
4) Cron 支持：``addCronTask(Runnable, String)`` / ``getCronTaskList()`` 与 Java 同名，
   内部把表达式包成 ``CronTrigger``（``org.springframework.scheduling.support``），
   在 ``afterPropertiesSet()`` 里交给 ``taskScheduler.schedule(task, trigger)``。
   Java 的 ``CronTask`` 对象在替身里退化成 ``(runnable, trigger)`` 二元组。
5) ``afterPropertiesSet()`` 在 Java 里由 ``InitializingBean`` 调用一次；替身用
   ``_started`` 保证**重复调用不会重复排期**（``app/scheduler`` 的 ``start_scheduler``
   因此是幂等的），对应 Spring 容器只 refresh 一次的事实。
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

from org.springframework.scheduling.support.CronExpression import CronExpression
from org.springframework.scheduling.support.CronTrigger import CronTrigger

__all__ = ["ScheduledTaskRegistrar"]


class ScheduledTaskRegistrar(object):
    """`ScheduledTaskRegistrar` 的替身。"""

    def __init__(self) -> None:
        self.taskScheduler: Any = None
        # 对应 Java 的 List<IntervalTask> fixedRateTasks / fixedDelayTasks
        self._fixed_rate_tasks: List[Tuple[Callable[[], Any], int, int]] = []   # (task, start_delay_ms, interval_ms)
        self._fixed_delay_tasks: List[Tuple[Callable[[], Any], int, int]] = []
        # 对应 Java 的 List<CronTask> cronTasks：(runnable, CronTrigger)
        self._cron_tasks: List[Tuple[Callable[[], Any], CronTrigger]] = []
        self._started = False

    # ------------------------------------------------------------------ 配置
    def setTaskScheduler(self, task_scheduler: Any) -> None:
        self.taskScheduler = task_scheduler

    def getTaskScheduler(self) -> Any:
        return self.taskScheduler

    # ------------------------------------------------------------------ 登记
    def addFixedRateTask(self, task: Callable[[], Any], interval_ms: int,
                         initial_delay_ms: int = 0) -> None:
        """等价 ``addFixedRateTask(Runnable, long)``（Java 侧由注解解析器调用）。"""
        self._fixed_rate_tasks.append((task, initial_delay_ms, interval_ms))

    def addFixedDelayTask(self, task: Callable[[], Any], delay_ms: int,
                          initial_delay_ms: int = 0) -> None:
        self._fixed_delay_tasks.append((task, initial_delay_ms, delay_ms))

    def addCronTask(self, task: Callable[[], Any], cron_expression: Any) -> None:
        """等价 ``addCronTask(Runnable, String)``：登记一个 cron 任务。

        ``cron_expression`` 既可以是表达式字符串（此处解析，等价 Java 的
        ``new CronTrigger(cronExpression)``），也可以直接传 ``CronTrigger``。
        """
        trigger = (CronTrigger(CronExpression.parse(cron_expression))
                   if isinstance(cron_expression, str) else cron_expression)
        self._cron_tasks.append((task, trigger))

    def getCronTaskList(self) -> List[Tuple[Callable[[], Any], CronTrigger]]:
        return list(self._cron_tasks)

    def getFixedRateTaskList(self) -> List[Tuple[Callable[[], Any], int, int]]:
        return list(self._fixed_rate_tasks)

    def getFixedDelayTaskList(self) -> List[Tuple[Callable[[], Any], int, int]]:
        return list(self._fixed_delay_tasks)

    # ------------------------------------------------------------------ 启动
    def afterPropertiesSet(self) -> None:
        """对应 Java 的 ``InitializingBean#afterPropertiesSet()``：把登记的任务排期。"""
        scheduler: Optional[Any] = self.taskScheduler
        if scheduler is None:
            # Java 在没有 TaskScheduler 时会退回默认的 single-thread scheduler；
            # 这里保持“没有调度器就不跑”的保守行为，避免隐式后台线程。
            return
        if self._started:
            return
        self._started = True
        import time
        from datetime import datetime

        for task, initial_delay_ms, interval_ms in self._fixed_rate_tasks:
            start = datetime.fromtimestamp(time.time() + initial_delay_ms / 1000.0)
            scheduler.scheduleAtFixedRate(task, start, interval_ms)
        for task, initial_delay_ms, delay_ms in self._fixed_delay_tasks:
            start = datetime.fromtimestamp(time.time() + initial_delay_ms / 1000.0)
            scheduler.scheduleWithFixedDelay(task, start, delay_ms)
        for task, trigger in self._cron_tasks:
            scheduler.schedule(task, trigger)

    def destroy(self) -> None:
        """对应 ``DisposableBean#destroy()``：容器关闭时停止调度。"""
        scheduler = self.taskScheduler
        if scheduler is not None and hasattr(scheduler, "shutdown"):
            scheduler.shutdown()
