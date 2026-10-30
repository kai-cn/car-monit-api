package com.ruoyi.base.config;

import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka生产者配置类
 * 
 * 功能说明：
 * - 配置Kafka生产者的核心参数，确保数据传输的可靠性和一致性
 * - 实现消息零丢失的关键配置：ack=all、幂等性、无限重试等
 */
@Configuration
@EnableKafka
public class KafkaProducerConfig {

    // 从配置文件中读取Kafka集群地址
    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    /**
     * 创建Kafka生产者工厂
     * 
     * 思路：通过配置参数构建一个高可靠的ProducerFactory
     * 目的：确保消息发送的可靠性，防止数据丢失
     * 
     * @return ProducerFactory 生产者工厂实例
     */
    @Bean
    public ProducerFactory<String, Object> producerFactory() {
        // 创建配置参数Map
        Map<String, Object> configProps = new HashMap<>();
        
        // 配置Kafka集群地址
        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        
        // 配置Key序列化器：使用StringSerializer将key序列化为字符串
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        
        // 配置Value序列化器：使用JsonSerializer将对象序列化为JSON
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);
        
        /**
         * 【关键配置1】acks=all
         * 说明：要求所有ISR（同步副本）都确认收到消息
         * 目的：确保消息不丢失，只有当所有副本都写入成功后才认为发送成功
         * 注意：会增加延迟，但能保证最高的可靠性
         */
        configProps.put(ProducerConfig.ACKS_CONFIG, "all");
        
        /**
         * 【关键配置2】retries=Integer.MAX_VALUE
         * 说明：设置最大重试次数为无限大
         * 目的：只要消息没有发送成功，就一直重试，直到成功为止
         * 注意：配合幂等性使用，防止消息重复
         */
        configProps.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        
        /**
         * 【关键配置3】enable.idempotence=true
         * 说明：启用幂等性生产者
         * 目的：保证消息不会重复发送，即使发生重试也不会产生重复消息
         * 原理：Kafka会为每个生产者分配一个PID（Producer ID），并为每条消息分配序列号
         */
        configProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        
        /**
         * 【关键配置4】max.in.flight.requests.per.connection=5
         * 说明：限制每个连接上未确认的请求数为5
         * 目的：在保证消息顺序的同时，提高吞吐量
         * 注意：必须≤5才能保证幂等性和消息顺序性
         */
        configProps.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5);
        
        /**
         * 【性能配置1】batch.size=16384 (16KB)
         * 说明：设置批量发送的大小为16KB
         * 目的：将多条消息打包成一个批次发送，减少网络请求次数，提高吞吐量
         */
        configProps.put(ProducerConfig.BATCH_SIZE_CONFIG, 16384);
        
        /**
         * 【性能配置2】linger.ms=10
         * 说明：设置等待时间为10毫秒
         * 目的：如果批次未满，最多等待10毫秒后也会发送，平衡延迟和吞吐量
         */
        configProps.put(ProducerConfig.LINGER_MS_CONFIG, 10);
        
        /**
         * 【性能配置3】buffer.memory=33554432 (32MB)
         * 说明：设置生产者缓冲区大小为32MB
         * 目的：用于缓存等待发送的消息，防止发送速度过快导致缓冲区溢出
         */
        configProps.put(ProducerConfig.BUFFER_MEMORY_CONFIG, 33554432);
        
        /**
         * 【性能配置4】compression.type=lz4
         * 说明：启用LZ4压缩算法
         * 目的：压缩消息数据，减少网络传输量和存储成本
         * 优势：LZ4压缩速度快，压缩率适中，对性能影响小
         */
        configProps.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");
        
        // 创建并返回生产者工厂
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    /**
     * 创建KafkaTemplate
     * 
     * 思路：使用上面配置的ProducerFactory创建KafkaTemplate
     * 目的：提供一个高级别的Kafka操作模板，简化消息发送操作
     * 
     * @return KafkaTemplate Kafka模板实例
     */
    @Bean
    public KafkaTemplate<String, Object> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
