# -*- coding: utf-8 -*-
"""Scheduler subsystem -- the ``@EnableScheduling`` equivalent (Phase 2c).

``app.main`` 的 lifespan 只依赖两个入口：

    start_scheduler() -> int      # 注册并启动全部 @Scheduled 任务，返回任务数
    shutdown_scheduler() -> None  # 容器关闭时停止（幂等）

实现细节见 [registry][app.scheduler.registry]；cron 解析在
``org.springframework.scheduling.support.CronExpression``，
线程池与 Trigger 调度在 ``org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler``。
"""
from __future__ import annotations

from app.scheduler.registry import (JOB_CLASSES, JobSpec, describe, is_started, plan,
                                    shutdown_scheduler, start_scheduler)

__all__ = ["JOB_CLASSES", "JobSpec", "plan", "start_scheduler", "shutdown_scheduler",
           "is_started", "describe"]
