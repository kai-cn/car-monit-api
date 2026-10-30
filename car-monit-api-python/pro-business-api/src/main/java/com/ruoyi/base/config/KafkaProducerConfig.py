# -*- coding: utf-8 -*-
"""com.ruoyi.base.config.KafkaProducerConfig

源文件：pro-business-api/src/main/java/com/ruoyi/base/config/KafkaProducerConfig.java

Kafka 生产者配置类：
- 配置生产者的核心参数，确保数据传输的可靠性和一致性
- 实现消息零丢失的关键配置：ack=all、幂等性、无限重试等

【Java→Python】整体说明
1) ``@Configuration`` + ``@EnableKafka`` + ``@Bean`` → Python 无容器：
   本类退化为**Bean 工厂**：方法名与 Java 的 @Bean 方法一一对应
   （``producerFactory()`` / ``kafkaTemplate()``），由启动代码显式调用并
   用 ``SpringUtils.register_bean("kafkaTemplate", ...)`` 注册。
2) ``@Value("${spring.kafka.bootstrap-servers}")`` 注入**私有字段**：
   Python 无字段注入，改为构造器里 ``Environment().value(...)`` 显式取值
   （等价 Spring 启动时解析占位符）。注意 Java 此处**没有默认值**，
   配置缺失会启动失败 —— Python 侧同样抛 ``KeyError``，不静默兜底。
3) ``Map<String, Object> configProps = new HashMap<>()`` → ``dict``；
   ``ProducerConfig.XXX_CONFIG`` 常量在 Python 侧是**同名的类属性**。
4) ``StringSerializer.class`` / ``JsonSerializer.class`` 传给 Kafka 的是 **Class 对象**，
   Kafka 内部反射实例化；Python 没有这套机制，直接把**类本身**放进 dict，
   由 ``DefaultKafkaProducerFactory`` 替身按需实例化（见该类注释）。
5) ``Integer.MAX_VALUE`` → ``sys.maxsize`` 不是等价物（Python int 无限精度）；
   为了与 Java 的 2^31-1 完全一致，这里显式写 ``2 ** 31 - 1``。
6) ``new KafkaTemplate<>(producerFactory())`` → 替身构造器同样接受工厂对象，
   并从中读取 ``bootstrap.servers``，因此这一行 Python 与 Java 逐字对应。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from org.apache.kafka.clients.producer.ProducerConfig import ProducerConfig
from org.apache.kafka.common.serialization.JsonSerializer import JsonSerializer
from org.apache.kafka.common.serialization.StringSerializer import StringSerializer
from org.springframework.core.env.Environment import Environment
from org.springframework.kafka.core.DefaultKafkaProducerFactory import DefaultKafkaProducerFactory
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate
from org.springframework.kafka.core.ProducerFactory import ProducerFactory

log = logging.getLogger(__name__)

# 【Java→Python】`Integer.MAX_VALUE` = 2^31-1；Python 的 int 无上限，
# sys.maxsize 在 64 位平台是 2^63-1，二者不等价，必须显式写常量。
INTEGER_MAX_VALUE = 2 ** 31 - 1

__all__ = ["KafkaProducerConfig"]


class KafkaProducerConfig(object):
    """Kafka 生产者配置（Bean 工厂）。"""

    def __init__(self, environment: Optional[Environment] = None) -> None:
        # 【Java→Python】@Value 字段注入 → 构造器显式解析（无默认值 → 缺失即抛 KeyError）
        env = environment or Environment()
        self.bootstrapServers: str = env.value("${spring.kafka.bootstrap-servers}", str)

    # ------------------------------------------------------------------ @Bean
    def producerFactory(self) -> ProducerFactory:
        """创建 Kafka 生产者工厂。

        思路：通过配置参数构建一个高可靠的 ProducerFactory
        目的：确保消息发送的可靠性，防止数据丢失

        【Java→Python】Java 的 ``new HashMap<>()`` → ``dict()``；
        ``configProps.put(k, v)`` → ``configProps[k] = v``（语义一致，仅写法不同）。
        """
        # 创建配置参数 Map
        configProps: Dict[str, Any] = {}

        # 配置 Kafka 集群地址
        configProps[ProducerConfig.BOOTSTRAP_SERVERS_CONFIG] = self.bootstrapServers

        # 配置 Key 序列化器：使用 StringSerializer 将 key 序列化为字符串
        configProps[ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG] = StringSerializer

        # 配置 Value 序列化器：使用 JsonSerializer 将对象序列化为 JSON
        configProps[ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG] = JsonSerializer

        # 【关键配置1】acks=all
        # 说明：要求所有 ISR（同步副本）都确认收到消息
        # 目的：确保消息不丢失，只有当所有副本都写入成功后才认为发送成功
        # 注意：会增加延迟，但能保证最高的可靠性
        configProps[ProducerConfig.ACKS_CONFIG] = "all"

        # 【关键配置2】retries=Integer.MAX_VALUE
        # 说明：设置最大重试次数为无限大
        # 目的：只要消息没有发送成功，就一直重试，直到成功为止
        # 注意：配合幂等性使用，防止消息重复
        configProps[ProducerConfig.RETRIES_CONFIG] = INTEGER_MAX_VALUE

        # 【关键配置3】enable.idempotence=true
        # 说明：启用幂等性生产者
        # 目的：保证消息不会重复发送，即使发生重试也不会产生重复消息
        # 原理：Kafka 会为每个生产者分配一个 PID（Producer ID），并为每条消息分配序列号
        configProps[ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG] = True

        # 【关键配置4】max.in.flight.requests.per.connection=5
        # 说明：限制每个连接上未确认的请求数为 5
        # 目的：在保证消息顺序的同时，提高吞吐量
        # 注意：必须≤5 才能保证幂等性和消息顺序性
        configProps[ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION] = 5

        # 【性能配置1】batch.size=16384 (16KB)
        # 说明：设置批量发送的大小为 16KB
        # 目的：将多条消息打包成一个批次发送，减少网络请求次数，提高吞吐量
        configProps[ProducerConfig.BATCH_SIZE_CONFIG] = 16384

        # 【性能配置2】linger.ms=10
        # 说明：设置等待时间为 10 毫秒
        # 目的：如果批次未满，最多等待 10 毫秒后也会发送，平衡延迟和吞吐量
        configProps[ProducerConfig.LINGER_MS_CONFIG] = 10

        # 【性能配置3】buffer.memory=33554432 (32MB)
        # 说明：设置生产者缓冲区大小为 32MB
        # 目的：用于缓存等待发送的消息，防止发送速度过快导致缓冲区溢出
        configProps[ProducerConfig.BUFFER_MEMORY_CONFIG] = 33554432

        # 【性能配置4】compression.type=lz4
        # 说明：启用 LZ4 压缩算法
        # 目的：压缩消息数据，减少网络传输量和存储成本
        # 优势：LZ4 压缩速度快，压缩率适中，对性能影响小
        configProps[ProducerConfig.COMPRESSION_TYPE_CONFIG] = "lz4"

        # 创建并返回生产者工厂
        # 【Java→Python】Java 泛型 `<>` 由编译器推断为 <String, Object>；
        # Python 泛型运行时擦除，直接构造即可。
        return DefaultKafkaProducerFactory(configProps)

    def kafkaTemplate(self) -> KafkaTemplate:
        """创建 KafkaTemplate。

        思路：使用上面配置的 ProducerFactory 创建 KafkaTemplate
        目的：提供一个高级别的 Kafka 操作模板，简化消息发送操作

        【Java→Python】替身的 KafkaTemplate 构造器同样吃 ProducerFactory，
        因此这一行与 Java 完全一致（替身内部取 bootstrap.servers 做日志/标识）。
        """
        return KafkaTemplate(self.producerFactory())
