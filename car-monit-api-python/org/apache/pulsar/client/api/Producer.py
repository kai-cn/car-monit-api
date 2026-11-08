# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.Producer

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.Producer<T>`，
由 `PulsarClient.newProducer(Schema).topic(...).create()` 创建，业务代码只用到：
    producer.newMessage().key(k).value(v).sendAsync();
    producer.isConnected();
    producer.close();

【Java→Python 关键差异】
1) 真实 Pulsar 的消息先写入 BookKeeper，成功后返回 `MessageId(ledgerId:entryId:...)`；
   本替身用自增 entryId + 固定 ledgerId=0 模拟，`sentMessages()` 供测试检查。
2) 真实 `sendAsync()` 在 IO 线程完成；本替身的 `TypedMessageBuilder.sendAsync`
   在 commonPool 线程调用 `_doSend`，异常会进入 CompletableFuture 的异常链
   （对应 Pulsar 的 `PulsarClientException`），由 `exceptionally` 分支处理。
3) 提供 `fail_next`/`always_fail` 两个“测试注入开关”，便于验证失败重试链路
   （Java 侧靠 broker 故障注入，无法在单测里稳定复现）。
4) `close()` 在 Java 里会 flush 未确认消息并断开连接；替身只是把 connected 置 False。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from org.apache.pulsar.client.api.MessageId import MessageId
from org.apache.pulsar.client.api.TypedMessageBuilder import TypedMessageBuilder

from app.runtime import reject_shim_operation

__all__ = ["Producer"]


class Producer(object):
    """`Producer<T>` 的进程内替身（本工程只消费 JSON 字符串）。"""

    def __init__(self, topic: str = "persistent://public/default/default",
                 schema: Any = None) -> None:
        self.topic = topic
        self.schema = schema
        self._connected = True
        self._entry_id = 0                       # 模拟 ledger 内的 entry 自增
        self._ledger_id = 0                      # 固定一个 ledger
        self._sent_messages: List[Tuple[str, Any, Any]] = []
        self.fail_next: Optional[BaseException] = None  # 注入“下一次发送失败”
        self.always_fail = False                          # 注入“持续发送失败”

    # ------------------------------------------------------------------ 元信息
    def getTopic(self) -> str:
        return self.topic

    def getProducerName(self) -> str:
        """等价 `getProducerName()`：真实 Pulsar 未指定时自动生成。"""
        return "producer-%s" % self.topic

    def isConnected(self) -> bool:
        """健康检查用：连接是否有效。"""
        return self._connected

    # ------------------------------------------------------------------ 发送
    def newMessage(self) -> TypedMessageBuilder:
        """等价 `newMessage()`：返回消息构建器。"""
        return TypedMessageBuilder(self)

    def send(self, value: Any) -> MessageId:
        """等价 `send(T value)`：同步发送（无 key）。"""
        return self.newMessage().value(value).send()

    def sendAsync(self, value: Any):
        """等价 `sendAsync(T value)`：异步发送（无 key）。"""
        return self.newMessage().value(value).sendAsync()

    def _doSend(self, key: Optional[str], value: Any, properties: Dict[str, str]) -> MessageId:
        """真正“写 broker”的动作（由 TypedMessageBuilder 调用）。

        【Java→Python】真实 Pulsar 发送失败会抛 `PulsarClientException`；这里用
        RuntimeError 表达，异常会通过 CompletableFuture 传递到 `exceptionally`。
        """
        # P0-2：prod 模式下拒绝“假成功”发送（send/sendAsync/TypedMessageBuilder 均收口于此）。
        reject_shim_operation(
            "Pulsar Producer.send/sendAsync",
            "（真实 Pulsar 适配器未实现，消息不会写入 BookKeeper。）")
        error = self._next_error()
        if error is not None:
            raise error

        self._entry_id += 1
        self._sent_messages.append((self.topic, key, value))
        return MessageId(ledger_id=self._ledger_id, entry_id=self._entry_id)

    def close(self) -> None:
        """等价 `close()`：断开连接（本替身只改状态）。"""
        self._connected = False

    # ------------------------------------------------------------------ 测试辅助
    def sentMessages(self) -> List[Tuple[str, Any, Any]]:
        """查看已“发送成功”的消息（Java 没有此方法，仅替身用于校验）。"""
        return list(self._sent_messages)

    def _next_error(self) -> Optional[BaseException]:
        if not self._connected:
            return RuntimeError("org.apache.pulsar.client.api.PulsarClientException: Producer 已关闭")
        if self.always_fail:
            return RuntimeError("org.apache.pulsar.client.api.PulsarClientException: 模拟发送失败")
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            return error
        return None
