# -*- coding: utf-8 -*-
"""app.middleware：真实中间件适配层（P2）。

替身层（com/java/javax/org 顶层）保持离线可用；本包提供"配置即启用"的
真实客户端适配：
    real_redis.RealRedisTemplate   CAR_MONIT_REDIS_URL → 真实 Redis 读写
    real_es.RealEsBackend          CAR_MONIT_ES_URL → 真实 Elasticsearch REST/DSL
    real_kafka.RealKafkaProducer   CAR_MONIT_KAFKA_URL → 真实 Kafka 生产/消费

设计约束：与 Java 行为等价——失败语义对齐"中间件宕机"（prod 模式抛错），
shim 模式提供可配置降级（熔断到进程内内存），CI 无服务时自动降级不红。

优雅关闭（H6）
-------------
Spring 容器关闭时会调用各客户端 Bean 的 destroy 方法（连接池/缓冲区释放）。
:func:`shutdown_middleware` 是这些 destroy 回调的等价物，由 ``app.main`` 的
lifespan 在调度器/Bean 停止之后调用；每一步都尽力而为、幂等。
"""
from __future__ import annotations

import logging

__all__ = ["shutdown_middleware"]

log = logging.getLogger(__name__)


def shutdown_middleware() -> None:
    """按依赖顺序关闭进程级中间件连接（Kafka → ES → Redis → DB）。"""
    steps = (
        ("kafka", "app.middleware.real_kafka", "close_shared_kafka_producer"),
        ("es", "app.middleware.real_es", "close_shared_es_backend"),
        ("redis", "com.ruoyi.common.core.redis.RedisCache",
         "close_shared_redis_template"),
        ("db", "app.db.engine", "close_database"),
    )
    for name, module_name, function_name in steps:
        try:
            module = __import__(module_name, fromlist=[function_name])
            getattr(module, function_name)()
        except Exception:  # noqa: BLE001 - 停机阶段不因单个客户端失败阻断
            log.exception("[中间件关闭] %s 失败（继续关闭其余组件）", name)
