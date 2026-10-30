# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.ExchangeBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.ExchangeBuilder``。
本工程用法（RabbitMqConfig）：
    ExchangeBuilder.directExchange(snapshotFlowTopic).durable(true).build()

【Java→Python】关键差异
1) Java 的 ``ExchangeBuilder`` 是**抽象类**，``directExchange()`` / ``topicExchange()``
   等静态方法返回匿名子类；替身用一个具体类 + ``_type`` 字段表达。
2) 静态工厂在 Java 里是 ``directExchange(String name)``；Python 用 ``@staticmethod``，
   调用写法一致。``ExchangeBuilder`` 的构造器在 Java 里是 protected，不直接使用。
3) Java 的 ``durable(boolean)`` / ``autoDelete(boolean)`` / ``internal(boolean)``
   / ``withArgument(String,Object)`` 均链式返回 this；本工程只用 ``durable``，
   其余按“用到才实现”的原则补上 autoDelete/withArgument。
4) ``build()`` 的返回类型在 Java 里是 ``Exchange``（实际是 ``DirectExchange``）；
   替身返回 ``Exchange`` 实例并把 type 设为 "direct"。
"""

from __future__ import annotations

from typing import Any, Dict

from org.springframework.amqp.core.Exchange import (
    Exchange, TYPE_DIRECT, TYPE_FANOUT, TYPE_HEADERS, TYPE_TOPIC)

__all__ = ["ExchangeBuilder"]


class ExchangeBuilder(object):
    """``ExchangeBuilder`` 的替身。"""

    def __init__(self, name: str, exchange_type: str) -> None:
        self._name = name
        self._type = exchange_type
        # Java 的 ExchangeBuilder 默认 durable=true
        self._durable = True
        self._auto_delete = False
        self._internal = False
        self._arguments: Dict[str, Any] = {}

    # ------------------------------------------------------------------ 静态工厂
    @staticmethod
    def directExchange(name: str) -> "ExchangeBuilder":
        return ExchangeBuilder(name, TYPE_DIRECT)

    @staticmethod
    def topicExchange(name: str) -> "ExchangeBuilder":
        return ExchangeBuilder(name, TYPE_TOPIC)

    @staticmethod
    def fanoutExchange(name: str) -> "ExchangeBuilder":
        return ExchangeBuilder(name, TYPE_FANOUT)

    @staticmethod
    def headersExchange(name: str) -> "ExchangeBuilder":
        return ExchangeBuilder(name, TYPE_HEADERS)

    # ------------------------------------------------------------------ 链式 setter
    def durable(self, durable: bool) -> "ExchangeBuilder":
        self._durable = durable
        return self

    def autoDelete(self, auto_delete: bool) -> "ExchangeBuilder":
        self._auto_delete = auto_delete
        return self

    def internal(self, internal: bool) -> "ExchangeBuilder":
        self._internal = internal
        return self

    def withArgument(self, key: str, value: Any) -> "ExchangeBuilder":
        self._arguments[key] = value
        return self

    # ------------------------------------------------------------------ 构建
    def build(self) -> Exchange:
        return Exchange(self._name, self._type, self._durable,
                        self._auto_delete, self._arguments)

    def __repr__(self) -> str:
        return "ExchangeBuilder(name=%r, type=%r)" % (self._name, self._type)
