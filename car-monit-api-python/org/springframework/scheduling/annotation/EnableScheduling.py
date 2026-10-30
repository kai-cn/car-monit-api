# -*- coding: utf-8 -*-
"""org.springframework.scheduling.annotation.EnableScheduling

【无 Java 源文件：框架类替身】
Java 侧：`@EnableScheduling`（Spring 的“开关型”注解），作用是在容器里注册
`ScheduledAnnotationBeanPostProcessor`，让 `@Scheduled` 方法真正被排期。

【Java→Python 关键差异】
1) Python 没有注解，也没有容器后处理器；本替身实现为**类装饰器 / 函数装饰器**，
   只做两件事：打上 ``__enable_scheduling__ = True`` 标记、原样返回目标。
2) Spring 里该注解只应出现在 ``@Configuration`` 类上；Python 侧可以标在任意类，
   由启动代码（``EcBusinessApiApplication.main``）决定是否真的扫描并启动任务。
3) 与 ``@Scheduled`` 替身的分工：本注解只“声明启用”，真正的扫描与排期在
   ``app.scheduler.start_scheduler()``（它内部按 ``SchedulingConfig`` 建线程池，
   再用 ``ScheduledTaskRegistrar`` 排期）。
"""
from __future__ import annotations

from typing import TypeVar

__all__ = ["EnableScheduling"]

T = TypeVar("T")


def EnableScheduling(target: T) -> T:
    """标记“启用定时任务”（等价 `@EnableScheduling`）。"""
    # 【Java→Python】注解无参数，这里直接给目标对象挂标记属性；
    # 类与函数都可以挂属性，因此一个函数即可同时支持两种用法。
    try:
        setattr(target, "__enable_scheduling__", True)
    except (AttributeError, TypeError):  # pragma: no cover - 内建类型不可挂属性
        pass
    return target
