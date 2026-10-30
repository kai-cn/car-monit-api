# -*- coding: utf-8 -*-
"""org.apache.rocketmq.spring.core.RocketMQListener

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-spring-boot-starter：
``org.apache.rocketmq.spring.core.RocketMQListener<T>``。
它只有一个方法：
    void onMessage(T message);

本工程用法（RocketMqConsumer）：
    public class RocketMqConsumer implements RocketMQListener<MessageExt> {
        @Override public void onMessage(MessageExt messageExt) { ... }
    }

【Java→Python】关键差异
1) Java 的 **泛型接口** ``RocketMQListener<MessageExt>`` 在 Python 里没有运行时泛型；
   这里用 ``Generic[T]`` 仅作类型标注（运行时不校验消息类型），
   对应 Java 的泛型擦除。
2) Java 的 ``@Override`` 由编译器校验；Python 用 ``abc.ABC`` + ``@abstractmethod``
   在**实例化时**校验“必须实现 onMessage”（没有覆盖就 TypeError）。
   注意：这与编译期检查不完全等价，若子类漏写 onMessage，报错时机被推迟。
3) Java 的接口方法默认 public；Python 无访问修饰符，按约定不加下划线。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

__all__ = ["RocketMQListener"]

T = TypeVar("T")


class RocketMQListener(ABC, Generic[T]):
    """``RocketMQListener<T>`` 的替身（抽象接口）。"""

    @abstractmethod
    def onMessage(self, message: T) -> None:
        """消费一条消息；实现方不应吞掉异常（RocketMQ 依赖异常触发重投）。"""
        raise NotImplementedError
