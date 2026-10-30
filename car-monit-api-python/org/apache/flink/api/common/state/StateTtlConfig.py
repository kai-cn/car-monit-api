# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.StateTtlConfig

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.StateTtlConfig``。
本工程用法（VehicleTrackFlinkJob.open）：
    StateTtlConfig ttlConfig = StateTtlConfig
            .newBuilder(Time.milliseconds(STATE_TTL))        // 30 天
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .cleanupIncrementally(10, true)
            .build();

【Java→Python】关键差异
1) Java 的 ``StateTtlConfig`` 是**不可变配置对象** + 内部 ``Builder``；
   ``newBuilder(Time)`` 返回 Builder，链式 setter 都返回 this，``build()``
   才产出 StateTtlConfig。替身保持完全相同的调用链。
2) ``UpdateType`` / ``StateVisibility`` 是 Java **嵌套枚举**：
   ``StateTtlConfig.UpdateType.OnCreateAndWrite``。Python 用嵌套类 + 类属性
   表达（不能用 Enum 嵌套，否则 ``UpdateType.OnCreateAndWrite`` 属性名
   与 Enum 成员名的大小写习惯不符）。取值用字符串常量，仅作记录。
3) **TTL 在替身里不做真实过期**：Flink 由状态后端在读写时惰性清理；
   Python 侧没有状态后端，``StateTtlConfig`` 只保存配置供断言
   （见 ValueStateDescriptor.getTtlConfig）。
4) ``cleanupIncrementally(entries, runCleanupForEveryRecord)`` 的两个参数
   语义与 Java 一致：每处理 N 条记录触发一次清理、是否每条记录后都清理。
"""
from __future__ import annotations

from org.apache.flink.api.common.time.Time import Time

__all__ = ["StateTtlConfig"]


class UpdateType(object):
    """对应 ``StateTtlConfig.UpdateType`` 枚举。"""

    #: 创建 / 写入时刷新 TTL
    OnCreateAndWrite = "OnCreateAndWrite"
    #: 读 / 写时都刷新 TTL（= 滑动过期）
    OnReadAndWrite = "OnReadAndWrite"


class StateVisibility(object):
    """对应 ``StateTtlConfig.StateVisibility`` 枚举。"""

    #: 过期数据即使还没被清理也不返回（推荐）
    NeverReturnExpired = "NeverReturnExpired"
    #: 已过期但未清理的数据仍会返回
    ReturnExpiredIfNotCleanedUp = "ReturnExpiredIfNotCleanedUp"


class StateTtlConfig(object):
    """``StateTtlConfig`` 的替身（不可变配置 + Builder）。"""

    # 【Java→Python】Java 的两个枚举是**嵌套类型**，Python 用模块级类 + 类属性挂载
    UpdateType = UpdateType
    StateVisibility = StateVisibility

    def __init__(self, ttl: Time) -> None:
        self._ttl = ttl
        self.update_type: str = UpdateType.OnCreateAndWrite
        self.state_visibility: str = StateVisibility.NeverReturnExpired
        self.cleanup_size: int = 0
        self.cleanup_every_record: bool = False

    # ------------------------------------------------------------------ Builder
    @staticmethod
    def newBuilder(ttl: Time) -> "Builder":
        """对应 ``newBuilder(Time ttl)``。"""
        return StateTtlConfig.Builder(ttl)

    class Builder(object):
        """对应 ``StateTtlConfig.Builder``。"""

        def __init__(self, ttl: Time) -> None:
            self._config = StateTtlConfig(ttl)

        def setUpdateType(self, update_type: str) -> "StateTtlConfig.Builder":
            self._config.update_type = update_type
            return self

        def setStateVisibility(self, state_visibility: str) -> "StateTtlConfig.Builder":
            self._config.state_visibility = state_visibility
            return self

        def cleanupIncrementally(self, cleanup_size: int,
                                 run_cleanup_for_every_record: bool) -> "StateTtlConfig.Builder":
            self._config.cleanup_size = int(cleanup_size)
            self._config.cleanup_every_record = bool(run_cleanup_for_every_record)
            return self

        def cleanupInRocksdbCompactFilter(self, cleanup_size: int) -> "StateTtlConfig.Builder":
            """RocksDB 压缩过滤清理（本工程未使用，保留签名方便迁移）。"""
            self._config.cleanup_size = int(cleanup_size)
            return self

        def build(self) -> "StateTtlConfig":
            return self._config

    # ------------------------------------------------------------------ getter
    def getTtl(self) -> Time:
        return self._ttl

    def getUpdateType(self) -> str:
        return self.update_type

    def getStateVisibility(self) -> str:
        return self.state_visibility

    def __repr__(self) -> str:
        return ("StateTtlConfig(ttl=%r, updateType=%s, visibility=%s, "
                "cleanupSize=%d, everyRecord=%r)" %
                (self._ttl, self.update_type, self.state_visibility,
                 self.cleanup_size, self.cleanup_every_record))
