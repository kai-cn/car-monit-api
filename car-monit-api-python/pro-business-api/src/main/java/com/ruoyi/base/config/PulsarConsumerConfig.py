# -*- coding: utf-8 -*-
"""com.ruoyi.base.config.PulsarConsumerConfig

源文件：pro-business-api/src/main/java/com/ruoyi/base/config/PulsarConsumerConfig.java

Pulsar 消费者配置类：
- 配置 Pulsar 客户端和核心消费者参数
- 实现与原 Kafka 消费者等价的可靠性保证（手动确认、批量拉取、重试机制）

Pulsar 与 Kafka 消费模型的关键区别：
----------------------------------------------------------------------------
特性                      Kafka                              Pulsar
----------------------------------------------------------------------------
消息确认方式              commit offset 到 __consumer_offsets  Topic 内基于 MessageId 确认
重放机制                  seek(offset)                       seek(messageId) / seekByTime()
死信队列                  手动实现                           subscription + deadLetterPolicy 原生支持
消息路由                  partition 由 producer key hash     partition 由 producer key hash 或轮询
订阅模式                  consumer group 订阅整个 Topic        subscription 支持独占/共享/故障转移/键共享
批量消费                  max.poll.records 控制一次拉取条数   receiverQueueSize 控制预取队列大小
----------------------------------------------------------------------------

核心参数映射（与原 Kafka 配置对齐）：
----------------------------------------------------------------------------
原 Kafka 参数              对应 Pulsar 配置                         说明
----------------------------------------------------------------------------
bootstrap.servers          serviceUrl                              Pulsar 服务地址
group.id                   subscriptionName                        订阅名称（逻辑等价）
enable.auto.commit=false   ackTimeout + acknowledgeAsync           手动确认模式
max.poll.records           receiverQueueSize                       每次预取队列大小
auto.offset.reset          subscriptionInitialPosition              消费起始位置
heartbeat.interval.ms     subscriptionType=Shared                  共享订阅保证负载均衡
----------------------------------------------------------------------------

【Java→Python】整体说明（本文件差异最密集，务必逐条对照）
1) **本类在 Java 里没有 @Configuration！** 源码中是 ``//@Configuration``（被注释掉），
   因此 Spring **不会**把它注册为 Bean，``@Bean`` 方法也不会被容器调用；
   真正创建 Consumer 的是 SnapshotFlowPulsarConsumer / DebeziumReadonlyPulsarConsumer。
   Python 侧保留为普通类（方法可被显式调用），并**不带任何容器标记**，忠实还原这一点。
2) ``@Value("${spring.pulsar.xxx:默认值}")`` 有默认值 → Python 用
   ``Environment().value("${...:...}", 类型)``，默认值缺失时不会抛异常
   （与 Java 有默认值的占位符一致）。
   ``int`` / ``long`` 两类 Java 数值类型在 Python 里**都是 int**（无 32/64 位之分）。
3) ``PulsarClient.builder()`` 是**静态内部类 Builder** 的工厂；Python 无内部类，
   改为独立类 ``PulsarClientBuilder``（见 org.apache.pulsar.client.api.PulsarClient）。
   ``build()`` 在 Java 会真正建连，Python 替身只保存配置。
4) ``throws PulsarClientException`` 是**受检异常声明**；Python 无受检异常，
   这些 ``throws`` 在翻译后**直接消失**（不写 try/except 也能编译通过）。
5) ``SubscriptionType.Shared`` / ``SubscriptionInitialPosition.Latest`` 是 enum 常量；
   Python 用 ``enum.Enum`` 还原，比较与传递方式不变（``Key_Shared`` 保留原名）。
6) ``TimeUnit.SECONDS`` / ``MILLISECONDS`` → java.util.concurrent.TimeUnit 替身枚举，
   ``ackTimeout(ackTimeoutMs, TimeUnit.MILLISECONDS)`` 写法与 Java 一致。
7) 链式调用（``.topic(...).subscriptionName(...)...subscribe()``）在 Python 同样成立，
   因为 ConsumerBuilder 的每个方法都 ``return self``（对应 Java 返回 this）。
8) ``deadLetterPolicy(DeadLetterPolicy.builder()....build())``：Builder 是静态内部类 →
   Python 独立类 ``DeadLetterPolicyBuilder``，由 ``DeadLetterPolicy.builder()`` 返回。
"""
from __future__ import annotations

import logging
from typing import Optional

from java.util.concurrent.TimeUnit import TimeUnit
from org.apache.pulsar.client.api.Consumer import Consumer
from org.apache.pulsar.client.api.DeadLetterPolicy import DeadLetterPolicy
from org.apache.pulsar.client.api.PulsarClient import PulsarClient
from org.apache.pulsar.client.api.Schema import Schema
from org.apache.pulsar.client.api.SubscriptionInitialPosition import SubscriptionInitialPosition
from org.apache.pulsar.client.api.SubscriptionType import SubscriptionType
from org.springframework.core.env.Environment import Environment

log = logging.getLogger(__name__)

__all__ = ["PulsarConsumerConfig"]


class PulsarConsumerConfig(object):
    """Pulsar 消费者配置（Bean 工厂）。

    【Java→Python】Java 源码中 ``@Configuration`` 被注释掉（``//@Configuration``），
    所以本类在容器里**不存在 Bean**；Python 侧同样不注册，只提供可显式调用的工厂方法。
    """

    def __init__(self, environment: Optional[Environment] = None) -> None:
        # 【Java→Python】@Value 字段注入 → 构造器里显式解析（字段顺序与 Java 一致）
        env = environment or Environment()

        # Pulsar 服务地址
        # 与生产者端保持一致：pulsar://broker-host:6650
        self.serviceUrl: str = env.value(
            "${spring.pulsar.service-url:pulsar://localhost:6650}", str)

        # 消费者订阅名称（等价于 Kafka group.id）
        # 目的：
        # - 同一 subscriptionName 的多个消费者会自动组成消费组
        # - broker 按 subscription 追踪消息确认状态
        self.subscriptionName: str = env.value(
            "${spring.pulsar.subscription-name:ods-rt-szdn-snapshot-flow-sub}", str)

        # 默认消费主题（与生产者端配置保持一致）
        self.defaultTopic: str = env.value(
            "${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}", str)

        # 接收队列大小（receiverQueueSize）
        # 功能：控制消费者从 broker 预取到本地队列的消息数
        # 与 Kafka 的 max.poll.records 逻辑类似，但 Pulsar 是预取到内存
        # 默认值 1000：太小会增加网络开销，太大会造成 OOM
        self.receiverQueueSize: int = env.value(
            "${spring.pulsar.receiver-queue-size:1000}", int)

        # 确认超时时间（ackTimeout，单位毫秒）
        # 功能：如果消息接收后超过这个时间未确认，broker 会自动重新投递
        # 相当于 Kafka 的 max.poll.interval.ms 的安全网
        # 【Java→Python】Java 的 long → Python 的 int（Python 无 32/64 位整型之分）
        self.ackTimeoutMs: int = env.value("${spring.pulsar.ack-timeout-ms:60000}", int)

        # 最大重试次数（用于死信队列策略）
        # 目的：超过此次数后，消息被自动路由到死信主题
        self.maxRetryTimes: int = env.value("${spring.pulsar.max-retry-times:3}", int)

    # ------------------------------------------------------------------ @Bean
    def pulsarConsumerClient(self) -> PulsarClient:
        """创建 Pulsar 客户端（消费者端）。

        思路：
        1. 一个应用只需要一个 PulsarClient（线程安全，支持多 consumer / producer）
        2. 与生产者端可以共用同一个客户端实例
        3. 这里独立声明一个消费者端专用客户端，保证模块独立性

        性能配置：
        - listenerThreads=8：异步消息监听器的工作线程池
        - ioThreads=8：处理网络读写的 IO 线程池
        - operationTimeout=30s：连接、订阅等管理操作超时

        【Java→Python】``throws PulsarClientException`` 在 Python 中不存在
        （无受检异常）；``PulsarClient.builder()`` 返回的是替身 Builder。
        """
        return (PulsarClient.builder()
                .serviceUrl(self.serviceUrl)
                .listenerThreads(8)
                .ioThreads(8)
                .operationTimeout(30, TimeUnit.SECONDS)
                .connectionTimeout(30, TimeUnit.SECONDS)
                .build())

    def snapshotFlowConsumer(self, client: PulsarClient) -> Consumer:
        """创建门架抓拍流水的消费者（主消费者）。

        思路（与原 Kafka SnapshotFlowKafkaConsumerV2 对齐）：
        1. 使用 Shared 订阅模式（等价于 Kafka consumer group）
           允许多个 consumer 实例同时订阅同一主题，消息被平均分发
           与 Kafka 的 group.id 机制逻辑等价

        2. 使用消息监听器（MessageListener）模式
           与 Spring Kafka 的 @KafkaListener 功能等价
           消息被异步推送到监听器，无需手动 poll()

        3. DeadLetterPolicy：死信队列策略
           - 消息超过 maxRedeliverCount 次未确认，则自动路由到 DLQ
           - 与 Kafka 的 RetryLetterTopic + DLT 功能等价

        4. SubscriptionInitialPosition.Latest：仅消费新到达的消息
           等价于 Kafka 的 auto.offset.reset=latest
           在启动后跳过历史积压数据，适合实时场景

        5. Schema.STRING：与生产者端发送的 JSON 字符串匹配
           与原 Kafka 的 StringSerializer/StringDeserializer 等价

        可靠性保证：
        - MessageListener#received() 收到消息后执行业务处理
        - 处理成功调用 consumer.acknowledge(msg) 确认
        - 处理失败调用 consumer.negativeAcknowledge(msg) 触发重投
        - 超过 maxRetryTimes 次的消息由 Broker 自动路由到 DLQ

        :param client: Pulsar 客户端实例
        :return: 已订阅的字符串消息消费者
        """
        return (client.newConsumer(Schema.STRING)
                # 订阅主题（与生产者端发布的主题相同）
                .topic(self.defaultTopic)
                # 订阅名称：等价于 Kafka 的 group.id
                .subscriptionName(self.subscriptionName)
                # 订阅类型：Shared = 共享模式
                # - Kafka 的 consumer group 默认就是 Shared 行为
                # - 支持多个 consumer 实例同时消费，消息按轮询分发
                .subscriptionType(SubscriptionType.Shared)
                # 订阅初始位置：Latest 等价于 Kafka auto.offset.reset=latest
                # - 首次订阅时从最新消息开始消费（不消费历史数据）
                # - 已经存在的订阅会从上次确认的位置继续
                .subscriptionInitialPosition(SubscriptionInitialPosition.Latest)
                # 接收队列大小：控制预取到内存的消息数
                .receiverQueueSize(self.receiverQueueSize)
                # 确认超时：60 秒未确认则重投（由 Broker 触发）
                .ackTimeout(self.ackTimeoutMs, TimeUnit.MILLISECONDS)
                # 确认超时的 tick 时间：1 秒检查一次
                .ackTimeoutTickTime(1, TimeUnit.SECONDS)
                # 死信队列策略：超过 maxRetryTimes 次未确认则路由到 DLQ
                # deadLetterPolicy 是 Pulsar 2.10+ 功能
                .deadLetterPolicy(DeadLetterPolicy.builder()
                                  .maxRedeliverCount(self.maxRetryTimes)
                                  .deadLetterTopic(self.defaultTopic + "-DLQ")
                                  .build())
                # 启用重试主题：与死信队列配合
                .enableRetry(True)
                # 消费者名称：用于日志和监控标识
                .consumerName("car-monit-snapshot-flow-consumer")
                # 创建并订阅（阻塞操作，订阅成功后才返回）
                .subscribe())

    def debeziumReadonlyConsumer(self, client: PulsarClient) -> Consumer:
        """CDC 只读消费者（Debezium Read-Only Consumer）。

        设计思路：
        - 使用独立的 subscription，不与主消费者共享消费进度
        - 使用 Key_Shared 模式（如果需要按 key 保证顺序）
        - 与原 DebeziumReadonlyKafkaConsumer 的功能等价

        :param client: Pulsar 客户端实例
        :return: Debezium CDC 主题消费者
        """
        return (client.newConsumer(Schema.STRING)
                .topic(self.defaultTopic)
                # 独立的订阅名称（与主消费者使用不同 subscription）
                .subscriptionName("debezium-readonly-sub")
                # 对于 CDC 场景，通常需要按 key 顺序处理同一 dataId 的消息
                # Key_Shared 模式：相同 key 的消息始终路由到同一 consumer
                # 比 Shared 模式更适合有序场景（但要求消息必须有 key）
                .subscriptionType(SubscriptionType.Key_Shared)
                # 从最早的消息开始消费（适合 CDC：需要回放所有变更）
                .subscriptionInitialPosition(SubscriptionInitialPosition.Earliest)
                .receiverQueueSize(2000)
                .ackTimeout(120, TimeUnit.SECONDS)
                .consumerName("car-monit-debezium-consumer")
                # 死信策略：CDC 消息重试次数可放宽，避免漏处理
                .deadLetterPolicy(DeadLetterPolicy.builder()
                                  .maxRedeliverCount(5)
                                  .deadLetterTopic(self.defaultTopic + "-cdc-DLQ")
                                  .build())
                .enableRetry(True)
                .subscribe())
