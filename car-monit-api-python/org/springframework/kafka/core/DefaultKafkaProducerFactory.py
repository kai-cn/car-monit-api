# -*- coding: utf-8 -*-
"""org.springframework.kafka.core.DefaultKafkaProducerFactory

【无 Java 源文件：框架类替身】
Java 侧来自 spring-kafka：`DefaultKafkaProducerFactory<K, V>`。

【Java→Python 关键差异】
1) Java 构造器 ``new DefaultKafkaProducerFactory<>(configProps)`` 会**复制**配置
   （`new HashMap<>(configs)`）并按 key/value 序列化器反射实例化 KafkaProducer；
   Python 替身同样做浅复制，序列化器只在 ``createProducer()`` 时按需实例化。
2) ``createProducer()`` 在 Java 里返回 KafkaProducer（内含真实网络连接）；
   Python 替身返回一个**占位生产者**，只暴露 ``close()``/``send()``，避免引入
   不可用的网络依赖；真正发送由 KafkaTemplate 替身完成。
3) Java 侧 ``getConfigurationProperties()`` 返回不可变副本；Python 同样返回 ``dict(...)``。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar

from org.springframework.kafka.core.ProducerFactory import ProducerFactory

__all__ = ["DefaultKafkaProducerFactory", "PlaceholderKafkaProducer"]

K = TypeVar("K")
V = TypeVar("V")


class PlaceholderKafkaProducer(object):
    """``org.apache.kafka.clients.producer.KafkaProducer`` 的最小占位。"""

    def __init__(self, configs: Dict[str, Any]) -> None:
        self.configs = configs
        self.closed = False

    def close(self, timeout_ms: Optional[int] = None) -> None:
        self.closed = True

    def flush(self) -> None:
        return None


class DefaultKafkaProducerFactory(ProducerFactory):
    """`DefaultKafkaProducerFactory<K,V>` 的替身。"""

    def __init__(self, config_props: Optional[Dict[str, Any]] = None) -> None:
        # 【Java→Python】Java 的 HashMap 复制在这里对应 dict(...)；
        # 注意 Java 是浅复制（value 仍是同一对象），Python 行为一致。
        self._config_props: Dict[str, Any] = dict(config_props or {})
        self._producer: Optional[PlaceholderKafkaProducer] = None

    # ------------------------------------------------------------------ 属性
    def getConfigurationProperties(self) -> Dict[str, Any]:
        return dict(self._config_props)

    def getKeySerializer(self) -> Any:
        # 对应 Java 的 keySerializer 字段：这里是“类的引用”（如 StringSerializer），
        # 真实 Kafka 用反射实例化；替身直接返回该类以便测试检查配置正确性。
        return self._config_props.get("key.serializer")

    def getValueSerializer(self) -> Any:
        return self._config_props.get("value.serializer")

    def setKeySerializer(self, serializer: Any) -> None:
        self._config_props["key.serializer"] = serializer

    def setValueSerializer(self, serializer: Any) -> None:
        self._config_props["value.serializer"] = serializer

    # ------------------------------------------------------------------ 生命周期
    def createProducer(self) -> PlaceholderKafkaProducer:
        """对应 Java 的 ``createProducer()``：单例复用（默认非 per-thread 模式）。"""
        if self.isProducerPerThread():
            return PlaceholderKafkaProducer(self.getConfigurationProperties())
        if self._producer is None or self._producer.closed:
            self._producer = PlaceholderKafkaProducer(self.getConfigurationProperties())
        return self._producer

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close()
            self._producer = None
