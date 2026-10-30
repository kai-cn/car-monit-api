# -*- coding: utf-8 -*-
"""org.springframework.amqp.core.Exchange

【无 Java 源文件：框架类替身】
Java 侧来自 spring-amqp：``org.springframework.amqp.core.Exchange``。
本工程用法（RabbitMqConfig）：
    @Bean public Exchange snapshotFlowExchange() {
        return ExchangeBuilder.directExchange(topic).durable(true).build();
    }

【Java→Python】关键差异
1) Java 的 ``Exchange`` 是**抽象类**，实际实例是 ``DirectExchange`` / ``TopicExchange`` /
   ``FanoutExchange`` / ``HeadersExchange`` 等子类；``ExchangeBuilder.directExchange()``
   返回的是 builder，``build()`` 才产出 ``DirectExchange``。
   本工程只通过 builder 使用、从不 ``instanceof DirectExchange``，因此替身直接用
   一个具体类 ``Exchange`` + ``type`` 字段表达（type = "direct"/"topic"/...）。
2) Java 的 ``isDurable()`` / ``isAutoDelete()`` 是 boolean getter；Python 同名方法。
3) ``getArguments()`` 在 Java 里返回不可变 ``Map<String,Object>``；替身返回副本。
4) ``Exchange`` 还有 ``setAdminsThatShouldDeclare`` 等容器内部方法，不实现。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["Exchange"]

#: RabbitMQ 支持的交换机类型（Java 子类名去掉 "Exchange" 后缀的小写形式）
TYPE_DIRECT = "direct"
TYPE_TOPIC = "topic"
TYPE_FANOUT = "fanout"
TYPE_HEADERS = "headers"


class Exchange(object):
    """``Exchange`` 的替身（name + type + durable + autoDelete + arguments）。"""

    def __init__(self, name: str, type: str = TYPE_DIRECT, durable: bool = True,
                 auto_delete: bool = False,
                 arguments: Optional[Dict[str, Any]] = None) -> None:
        self._name = name
        self._type = type
        self._durable = durable
        self._auto_delete = auto_delete
        self._arguments = dict(arguments or {})

    # ------------------------------------------------------------------ getter
    def getName(self) -> str:
        return self._name

    def getType(self) -> str:
        return self._type

    def isDurable(self) -> bool:
        # Java 的字段默认值是 true（Exchange(String name) 构造器等价 durable=true）
        return self._durable

    def isAutoDelete(self) -> bool:
        return self._auto_delete

    def getArguments(self) -> Dict[str, Any]:
        return dict(self._arguments)

    def __repr__(self) -> str:
        return "Exchange(name=%r, type=%r, durable=%r, autoDelete=%r)" % (
            self._name, self._type, self._durable, self._auto_delete)
