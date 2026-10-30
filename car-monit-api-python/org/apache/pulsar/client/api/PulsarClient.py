# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.PulsarClient

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.PulsarClient`。
PulsarConsumerConfig 里的用法：
    PulsarClient.builder()
            .serviceUrl(serviceUrl)
            .listenerThreads(8)
            .ioThreads(8)
            .operationTimeout(30, TimeUnit.SECONDS)
            .connectionTimeout(30, TimeUnit.SECONDS)
            .build();
并且 ``client.newConsumer(Schema.STRING)...subscribe()``。

【Java→Python 关键差异】
1) Java 的 ``builder()`` 返回**静态内部类** ``PulsarClient.Builder``；Python 无内部类，
   改为独立的 ``PulsarClientBuilder``（由 ``PulsarClient.builder()`` 返回），
   Builder 自身实现 ``AutoCloseable``（Java 里可 try-with-resources），这里提供 ``close()``。
2) ``build()`` 在 Java 里会**真正建立到 broker 的连接**（TCP 握手 + 鉴权），
   失败抛 ``PulsarClientException``；Python 替身只保存配置并置 ``connected=True``，
   不发起任何网络 IO —— 因此业务代码可以在无 Pulsar 环境下跑通。
3) 最关键的差异：Java 的 ``PulsarClient`` 是**线程安全单例 Bean**，由 Spring 容器管理
   生命周期；Python 无容器，每次 ``PulsarConsumerConfig.pulsarConsumerClient()``
   都会 new 一个（配置类方法只应在启动时调用一次）。
4) Java 的 ``newConsumer(Schema)`` 抛受检 ``PulsarClientException``；Python 直接返回
   ``ConsumerBuilder``。``newProducer`` 同理返回 ``ProducerBuilder``。
5) 这里的 ``PulsarClientException`` 是无 Java 源文件的**受检异常替身**：Python 无受检
   异常机制，业务代码不必 try/except 包裹（本工程 PulsarConsumerConfig 的 ``throws``
   声明在 Python 里被丢弃）。
"""
from __future__ import annotations

from typing import Any, Optional

from org.apache.pulsar.client.api.ConsumerBuilder import ConsumerBuilder
from org.apache.pulsar.client.api.Producer import Producer
from org.apache.pulsar.client.api.Schema import Schema

__all__ = ["PulsarClient", "PulsarClientBuilder", "PulsarClientException",
           "ProducerBuilder"]


class PulsarClientException(Exception):
    """`org.apache.pulsar.client.api.PulsarClientException` 的替身。

    【Java→Python】Java 里是**受检异常**（继承 Exception，调用方必须声明 throws
    或 try/catch）；Python 没有受检异常，这个类只是为了让 “抛什么异常” 保持一致，
    需要时用 ``raise PulsarClientException(...)``。
    """


class ProducerBuilder(object):
    """``PulsarClient.newProducer(Schema)`` 返回的构建器（最小子集）。"""

    def __init__(self, client: Any = None, schema: Optional[Schema] = None) -> None:
        self._client = client
        self._schema = schema
        self._topic: str = ""
        self._producer_name: Optional[str] = None

    def topic(self, topic_name: str) -> "ProducerBuilder":
        self._topic = topic_name
        return self

    def producerName(self, producer_name: str) -> "ProducerBuilder":
        self._producer_name = producer_name
        return self

    def create(self) -> Producer:
        """等价 ``create()``：Java 阻塞建连，Python 直接返回 Producer 替身。"""
        return Producer(topic=self._topic or "persistent://public/default/default",
                        schema=self._schema)


class PulsarClient(object):
    """`PulsarClient` 的替身（持有连接配置，不做真实 IO）。"""

    def __init__(self, service_url: str = "pulsar://localhost:6650") -> None:
        self.serviceUrl = service_url
        self.listenerThreads = 1
        self.ioThreads = 1
        self.operationTimeoutMs = 30000
        self.connectionTimeoutMs = 30000
        self.connected = True

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def builder() -> "PulsarClientBuilder":
        return PulsarClientBuilder()

    # ------------------------------------------------------------------ 创建消费者/生产者
    def newConsumer(self, schema: Optional[Schema] = None) -> ConsumerBuilder:
        """等价 ``newConsumer(Schema<T>)``。"""
        return ConsumerBuilder(self, schema)

    def newProducer(self, schema: Optional[Schema] = None) -> ProducerBuilder:
        """等价 ``newProducer(Schema<T>)``。"""
        return ProducerBuilder(self, schema)

    # ------------------------------------------------------------------ 生命周期
    def isClosed(self) -> bool:
        return not self.connected

    def close(self) -> None:
        """等价 ``close()``：关闭客户端及所有底层连接。"""
        self.connected = False

    def shutdown(self) -> None:
        """等价 ``shutdown()``（已废弃）：与 close 等价。"""
        self.close()


class PulsarClientBuilder(object):
    """``PulsarClient.Builder`` 的替身（链式配置，返回 self）。"""

    def __init__(self) -> None:
        self._service_url: str = "pulsar://localhost:6650"
        self._listener_threads: int = 1
        self._io_threads: int = 1
        self._operation_timeout_ms: int = 30000
        self._connection_timeout_ms: int = 30000
        self._authentication: Any = None

    def serviceUrl(self, service_url: str) -> "PulsarClientBuilder":
        self._service_url = service_url
        return self

    def listenerThreads(self, listener_threads: int) -> "PulsarClientBuilder":
        self._listener_threads = listener_threads
        return self

    def ioThreads(self, io_threads: int) -> "PulsarClientBuilder":
        self._io_threads = io_threads
        return self

    def operationTimeout(self, timeout: int, unit: Any) -> "PulsarClientBuilder":
        # 【Java→Python】Java 是 (long, TimeUnit)；TimeUnit 替身用 float 系数，转回 int
        self._operation_timeout_ms = int(unit.toMillis(timeout)) if unit is not None else timeout
        return self

    def connectionTimeout(self, timeout: int, unit: Any) -> "PulsarClientBuilder":
        self._connection_timeout_ms = int(unit.toMillis(timeout)) if unit is not None else timeout
        return self

    def authentication(self, authentication: Any) -> "PulsarClientBuilder":
        self._authentication = authentication
        return self

    def build(self) -> PulsarClient:
        client = PulsarClient(self._service_url)
        client.listenerThreads = self._listener_threads
        client.ioThreads = self._io_threads
        client.operationTimeoutMs = self._operation_timeout_ms
        client.connectionTimeoutMs = self._connection_timeout_ms
        return client

    def close(self) -> None:
        # 对应 Java 的 `Builder implements AutoCloseable`
        return None
