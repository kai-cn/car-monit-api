# -*- coding: utf-8 -*-
"""app.middleware：真实中间件适配层（P2）。

替身层（com/java/javax/org 顶层）保持离线可用；本包提供"配置即启用"的
真实客户端适配：
    real_redis.RealRedisTemplate   CAR_MONIT_REDIS_URL → 真实 Redis 读写
    real_es.RealEsBackend          CAR_MONIT_ES_URL → 真实 Elasticsearch REST/DSL
    real_kafka.RealKafkaProducer   CAR_MONIT_KAFKA_URL → 真实 Kafka 生产/消费

设计约束：与 Java 行为等价——失败语义对齐"中间件宕机"（prod 模式抛错），
shim 模式提供可配置降级（熔断到进程内内存），CI 无服务时自动降级不红。
"""
