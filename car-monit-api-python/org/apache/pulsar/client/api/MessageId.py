# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.MessageId

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.MessageId`（接口），
实际实现为 `MessageIdImpl`（内部类）。业务代码用法：
    CompletableFuture<MessageId> future = builder.sendAsync();
    pulsarMessageRecordMapper.updateStatusById(..., messageId.toString());

【Java→Python 关键差异】
1) Java 的 `MessageId` 是接口，`toString()` 输出 `"ledgerId:entryId:partitionIndex:batchIndex"`
   （Pulsar 3.x 的 MessageIdImpl#toString 即此格式）。Python 用普通类实现同一格式，
   保证落库的 message_id 字符串形态一致。
2) Java 的 MessageId 实现 Comparable/equals；这里补 `__eq__`/`__hash__`，便于测试断言。
"""
from __future__ import annotations

__all__ = ["MessageId"]


class MessageId(object):
    """`MessageId` 的进程内替身：只描述“消息在哪个 ledger/entry”。"""

    def __init__(self, ledger_id: int = 0, entry_id: int = 0,
                 partition_index: int = -1, batch_index: int = -1) -> None:
        self._ledger_id = ledger_id
        self._entry_id = entry_id
        self._partition_index = partition_index
        self._batch_index = batch_index

    def toString(self) -> str:
        # 与 Pulsar MessageIdImpl#toString() 的格式保持一致
        return "%d:%d:%d:%d" % (self._ledger_id, self._entry_id,
                                self._partition_index, self._batch_index)

    def __str__(self) -> str:
        # 【Java→Python】Java 的字符串拼接会调用 toString()；Python 对应 __str__
        return self.toString()

    def __repr__(self) -> str:
        return "MessageId(%s)" % self.toString()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageId):
            return NotImplemented
        return self.toString() == other.toString()

    def __hash__(self) -> int:
        return hash(self.toString())
