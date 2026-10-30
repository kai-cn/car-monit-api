# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.BindingBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.BindingBuilder``。
本工程用法（RabbitMqConfig）：
    BindingBuilder.bind(snapshotFlowQueue)
            .to(snapshotFlowExchange)
            .with("snapshot.flow")
            .noargs();

【Java→Python】关键差异（关键字冲突，务必注意）
1) Java 的 ``with(String routingKey)`` 无法在 Python 中同名声明
   （``with`` 是**关键字**，``x.with(...)`` 会直接 SyntaxError），
   因此改名为 ``with_``；``RabbitMqConfig.py`` 中也同步写成 ``.with_(...)``。
2) Java 的三段式 builder 用**静态内部类**实现：
   ``BindingBuilder.DestinationConfigurer`` → ``.to()`` 返回
   ``ExchangeConfigurer`` → ``.with()`` 返回 ``RoutingKeyConfigurer`` → ``.noargs()``。
   替身把这三个内部类提升为模块级类（Python 嵌套类可读性差），
   但保留相同的链式方法与返回类型，调用链一字不差。
3) ``bind(Queue)`` 与 ``bind(Exchange)`` 在 Java 里是两个重载（目标不同）；
   Python 单方法按类型分派：Queue → QUEUE 目标，Exchange → EXCHANGE 目标。
   本工程只用 ``bind(Queue)``。
4) ``and(Map<String,Object>)``（带 headers 的绑定）本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, Dict

from org.springframework.amqp.core.Binding import (
    Binding, DESTINATION_EXCHANGE, DESTINATION_QUEUE)
from org.springframework.amqp.core.Exchange import Exchange
from org.springframework.amqp.core.Queue import Queue

__all__ = ["BindingBuilder", "DestinationConfigurer", "ExchangeConfigurer",
           "RoutingKeyConfigurer"]


class DestinationConfigurer(object):
    """对应 ``BindingBuilder.DestinationConfigurer``（bind(...) 的返回类型）。"""

    def __init__(self, destination: str, destination_type: str) -> None:
        self._destination = destination
        self._destination_type = destination_type

    def to(self, exchange: Exchange) -> "ExchangeConfigurer":
        """对应 ``to(Exchange exchange)``。"""
        return ExchangeConfigurer(self._destination, self._destination_type,
                                  exchange.getName())


class ExchangeConfigurer(object):
    """对应 ``BindingBuilder.ExchangeConfigurer``。"""

    def __init__(self, destination: str, destination_type: str,
                 exchange: str) -> None:
        self._destination = destination
        self._destination_type = destination_type
        self._exchange = exchange

    def with_(self, routing_key: str) -> "RoutingKeyConfigurer":
        """对应 ``with(String routingKey)``；因 with 是关键字而改名。"""
        return RoutingKeyConfigurer(self._destination, self._destination_type,
                                    self._exchange, routing_key)


class RoutingKeyConfigurer(object):
    """对应 ``BindingBuilder.RoutingKeyConfigurer``。"""

    def __init__(self, destination: str, destination_type: str,
                 exchange: str, routing_key: str) -> None:
        self._destination = destination
        self._destination_type = destination_type
        self._exchange = exchange
        self._routing_key = routing_key

    def noargs(self) -> Binding:
        """对应 ``noargs()``：不带 headers 参数的绑定。"""
        return Binding(self._destination, self._destination_type,
                       self._exchange, self._routing_key, {})

    def and_(self, arguments: Dict[str, Any]) -> Binding:
        """对应 ``and(Map<String,Object> arguments)``（工程未使用）。"""
        return Binding(self._destination, self._destination_type,
                       self._exchange, self._routing_key, arguments)


class BindingBuilder(object):
    """``BindingBuilder`` 的入口（静态 ``bind``）。"""

    @staticmethod
    def bind(destination: Any) -> DestinationConfigurer:
        """对应 ``bind(Queue)`` / ``bind(Exchange)`` 两个重载。"""
        if isinstance(destination, Queue):
            return DestinationConfigurer(destination.getName(), DESTINATION_QUEUE)
        if isinstance(destination, Exchange):
            return DestinationConfigurer(destination.getName(), DESTINATION_EXCHANGE)
        # 【Java→Python】Java 在编译期就会拒绝其它类型；Python 只能在运行时抛 TypeError
        raise TypeError("BindingBuilder.bind 只接受 Queue 或 Exchange，实际为 "
                        + type(destination).__name__)
