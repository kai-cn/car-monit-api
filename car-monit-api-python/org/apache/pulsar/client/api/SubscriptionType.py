# -*- coding: utf-8 -*-
"""org.apache.pulsar.client.api.SubscriptionType

【无 Java 源文件：框架类替身】
Java 侧来自 pulsar-client-api：`org.apache.pulsar.client.api.SubscriptionType`
是一个 **enum**，取值 Exclusive / Failover / Shared / Key_Shared。

【Java→Python 关键差异】
1) Java enum 常量本身是对象；Python 用 ``enum.Enum`` 还原，``SubscriptionType.Shared``
   仍是唯一对象，可直接用 ``==`` 比较（与 Java 一致）。
2) Java 的 ``Key_Shared`` 是合法标识符（下划线），Python 直接沿用。
3) 最容易被忽略的差异：Java 的 ``name()`` / ``ordinal()`` 是**方法**，
   Python 的 ``.name`` / ``.value`` 是**属性** —— 调用点不要写 ``name()``。
4) Java 静态方法 ``valueOf(String)`` → Python 用下标 ``SubscriptionType["Shared"]``
   （模块级另提供 ``valueOf(name)`` 便于逐行对照）。
"""
from __future__ import annotations

from enum import Enum

__all__ = ["SubscriptionType", "valueOf"]


class SubscriptionType(Enum):
    """Pulsar 订阅类型。"""

    Exclusive = "Exclusive"
    Failover = "Failover"
    Shared = "Shared"
    Key_Shared = "Key_Shared"

    def __str__(self) -> str:
        # Java 的 Enum#toString() 默认返回常量名
        return self.name


def valueOf(name: str) -> SubscriptionType:
    """等价 Java 的静态方法 ``SubscriptionType.valueOf(String)``。"""
    return SubscriptionType[name]
