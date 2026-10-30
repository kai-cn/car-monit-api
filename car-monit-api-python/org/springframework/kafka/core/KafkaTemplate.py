# -*- coding: utf-8 -*-
"""org.springframework.kafka.core.KafkaTemplate

【无 Java 源文件：框架类替身】
Java 侧来自 spring-kafka：`org.springframework.kafka.core.KafkaTemplate<K, V>`。
业务代码用法：
    kafkaTemplate.send(topic, key, value).addCallback(callback);
    kafkaTemplate.send(topic, key, value);            // 忽略返回值

【Java→Python 关键差异】
1) Java 的 KafkaTemplate 把消息交给 KafkaProducer，**异步**返回 ListenableFuture，
   broker ack 由网络线程触发回调；本替身没有真实 broker，`send()` 在**当前线程同步完成**
   （offset 用自增计数器模拟），并利用 ListenableFuture 的「先完成、后注册回调」语义
   让 `addCallback` 立即收到结果 —— 调用方的写法与 Java 完全一致。
2) 真实发送失败时 Java 抛 KafkaException / 触发 onFailure；本替身提供
   `fail_next`（注入一次失败）与 `always_fail` 两个开关，便于测试 onFailure 分支。
3) `KafkaTemplate` 在 Spring 里是**单例 Bean**；这里用模块级 `defaultKafkaTemplate()`
   还原“所有服务向同一个 Kafka 集群发送”的语义，测试也可直接检查已发送记录。
4) `flush()` 在真实 Kafka 里是等待缓冲区清空；本替身无缓冲，等价空操作。
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from org.springframework.kafka.support.SendResult import RecordMetadata, SendResult
from org.springframework.util.concurrent.ListenableFuture import ListenableFuture

__all__ = ["KafkaTemplate", "defaultKafkaTemplate"]


class KafkaTemplate(object):
    """`KafkaTemplate<K,V>` 的进程内替身。"""

    def __init__(self, bootstrap_servers: Any = "localhost:9092") -> None:
        # 【Java→Python】Java 的构造器吃的是 ``ProducerFactory``：
        #     new KafkaTemplate<>(producerFactory())
        # 替身允许直接传工厂对象，内部从它配置的 bootstrap.servers 取地址；
        # 这样 KafkaProducerConfig.kafkaTemplate() 的写法可以与 Java 逐字一致。
        if hasattr(bootstrap_servers, "getConfigurationProperties"):
            configs = bootstrap_servers.getConfigurationProperties()
            bootstrap_servers = str(configs.get("bootstrap.servers", "localhost:9092"))
        self.bootstrap_servers = bootstrap_servers
        # 【Java→Python】模拟 broker 侧状态：分区固定为 0，offset 按 topic 自增
        self._offset_by_topic: dict = {}
        self._sent_records: List[Tuple[str, Any, Any]] = []
        self.fail_next: Optional[BaseException] = None  # 注入“下一次发送失败”
        self.always_fail = False  # 注入“持续发送失败”

    # ------------------------------------------------------------------ 发送
    def send(self, topic: str, key: Any = None, value: Any = None) -> ListenableFuture:
        """等价 `send(String topic, K key, V value)`；返回已完成的 ListenableFuture。"""
        future = ListenableFuture()

        error = self._next_error()
        if error is not None:
            # 真实 Kafka 在元数据不可用时同步抛 KafkaException；
            # 本替身把失败放进 Future，让 onFailure 分支得以执行（更像 broker 拒绝 ack）。
            future._setException(error)
            return future

        self._sent_records.append((topic, key, value))
        offset = self._offset_by_topic.get(topic, 0)
        self._offset_by_topic[topic] = offset + 1
        metadata = RecordMetadata(_topic=topic, _partition=0, _offset=offset)
        future._setResult(SendResult(metadata, producer_record=(topic, key, value)))
        return future

    def sendDefault(self, value: Any) -> ListenableFuture:
        """等价 `sendDefault(V value)`：使用配置的默认 topic。"""
        return self.send(self.default_topic, None, value)  # type: ignore[attr-defined]

    def flush(self) -> None:
        """等待缓冲区清空（本替身无缓冲，空操作）。"""
        return None

    def close(self) -> None:
        return None

    # ------------------------------------------------------------------ 测试辅助
    def sentRecords(self) -> List[Tuple[str, Any, Any]]:
        """查看已“发送成功”的记录（Java 没有这个方法，仅替身用于校验）。"""
        return list(self._sent_records)

    def _next_error(self) -> Optional[BaseException]:
        if self.always_fail:
            return RuntimeError("org.apache.kafka.common.errors.TimeoutException: 模拟发送失败")
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            return error
        return None


# 进程级单例：等价 Spring 容器里唯一的 KafkaTemplate Bean
_DEFAULT_TEMPLATE: Optional[KafkaTemplate] = None


def defaultKafkaTemplate() -> KafkaTemplate:
    global _DEFAULT_TEMPLATE
    if _DEFAULT_TEMPLATE is None:
        _DEFAULT_TEMPLATE = KafkaTemplate()
    return _DEFAULT_TEMPLATE
