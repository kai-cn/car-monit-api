# -*- coding: utf-8 -*-
"""``@EnableScheduling`` equivalent: component scan -> post-processor -> registrar.

Migrated from: pro-business-api/src/main/java/com/ruoyi/base/config/SchedulingConfig.java
               (``@Configuration`` + ``@EnableScheduling`` + ``SchedulingConfigurer``)

Java 的启动链路（Spring Boot 2.4.5）：

1. ``@SpringBootApplication`` 组件扫描，把 ``@Component`` / ``@Service`` 交给容器；
2. ``@EnableScheduling`` 注册 ``ScheduledAnnotationBeanPostProcessor``，
   逐个 Bean 扫描 ``@Scheduled`` 方法；
3. ``SchedulingConfig#configureTasks`` 把 ``ThreadPoolTaskScheduler``
   （poolSize=10、前缀 ``scheduler-``、等待 60s）交给 ``ScheduledTaskRegistrar``；
4. 容器 refresh 末尾调用 ``ScheduledTaskRegistrar#afterPropertiesSet``，
   任务真正开始按 cron / fixedRate 触发。

Python 侧逐条对应：

+--------------------------------+-----------------------------------------------+
| Java                           | Python (本模块)                               |
+================================+===============================================+
| 组件扫描结果                   | ``JOB_CLASSES``（显式清单，理由见下）          |
| ScheduledAnnotationBeanPost... | ``Scheduled.registerScheduled(instance, reg)`` |
| SchedulingConfig#configureTasks| ``SchedulingConfig()``                        |
| ScheduledTaskRegistrar#after.. | ``registrar.afterPropertiesSet()``             |
| 容器关闭 -> destroy            | ``shutdown_scheduler()``                       |
+--------------------------------+-----------------------------------------------+

为什么 ``JOB_CLASSES`` 是显式清单而不是真的扫包
------------------------------------------------
Spring 扫的是**注解**，Python 只能靠 ``pkgutil`` 遍历 166 个模块并逐个 import。
那会把全部 controller / 消费者一起加载（Kafka 消费者会真的开始拉取），
代价与副作用都远超收益。因此这里列出“组件扫描的**结果**”：

    com.ruoyi.base.task.TrackTask                       3 个 cron
    com.ruoyi.base.task.DataFlowTask                    2 个 cron
    com.ruoyi.base.service.impl.DataLossDetectionService      1 个 fixedRateString
    com.ruoyi.base.service.impl.DelayMonitoringService        1 个 fixedRate
    com.ruoyi.base.service.impl.DataReliabilityService        2 个（fixedRateString / fixedRate）
    com.ruoyi.base.service.optimization.GaussEsConsistencyService  1 个 cron

**``CarTask`` 不在此列**：它的 Java 源文件整体被块注释（``/*`` … ``*/``），
javac 编译时该类根本不存在，自然也不会注册任何任务。``tools/`` 下的
``test_phase2e`` 会核对“源码里的 ``@Scheduled`` 装饰器数量”与清单一致，
防止将来新增任务时忘记登记。
"""
from __future__ import annotations

import datetime as _dt
import inspect
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from com.ruoyi.base.config.SchedulingConfig import SchedulingConfig
from com.ruoyi.base.service.impl.DataLossDetectionService import DataLossDetectionService
from com.ruoyi.base.service.impl.DataReliabilityService import DataReliabilityService
from com.ruoyi.base.service.impl.DelayMonitoringService import DelayMonitoringService
from com.ruoyi.base.service.optimization.GaussEsConsistencyService import GaussEsConsistencyService
from com.ruoyi.base.task.DataFlowTask import DataFlowTask
from com.ruoyi.base.task.TrackTask import TrackTask
from org.springframework.scheduling.annotation.Scheduled import (scheduledMethods,
                                                                scheduledTrigger,
                                                                registerScheduled)
from org.springframework.scheduling.config.ScheduledTaskRegistrar import ScheduledTaskRegistrar

__all__ = ["JOB_CLASSES", "JobSpec", "plan", "start_scheduler", "shutdown_scheduler",
           "is_started", "describe"]

log = logging.getLogger(__name__)

#: 等价“组件扫描出的带 @Scheduled 的 Bean”（顺序与 Java 包名一致）
JOB_CLASSES: Tuple[type, ...] = (
    TrackTask,
    DataFlowTask,
    DataLossDetectionService,
    DelayMonitoringService,
    DataReliabilityService,
    GaussEsConsistencyService,
)


@dataclass(frozen=True)
class JobSpec:
    """一个 ``@Scheduled`` 方法的静态描述（供启动日志与 ``/health`` 使用）。"""

    bean: str        # com.ruoyi.base.task.TrackTask（= Java 全限定类名）
    method: str      # syncCurrentTrack
    kind: str        # cron / fixedRate / fixedDelay
    trigger: str     # "0 0/3 * * * ?" 或 "600000"
    java: str        # 源码里的注解原文，便于逐字对照

    def as_dict(self) -> Dict[str, str]:
        return {"bean": self.bean, "method": self.method,
                "kind": self.kind, "trigger": self.trigger, "java": self.java}


@dataclass
class _SchedulerState:
    """已启动的调度器句柄（等价 Spring 容器里的 TaskScheduler Bean）。"""

    config: SchedulingConfig
    registrar: ScheduledTaskRegistrar
    jobs: List[JobSpec]
    startedAt: _dt.datetime = field(default_factory=_dt.datetime.now)

    @property
    def count(self) -> int:
        return len(self.jobs)


_LOCK = threading.Lock()
_STATE: Optional[_SchedulerState] = None


# ---------------------------------------------------------------- 静态清单
def _javaAnnotation(kind: str, trigger: str, config: Dict[str, Any]) -> str:
    """还原注解在 Java 源码里的写法（``fixedRateString`` 与 ``fixedRate`` 要区分）。"""
    if kind == "cron":
        return '@Scheduled(cron = "%s")' % trigger
    if config.get(kind + "String") is not None:
        return '@Scheduled(%sString = "%s")' % (kind, config[kind + "String"])
    return "@Scheduled(%s = %s)" % (kind, config[kind])


def plan(bean_classes: Sequence[type] = JOB_CLASSES) -> List[JobSpec]:
    """列出会被注册的任务（**不实例化 Bean、不启动线程**，可安全用于测试/健康检查）。

    等价于 ``ScheduledAnnotationBeanPostProcessor`` 扫描阶段的“待注册任务表”。
    """
    specs: List[JobSpec] = []
    for bean_class in bean_classes:
        # 只扫描类自身的函数对象：@Scheduled 装饰器把元数据挂在函数上，
        # 因此这里不需要实例化就能读到（Spring 也必须先创建 Bean 才能反射，Python 不必）。
        for method_name, member in inspect.getmembers(bean_class, predicate=inspect.isfunction):
            config = getattr(member, "__scheduled__", None)
            if not config:
                continue
            kind, value = scheduledTrigger(config, method_name)
            trigger = value if kind == "cron" else str(value[0])
            specs.append(JobSpec(
                bean=bean_class.__module__,
                method=method_name,
                kind=kind,
                trigger=trigger,
                java=_javaAnnotation(kind, trigger, config),
            ))
    specs.sort(key=lambda spec: (spec.bean, spec.method))
    return specs


# ---------------------------------------------------------------- 生命周期
def start_scheduler(bean_classes: Optional[Sequence[type]] = None) -> int:
    """启动全部 ``@Scheduled`` 任务，返回注册数量（幂等：重复调用返回同一计数）。

    等价 Spring 启动时的“组件扫描 → 后处理器 → configureTasks → afterPropertiesSet”。
    ``bean_classes`` 仅测试注入用（默认 :data:`JOB_CLASSES`）。
    """
    global _STATE
    with _LOCK:
        if _STATE is not None:
            return _STATE.count

        classes = tuple(bean_classes) if bean_classes is not None else JOB_CLASSES
        jobs = plan(classes)
        if not jobs:
            log.info("[定时任务] 没有发现 @Scheduled 方法，调度器未启动")
            return 0

        # 1) @EnableScheduling + SchedulingConfigurer#configureTasks
        config = SchedulingConfig()
        scheduler = config.taskRegistrar.getTaskScheduler()

        # 2) ScheduledAnnotationBeanPostProcessor：逐个 Bean 登记
        registrar = ScheduledTaskRegistrar()
        registrar.setTaskScheduler(scheduler)
        wanted = {job.bean for job in jobs}
        try:
            for bean_class in classes:
                if bean_class.__module__ not in wanted:
                    # 没有 @Scheduled 的类不需要创建实例（Spring 在扫描阶段就已判定）
                    continue
                instance = bean_class()
                registerScheduled(instance, registrar)
        except Exception:
            # Java 侧 Bean 创建失败会让整个 ApplicationContext 启动失败；
            # 这里已创建的线程池必须先收掉，避免泄漏后再把异常抛给调用方。
            config.shutdown()
            raise

        # 3) 容器 refresh 末尾：真正排期
        registrar.afterPropertiesSet()

        _STATE = _SchedulerState(config=config, registrar=registrar, jobs=jobs)
        for job in jobs:
            log.info("[定时任务] 注册 %s#%s → %s %s",
                     job.bean, job.method, job.kind, job.trigger)
        log.info("[定时任务] 调度器已启动，共 %s 个任务（线程池 %s，前缀 %s）",
                 len(jobs), scheduler.getPoolSize(), scheduler.threadNamePrefix)

    _registerHealthProbe()
    return len(jobs)


def shutdown_scheduler() -> None:
    """停止全部任务（等价容器关闭时 ``ThreadPoolTaskScheduler#destroy``）。"""
    global _STATE
    with _LOCK:
        state, _STATE = _STATE, None
    if state is None:
        return
    try:
        state.config.shutdown()
    finally:
        _unregisterHealthProbe()
    log.info("[定时任务] 调度器已停止，共 %s 个任务", state.count)


def is_started() -> bool:
    return _STATE is not None


def describe() -> Dict[str, Any]:
    """``/health`` 的调度器探针：已注册任务清单（不是最后一次执行结果）。"""
    state = _STATE
    if state is None:
        return {"started": False, "tasks": 0, "jobs": []}
    return {
        "started": True,
        "tasks": state.count,
        "startedAt": state.startedAt.isoformat(timespec="seconds"),
        "jobs": [job.as_dict() for job in state.jobs],
    }


def _registerHealthProbe() -> None:
    try:
        from app.health import health_registry

        health_registry.register("scheduler", describe)
    except Exception as error:  # noqa: BLE001 - 健康探针缺失不应影响调度
        log.debug("scheduler probe not registered: %s", error)


def _unregisterHealthProbe() -> None:
    try:
        from app.health import health_registry

        health_registry.unregister("scheduler")
    except Exception as error:  # noqa: BLE001
        log.debug("scheduler probe not unregistered: %s", error)
