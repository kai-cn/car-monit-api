# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer

【无 Java 源文件：框架类替身】
Java 侧来自 flink-connector-kafka_2.11：
``org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer<T>``。
本工程用法（VehicleTrackFlinkJob.createCDCDataStream / createRawDataStream）：
    Props: bootstrap.servers / group.id / auto.offset.reset / enable.auto.commit
    FlinkKafkaConsumer<String> consumer =
            new FlinkKafkaConsumer<>(CDC_TOPIC, new SimpleStringSchema(), props);
    env.addSource(consumer).name("Kafka-CDC 数据源").map(new CDCEventParser());

【Java→Python】关键差异
1) **不会真的连 Kafka（未设置 CAR_MONIT_KAFKA_URL 时）**：Java 的
   ``run(SourceContext)`` 内部会创建 fetcher 线程、持续 poll 并
   ``ctx.collect``，直到 ``cancel()`` 才退出。纯替身模式下 ``run`` 只打
   日志并**立即返回**（不会阻塞、不会产数据）；测试时请用
   ``DataStream.feed([...])`` 注入消息。
2) **P2-4 真实路径**：设置 ``CAR_MONIT_KAFKA_URL`` 后，``run`` 改为真实
   消费循环（confluent-kafka Consumer）：消费组 / ``auto.offset.reset`` /
   ``enable.auto.commit`` 来自构造 props；``enable.auto.commit=false`` 时
   每条 collect 后同步提交（Flink 在 checkpoint 提交位点，本地环境无
   checkpoint，改逐条提交保持 at-least-once）；broker 不可用时记录
   warning 并继续 poll（Java 的 Flink source 持续重试、作业不挂，对齐）；
   反序列化异常向上抛（Java：source 失败）。``bootstrap.servers`` 以 env
   为准（真实集群的唯一事实源）。
3) Java 构造器有 4 个重载（topic / topics / Pattern + schema + props）；
   本工程只用 ``(String topic, DeserializationSchema, Properties)``，
   替身按该签名实现，``topic`` 也接受列表以兼容 ``(List, schema, props)``。
4) Java 的 ``Properties`` 是 ``java.util.Properties``（Hashtable 子类）；
   Python 侧对应内置 ``dict``（业务代码里就是 ``props.setProperty(...)``
   的替身方法，见 java.util.Properties）。
5) Java 的 ``setStartFromGroupOffsets`` / ``setStartFromEarliest`` 等
   offset 配置方法本工程未使用，替身不实现（调用即 AttributeError，
   与“没有调用”等价）。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from org.apache.flink.streaming.api.functions.source.SourceFunction import (
    SourceContext,
    SourceFunction,
)

__all__ = ["FlinkKafkaConsumer"]

log = logging.getLogger(__name__)


class FlinkKafkaConsumer(SourceFunction):
    """``FlinkKafkaConsumer<T>`` 的替身（不连接真实 Kafka）。"""

    def __init__(self, topic: Any, deserialization_schema: Any,
                 props: Any) -> None:
        # 【Java→Python】Java 的 topic 参数还有 List<String> / Pattern 重载；
        # 这里把单 topic 与 topic 列表统一成列表保存。
        if isinstance(topic, (list, tuple)):
            self._topics: List[str] = [str(item) for item in topic]
        else:
            self._topics = [str(topic)]
        self._schema = deserialization_schema
        self._props = props
        self._running = False

    # ------------------------------------------------------------------ SourceFunction
    def run(self, ctx: SourceContext) -> None:
        """对应 ``run(SourceContext<T>)``。

        纯替身模式：不连接 Kafka，直接返回（见文件头差异说明）。
        真实模式（CAR_MONIT_KAFKA_URL 已设置）：阻塞消费循环，直到 ``cancel()``。
        """
        from app.middleware.real_kafka import shared_kafka_url
        if shared_kafka_url() is not None:
            return self._run_real(ctx)
        log.info("[Kafka替身] FlinkKafkaConsumer.run() 被调用：topics=%s，"
                 "本地替身不连接 Kafka，也不发射任何消息", self._topics)
        self._running = True
        # 真实实现在这里 while(running) { poll(); ctx.collect(); }

    def _run_real(self, ctx: SourceContext) -> None:
        """P2-4 真实消费循环（confluent-kafka Consumer，见文件头差异说明）。"""
        from confluent_kafka import Consumer as ConfluentConsumer
        from confluent_kafka import KafkaError

        from app.middleware.real_kafka import consumer_conf_from_props

        conf = consumer_conf_from_props(self._props)
        auto_commit = conf["enable.auto.commit"]
        consumer = ConfluentConsumer(conf)
        consumer.subscribe(self._topics)
        self._running = True
        log.info("[Kafka适配] 真实消费循环启动：topics=%s, autoCommit=%s",
                 self._topics, auto_commit)
        try:
            while self._running:
                message = consumer.poll(0.5)
                if message is None:
                    continue
                error = message.error()
                if error is not None:
                    if error.code() == KafkaError._PARTITION_EOF:
                        continue
                    # Java 的 Flink source 对 broker 故障持续重试（作业不挂），
                    # 这里记录 warning 后继续 poll（不熔断、不退出）
                    log.warning("[Kafka适配] poll 错误（继续重试）：%s", error)
                    continue
                # 反序列化异常向上抛（Java：source 失败，作业进入 FAILED）
                element = self._schema.deserialize(message.value())
                ctx.collect(element)
                if not auto_commit:
                    # Flink 在 checkpoint 提交位点；本地环境无 checkpoint →
                    # 每条同步提交（at-least-once，见文件头说明）
                    consumer.commit(message=message, asynchronous=False)
        finally:
            consumer.close()
            log.info("[Kafka适配] 真实消费循环退出：topics=%s", self._topics)

    def cancel(self) -> None:
        """对应 ``cancel()``。"""
        self._running = False
        log.info("[Kafka替身] FlinkKafkaConsumer.cancel() 被调用：topics=%s",
                 self._topics)

    # ------------------------------------------------------------------ 断言辅助
    def getTopics(self) -> List[str]:
        return list(self._topics)

    def getProperties(self) -> Any:
        return self._props

    def getDeserializationSchema(self) -> Any:
        return self._schema

    def isRunning(self) -> bool:
        """Java 无此方法；替身用于断言 run/cancel 的状态。"""
        return self._running

    def __repr__(self) -> str:
        return "FlinkKafkaConsumer(topics=%r, schema=%r)" % (self._topics,
                                                             self._schema)
