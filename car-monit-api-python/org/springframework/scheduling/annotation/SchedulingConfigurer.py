# -*- coding: utf-8 -*-
"""org.springframework.scheduling.annotation.SchedulingConfigurer

【无 Java 源文件：框架类替身】
Java 侧来自 spring-context：`org.springframework.scheduling.annotation.SchedulingConfigurer`，
是一个**函数式接口**（只有一个抽象方法）：
    public interface SchedulingConfigurer {
        void configureTasks(ScheduledTaskRegistrar taskRegistrar);
    }
SchedulingConfig 通过 ``implements SchedulingConfigurer`` + ``@Override configureTasks``
把自定义线程池交给 Spring 的定时任务体系。

【Java→Python 关键差异】
1) Java 接口的**方法签名即契约**，实现类写错方法名会编译失败；Python 没有编译期检查，
   因此用 ``abc.ABC`` + ``@abstractmethod`` 还原“必须实现”的约束 ——
   若子类漏实现，**实例化时**抛 TypeError（对应 Java 的编译错误）。
2) Java 8 起它是 ``@FunctionalInterface``，可以用 lambda 实现；
   Python 侧同理可直接传一个普通函数/可调用对象给启动代码，不必建类。
3) 参数类型 ``ScheduledTaskRegistrar`` 在 Java 是强类型；Python 用类型标注表示
   （运行时不校验），鸭子类型即可。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from org.springframework.scheduling.config.ScheduledTaskRegistrar import ScheduledTaskRegistrar

__all__ = ["SchedulingConfigurer"]


class SchedulingConfigurer(ABC):
    """`SchedulingConfigurer` 的抽象替身。"""

    @abstractmethod
    def configureTasks(self, task_registrar: ScheduledTaskRegistrar) -> None:
        """配置定时任务（由容器在初始化阶段调用）。"""
