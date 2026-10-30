package com.ruoyi.base.config;

import org.apache.pulsar.client.api.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

/**
 * Pulsar 消费者配置类
 *
 * 功能说明：
 * - 配置 Pulsar 客户端和核心消费者参数
 * - 实现与原 Kafka 消费者等价的可靠性保证（手动确认、批量拉取、重试机制）
 *
 * Pulsar 与 Kafka 消费模型的关键区别：
 * ----------------------------------------------------------------------------
 * 特性                      Kafka                              Pulsar
 * ----------------------------------------------------------------------------
 * 消息确认方式              commit offset 到 __consumer_offsets  Topic 内基于 MessageId 确认
 * 重放机制                  seek(offset)                       seek(messageId) / seekByTime()
 * 死信队列                  手动实现                           subscription + deadLetterPolicy 原生支持
 * 消息路由                  partition 由 producer key hash     partition 由 producer key hash 或轮询
 * 订阅模式                  consumer group 订阅整个 Topic        subscription 支持独占/共享/故障转移/键共享
 * 批量消费                  max.poll.records 控制一次拉取条数   receiverQueueSize 控制预取队列大小
 * ----------------------------------------------------------------------------
 *
 * 核心参数映射（与原 Kafka 配置对齐）：
 * ----------------------------------------------------------------------------
 * 原 Kafka 参数              对应 Pulsar 配置                         说明
 * ----------------------------------------------------------------------------
 * bootstrap.servers          serviceUrl                              Pulsar 服务地址
 * group.id                   subscriptionName                        订阅名称（逻辑等价）
 * enable.auto.commit=false   ackTimeout + acknowledgeAsync           手动确认模式
 * max.poll.records           receiverQueueSize                       每次预取队列大小
 * auto.offset.reset          subscriptionInitialPosition              消费起始位置
 * heartbeat.interval.ms     subscriptionType=Shared                  共享订阅保证负载均衡
 * ----------------------------------------------------------------------------
 */
//@Configuration
public class PulsarConsumerConfig {

    /**
     * Pulsar 服务地址
     * 与生产者端保持一致：pulsar://broker-host:6650
     */
    @Value("${spring.pulsar.service-url:pulsar://localhost:6650}")
    private String serviceUrl;

    /**
     * 消费者订阅名称（等价于 Kafka group.id）
     * 目的：
     * - 同一 subscriptionName 的多个消费者会自动组成消费组
     * - broker 按 subscription 追踪消息确认状态
     */
    @Value("${spring.pulsar.subscription-name:ods-rt-szdn-snapshot-flow-sub}")
    private String subscriptionName;

    /**
     * 默认消费主题
     * 与生产者端配置保持一致
     */
    @Value("${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}")
    private String defaultTopic;

    /**
     * 接收队列大小（receiverQueueSize）
     * 功能：控制消费者从 broker 预取到本地队列的消息数
     * 与 Kafka 的 max.poll.records 逻辑类似，但 Pulsar 是预取到内存
     * 默认值 1000：太小会增加网络开销，太大会造成 OOM
     */
    @Value("${spring.pulsar.receiver-queue-size:1000}")
    private int receiverQueueSize;

    /**
     * 确认超时时间（ackTimeout，单位毫秒）
     * 功能：如果消息接收后超过这个时间未确认，broker 会自动重新投递
     * 相当于 Kafka 的 max.poll.interval.ms 的安全网
     */
    @Value("${spring.pulsar.ack-timeout-ms:60000}")
    private long ackTimeoutMs;

    /**
     * 最大重试次数（用于死信队列策略）
     * 目的：超过此次数后，消息被自动路由到死信主题
     */
    @Value("${spring.pulsar.max-retry-times:3}")
    private int maxRetryTimes;

    /**
     * 创建 Pulsar 客户端（消费者端）
     *
     * 思路：
     * 1. 一个应用只需要一个 PulsarClient（线程安全，支持多 consumer / producer）
     * 2. 与生产者端可以共用同一个客户端实例
     * 3. 这里独立声明一个消费者端专用客户端，保证模块独立性
     *
     * 性能配置：
     * - listenerThreads=8：异步消息监听器的工作线程池
     * - ioThreads=8：处理网络读写的 IO 线程池
     * - operationTimeout=30s：连接、订阅等管理操作超时
     *
     * @return Pulsar 客户端实例
     */
    @Bean
    public PulsarClient pulsarConsumerClient() throws PulsarClientException {
        return PulsarClient.builder()
                .serviceUrl(serviceUrl)
                .listenerThreads(8)
                .ioThreads(8)
                .operationTimeout(30, TimeUnit.SECONDS)
                .connectionTimeout(30, TimeUnit.SECONDS)
                .build();
    }

    /**
     * 创建门架抓拍流水的消费者（主消费者）
     *
     * 思路（与原 Kafka SnapshotFlowKafkaConsumerV2 对齐）：
     * 1. 使用 Shared 订阅模式（等价于 Kafka consumer group）
     *    允许多个 consumer 实例同时订阅同一主题，消息被平均分发
     *    与 Kafka 的 group.id 机制逻辑等价
     *
     * 2. 使用消息监听器（MessageListener）模式
     *    与 Spring Kafka 的 @KafkaListener 功能等价
     *    消息被异步推送到监听器，无需手动 poll()
     *
     * 3. DeadLetterPolicy：死信队列策略
     *    - 消息超过 maxRedeliverCount 次未确认，则自动路由到 DLQ
     *    - 与 Kafka 的 RetryLetterTopic + DLT 功能等价
     *
     * 4. SubscriptionInitialPosition.Latest：仅消费新到达的消息
     *    等价于 Kafka 的 auto.offset.reset=latest
     *    在启动后跳过历史积压数据，适合实时场景
     *
     * 5. Schema.STRING：与生产者端发送的 JSON 字符串匹配
     *    与原 Kafka 的 StringSerializer/StringDeserializer 等价
     *
     * 可靠性保证：
     * - MessageListener#received() 收到消息后执行业务处理
     * - 处理成功调用 consumer.acknowledge(msg) 确认
     * - 处理失败调用 consumer.negativeAcknowledge(msg) 触发重投
     * - 超过 maxRetryTimes 次的消息由 Broker 自动路由到 DLQ
     *
     * @param client Pulsar 客户端实例
     * @return 已订阅的字符串消息消费者
     */
    @Bean
    public Consumer<String> snapshotFlowConsumer(PulsarClient client) throws PulsarClientException {
        return client.newConsumer(Schema.STRING)
                // 订阅主题（与生产者端发布的主题相同）
                .topic(defaultTopic)
                // 订阅名称：等价于 Kafka 的 group.id
                .subscriptionName(subscriptionName)
                // 订阅类型：Shared = 共享模式
                // - Kafka 的 consumer group 默认就是 Shared 行为
                // - 支持多个 consumer 实例同时消费，消息按轮询分发
                .subscriptionType(SubscriptionType.Shared)
                // 订阅初始位置：Latest 等价于 Kafka auto.offset.reset=latest
                // - 首次订阅时从最新消息开始消费（不消费历史数据）
                // - 已经存在的订阅会从上次确认的位置继续
                .subscriptionInitialPosition(SubscriptionInitialPosition.Latest)
                // 接收队列大小：控制预取到内存的消息数
                .receiverQueueSize(receiverQueueSize)
                // 确认超时：60 秒未确认则重投（由 Broker 触发）
                .ackTimeout(ackTimeoutMs, TimeUnit.MILLISECONDS)
                // 确认超时的 tick 时间：1 秒检查一次
                .ackTimeoutTickTime(1, TimeUnit.SECONDS)
                // 死信队列策略：超过 maxRetryTimes 次未确认则路由到 DLQ
                // deadLetterPolicy 是 Pulsar 2.10+ 功能
                .deadLetterPolicy(DeadLetterPolicy.builder()
                        .maxRedeliverCount(maxRetryTimes)
                        .deadLetterTopic(defaultTopic + "-DLQ")
                        .build())
                // 启用重试主题：与死信队列配合
                .enableRetry(true)
                // 消费者名称：用于日志和监控标识
                .consumerName("car-monit-snapshot-flow-consumer")
                // 创建并订阅（阻塞操作，订阅成功后才返回）
                .subscribe();
    }

    /**
     * CDC 只读消费者（Debezium Read-Only Consumer）
     *
     * 设计思路：
     * - 使用独立的 subscription，不与主消费者共享消费进度
     * - 使用 Key_Shared 模式（如果需要按 key 保证顺序）
     * - 与原 DebeziumReadonlyKafkaConsumer 的功能等价
     *
     * @param client Pulsar 客户端实例
     * @return Debezium CDC 主题消费者
     */
    @Bean
    public Consumer<String> debeziumReadonlyConsumer(PulsarClient client) throws PulsarClientException {
        return client.newConsumer(Schema.STRING)
                .topic(defaultTopic)
                // 独立的订阅名称（与主消费者使用不同 subscription）
                .subscriptionName("debezium-readonly-sub")
                // 对于 CDC 场景，通常需要按 key 顺序处理同一 dataId 的消息
                // Key_Shared 模式：相同 key 的消息始终路由到同一 consumer
                // 比 Shared 模式更适合有序场景（但要求消息必须有 key）
                .subscriptionType(SubscriptionType.Key_Shared)
                // 从最早的消息开始消费（适合 CDC：需要回放所有变更）
                .subscriptionInitialPosition(SubscriptionInitialPosition.Earliest)
                .receiverQueueSize(2000)
                .ackTimeout(120, TimeUnit.SECONDS)
                .consumerName("car-monit-debezium-consumer")
                // 死信策略：CDC 消息重试次数可放宽，避免漏处理
                .deadLetterPolicy(DeadLetterPolicy.builder()
                        .maxRedeliverCount(5)
                        .deadLetterTopic(defaultTopic + "-cdc-DLQ")
                        .build())
                .enableRetry(true)
                .subscribe();
    }
}
