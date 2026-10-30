# -*- coding: utf-8 -*-
"""com.ruoyi.common.constant.ScheduleConstants

源文件：pro-base-common/src/main/java/com/ruoyi/common/constant/ScheduleConstants.java
"""
from __future__ import annotations

from enum import Enum


class ScheduleConstants:
    """任务调度通用常量。

    【Java→Python】嵌套枚举 Status 在 Java 中是 ScheduleConstants.Status；
    移植后用模块级枚举 + 类属性别名保持同样的访问路径。
    """

    TASK_CLASS_NAME = "TASK_CLASS_NAME"
    TASK_PROPERTIES = "TASK_PROPERTIES"       # 执行目标key
    MISFIRE_DEFAULT = "0"                     # 默认
    MISFIRE_IGNORE_MISFIRES = "1"             # 立即触发执行
    MISFIRE_FIRE_AND_PROCEED = "2"            # 触发一次执行
    MISFIRE_DO_NOTHING = "3"                  # 不触发立即执行


class Status(Enum):
    """ScheduleConstants.Status。

    【Java→Python】Java 枚举的 getValue() → Python 枚举的 .value；
    为兼容 Java 调用写法，额外提供 getValue() 方法（但 Python 侧属性名带下划线）。
    """

    NORMAL = "0"      # 正常
    PAUSE = "1"       # 暂停

    def getValue(self) -> str:
        return self.value


# 保持 ScheduleConstants.Status.NORMAL 的访问路径
ScheduleConstants.Status = Status
