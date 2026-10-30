# -*- coding: utf-8 -*-
"""org.apache.kafka.clients.producer.ProducerConfig

【无 Java 源文件：框架类替身】
Java 侧来自 kafka-clients jar：`org.apache.kafka.clients.producer.ProducerConfig`，
业务代码只用到它的**配置项常量名**：
    configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);

【Java→Python 关键差异】
1) Java 的常量是 `public static final String`，Python 用类属性 + 大写命名还原；
   取用时写 `ProducerConfig.BOOTSTRAP_SERVERS_CONFIG`，与 Java 完全一致。
2) Java 还提供 `configDef()` 静态方法返回 ConfigDef（参数类型/默认值/校验器元数据）；
   Python 替身不承载校验框架，仅提供 ``ConfigDef`` 的极简占位与 `configDef()`。
3) 常量值必须与真实 Kafka 完全一致 —— 下游 ``DefaultKafkaProducerFactory`` 会把这些
   key 原样传给 KafkaProducer，写错 key 不会报错但配置会静默失效。
"""
from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["ProducerConfig", "ConfigDef"]


class ConfigDef(object):
    """`org.apache.kafka.common.config.ConfigDef` 的极简占位（仅承载参数定义表）。"""

    def __init__(self) -> None:
        self._names: List[str] = []

    def define(self, name: str, type_: Any = None, default: Any = None) -> "ConfigDef":
        # 【Java→Python】ConfigDef.define 是链式调用（返回 this），这里同样返回 self
        self._names.append(name)
        return self

    def names(self) -> List[str]:
        return list(self._names)


class ProducerConfig(object):
    """`ProducerConfig` 的常量集合（值与 Kafka 官方完全一致）。"""

    # 生产者唯一标识（Kafka 2.4+ 可省略，由 broker 生成默认值）
    TRANSACTIONAL_ID_CONFIG = "transactional.id"
    BOOTSTRAP_SERVERS_CONFIG = "bootstrap.servers"
    KEY_SERIALIZER_CLASS_CONFIG = "key.serializer"
    VALUE_SERIALIZER_CLASS_CONFIG = "value.serializer"
    ACKS_CONFIG = "acks"
    RETRIES_CONFIG = "retries"
    ENABLE_IDEMPOTENCE_CONFIG = "enable.idempotence"
    MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION = "max.in.flight.requests.per.connection"
    BATCH_SIZE_CONFIG = "batch.size"
    LINGER_MS_CONFIG = "linger.ms"
    BUFFER_MEMORY_CONFIG = "buffer.memory"
    COMPRESSION_TYPE_CONFIG = "compression.type"
    CLIENT_ID_CONFIG = "client.id"
    DELIVERY_TIMEOUT_MS_CONFIG = "delivery.timeout.ms"
    REQUEST_TIMEOUT_MS_CONFIG = "request.timeout.ms"

    @staticmethod
    def configDef() -> ConfigDef:
        """Java 的 `ProducerConfig.configDef()`：返回全部参数定义。

        【Java→Python】真实实现是近 100 行的 ``.define(...)`` 链；这里只列出本工程
        实际 put 进去的 11 个 key，足以对照，不参与任何校验逻辑。
        """
        defaults = ProducerConfig.defaultConfig()
        definition = ConfigDef()
        for name, default in defaults.items():
            definition.define(name, default=default)
        return definition

    @staticmethod
    def configNames() -> List[str]:
        return ProducerConfig.configDef().names()

    @staticmethod
    def defaultConfig() -> Dict[str, Any]:
        """等价 `ProducerConfig.configDef().defaultValues()` 的扁平化结果。"""
        return {
            ProducerConfig.BOOTSTRAP_SERVERS_CONFIG: "",
            ProducerConfig.ACKS_CONFIG: "1",
            ProducerConfig.RETRIES_CONFIG: 2147483647,
            ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG: "false",
            ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION: 5,
            ProducerConfig.BATCH_SIZE_CONFIG: 16384,
            ProducerConfig.LINGER_MS_CONFIG: 0,
            ProducerConfig.BUFFER_MEMORY_CONFIG: 33554432,
            ProducerConfig.COMPRESSION_TYPE_CONFIG: "none",
        }
