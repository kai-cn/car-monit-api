# -*- coding: utf-8 -*-
"""t09a 自检：启动骨架（EcBusinessApiApplication/HasStatic/Test）+ config 4 个 + 框架替身。"""
import io
import os
import sys
from contextlib import redirect_stdout

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.HasStatic import HasStatic  # noqa: E402
from com.ruoyi.base.Test import Test  # noqa: E402
from com.ruoyi.base.config.KafkaProducerConfig import KafkaProducerConfig  # noqa: E402
from com.ruoyi.base.config.PulsarConsumerConfig import PulsarConsumerConfig  # noqa: E402
from com.ruoyi.base.config.SchedulingConfig import SchedulingConfig  # noqa: E402
from com.ruoyi.EcBusinessApiApplication import EcBusinessApiApplication  # noqa: E402
from org.apache.pulsar.client.api.SubscriptionInitialPosition import SubscriptionInitialPosition  # noqa: E402
from org.apache.pulsar.client.api.SubscriptionType import SubscriptionType  # noqa: E402
from org.springframework.kafka.core.DefaultKafkaProducerFactory import DefaultKafkaProducerFactory  # noqa: E402
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


def capture(fn):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        fn()
    return buffer.getvalue()


# ------------------------------------------------------------------ 1) HasStatic：static 字段语义
HasStatic.x = 100  # 复位（多次运行保持一致）
check("HasStatic output", capture(HasStatic.main), "x=102\n")
check("HasStatic after", HasStatic.x, 102)

# ------------------------------------------------------------------ 2) Test：字符串驻留语义
out = capture(Test.main).split("\n")
check("Test line1", out[0], "False")   # s1 == s2 → false（引用不同）
check("Test line2", out[1], "True")    # s1 == s3 → true（常量池同一对象）

# ------------------------------------------------------------------ 3) KafkaProducerConfig
kafka = KafkaProducerConfig()
check("kafka bootstrap", kafka.bootstrapServers, "localhost:9092")

factory = kafka.producerFactory()
check("factory type", isinstance(factory, DefaultKafkaProducerFactory), True)
props = factory.getConfigurationProperties()
check("kafka acks", props["acks"], "all")
check("kafka retries", props["retries"], 2147483647)
check("kafka idempotence", props["enable.idempotence"], True)
check("kafka in-flight", props["max.in.flight.requests.per.connection"], 5)
check("kafka batch.size", props["batch.size"], 16384)
check("kafka linger.ms", props["linger.ms"], 10)
check("kafka buffer.memory", props["buffer.memory"], 33554432)
check("kafka compression", props["compression.type"], "lz4")
check("kafka key serializer", props["key.serializer"].__name__, "StringSerializer")
check("kafka value serializer", props["value.serializer"].__name__, "JsonSerializer")

template = kafka.kafkaTemplate()
check("template type", isinstance(template, KafkaTemplate), True)
check("template bootstrap", template.bootstrap_servers, "localhost:9092")

# 生产者复用 + close 后可重建（对应 Java 的 producer 缓存语义）
producer1 = factory.createProducer()
check("producer reuse", factory.createProducer() is producer1, True)
factory.close()
check("producer closed", producer1.closed, True)
check("producer recreate", factory.createProducer() is producer1, False)

# ------------------------------------------------------------------ 4) PulsarConsumerConfig
pulsar = PulsarConsumerConfig()
check("pulsar serviceUrl", pulsar.serviceUrl, "pulsar://localhost:6650")
check("pulsar subscription", pulsar.subscriptionName, "ods-rt-szdn-snapshot-flow-sub")
check("pulsar topic", pulsar.defaultTopic,
      "persistent://public/default/ods-rt-szdn-snapshot-flow")
check("pulsar queue size", pulsar.receiverQueueSize, 1000)
check("pulsar ackTimeout", pulsar.ackTimeoutMs, 60000)
check("pulsar maxRetry", pulsar.maxRetryTimes, 3)

client = pulsar.pulsarConsumerClient()
check("client serviceUrl", client.serviceUrl, "pulsar://localhost:6650")
check("client listenerThreads", client.listenerThreads, 8)
check("client ioThreads", client.ioThreads, 8)
check("client operationTimeout", client.operationTimeoutMs, 30000)
check("client connectionTimeout", client.connectionTimeoutMs, 30000)

consumer = pulsar.snapshotFlowConsumer(client)
check("main consumer topic", consumer.getTopic(),
      "persistent://public/default/ods-rt-szdn-snapshot-flow")
check("main consumer sub", consumer.getSubscription(), "ods-rt-szdn-snapshot-flow-sub")
check("main consumer type", consumer.getSubscriptionType(), SubscriptionType.Shared)
check("main consumer connected", consumer.isConnected(), True)

cdc = pulsar.debeziumReadonlyConsumer(client)
check("cdc consumer type", cdc.getSubscriptionType(), SubscriptionType.Key_Shared)
check("cdc consumer sub", cdc.getSubscription(), "debezium-readonly-sub")

# 死信策略（链路：DeadLetterPolicy.builder() -> maxRedeliverCount -> deadLetterTopic）
from org.apache.pulsar.client.api.DeadLetterPolicy import DeadLetterPolicy  # noqa: E402
policy = DeadLetterPolicy.builder().maxRedeliverCount(3).deadLetterTopic("t-DLQ").build()
check("dlq max", policy.getMaxRedeliverCount(), 3)
check("dlq topic", policy.getDeadLetterTopic(), "t-DLQ")
check("initial position enum", SubscriptionInitialPosition.Latest.name, "Latest")

# ------------------------------------------------------------------ 5) SchedulingConfig
scheduling = SchedulingConfig()
scheduler = scheduling.taskRegistrar.getTaskScheduler()
check("scheduler exists", scheduler is not None, True)
check("scheduler pool", scheduler.poolSize, 10)
check("scheduler prefix", scheduler.threadNamePrefix, "scheduler-")
check("scheduler wait", scheduler.waitForTasksToCompleteOnShutdown, True)
check("scheduler await", scheduler.awaitTerminationSeconds, 60)
check("scheduler pool size getter", scheduler.getPoolSize(), 10)

# 调度器真的能按周期跑（100ms × 3 次）
import threading  # noqa: E402
import time  # noqa: E402

counter = [0]


def _tick():
    counter[0] += 1


scheduled = scheduler.scheduleAtFixedRate(_tick, None, 100)
deadline = time.time() + 1.5
while time.time() < deadline and counter[0] < 3:
    time.sleep(0.02)
scheduled.cancel()
check("scheduler ran", counter[0] >= 3, True)
scheduling.shutdown()
# P1-5 修正：现行 ThreadPoolTaskScheduler 替身 shutdown 后清空 _workers/_loops
# （旧断言 scheduler._executor 是更早版本替身的内部属性）
check("scheduler closed", scheduler._workers, [])

# ------------------------------------------------------------------ 6) EcBusinessApiApplication
context = EcBusinessApiApplication.main([])
env = context.getEnvironment()
check("context active", context.isActive(), True)
check("server.port", env.getProperty("server.port"), 9901)
check("context-path", env.getProperty("server.servlet.context-path"), "/")
context.close()
check("context closed", context.isActive(), False)

# ------------------------------------------------------------------ 7) PulsarProducerConfig 无类（1 行 package 声明）
import com.ruoyi.base.config.PulsarProducerConfig as producer_config_module  # noqa: E402
check("PulsarProducerConfig declares no class", producer_config_module.__all__, [])

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("T09A SMOKE OK" if not failures else "T09A SMOKE FAILED")
