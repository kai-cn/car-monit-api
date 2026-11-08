# -*- coding: utf-8 -*-
"""真实 Kafka 适配（P2-4，docs/迁移审阅报告.md）。

背景
----
此前 Kafka 相关类全部是进程内替身（KafkaTemplate 的消息进 ``_sent_records``
列表、FlinkKafkaConsumer 的 ``run`` 是空操作）。本模块在设置
``CAR_MONIT_KAFKA_URL``（bootstrap servers，如 ``127.0.0.1:9092``）后，
把发送/消费切换到真实 broker（confluent-kafka 2.16 / librdkafka），业务代码零改动。

生产者语义（对齐业务 KafkaProducerConfig 的可靠性配置）
--------------------------------------------------------
* ``acks=all`` + ``enable.idempotence=true`` + ``linger.ms=10`` + ``lz4`` +
  ``max.in.flight=5``：逐项镜像业务配置；Java 的 ``retries=MAX`` 在 librdkafka
  里的对应语义是"可重试错误无限重试直到 message.timeout.ms"（默认行为），
  ``message.timeout.ms=120000`` 对齐 Java ``delivery.timeout.ms`` 默认值。
* **配置键名映射**：librdkafka 不认识 Java 键名（``buffer.memory`` 会抛
  Unknown configuration property），``buffer.memory=32MB`` 映射为
  ``queue.buffering.max.kbytes=32768``。
* 序列化：直接复用替身的 :class:`StringSerializer` / :class:`JsonSerializer`
  （key 字符串 → UTF-8；value 对象 → fastjson2 JSON 字节）——与替身/Java
  逐字节一致。
* 发送回调：``send()`` 立即返回 ``ListenableFuture``，broker ack 后由
  librdkafka 回调线程完成 future（Java 的 KafkaTemplate 同样在 producer IO
  线程触发回调）；送达失败 → ``_setException``（onFailure 分支执行）。

消费语义（FlinkKafkaConsumer 真实路径）
----------------------------------------
* 消费组 / ``auto.offset.reset`` / ``enable.auto.commit`` 全部来自业务 props；
  ``bootstrap.servers`` 以 ``CAR_MONIT_KAFKA_URL`` 为准（env 是真实集群的
  唯一事实源，props 里可能是生产地址）。
* ``enable.auto.commit=false``（Flink 标准）：Java 在 checkpoint 时提交位点，
  本地替身环境无 checkpoint → **每条 collect 后同步提交**（at-least-once，
  与 Flink 语义一致：故障恢复后重复消费而非丢失）。
* broker 不可用：Java 的 Flink source 持续重试（作业不挂），对齐为记录
  warning 后继续 poll（**不熔断、不退出**）。
* 反序列化异常：schema 的异常向上抛（Java：source 失败）；非法 UTF-8 由
  SimpleStringSchema 按 Java ``new String(bytes, UTF_8)`` 语义替换字符。

降级语义（仅生产者；消费者按上一条持续重试）
----------------------------------------------
* ``CAR_MONIT_KAFKA_FALLBACK=error``（prod 模式默认）：失败**抛错/进失败
  future**——对齐 Java（KafkaException 传播 / onFailure）；
* ``CAR_MONIT_KAFKA_FALLBACK=memory``（shim 模式默认）：**疑似不可用**的
  同步/送达错误（broker 全不可达、传输层、超时耗尽）触发熔断，后续 send
  落回进程内替身（60s 半开重试，恢复自动切回）；**确定性错误**（消息
  超限等）不触发熔断，只让该条消息失败；降级期间写入不会回灌真实 broker，
  失败瞬间的消息保持失败（与 Java 一致，不静默重投）。

线程安全：confluent-kafka 客户端自带后台线程；熔断标志仅做尽力而为的
原子性（竞争最坏结果是多打一条日志/多一次重试）。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

from confluent_kafka import KafkaError, KafkaException, Producer
from confluent_kafka import Consumer as ConfluentConsumer

from org.apache.kafka.common.serialization.JsonSerializer import JsonSerializer
from org.apache.kafka.common.serialization.StringSerializer import StringSerializer
from org.springframework.kafka.support.SendResult import RecordMetadata, SendResult
from org.springframework.util.concurrent.ListenableFuture import ListenableFuture

from app.middleware.breaker import CircuitBreaker

__all__ = [
    "RealKafkaProducer",
    "consumer_conf_from_props",
    "kafka_fallback_policy",
    "shared_kafka_producer",
    "shared_kafka_url",
]

log = logging.getLogger(__name__)

#: 熔断后多久半开重试真实 broker（秒）
_RETRY_SECONDS = 60.0

#: 生产者配置：逐项镜像业务 KafkaProducerConfig（Java 键名 → librdkafka 键名，
#: 见模块 docstring 的映射说明；retries=MAX 对应 librdkafka 的"重试到超时"默认行为）
_PRODUCER_CONF = {
    "acks": "all",
    "enable.idempotence": True,
    "linger.ms": 10,
    "compression.type": "lz4",
    "max.in.flight.requests.per.connection": 5,
    "batch.size": 16384,
    "queue.buffering.max.kbytes": 32768,  # Java buffer.memory=32MB
    "message.timeout.ms": 120000,         # Java delivery.timeout.ms 默认
}

#: 疑似"服务不可用"的送达错误（触发熔断）；其余（消息超限等）视为确定性错误。
#: 注意 confluent-kafka 里客户端本地错误带下划线前缀（_ALL_BROKERS_DOWN 等），
#: 服务端错误用原始码值（NETWORK_EXCEPTION=13 等）。
_OUTAGE_CODES = frozenset((
    KafkaError._ALL_BROKERS_DOWN,
    KafkaError._TRANSPORT,
    KafkaError.NETWORK_EXCEPTION,
    KafkaError._MSG_TIMED_OUT,
    KafkaError._AUTHENTICATION,
))


def kafka_fallback_policy() -> str:
    """降级策略：``CAR_MONIT_KAFKA_FALLBACK`` 显式优先；默认 prod=error / shim=memory。"""
    explicit = (os.environ.get("CAR_MONIT_KAFKA_FALLBACK") or "").strip().lower()
    if explicit in ("memory", "error"):
        return explicit
    from app.runtime import is_strict

    return "error" if is_strict() else "memory"


def shared_kafka_url() -> Optional[str]:
    """真实集群开关：``CAR_MONIT_KAFKA_URL``（bootstrap servers）；未设 → ``None``。"""
    return (os.environ.get("CAR_MONIT_KAFKA_URL") or "").strip() or None


def _looks_like_outage(error: Any) -> bool:
    """是否疑似“服务不可用”（触发熔断）。None 安全。

    librdkafka 的 ``produce()`` 也可能同步抛 KafkaException（如消息超限的
    客户端侧拦截），同步/异步路径都必须按错误类别分流。
    """
    if error is None:
        return False
    code = error.code()
    if not isinstance(code, int):
        return False
    return code in _OUTAGE_CODES


def _as_exception(error: KafkaError) -> RuntimeError:
    """librdkafka 错误 → 与替身文案风格一致的异常（业务只做 str(e)/日志）。"""
    return RuntimeError(
        "org.apache.kafka.common.errors.%s: %s" % (error.name(), error.str()))


# --------------------------------------------------------------------- 生产者
class RealKafkaProducer:
    """真实 Kafka 生产者后端（confluent-kafka Producer + 替身序列化器）。

    构造**不建连**（librdkafka 惰性连接），首次 produce 才触达 broker。
    """

    def __init__(self, bootstrap_servers: str, fallback: Optional[str] = None,
                 client: Optional[Any] = None,
                 value_serializer: Optional[Any] = None,
                 key_serializer: Optional[Any] = None) -> None:
        self._url = bootstrap_servers
        self._fallback = fallback or kafka_fallback_policy()
        self._key_serializer = key_serializer or StringSerializer()
        self._value_serializer = value_serializer or JsonSerializer()
        self._producer = client or Producer(
            dict(_PRODUCER_CONF, **{"bootstrap.servers": bootstrap_servers}))
        self._breaker = CircuitBreaker(_RETRY_SECONDS)

    # ------------------------------------------------------------- dispatch
    def _trip(self, reason: Any) -> None:
        # H2：失败分支无条件刷新窗口计时（包括半开探测失败）
        first = self._breaker.failure()
        log.warning("[Kafka适配] %s（疑似 broker 不可用），熔断降级为进程内替身"
                    "（%.0fs 后半开重试；降级期间的写入不会回灌真实 broker）: %s",
                    "发送失败" if first else "半开探测仍失败", _RETRY_SECONDS, reason)

    @property
    def degraded(self) -> bool:
        """当前是否处于熔断降级（供健康检查/测试观察）。"""
        return self._breaker.degraded

    # ----------------------------------------------------------------- 发送
    def send(self, topic: str, key: Any, value: Any,
             memory: Callable[[], ListenableFuture]) -> ListenableFuture:
        """等价 ``KafkaTemplate.send``：立即返回 future，ack 后完成。"""
        allowed, probe = self._breaker.acquire()
        if not allowed:
            return memory()

        future = ListenableFuture()
        try:
            key_bytes = self._key_serializer.serialize(topic, key)
            value_bytes = self._value_serializer.serialize(topic, value)
        except Exception:  # noqa: BLE001 - 序列化失败=确定性错误，直接进失败 future
            if probe:
                self._breaker.release_probe()
            future._setException(
                RuntimeError("org.apache.kafka.common.errors.SerializationException: "
                             "key/value 序列化失败"))
            return future

        def _on_delivery(error: Optional[KafkaError], msg: Any) -> None:
            if error is None:
                metadata = RecordMetadata(_topic=msg.topic(),
                                          _partition=msg.partition(),
                                          _offset=msg.offset())
                future._setResult(SendResult(metadata,
                                             producer_record=(topic, key, value)))
                if self._breaker.success():
                    log.info("[Kafka适配] 真实 broker 已恢复（%s）", self._url)
                return
            if self._fallback == "memory" and _looks_like_outage(error):
                # H2：送达失败无条件刷新窗口计时
                self._trip(error)
            elif probe:
                self._breaker.release_probe()
            future._setException(_as_exception(error))

        try:
            self._producer.produce(topic=topic, key=key_bytes, value=value_bytes,
                                   on_delivery=_on_delivery)
        except BufferError:
            # 32MB 发送队列打满：Java 在 max.block.ms 后抛 TimeoutException，
            # 这里直接失败该条（文档化差异：不阻塞调用线程）
            if probe:
                self._breaker.release_probe()
            future._setException(
                RuntimeError("org.apache.kafka.common.errors.TimeoutException: "
                             "本地发送队列已满（BufferError）"))
        except KafkaException as error:
            if self._fallback == "error":
                if probe:
                    self._breaker.release_probe()
                raise
            inner = error.args[0] if error.args else None
            if _looks_like_outage(inner):
                self._trip(error)
                return memory()
            # 确定性同步错误（如消息超限的客户端侧拦截）：只失败该条，不熔断
            if probe:
                self._breaker.release_probe()
            future._setException(_as_exception(inner) if inner is not None
                                 else RuntimeError(str(error)))
        return future

    # ------------------------------------------------------------- 生命周期
    def flush(self, timeout: float = 10.0) -> int:
        """等待缓冲区清空；返回未送达条数（0 = 全部送达）。"""
        return self._producer.flush(timeout)

    def close(self) -> None:
        try:
            self._producer.flush(10)
        except Exception:  # noqa: BLE001 - 关闭期尽力而为
            log.warning("[Kafka适配] 关闭前 flush 异常（忽略）", exc_info=True)


# --------------------------------------------------------------------- 消费
def consumer_conf_from_props(props: Any) -> Dict[str, Any]:
    """业务 props（FlinkKafkaConsumer 的 Properties）→ confluent Consumer 配置。

    ``bootstrap.servers`` 以 ``CAR_MONIT_KAFKA_URL`` 为准（env 是真实集群的
    唯一事实源）；其余键（group.id / auto.offset.reset / enable.auto.commit）
    原样透传，缺省值与 Java 相同。
    """
    raw = dict(props or {})
    return {
        "bootstrap.servers": shared_kafka_url() or "localhost:9092",
        "group.id": str(raw.get("group.id", "flink-consumer")),
        "auto.offset.reset": str(raw.get("auto.offset.reset", "latest")),
        "enable.auto.commit": str(raw.get("enable.auto.commit", "true")).lower()
                              in ("true", "1"),
    }


def create_consumer(props: Any) -> Any:
    """按业务 props 创建真实 Consumer（供 FlinkKafkaConsumer 的真实 run 使用）。"""
    return ConfluentConsumer(consumer_conf_from_props(props))


# -------------------------------------------------------------------- 工厂
_SHARED_PRODUCER: Dict[str, Any] = {"url": None, "producer": None}


def shared_kafka_producer() -> Optional[RealKafkaProducer]:
    """进程级共享生产者后端：``CAR_MONIT_KAFKA_URL`` 未设 → ``None``（纯替身）。

    URL 变化时重建（与 shared_redis_template / shared_es_backend 同语义）；
    KafkaTemplate 是 Spring 单例 Bean，所有业务服务共享同一个生产者连接。
    """
    url = shared_kafka_url()
    if not url:
        _SHARED_PRODUCER["url"] = None
        _SHARED_PRODUCER["producer"] = None
        return None
    if _SHARED_PRODUCER["url"] != url or _SHARED_PRODUCER["producer"] is None:
        _SHARED_PRODUCER["url"] = url
        _SHARED_PRODUCER["producer"] = RealKafkaProducer(url)
    return _SHARED_PRODUCER["producer"]
