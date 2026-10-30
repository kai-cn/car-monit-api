# -*- coding: utf-8 -*-
"""org.springframework.kafka.support.SendResult / RecordMetadata

【无 Java 源文件：框架类替身】
Java 侧：
    org.springframework.kafka.support.SendResult<K, V>       // send() 成功结果
    org.apache.kafka.clients.producer.RecordMetadata        // 元数据（offset/partition）
业务代码用法：
    result.getRecordMetadata().offset()

【Java→Python 关键差异】
1) Java 的 `SendResult` 是 ProducerRecord + RecordMetadata 的二元组；Python 用
   普通类 + dataclass 等价表达，方法名保持 `getRecordMetadata()`。
2) `offset()` 是 Kafka 分区内偏移量（long）→ Python int。
3) 真实 Kafka 的 offset 由 broker 分配；本替身由 KafkaTemplate 用自增计数器模拟。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["RecordMetadata", "SendResult"]


@dataclass
class RecordMetadata(object):
    """`org.apache.kafka.clients.producer.RecordMetadata` 的替身。"""

    _topic: str = ""
    _partition: int = 0
    _offset: int = 0

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return self._partition

    def offset(self) -> int:
        return self._offset

    def hasOffset(self) -> bool:
        return self._offset >= 0


class SendResult(object):
    """`org.springframework.kafka.support.SendResult<K,V>` 的替身。"""

    def __init__(self, record_metadata: RecordMetadata, producer_record: Any = None) -> None:
        self._record_metadata = record_metadata
        self._producer_record = producer_record

    def getRecordMetadata(self) -> RecordMetadata:
        return self._record_metadata

    def getProducerRecord(self) -> Any:
        """对应 `getProducerRecord()`（含 topic/key/value）。"""
        return self._producer_record
