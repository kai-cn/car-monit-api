# -*- coding: utf-8 -*-
"""org.apache.rocketmq.client.producer.DefaultMQProducer

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.client.producer.DefaultMQProducer``。
本工程用法（RocketMqProducer）：
    SendResult result = producer.send(message);
    另外通过 @Bean 注入，生命周期方法为 @PreDestroy destroy()（本类自身不 start）。

【Java→Python】关键差异
1) **没有真实 broker**：真实 ``send`` 会把消息通过 Netty 发到 NameServer/Broker 并等待
   存储结果；替身在当前线程把消息记到**类级列表** ``_SENT_MESSAGES``（模拟同一个
   RocketMQ 集群），并立即返回 ``SEND_OK``。这样“发送成功/失败”两条分支都能测试。
2) **启动状态检查**：真实客户端在 ``start()`` 之前调用 ``send`` 会抛
   ``MQClientException: The producer service state not OK``；替身同样在未启动时抛
   ``RuntimeError``（对应 MQClientException），便于暴露“忘记 start”的配置问题。
3) **异常语义**：``start()`` 在 Java 里抛受检的 ``MQClientException``；
   ``send()`` 抛 ``MQClientException`` / ``RemotingException`` / ``InterruptedException``。
   Python 无受检异常，替身统一用 ``RuntimeError`` / ``ConnectionError`` 表达。
4) **注入失败**：提供 ``fail_next``（下一次失败）、``always_fail``（持续失败）与
   ``fail_status``（返回非 SEND_OK 的 SendStatus）三个开关，用于覆盖
   ``sendBatchMessages`` 的 catch 与 else 分支。
5) Java 的 ``setNamesrvAddr`` / ``setInstanceName`` / ``setVipChannelEnabled`` 等
   配置方法在替身里只保存值（不建连接），返回 ``None``（Java 里也是 void）。
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional, Tuple

from org.apache.rocketmq.client.producer.SendResult import SendResult
from org.apache.rocketmq.client.producer.SendStatus import SendStatus
from org.apache.rocketmq.common.message.Message import Message
from org.apache.rocketmq.common.message.MessageQueue import MessageQueue

__all__ = ["DefaultMQProducer"]


class DefaultMQProducer(object):
    """``DefaultMQProducer`` 的进程内替身。"""

    #: 模拟 broker 存储：所有 producer 实例共享（Java 里同一个集群也是共享的）
    _SENT_MESSAGES: List[Tuple[str, Optional[str], Optional[str], bytes]] = []
    #: 模拟每 (topic, queueId) 的 offset 自增
    _OFFSETS: dict = {}

    def __init__(self, producer_group: str = "DEFAULT_PRODUCER") -> None:
        # Java 构造器：DefaultMQProducer(String producerGroup)
        self._producer_group = producer_group
        self._namesrv_addr: Optional[str] = None
        self._instance_name = "DEFAULT"
        self._vip_channel_enabled = True
        self._send_msg_timeout = 3000
        self._retry_times_when_send_failed = 2
        self._started = False
        # 测试注入开关（Java 无）
        self.fail_next: Optional[BaseException] = None
        self.always_fail = False
        self.fail_status: Optional[SendStatus] = None

    # ------------------------------------------------------------------ 生命周期
    def start(self) -> None:
        """对应 ``start()``：真实实现会拉取路由、启动定时任务。"""
        self._started = True

    def shutdown(self) -> None:
        """对应 ``shutdown()``。"""
        self._started = False

    # ------------------------------------------------------------------ 配置
    def setNamesrvAddr(self, namesrv_addr: str) -> None:
        self._namesrv_addr = namesrv_addr

    def getNamesrvAddr(self) -> Optional[str]:
        return self._namesrv_addr

    def setInstanceName(self, instance_name: str) -> None:
        self._instance_name = instance_name

    def getInstanceName(self) -> str:
        return self._instance_name

    def setVipChannelEnabled(self, enabled: bool) -> None:
        self._vip_channel_enabled = enabled

    def setSendMsgTimeout(self, timeout_millis: int) -> None:
        self._send_msg_timeout = int(timeout_millis)

    def setRetryTimesWhenSendFailed(self, retry_times: int) -> None:
        self._retry_times_when_send_failed = int(retry_times)

    def getProducerGroup(self) -> str:
        return self._producer_group

    # ------------------------------------------------------------------ 发送
    def send(self, message: Any, timeout: Optional[int] = None) -> SendResult:
        """对应 ``send(Message)`` / ``send(Message, long timeout)``。

        批量重载 ``send(Collection<Message>)`` 也用本方法表达：传入 list/tuple 时
        逐条发送并返回最后一条的结果（Java 的批量发送同样逐条投递）。
        """
        if not self._started:
            # 对应 MQClientException: The producer service state not OK
            raise RuntimeError("MQClientException: The producer service state not OK")

        error = self._next_error()
        if error is not None:
            raise error

        if isinstance(message, (list, tuple)):
            result: Optional[SendResult] = None
            for item in message:
                result = self.send(item, timeout)
            if result is None:
                raise ValueError("send(Collection) 的消息集合不能为空")
            return result

        if not isinstance(message, Message):
            raise TypeError("producer.send 只接受 Message/Collection，实际为 "
                            + type(message).__name__)

        topic = message.getTopic()
        queue_key = (topic, 0)
        offset = self._OFFSETS.get(queue_key, 0)
        self._OFFSETS[queue_key] = offset + 1
        self._SENT_MESSAGES.append((topic, message.getTags(), message.getKeys(),
                                    message.getBody()))

        status = self.fail_status or SendStatus.SEND_OK
        return SendResult(status,
                          msg_id=uuid.uuid4().hex,  # broker 生成的 32 位 hex
                          message_queue=MessageQueue(topic, "broker-a", 0),
                          queue_offset=offset)

    # ------------------------------------------------------------------ 内部
    def _next_error(self) -> Optional[BaseException]:
        if self.always_fail:
            return RuntimeError(
                "RemotingException: 模拟 RocketMQ broker 不可用")
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            return error
        return None

    # ------------------------------------------------------------------ 测试辅助
    @classmethod
    def sentMessages(cls) -> List[Tuple[str, Optional[str], Optional[str], bytes]]:
        """查看已“发送成功”的消息（Java 无此方法，仅供测试断言）。"""
        return list(cls._SENT_MESSAGES)

    @classmethod
    def reset(cls) -> None:
        """清空模拟 broker（Java 无此方法，仅供测试隔离）。"""
        cls._SENT_MESSAGES.clear()
        cls._OFFSETS.clear()

    def __repr__(self) -> str:
        return "DefaultMQProducer(producerGroup=%r, started=%r)" % (
            self._producer_group, self._started)
