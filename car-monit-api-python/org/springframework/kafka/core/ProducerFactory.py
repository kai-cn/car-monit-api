# -*- coding: utf-8 -*-
"""org.springframework.kafka.core.ProducerFactory

【无 Java 源文件：框架类替身】
Java 侧来自 spring-kafka：`org.springframework.kafka.core.ProducerFactory<K, V>`，
`DefaultKafkaProducerFactory` 是它的默认实现，被 KafkaProducerConfig 的
`producerFactory()` @Bean 返回、再喂给 `new KafkaTemplate<>(producerFactory())`。

【Java→Python 关键差异】
1) Java 泛型 `<K, V>` 在 Python 运行时被擦除，由 ``typing.Generic`` 仅做静态标注。
2) 真实接口方法：`createProducer()`（返回 KafkaProducer）、
   `getConfigurationProperties()`、`isProducerPerThread()`、`closeProducer(...)`、
   `close()`。Python 替身把 ``createProducer()`` 收敛为返回**进程内 KafkaProducer 替身**
   （见 ``org.apache.kafka.clients.producer.KafkaProducer``：本替身不落地，直接用
   KafkaTemplate 的模块级单例模拟 broker）。
3) ``KafkaTemplate`` 在本工程只在配置类里被创建，业务代码注入的是 Bean；
   Python 侧通过 ``KafkaTemplate(bootstrap_servers=...)`` 或直接把本工厂传给
   KafkaTemplate 构造器（替身会从配置里取 ``bootstrap.servers``）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

__all__ = ["ProducerFactory"]

K = TypeVar("K")
V = TypeVar("V")


class ProducerFactory(ABC, Generic[K, V]):
    """`ProducerFactory<K,V>` 的抽象替身。"""

    @abstractmethod
    def createProducer(self) -> Any:
        """创建（或复用）底层生产者。"""

    @abstractmethod
    def getConfigurationProperties(self) -> Dict[str, Any]:
        """返回构造时传入的配置项（Kafka 原生 properties）。"""

    def isProducerPerThread(self) -> bool:
        return False

    def closeProducer(self, producer: Any) -> None:
        # Java 默认实现：producer.close(...)
        if hasattr(producer, "close"):
            producer.close()

    def close(self) -> None:
        return None
