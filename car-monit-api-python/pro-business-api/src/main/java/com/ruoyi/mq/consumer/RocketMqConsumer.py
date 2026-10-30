# -*- coding: utf-8 -*-
"""com.ruoyi.mq.consumer.RocketMqConsumer

源文件：pro-business-api/src/main/java/com/ruoyi/mq/consumer/RocketMqConsumer.java

【Java→Python】关键差异
1) **类上的 ``@Component`` / ``@RocketMQMessageListener`` 在 Java 源码里被
   ``/* ... */`` 整段注释掉了** —— 也就是说这个消费者**没有注册到 Spring 容器**，
   运行时不会有人调用 ``onMessage``。这是原工程现状，Python 版忠实保留
   （下面的注释块与 Java 一一对应）；若要启用，需同时恢复注解/装饰器语义。
2) ``implements RocketMQListener<MessageExt>`` → 继承抽象基类 ``RocketMQListener``；
   泛型参数在 Python 运行时被擦除（仅类型标注）。
3) ``new String(messageExt.getBody(), StandardCharsets.UTF_8)``
   → ``messageExt.getBody().decode(StandardCharsets.UTF_8)``
   （Java 的 String 构造器解码 → Python 的 bytes.decode）。
4) ``Long.valueOf(data.getId())`` → ``int(data.getId())``：
   解析失败时 Java 抛 ``NumberFormatException``，Python 抛 ``ValueError``，
   两者都会被外层 ``except Exception`` 捕获并转换成 ``RuntimeException``。
5) ``throw new RuntimeException("消息处理失败", e)``
   → ``raise RuntimeError("消息处理失败") from e``：
   Python 用 ``raise ... from e`` 保留原始异常链（等价 Java 的 cause）。
6) **死信队列**：RocketMQ 的 broker 在 ``reconsumeTimes > maxReconsumeTimes`` 时
   自动把消息投递到 ``%DLQ%<consumerGroup>``，代码里的 ``if`` 只是**打日志**，
   没有任何“手动发送死信”的动作 —— 忠实保留该行为。
7) ``log.error("...", msgId, reconsumeTimes, e)``（SLF4J 末参为 Throwable）
   → ``log.error("...", msgId, reconsumeTimes, exc_info=True)``。
"""
from __future__ import annotations

import logging
from typing import Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.mq.service.DataProcessService import DataProcessService
from java.nio.charset.StandardCharsets import StandardCharsets
from org.apache.rocketmq.common.message.MessageExt import MessageExt
from org.apache.rocketmq.spring.core.RocketMQListener import RocketMQListener

log = logging.getLogger(__name__)

# 原 Java 类上的注解（已被 /* */ 注释，未生效）：
# @Component
# @RocketMQMessageListener(
#         topic = "${rocketmq.topic.snapshot-flow:topic_snapshot_flow}",
#         consumerGroup = "${rocketmq.consumer.group:snapshot_flow_consumer}",
#         maxReconsumeTimes = 3
# )


class RocketMqConsumer(RocketMQListener):
    """RocketMQ 消费者（消费快照流量并写入 MySQL 分表 / ES）。"""

    MAX_RETRY_COUNT = 3

    def __init__(self, dataProcessService: Optional[DataProcessService] = None) -> None:
        # 【Java→Python】Spring 构造器注入 → 可选参数，缺省 new 一个实现
        self.dataProcessService = dataProcessService or DataProcessService()
        log.info("[RocketMQ消费者] 初始化完成")

    # ------------------------------------------------------------------ 消费
    def onMessage(self, messageExt: MessageExt) -> None:
        """对应 ``onMessage(MessageExt messageExt)``。"""
        msgId = messageExt.getMsgId()
        reconsumeTimes = messageExt.getReconsumeTimes()

        log.debug("[RocketMQ消费者] 收到消息, msgId=%s, reconsumeTimes=%s",
                  msgId, reconsumeTimes)

        try:
            # 解析消息体：new String(bytes, UTF_8) → bytes.decode(...)
            body = messageExt.getBody().decode(StandardCharsets.UTF_8)
            data: OdsRtSzdnSnapshotFlowAddcode = JSON.parseObject(
                body, OdsRtSzdnSnapshotFlowAddcode)

            # 幂等性检查
            if self.dataProcessService.isProcessed(msgId):
                log.debug("[RocketMQ消费者] 消息已处理, msgId=%s", msgId)
                return

            # 处理数据（存入MySQL分表和ES）
            self.dataProcessService.process(data)

            # 标记消息已处理
            self.dataProcessService.markProcessed(msgId, int(data.getId()))

            log.info("[RocketMQ消费者] 消息处理成功, msgId=%s, dataId=%s",
                     msgId, data.getId())

        except Exception as e:  # noqa: BLE001 - Java 捕获 Exception
            log.error("[RocketMQ消费者] 处理消息失败, msgId=%s, reconsumeTimes=%s",
                      msgId, reconsumeTimes, exc_info=True)

            # 如果重试次数超过阈值，发送到死信队列
            if reconsumeTimes >= RocketMqConsumer.MAX_RETRY_COUNT:
                log.warning("[RocketMQ消费者] 消息超过重试次数，进入死信队列, msgId=%s",
                            msgId)
                # RocketMQ会自动将超过maxReconsumeTimes的消息发送到死信队列

            # 抛出异常触发重新投递（raise ... from e 保留 cause）
            raise RuntimeError("消息处理失败") from e
