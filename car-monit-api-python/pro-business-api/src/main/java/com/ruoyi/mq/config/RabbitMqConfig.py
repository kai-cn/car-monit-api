# -*- coding: utf-8 -*-
"""com.ruoyi.mq.config.RabbitMqConfig

源文件：pro-business-api/src/main/java/com/ruoyi/mq/config/RabbitMqConfig.java

【Java→Python】关键差异（本文件有两处必须注意的命名冲突）
1) **字段与方法同名**：Java 允许 ``private String deadLetterExchange;`` 与
   ``public Exchange deadLetterExchange()`` 共存；Python 的**实例属性会遮蔽类方法**
   （``config.deadLetterExchange`` 拿到的是字符串，方法不可再调用）。
   因此两个字段改名为：``deadLetterExchangeName`` / ``deadLetterQueueName``，
   方法名保持 Java 原名不变（对外 API 不受影响）。
2) **``with(...)`` 是 Python 关键字**：Java 的
   ``BindingBuilder.bind(q).to(ex).with("snapshot.flow").noargs()``
   必须写成 ``.with_("snapshot.flow")``（见 BindingBuilder.py）。
3) ``@Value("${mq.topic.snapshot-flow}")`` → ``Environment().value(...)``。
   Java 的占位符没有默认值，配置缺失时 Spring 启动失败；Environment 替身同样
   抛 ``KeyError``（见 Environment.py 注释第 4 条）。
   构造器额外允许显式传参，便于单元测试不依赖 application.yml。
4) ``@Bean`` 方法：Spring 会把返回值注册为 Bean 并保证单例；Python 侧不注册容器，
   每次调用都会新建对象（值对象，无状态，语义等价）。``@Configuration`` 不翻译。
5) ``log.info("... {}", x)`` → ``log.info("... %s", x)``。
"""
from __future__ import annotations

import logging
from typing import Optional

from org.springframework.amqp.core.Binding import Binding
from org.springframework.amqp.core.BindingBuilder import BindingBuilder
from org.springframework.amqp.core.Exchange import Exchange
from org.springframework.amqp.core.ExchangeBuilder import ExchangeBuilder
from org.springframework.amqp.core.Queue import Queue
from org.springframework.amqp.core.QueueBuilder import QueueBuilder
from org.springframework.core.env.Environment import Environment

log = logging.getLogger(__name__)


class RabbitMqConfig(object):
    """RabbitMQ 交换机/队列/绑定配置（@Configuration）。"""

    def __init__(self, environment: Optional[Environment] = None,
                 snapshotFlowTopic: Optional[str] = None,
                 deadLetterExchangeName: Optional[str] = None,
                 deadLetterQueueName: Optional[str] = None,
                 deadLetterRoutingKey: Optional[str] = None) -> None:
        env = environment or Environment()
        # 【Java→Python】@Value 注入 → 构造器显式解析（显式传参优先，便于测试）
        self.snapshotFlowTopic = snapshotFlowTopic if snapshotFlowTopic is not None \
            else env.value("${mq.topic.snapshot-flow}")
        # 【Java→Python】字段改名，见模块注释第 1 条（避免遮蔽同名方法）
        self.deadLetterExchangeName = deadLetterExchangeName \
            if deadLetterExchangeName is not None \
            else env.value("${mq.dead-letter.exchange}")
        self.deadLetterQueueName = deadLetterQueueName \
            if deadLetterQueueName is not None \
            else env.value("${mq.dead-letter.queue}")
        self.deadLetterRoutingKey = deadLetterRoutingKey \
            if deadLetterRoutingKey is not None \
            else env.value("${mq.dead-letter.routing-key}")

    # ------------------------------------------------------------------ @Bean
    def snapshotFlowExchange(self) -> Exchange:
        """快照流量数据交换机（Direct Exchange）。"""
        log.info("[RabbitMQ配置] 创建交换机: %s", self.snapshotFlowTopic)
        return (ExchangeBuilder.directExchange(self.snapshotFlowTopic)
                .durable(True)  # 持久化
                .build())

    def snapshotFlowQueue(self) -> Queue:
        """快照流量数据队列（配置死信交换机 / 路由键 / TTL）。"""
        log.info("[RabbitMQ配置] 创建队列: queue.snapshot.flow")
        return (QueueBuilder.durable("queue.snapshot.flow")
                # 死信交换机
                .deadLetterExchange(self.deadLetterExchangeName)
                # 死信路由键
                .deadLetterRoutingKey(self.deadLetterRoutingKey)
                # 消息TTL（60秒）
                .ttl(60000)
                .build())

    def snapshotFlowBinding(self, snapshotFlowQueue: Queue,
                            snapshotFlowExchange: Exchange) -> Binding:
        """绑定队列到交换机。"""
        log.info("[RabbitMQ配置] 绑定队列到交换机")
        return (BindingBuilder.bind(snapshotFlowQueue)
                .to(snapshotFlowExchange)
                # 【Java→Python】Java 的 with(...) 是 Python 关键字 → with_(...)
                .with_("snapshot.flow")
                .noargs())

    def deadLetterExchange(self) -> Exchange:
        """死信交换机。"""
        log.info("[RabbitMQ配置] 创建死信交换机: %s", self.deadLetterExchangeName)
        return (ExchangeBuilder.directExchange(self.deadLetterExchangeName)
                .durable(True)
                .build())

    def deadLetterQueue(self) -> Queue:
        """死信队列。"""
        log.info("[RabbitMQ配置] 创建死信队列: %s", self.deadLetterQueueName)
        return QueueBuilder.durable(self.deadLetterQueueName).build()

    def deadLetterBinding(self, deadLetterQueue: Queue,
                          deadLetterExchange: Exchange) -> Binding:
        """绑定死信队列到死信交换机。"""
        log.info("[RabbitMQ配置] 绑定死信队列到死信交换机")
        return (BindingBuilder.bind(deadLetterQueue)
                .to(deadLetterExchange)
                .with_(self.deadLetterRoutingKey)
                .noargs())
