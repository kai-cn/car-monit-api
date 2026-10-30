# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.CheckpointingMode

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：``org.apache.flink.streaming.api.CheckpointingMode``。
本工程用法（VehicleTrackFlinkJob.main 步骤 1）：
    env.enableCheckpointing(60000, CheckpointingMode.EXACTLY_ONCE);

【Java→Python】关键差异
1) Java 是**枚举**，取值只有 EXACTLY_ONCE / AT_LEAST_ONCE；
   Python 用类属性字符串常量表达（与 StateTtlConfig 里的枚举替身风格一致），
   因为这里的值只被 env 记录、不参与分支判断，不需要 Enum 的身份语义。
2) 若需要 ``CheckpointingMode.EXACTLY_ONCE.name`` 形式的写法，
   字符串常量天然支持（``"EXACTLY_ONCE"``），无需额外适配。
"""
from __future__ import annotations

__all__ = ["CheckpointingMode"]


class CheckpointingMode(object):
    """``CheckpointingMode`` 枚举的替身。"""

    #: 精确一次语义（本工程使用）
    EXACTLY_ONCE = "EXACTLY_ONCE"
    #: 至少一次语义
    AT_LEAST_ONCE = "AT_LEAST_ONCE"

    @staticmethod
    def values():
        """对应 ``values()``（Java 枚举自带）。"""
        return [CheckpointingMode.EXACTLY_ONCE, CheckpointingMode.AT_LEAST_ONCE]

    @staticmethod
    def valueOf(name: str) -> str:
        """对应 ``valueOf(String)``：非法名称抛 ValueError（Java 抛 IllegalArgumentException）。"""
        if name not in CheckpointingMode.values():
            raise ValueError("No enum constant CheckpointingMode.%s" % name)
        return name
