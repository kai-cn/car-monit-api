# -*- coding: utf-8 -*-
"""java.time.Duration

【无 Java 源文件：JDK 类替身】（``java.time.Duration``）
业务代码用法（CompositeQueryOptimizationService.estimateDayRange）：
    return (int) java.time.Duration.between(start, end).toDays() + 1;

【Java→Python 关键差异】
1) Java 的 ``Duration`` 表示**基于时间的时间量**（秒 + 纳秒），与 ``Period``
   （基于日期）不同；``between`` 对两个 ``LocalDateTime`` 求的是**精确秒差**，
   ``toDays()`` 再做**向零截断**（不是按日期差，也不是四舍五入）：
       2024-01-01 00:00 → 2024-01-02 00:00 = 1 天
       2024-01-01 23:00 → 2024-01-02 01:00 = 0 天（2 小时 < 1 天）
   注意这与 ``ChronoUnit.DAYS.between`` 的结果**恰好一致**（两者都是截断），
   但它们对“负值”的处理同为向零截断，因此可互相替代 —— 转写仍保留
   ``Duration`` 原类名，以忠实反映原代码调用路径。
2) ``LocalDateTime`` 映射为 Python ``datetime``（全工程约定），
   ``Duration`` 内部用 ``timedelta`` 表示。
3) 本工程只用到 ``between`` / ``toDays``，其余（``ofHours`` / ``plus`` /
   ``toMillis`` 等）按需补充。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

__all__ = ["Duration"]


class Duration(object):
    """``java.time.Duration`` 的替身（内部包装 ``timedelta``）。"""

    def __init__(self, delta: timedelta) -> None:
        self._delta = delta

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def between(start_inclusive: datetime, end_exclusive: datetime) -> "Duration":
        """对应 ``static Duration between(Temporal startInclusive, Temporal endExclusive)``。"""
        return Duration(end_exclusive - start_inclusive)

    @staticmethod
    def ofDays(days: int) -> "Duration":
        return Duration(timedelta(days=days))

    @staticmethod
    def ofHours(hours: int) -> "Duration":
        return Duration(timedelta(hours=hours))

    @staticmethod
    def ofMinutes(minutes: int) -> "Duration":
        return Duration(timedelta(minutes=minutes))

    @staticmethod
    def ofSeconds(seconds: int) -> "Duration":
        return Duration(timedelta(seconds=seconds))

    @staticmethod
    def ofMillis(millis: int) -> "Duration":
        return Duration(timedelta(milliseconds=millis))

    # ------------------------------------------------------------------ 换算
    def toDays(self) -> int:
        """对应 ``toDays()``：**向零截断**（Java 整数除法语义）。"""
        total_seconds = int(self._delta.total_seconds())
        # 【Java→Python】`int()` 对正负都是向零截断；不能用 `//`（负数会向下取整）
        return int(total_seconds / 86400)

    def toHours(self) -> int:
        return int(int(self._delta.total_seconds()) / 3600)

    def toMinutes(self) -> int:
        return int(int(self._delta.total_seconds()) / 60)

    def toSeconds(self) -> int:
        return int(self._delta.total_seconds())

    def toMillis(self) -> int:
        return int(self._delta.total_seconds() * 1000)

    def getSeconds(self) -> int:
        """对应 ``getSeconds()``（秒部分，不含纳秒）。"""
        return int(self._delta.total_seconds())

    # ------------------------------------------------------------------ 运算
    def plus(self, other: "Duration") -> "Duration":
        return Duration(self._delta + other._delta)

    def minus(self, other: "Duration") -> "Duration":
        return Duration(self._delta - other._delta)

    def isNegative(self) -> bool:
        return self._delta < timedelta(0)

    def isZero(self) -> bool:
        return self._delta == timedelta(0)

    # ------------------------------------------------------------------ 比较
    def compareTo(self, other: Optional["Duration"]) -> int:
        if other is None:
            raise ValueError("compareTo 参数不能为 null")
        if self._delta < other._delta:
            return -1
        if self._delta > other._delta:
            return 1
        return 0

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Duration) and self._delta == other._delta

    def __hash__(self) -> int:
        return hash(self._delta)

    def toString(self) -> str:
        """对应 ``toString()``：ISO-8601 形式 ``PTnHnMnS``（简化版）。"""
        return "PT%dS" % self.toSeconds()

    def __repr__(self) -> str:
        return "Duration(%r)" % (self._delta,)
