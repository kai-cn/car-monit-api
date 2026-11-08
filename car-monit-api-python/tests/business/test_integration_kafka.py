# -*- coding: utf-8 -*-
"""P2-4：真实 Kafka 集成测试（默认跳过）。

开启方式（本机 broker 已起在 9092，Kafka 4.0 KRaft 模式）：
    CAR_MONIT_TEST_KAFKA=1 CAR_MONIT_KAFKA_URL=127.0.0.1:9092 \
      python -m pytest tests/business/test_integration_kafka.py -q

CI 的 integration job 由 service container（bitnami/kafka:3.7 KRaft）提供
服务并注入同组环境变量。topic 带 ``car-monit-p2-it-kafka-`` 前缀，消费组用
独立 group.id，不污染业务 topic/组。
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

import pytest

import bootstrap  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("CAR_MONIT_TEST_KAFKA") != "1",
                       reason="需要真实 Kafka：设置 CAR_MONIT_TEST_KAFKA=1 开启"),
]

KAFKA_URL = os.environ.get("CAR_MONIT_KAFKA_URL", "127.0.0.1:9092")
PREFIX = "car-monit-p2-it-kafka-"
#: 每次运行唯一后缀：topic/组跨运行不复用，测试可重复执行（broker 侧不清理）
RUN = uuid.uuid4().hex[:8]


def _admin_client():
    from confluent_kafka.admin import AdminClient

    return AdminClient({"bootstrap.servers": KAFKA_URL})


def _create_single_partition_topic(topic: str) -> None:
    """M-5：显式建 1 分区主题，避免多分区导致 key 散列/顺序断言不稳定。"""
    from confluent_kafka.admin import NewTopic

    futures = _admin_client().create_topics(
        [NewTopic(topic, num_partitions=1, replication_factor=1)])
    for future in futures.values():
        try:
            future.result(timeout=10)
        except Exception:  # noqa: BLE001 - 已存在时忽略
            pass


def _delete_topic(topic: str) -> None:
    futures = _admin_client().delete_topics([topic])
    for future in futures.values():
        try:
            future.result(timeout=10)
        except Exception:  # noqa: BLE001 - 清理尽力而为
            pass


@pytest.fixture()
def single_partition_topic():
    topic = PREFIX + "sp-" + uuid.uuid4().hex[:8]
    _create_single_partition_topic(topic)
    yield topic
    _delete_topic(topic)


@pytest.fixture()
def template(monkeypatch):
    monkeypatch.setenv("CAR_MONIT_KAFKA_URL", KAFKA_URL)
    from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate

    instance = KafkaTemplate()
    yield instance
    instance.flush()


def _consume_all(topic: str, group: str, timeout: float = 15.0):
    """独立消费组（earliest）拉全量，供断言。"""
    from confluent_kafka import Consumer

    consumer = Consumer({"bootstrap.servers": KAFKA_URL, "group.id": group,
                         "auto.offset.reset": "earliest",
                         "enable.auto.commit": False})
    consumer.subscribe([topic])
    got, deadline = [], time.time() + timeout
    while len(got) < 100 and time.time() < deadline:
        message = consumer.poll(0.5)
        if message is None or message.error():
            continue
        got.append((message.key(), message.value(), message.offset()))
    consumer.close()
    return got


def test_producer_roundtrip_and_callback(template, single_partition_topic) -> None:
    """发送回调链路：ListenableFuture 在 broker ack 后完成（真实 offset）。"""
    topic = single_partition_topic
    offsets, errors = [], []
    for i in range(5):
        template.send(topic, "key-%d" % i, "value-%d" % i).addCallback(
            lambda r: offsets.append(r.getRecordMetadata().offset()),
            lambda e: errors.append(str(e)))
    template.flush()
    assert errors == []
    assert len(offsets) == 5
    assert all(offset >= 0 for offset in offsets)

    got = _consume_all(topic, "p2-it-kafka-roundtrip-" + RUN)
    assert [v.decode() for _, v, _ in got] == ["value-%d" % i for i in range(5)]
    assert [k.decode() for k, _, _ in got] == ["key-%d" % i for i in range(5)]


def test_json_value_is_fastjson_bytes(template, single_partition_topic) -> None:
    """value 序列化与 Java/替身逐字节一致：fastjson camelCase JSON。"""
    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    topic = single_partition_topic
    entity = OdsSzdnGantry()
    entity.setId("g-1")
    entity.setGantryCode("G001")
    entity.setGantryName("集成门架")
    errors = []
    template.send(topic, "g-1", entity).addCallback(
        lambda _r: None, lambda e: errors.append(str(e)))
    template.flush()
    assert errors == []

    got = _consume_all(topic, "p2-it-kafka-json-" + RUN)
    assert len(got) == 1
    payload = json.loads(got[0][1])
    assert payload["gantryCode"] == "G001"
    assert payload["gantryName"] == "集成门架"


def test_deterministic_failure_fails_only_that_message(template) -> None:
    """消息超限：该条进失败 future（onFailure），不熔断，后续发送仍走真实路径。"""
    topic = PREFIX + "oversize-" + RUN
    errors, ok_offsets = [], []
    template.send(topic, "big", "x" * (2 * 1024 * 1024)).addCallback(
        lambda _r: None, lambda e: errors.append(str(e)))
    template.flush()
    assert len(errors) == 1
    assert "MSG_SIZE_TOO_LARGE" in errors[0]
    assert template._real.degraded is False  # 确定性错误不熔断

    template.send(topic, "small", "ok-value").addCallback(
        lambda r: ok_offsets.append(r.getRecordMetadata().offset()),
        lambda e: errors.append(str(e)))
    template.flush()
    assert len(errors) == 1  # 无新增失败
    assert ok_offsets and ok_offsets[0] >= 0


def test_kafka_producer_config_business_chain(monkeypatch) -> None:
    """业务 @Bean 链路（KafkaProducerConfig.kafkaTemplate）在真实模式下可发送。"""
    monkeypatch.setenv("CAR_MONIT_KAFKA_URL", KAFKA_URL)
    from com.ruoyi.base.config.KafkaProducerConfig import KafkaProducerConfig

    business_template = KafkaProducerConfig().kafkaTemplate()
    assert business_template._real is not None
    errors = []
    business_template.send(PREFIX + "config-" + RUN, "k", "v").addCallback(
        lambda _r: None, lambda e: errors.append(str(e)))
    business_template.flush()
    assert errors == []


def test_flink_consumer_group_offsets_and_incremental(single_partition_topic) -> None:
    """FlinkKafkaConsumer 真实路径：消费组 + 手动位点提交 + 二次运行只拿增量。"""
    from confluent_kafka import Consumer, Producer, TopicPartition

    from org.apache.flink.api.common.serialization.SimpleStringSchema import (
        SimpleStringSchema,
    )
    from org.apache.flink.streaming.api.functions.source.SourceFunction import (
        SourceContext,
    )
    from org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer import (
        FlinkKafkaConsumer,
    )

    topic = single_partition_topic
    group = "p2-it-kafka-flink-" + RUN

    def _produce(values):
        producer = Producer({"bootstrap.servers": KAFKA_URL})
        for value in values:
            producer.produce(topic, value=value.encode())
        producer.flush(10)

    def _run_until(consumer, count, timeout=20.0):
        ctx = SourceContext(consumer)
        thread = threading.Thread(target=consumer.run, args=(ctx,), daemon=True)
        thread.start()
        deadline = time.time() + timeout
        while len(ctx.getOutput()) < count and time.time() < deadline:
            time.sleep(0.2)
        consumer.cancel()
        thread.join(15)
        assert not thread.is_alive()
        return ctx.getOutput()

    _produce(["msg-0", "msg-1", "msg-2"])

    consumer = FlinkKafkaConsumer(topic, SimpleStringSchema(), {
        "group.id": group, "auto.offset.reset": "earliest",
        "enable.auto.commit": "false"})
    assert _run_until(consumer, 3) == ["msg-0", "msg-1", "msg-2"]

    # 同组二次运行：位点已提交，只拿增量（消费组语义）
    _produce(["msg-3", "msg-4"])
    consumer2 = FlinkKafkaConsumer(topic, SimpleStringSchema(), {
        "group.id": group, "auto.offset.reset": "earliest",
        "enable.auto.commit": "false"})
    assert _run_until(consumer2, 2) == ["msg-3", "msg-4"]

    # 位点断言：5 条全部提交（manual commit after collect）
    checker = Consumer({"bootstrap.servers": KAFKA_URL, "group.id": group})
    committed = checker.committed([TopicPartition(topic, 0)])
    assert committed and committed[0].offset == 5
    checker.close()
