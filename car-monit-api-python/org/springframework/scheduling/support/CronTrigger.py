# -*- coding: utf-8 -*-
"""org.springframework.scheduling.support.CronTrigger

【无 Java 源文件：框架类替身】
Java 侧来自 spring-context：`org.springframework.scheduling.support.CronTrigger`
（实现 `Trigger`），由 `ScheduledTaskRegistrar#scheduleCronTask` 包装
`@Scheduled(cron = "...")` 的方法后交给 `TaskScheduler#schedule(Runnable, Trigger)`。

【Java→Python 关键差异】
1) Java 的 `Trigger` 接口只有一个方法：
       Date nextExecutionTime(TriggerContext triggerContext);
   Python 侧用同名的 `next_execution_time(ctx)`（snake_case 为 Python 惯例，
   而**框架替身的公开方法一律保留 Java 驼峰**，与 `setPoolSize` 等保持一致，
   故这里同时提供驼峰别名 `nextExecutionTime`）。
2) `TriggerContext` 在 Java 里由 `ReschedulingRunnable` 维护，记录
   「上次计划执行时刻 / 上次实际开始时刻 / 上次完成时刻」；替身同样三字段 + `update()`。
3) **首次调用**：Java 的 `SimpleTriggerContext` 三个时刻都是 null，`CronTrigger`
   此时以“当前时刻”为基准计算下一次（否则 `@Scheduled(cron=...)` 永远不会首跑）。
   替身按同一语义处理：`lastCompletionTime` 为空时用 `datetime.now()`。
4) `nextExecutionTime` 返回 null 表示“不再触发”（例如 `CronExpression` 在 8 年
   搜索窗口内找不到匹配时刻）；`ReschedulingRunnable` 收到 null 后停止重排。
   替身同样返回 None，由调度循环退出。
5) 时区：Java 用 JVM 默认时区；替身用进程本地时区的**朴素 datetime**。
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from org.springframework.scheduling.support.CronExpression import CronExpression

__all__ = ["TriggerContext", "CronTrigger"]


class TriggerContext(object):
    """`TriggerContext` 的替身（等价 `SimpleTriggerContext`）。"""

    __slots__ = ("lastScheduledExecutionTime", "lastActualExecutionTime",
                 "lastCompletionTime")

    def __init__(self) -> None:
        self.lastScheduledExecutionTime: Optional[_dt.datetime] = None
        self.lastActualExecutionTime: Optional[_dt.datetime] = None
        self.lastCompletionTime: Optional[_dt.datetime] = None

    def update(self,
               last_scheduled_execution_time: Optional[_dt.datetime] = None,
               last_actual_execution_time: Optional[_dt.datetime] = None,
               last_completion_time: Optional[_dt.datetime] = None) -> None:
        """等价 `TriggerContext#update(Date, Date, Date)`。"""
        if last_scheduled_execution_time is not None:
            self.lastScheduledExecutionTime = last_scheduled_execution_time
        if last_actual_execution_time is not None:
            self.lastActualExecutionTime = last_actual_execution_time
        if last_completion_time is not None:
            self.lastCompletionTime = last_completion_time

    def lastScheduledExecutionTimeOrNow(self) -> _dt.datetime:  # pragma: no cover
        return self.lastScheduledExecutionTime or _dt.datetime.now()

    def lastCompletionTimeOrNow(self) -> _dt.datetime:
        return self.lastCompletionTime or _dt.datetime.now()

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return ("TriggerContext(scheduled=%s, actual=%s, completion=%s)"
                % (self.lastScheduledExecutionTime, self.lastActualExecutionTime,
                   self.lastCompletionTime))


class CronTrigger(object):
    """基于 `CronExpression` 的 `Trigger` 替身。"""

    __slots__ = ("expression",)

    def __init__(self, expression) -> None:
        # 与 Java 一致：构造器既接受 CronExpression，也接受字符串
        if isinstance(expression, str):
            expression = CronExpression.parse(expression)
        self.expression: CronExpression = expression

    # ---------------------------------------------------------------- Trigger
    def next_execution_time(self, context: TriggerContext) -> Optional[_dt.datetime]:
        """等价 `nextExecutionTime(TriggerContext)`：返回 None 表示不再触发。"""
        base = context.lastCompletionTime
        if base is None:
            # 【Java→Python】首个周期没有“上次完成时刻”，以当前时刻为基准（见文件头第 3 条）
            base = _dt.datetime.now()
        return self.expression.next_fire_time(base)

    # Java 驼峰别名：框架替身的公开方法保持 Java 命名，便于与源码逐字对照
    def nextExecutionTime(self, context: TriggerContext) -> Optional[_dt.datetime]:
        return self.next_execution_time(context)

    def getExpression(self) -> CronExpression:
        return self.expression

    def toString(self) -> str:
        return self.expression.toString()

    def __str__(self) -> str:
        return "CronTrigger(%s)" % self.expression.toString()

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return "CronTrigger(%r)" % self.expression.toString()
