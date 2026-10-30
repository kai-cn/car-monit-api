# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.time.Time

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.time.Time``。
本工程用法（VehicleTrackFlinkJob）：
    StateTtlConfig.newBuilder(Time.milliseconds(STATE_TTL))

【Java→Python】关键差异
1) Java 的 ``Time`` 封装 (size, unit) 并强制用静态工厂构造
   （``milliseconds`` / ``seconds`` / ``minutes``）；Python 没有重载与
   不可变值对象约束，这里保留同样的静态工厂与 ``toMilliseconds()``。
2) 本工程只用到毫秒语义；``Time`` 在替身里统一折算成 long 毫秒保存，
   避免调用方再关心单位换算（与 Flink 内部 ``Time.toMilliseconds()`` 一致）。
"""
from __future__ import annotations

__all__ = ["Time"]


class Time(object):
    """``Time`` 的替身（内部统一用毫秒表示）。"""

    def __init__(self, millis: int) -> None:
        self._millis = int(millis)

    # ------------------------------------------------------------------ 静态工厂
    @staticmethod
    def milliseconds(milliseconds: int) -> "Time":
        return Time(milliseconds)

    @staticmethod
    def seconds(seconds: int) -> "Time":
        return Time(int(seconds) * 1000)

    @staticmethod
    def minutes(minutes: int) -> "Time":
        return Time(int(minutes) * 60 * 1000)

    @staticmethod
    def hours(hours: int) -> "Time":
        return Time(int(hours) * 60 * 60 * 1000)

    @staticmethod
    def days(days: int) -> "Time":
        return Time(int(days) * 24 * 60 * 60 * 1000)

    # ------------------------------------------------------------------ 取值
    def toMilliseconds(self) -> int:
        return self._millis

    def toSeconds(self) -> int:
        return self._millis // 1000

    def toMinutes(self) -> int:
        return self._millis // (60 * 1000)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Time) and other._millis == self._millis

    def __hash__(self) -> int:
        return hash(self._millis)

    def __repr__(self) -> str:
        return "Time(%d ms)" % self._millis
