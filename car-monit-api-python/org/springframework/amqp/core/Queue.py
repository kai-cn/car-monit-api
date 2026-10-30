# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.Queue

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.Queue``。
本工程用法（RabbitMqConfig）：
    @Bean public Queue snapshotFlowQueue() {
        return QueueBuilder.durable("queue.snapshot.flow")
                .deadLetterExchange(deadLetterExchange)
                .deadLetterRoutingKey(deadLetterRoutingKey)
                .ttl(60000)
                .build();
    }

【Java→Python】关键差异
1) Java 的 ``Queue`` 有多个构造器：``Queue(String name)``（durable=true）、
   ``Queue(String name, boolean durable)``、``Queue(String name, boolean durable,
   boolean exclusive, boolean autoDelete, Map<String,Object> arguments)``。
   Python 无重载 → 用一个带默认值的构造器表达，默认值与 Java 的
   ``Queue(String name)`` 一致（durable=true, exclusive=false, autoDelete=false）。
2) 死信/TTL 等参数在 Java 里是 ``Map<String,Object> arguments`` 的固定 key：
   ``x-dead-letter-exchange`` / ``x-dead-letter-routing-key`` / ``x-message-ttl``，
   由 ``QueueBuilder`` 写入；替身保持同样的 key 名称（RabbitMQ 协议规定）。
3) ``Queue`` 的 ``getName()`` 是队列名；``getActualName()`` 支持表达式解析，
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["Queue"]

#: RabbitMQ 协议定义的队列参数 key（与 Spring QueueBuilder 写入的完全相同）
X_DEAD_LETTER_EXCHANGE = "x-dead-letter-exchange"
X_DEAD_LETTER_ROUTING_KEY = "x-dead-letter-routing-key"
X_MESSAGE_TTL = "x-message-ttl"
X_MAX_LENGTH = "x-max-length"


class Queue(object):
    """``Queue`` 的替身（name + durable + exclusive + autoDelete + arguments）。"""

    def __init__(self, name: str, durable: bool = True, exclusive: bool = False,
                 auto_delete: bool = False,
                 arguments: Optional[Dict[str, Any]] = None) -> None:
        self._name = name
        self._durable = durable
        self._exclusive = exclusive
        self._auto_delete = auto_delete
        self._arguments = dict(arguments or {})

    # ------------------------------------------------------------------ getter
    def getName(self) -> str:
        return self._name

    def isDurable(self) -> bool:
        return self._durable

    def isExclusive(self) -> bool:
        return self._exclusive

    def isAutoDelete(self) -> bool:
        return self._auto_delete

    def getArguments(self) -> Dict[str, Any]:
        return dict(self._arguments)

    def __repr__(self) -> str:
        return ("Queue(name=%r, durable=%r, exclusive=%r, autoDelete=%r, "
                "arguments=%r)" % (self._name, self._durable, self._exclusive,
                                   self._auto_delete, self._arguments))
