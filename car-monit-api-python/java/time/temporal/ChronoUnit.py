# -*- coding: utf-8 -*-
"""java.time.temporal.ChronoUnit

【无 Java 源文件：JDK 类替身】（``java.time.temporal.ChronoUnit``）
业务代码用法（optimization 包）：
    long days = ChronoUnit.DAYS.between(start, end);

【Java→Python 关键差异】
1) Java 的 ``ChronoUnit`` 是**枚举**，每个枚举常量都实现 ``TemporalUnit`` 的
   ``between(Temporal, Temporal)``；Python 这里用「枚举成员 + 同名方法」表达，
   调用写法 ``ChronoUnit.DAYS.between(a, b)`` 完全一致。
2) **``DAYS.between`` 不是简单的日期差**：JDK 的 ``LocalDateTime.until(end, DAYS)``
   先算日期相差天数，再按“时分秒”截断（不足一天舍去、**向零取整**）：
       2024-01-01 23:00 → 2024-01-02 01:00  = 0 天（不是 1 天）
       2024-01-02 01:00 → 2024-01-01 23:00  = 0 天
   本替身逐行还原该规则（``_daysBetween``），不能用 ``(b - a).days`` 替代
   —— 后者对负数会向下取整，结果差 1 天。
3) 本工程只用到 ``DAYS``；``HOURS`` / ``MINUTES`` / ``SECONDS`` / ``MILLIS``
   一并实现，全部遵循 Java 的“截断向零”规则（Python 的 `int()` 除法即向零截断）。
4) Java 的 `LocalDateTime` 映射为 Python `datetime`（见 LocalDateTime 替身说明），
   因此 `between` 的参数类型是 `datetime`，返回值是 Python `int`（即 Java 的 long）。
"""
from __future__ import annotations

from datetime import datetime

__all__ = ["ChronoUnit"]


class _ChronoUnit(object):
    """``TemporalUnit`` 的最小实现（每个枚举常量一个实例）。"""

    def __init__(self, name: str, millis: float) -> None:
        self._name = name
        #: 一个单位等于多少毫秒（DAYS = 86400000）
        self._millis = millis

    def between(self, start: datetime, end: datetime) -> int:
        """对应 ``long between(Temporal startInclusive, Temporal endExclusive)``。"""
        if self._name == "DAYS":
            return _daysBetween(start, end)
        # 其它单位：毫秒差 / 单位毫秒；`int()` 对正负都是向零截断（Java 整数除法语义）
        delta_millis = _epochMillis(end) - _epochMillis(start)
        return int(delta_millis / self._millis)

    def toString(self) -> str:
        """对应 ``Enum#name()``（本替身以 toString 暴露名称）。"""
        return self._name

    def __repr__(self) -> str:
        return "ChronoUnit.%s" % self._name


class ChronoUnit(object):
    """``ChronoUnit`` 枚举的替身（只暴露本工程及常见单位）。"""

    NANOS = _ChronoUnit("NANOS", 0.000001)
    MICROS = _ChronoUnit("MICROS", 0.001)
    MILLIS = _ChronoUnit("MILLIS", 1)
    SECONDS = _ChronoUnit("SECONDS", 1000)
    MINUTES = _ChronoUnit("MINUTES", 60 * 1000)
    HOURS = _ChronoUnit("HOURS", 60 * 60 * 1000)
    DAYS = _ChronoUnit("DAYS", 24 * 60 * 60 * 1000)

    @staticmethod
    def values():
        """对应 ``values()``（Java 枚举自带）。"""
        return [ChronoUnit.NANOS, ChronoUnit.MICROS, ChronoUnit.MILLIS,
                ChronoUnit.SECONDS, ChronoUnit.MINUTES, ChronoUnit.HOURS,
                ChronoUnit.DAYS]

    @staticmethod
    def valueOf(name: str):
        """对应 ``valueOf(String)``：非法名称抛 ValueError（Java 抛 IllegalArgumentException）。"""
        for unit in ChronoUnit.values():
            if unit.toString() == name:
                return unit
        raise ValueError("No enum constant ChronoUnit.%s" % name)


def _epochMillis(value: datetime) -> int:
    """等价 ``Date#getTime()``：epoch 毫秒。"""
    return int(value.timestamp() * 1000)


def _daysBetween(start: datetime, end: datetime) -> int:
    """逐行翻译 JDK ``LocalDateTime.daysUntil``：

        long days = endDate.toEpochDay() - startDate.toEpochDay();
        if (days > 0 && endTime < startTime) days -= 1;
        else if (days < 0 && endTime > startTime) days += 1;

    【Java→Python】`toEpochDay()` 与 `date().toordinal()` 的绝对基准虽然不同，
    但**差值一致**，因此可以直接相减。
    """
    days = end.date().toordinal() - start.date().toordinal()
    end_time = (end.hour, end.minute, end.second, end.microsecond)
    start_time = (start.hour, start.minute, start.second, start.microsecond)
    if days > 0 and end_time < start_time:
        days -= 1
    elif days < 0 and end_time > start_time:
        days += 1
    return days
