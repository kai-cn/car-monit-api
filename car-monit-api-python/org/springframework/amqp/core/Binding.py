# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.Binding

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.Binding``。
本工程用法（RabbitMqConfig）：
    @Bean public Binding snapshotFlowBinding(Queue q, Exchange ex) {
        return BindingBuilder.bind(q).to(ex).with("snapshot.flow").noargs();
    }

【Java→Python】关键差异
1) Java 的 ``Binding`` 有 ``BindingDestinationType``（QUEUE / EXCHANGE）与
   ``DestinationType`` 枚举；本工程只做队列到交换机的绑定（QUEUE），
   替身只记录 destination 名称。
2) Java 的 ``getDestination()`` / ``getExchange()`` / ``getRoutingKey()`` 返回 String；
   替身保持相同的返回值类型。
3) 构造器在 Java 里是 package-private（只能由 BindingBuilder 创建）；
   Python 无法限制访问级别，替身在 docstring 中说明“应由 BindingBuilder 创建”。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["Binding"]

DESTINATION_QUEUE = "QUEUE"
DESTINATION_EXCHANGE = "EXCHANGE"


class Binding(object):
    """``Binding`` 的替身（destination + exchange + routingKey）。"""

    def __init__(self, destination: str, destination_type: str, exchange: str,
                 routing_key: Optional[str] = None,
                 arguments: Optional[Dict[str, Any]] = None) -> None:
        self._destination = destination
        self._destination_type = destination_type
        self._exchange = exchange
        self._routing_key = routing_key
        self._arguments = dict(arguments or {})

    # ------------------------------------------------------------------ getter
    def getDestination(self) -> str:
        """目标名（本工程为队列名）。"""
        return self._destination

    def getDestinationType(self) -> str:
        return self._destination_type

    def getExchange(self) -> str:
        return self._exchange

    def getRoutingKey(self) -> Optional[str]:
        return self._routing_key

    def getArguments(self) -> Dict[str, Any]:
        return dict(self._arguments)

    def __repr__(self) -> str:
        return "Binding(destination=%r, exchange=%r, routingKey=%r)" % (
            self._destination, self._exchange, self._routing_key)
