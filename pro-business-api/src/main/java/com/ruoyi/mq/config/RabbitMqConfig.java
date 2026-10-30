package com.ruoyi.mq.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * RabbitMQ配置类
 * 配置交换机、队列、绑定关系以及死信队列
 */
@Slf4j
@Configuration
public class RabbitMqConfig {

    @Value("${mq.topic.snapshot-flow}")
    private String snapshotFlowTopic;

    @Value("${mq.dead-letter.exchange}")
    private String deadLetterExchange;

    @Value("${mq.dead-letter.queue}")
    private String deadLetterQueue;

    @Value("${mq.dead-letter.routing-key}")
    private String deadLetterRoutingKey;

    /**
     * 快照流量数据交换机
     * 类型：Direct Exchange（直连交换机）
     */
    @Bean
    public Exchange snapshotFlowExchange() {
        log.info("[RabbitMQ配置] 创建交换机: {}", snapshotFlowTopic);
        return ExchangeBuilder.directExchange(snapshotFlowTopic)
                .durable(true)  // 持久化
                .build();
    }

    /**
     * 快照流量数据队列
     * 配置死信队列支持
     */
    @Bean
    public Queue snapshotFlowQueue() {
        log.info("[RabbitMQ配置] 创建队列: queue.snapshot.flow");
        return QueueBuilder.durable("queue.snapshot.flow")
                // 死信交换机
                .deadLetterExchange(deadLetterExchange)
                // 死信路由键
                .deadLetterRoutingKey(deadLetterRoutingKey)
                // 消息TTL（60秒）
                .ttl(60000)
                .build();
    }

    /**
     * 绑定队列到交换机
     */
    @Bean
    public Binding snapshotFlowBinding(Queue snapshotFlowQueue, Exchange snapshotFlowExchange) {
        log.info("[RabbitMQ配置] 绑定队列到交换机");
        return BindingBuilder.bind(snapshotFlowQueue)
                .to(snapshotFlowExchange)
                .with("snapshot.flow")
                .noargs();
    }

    /**
     * 死信交换机
     */
    @Bean
    public Exchange deadLetterExchange() {
        log.info("[RabbitMQ配置] 创建死信交换机: {}", deadLetterExchange);
        return ExchangeBuilder.directExchange(deadLetterExchange)
                .durable(true)
                .build();
    }

    /**
     * 死信队列
     */
    @Bean
    public Queue deadLetterQueue() {
        log.info("[RabbitMQ配置] 创建死信队列: {}", deadLetterQueue);
        return QueueBuilder.durable(deadLetterQueue)
                .build();
    }

    /**
     * 绑定死信队列到死信交换机
     */
    @Bean
    public Binding deadLetterBinding(Queue deadLetterQueue, Exchange deadLetterExchange) {
        log.info("[RabbitMQ配置] 绑定死信队列到死信交换机");
        return BindingBuilder.bind(deadLetterQueue)
                .to(deadLetterExchange)
                .with(deadLetterRoutingKey)
                .noargs();
    }
}
