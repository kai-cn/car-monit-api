# -*- coding: utf-8 -*-
"""org.apache.rocketmq.client.producer.SendStatus

【无 Java 源文件：框架类替身】
Java 侧来自 rocketmq-client：``org.apache.rocketmq.client.producer.SendStatus``。
本工程用法（RocketMqProducer.sendBatchMessages）：
    if ("SEND_OK".equals(result.getSendStatus().name())) { ... }

【Java→Python】关键差异
1) Java 的 ``SendStatus`` 是枚举；Python 用 ``Enum``，常量小写定义、名称大写可读。
   **``name()`` 是方法 vs ``.name`` 是属性**：转写时 ``result.getSendStatus().name()``
   必须改成 ``result.getSendStatus().name``（Java 枚举方法名与 Python 内置属性同名）。
2) 枚举常量与 RocketMQ 源码保持一致：
   ``SEND_OK`` / ``FLUSH_DISK_TIMEOUT`` / ``FLUSH_SLAVE_TIMEOUT`` / ``SLAVE_NOT_AVAILABLE``。
   （``SEND_FAILED`` 不是官方 ``SendStatus`` 的常量，它来自异常路径，故不定义。）
3) 真实发送状态由 broker 返回；替身的 ``DefaultMQProducer`` 固定返回 ``SEND_OK``，
   可用 ``fail_status`` 注入其它状态以测试“发送失败→本地备份”分支。
"""

from __future__ import annotations

from enum import Enum

__all__ = ["SendStatus"]


class SendStatus(Enum):
    """``SendStatus`` 枚举替身。"""

    SEND_OK = "SEND_OK"
    FLUSH_DISK_TIMEOUT = "FLUSH_DISK_TIMEOUT"
    FLUSH_SLAVE_TIMEOUT = "FLUSH_SLAVE_TIMEOUT"
    SLAVE_NOT_AVAILABLE = "SLAVE_NOT_AVAILABLE"

    def name_(self) -> str:
        """Java 的 ``name()`` 的等价方法（避免与 Python 的 ``.name`` 属性混淆）。

        【Java→Python】Python ``Enum`` 已有 ``.name`` **属性**，不能再用 ``name``
        作为方法名，因此转写时统一用 ``.name``；此处额外提供 ``name_()``
        只是为了给习惯 Java 写法的调用方一个显式方法（本工程未使用）。
        """
        return self.name

    def __str__(self) -> str:
        # Java 枚举的 toString() 默认返回 name()
        return self.name
