# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.QueueBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.QueueBuilder``。
本工程用法（RabbitMqConfig）：
    QueueBuilder.durable("queue.snapshot.flow")
            .deadLetterExchange(deadLetterExchange)
            .deadLetterRoutingKey(deadLetterRoutingKey)
            .ttl(60000)
            .build()

【Java→Python】关键差异
1) Java 的 ``QueueBuilder`` 是抽象类，``durable(name)`` / ``nonDurable(name)`` 返回
   匿名子类；替身用具体类 + ``_durable`` 字段表达。
2) 死信相关方法在 Java 里只是往 ``arguments`` 塞协议 key：
   ``deadLetterExchange(name)`` → ``x-dead-letter-exchange``，
   ``deadLetterRoutingKey(key)`` → ``x-dead-letter-routing-key``，
   ``ttl(int)`` → ``x-message-ttl``。替身保持完全相同的 key，便于断言。
3) Java 的 ``ttl(int)`` 单位是**毫秒**（RabbitMQ 协议规定）；本工程传 60000 = 60 秒。
4) ``maxLength`` / ``maxPriority`` / ``singleActiveConsumer`` / ``quorum`` 等
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from org.springframework.amqp.core.Queue import (
    Queue, X_DEAD_LETTER_EXCHANGE, X_DEAD_LETTER_ROUTING_KEY, X_MESSAGE_TTL)

__all__ = ["QueueBuilder"]


class QueueBuilder(object):
    """``QueueBuilder`` 的替身。"""

    def __init__(self, name: str, durable: bool = True) -> None:
        self._name = name
        self._durable = durable
        self._exclusive = False
        self._auto_delete = False
        self._arguments: Dict[str, Any] = {}

    # ------------------------------------------------------------------ 静态工厂
    @staticmethod
    def durable(name: str) -> "QueueBuilder":
        """对应 ``durable(String name)``：durable=true。"""
        return QueueBuilder(name, True)

    @staticmethod
    def nonDurable(name: str) -> "QueueBuilder":
        return QueueBuilder(name, False)

    # ------------------------------------------------------------------ 链式 setter
    def deadLetterExchange(self, exchange_name: str) -> "QueueBuilder":
        """对应 ``deadLetterExchange(String)`` → x-dead-letter-exchange。"""
        self._arguments[X_DEAD_LETTER_EXCHANGE] = exchange_name
        return self

    def deadLetterRoutingKey(self, routing_key: str) -> "QueueBuilder":
        """对应 ``deadLetterRoutingKey(String)`` → x-dead-letter-routing-key。"""
        self._arguments[X_DEAD_LETTER_ROUTING_KEY] = routing_key
        return self

    def ttl(self, ttl_millis: int) -> "QueueBuilder":
        """对应 ``ttl(int)``：单位毫秒 → x-message-ttl。"""
        self._arguments[X_MESSAGE_TTL] = int(ttl_millis)
        return self

    def exclusive(self, exclusive: bool) -> "QueueBuilder":
        self._exclusive = exclusive
        return self

    def autoDelete(self, auto_delete: bool) -> "QueueBuilder":
        self._auto_delete = auto_delete
        return self

    def withArgument(self, key: str, value: Any) -> "QueueBuilder":
        self._arguments[key] = value
        return self

    # ------------------------------------------------------------------ 构建
    def build(self) -> Queue:
        return Queue(self._name, self._durable, self._exclusive,
                     self._auto_delete, self._arguments)

    def __repr__(self) -> str:
        return "QueueBuilder(name=%r, durable=%r)" % (self._name, self._durable)
