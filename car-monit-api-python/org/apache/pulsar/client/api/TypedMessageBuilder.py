# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.TypedMessageBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.TypedMessageBuilder<T>`，
由 `producer.newMessage()` 创建，链式设置 key/value 后 `sendAsync()`：
    TypedMessageBuilder<String> messageBuilder = producer.newMessage()
            .key(record.getDataId())
            .value(record.getMessageJson());
    CompletableFuture<MessageId> future = messageBuilder.sendAsync();

【Java→Python 关键差异】
1) Java 的 `sendAsync()` 把消息交给 Pulsar 的 IO 线程，**立即返回** future，回调由
   IO 线程触发；本替身用 `CompletableFuture.supplyAsync(...)` 在 commonPool 上执行
   “写入内存队列 + 生成 MessageId”，同样是“先返回 future、后完成”。
   由于 CompletableFuture 替身的 thenAccept/exceptionally 对“已完成/未完成”都兼容，
   调用方写法与 Java 完全一致（见 PulsarProducerService.sendMessage）。
2) Java 的 `property(name, value)` 是 `TypedMessageBuilder` 的可选项；这里同样保存到
   dict（本工程未使用，保留以便对照）。
3) `send()`（同步）在 Java 里会阻塞直到 broker ack；替身直接调用 Producer 的内存写入。
"""
from __future__ import annotations

from typing import Any, Optional

from java.util.concurrent.CompletableFuture import CompletableFuture
from org.apache.pulsar.client.api.MessageId import MessageId

__all__ = ["TypedMessageBuilder"]


class TypedMessageBuilder(object):
    """`TypedMessageBuilder<T>` 的进程内替身（链式 API 与 Java 同名）。"""

    def __init__(self, producer: Any) -> None:
        self._producer = producer
        self._key: Optional[str] = None
        self._value: Any = None
        self._properties: dict = {}

    # ------------------------------------------------------------------ 链式设置
    def key(self, key: str) -> "TypedMessageBuilder":
        """等价 `key(String key)`：消息路由键（Pulsar 里用于 key_shared 订阅）。"""
        self._key = key
        return self

    def value(self, value: Any) -> "TypedMessageBuilder":
        """等价 `value(T value)`：消息载荷（本工程是 JSON 字符串）。"""
        self._value = value
        return self

    def property(self, name: str, value: str) -> "TypedMessageBuilder":
        """等价 `property(String name, String value)`：附加属性。"""
        self._properties[name] = value
        return self

    # ------------------------------------------------------------------ 发送
    def send(self) -> MessageId:
        """等价 `send()`：同步发送并返回 MessageId。"""
        return self._producer._doSend(self._key, self._value, dict(self._properties))

    def sendAsync(self) -> CompletableFuture:
        """等价 `sendAsync()`：异步发送，返回 `CompletableFuture<MessageId>`。"""
        # 【Java→Python】用默认参数把当前 key/value 固化到 lambda 里，
        # 避免 builder 后续被复用修改导致闭包读到新值（Java 里是发出去就固定了）。
        key, value, properties = self._key, self._value, dict(self._properties)
        return CompletableFuture.supplyAsync(
            lambda: self._producer._doSend(key, value, properties))
