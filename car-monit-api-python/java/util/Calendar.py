# -*- coding: utf-8 -*-
"""java.util.Calendar

【无 Java 源文件：JDK 类替身】
业务代码用法（optimization 包）：
    Calendar cal = Calendar.getInstance();
    cal.setTime(start);
    cal.set(Calendar.HOUR_OF_DAY, 0); cal.set(Calendar.MINUTE, 0);
    cal.set(Calendar.SECOND, 0);      cal.set(Calendar.MILLISECOND, 0);
    while (cal.getTime().before(end)) { ... cal.add(Calendar.DAY_OF_MONTH, 1); }
    cal.add(Calendar.YEAR, -1);
    cal.set(Calendar.DAY_OF_MONTH, 1); cal.add(Calendar.MONTH, -1);

【Java→Python 关键差异】
1) Java 的 `Calendar` 是**可变**时间计算器（`set` / `add` 原地修改），
   Python 的 `datetime` 是**不可变**的。替身内部持有一个 `datetime` 字段，
   每次 `set` / `add` 都重建它 —— 对外调用写法与 Java 完全一致。
2) **`Calendar.MONTH` 在 Java 里是 0 基**（0=一月）。替身保留该语义：
   `set(Calendar.MONTH, 0)` → 一月；`add(Calendar.MONTH, n)` 按月增减并
   自动进位/借位（与 Java 一致；Python 侧用“年*12+月”换算再还原）。
3) `getTime()` 返回 `datetime`（全工程 `java.util.Date` → `datetime` 的约定），
   因此 `cal.getTime().before(end)` 在 Python 里写成
   `cal.getTime() < end`（见调用处注释）。
4) `Calendar.getInstance()` 在 Java 里按默认时区取当前时间；
   Python 用 `datetime.now()`（本机时区），语义一致。
"""
from __future__ import annotations

import calendar as _calendar
from datetime import datetime
from typing import Optional

__all__ = ["Calendar"]


class Calendar(object):
    """`java.util.Calendar` 的替身（可变时间计算器）。"""

    #: 字段常量（取值与原版 JDK 一致，便于逐字对照）
    YEAR = 1
    MONTH = 2
    DAY_OF_MONTH = 5
    #: 【Java→Python】Java 的 `HOUR`（12 小时制字段，取值 10）与 `HOUR_OF_DAY`
    #: （24 小时制，取值 11）是两个不同常量。本工程只用 `add(Calendar.HOUR, -1)`
    #: 做“减 1 小时”（LargeScaleDataSyncService 的水位默认值），
    #: 因此替身把 HOUR 与 HOUR_OF_DAY 按同一方式处理（按小时加减），
    #: 不模拟 12 小时制的 AM/PM 语义（本工程不读日历字段值）。
    HOUR = 10
    HOUR_OF_DAY = 11
    MINUTE = 12
    SECOND = 13
    MILLISECOND = 14

    def __init__(self, time: Optional[datetime] = None) -> None:
        #: 内部时间（Java: 毫秒时间戳 + 时区）
        self._time: datetime = time if time is not None else datetime.now()

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def getInstance() -> "Calendar":
        """对应 `static Calendar getInstance()`：默认时区当前时间。"""
        return Calendar(datetime.now())

    # ------------------------------------------------------------------ 读写
    def setTime(self, time: datetime) -> None:
        """对应 `setTime(Date date)`。"""
        self._time = time

    def getTime(self) -> datetime:
        """对应 `getTime()`：返回 `datetime`（见模块注释第 3 条）。"""
        return self._time

    # ------------------------------------------------------------------ set
    def set(self, field: int, value: int) -> None:
        """对应 `set(int field, int value)`（只实现本工程用到的字段）。"""
        if field == Calendar.YEAR:
            self._time = self._time.replace(year=int(value))
        elif field == Calendar.MONTH:
            # 【Java→Python】Java 的 MONTH 是 0 基，这里 +1 转成 Python 的 1 基
            self._time = self._time.replace(month=int(value) + 1)
        elif field == Calendar.DAY_OF_MONTH:
            self._time = self._time.replace(day=int(value))
        elif field == Calendar.HOUR_OF_DAY or field == Calendar.HOUR:
            self._time = self._time.replace(hour=int(value))
        elif field == Calendar.MINUTE:
            self._time = self._time.replace(minute=int(value))
        elif field == Calendar.SECOND:
            self._time = self._time.replace(second=int(value))
        elif field == Calendar.MILLISECOND:
            self._time = self._time.replace(microsecond=int(value) * 1000)
        else:
            raise ValueError("Calendar 替身未实现字段: %r" % (field,))

    # ------------------------------------------------------------------ add
    def add(self, field: int, amount: int) -> None:
        """对应 `add(int field, int amount)`：原地增减并自动进位/借位。"""
        if field == Calendar.YEAR:
            # 【Java→Python】按 12 个月换算：闰日 2024-02-29 `add(YEAR, -1)`
            # 在 Java 里得到 2023-02-28（月末溢出向下取整），与 _add_months 一致。
            self._time = _add_months(self._time, int(amount) * 12)
        elif field == Calendar.DAY_OF_MONTH:
            self._time = _add_days(self._time, amount)
        elif field == Calendar.MONTH:
            self._time = _add_months(self._time, amount)
        elif field == Calendar.HOUR_OF_DAY or field == Calendar.HOUR:
            self._time = _add_seconds(self._time, amount * 3600)
        elif field == Calendar.MINUTE:
            self._time = _add_seconds(self._time, amount * 60)
        elif field == Calendar.SECOND:
            self._time = _add_seconds(self._time, amount)
        else:
            raise ValueError("Calendar 替身未实现字段: %r" % (field,))

    # ------------------------------------------------------------------ 比较
    def before(self, other: datetime) -> bool:
        """对应 `before(Object when)`。"""
        return self._time < other

    def after(self, other: datetime) -> bool:
        """对应 `after(Object when)`。"""
        return self._time > other

    def __repr__(self) -> str:
        return "Calendar(%s)" % self._time.strftime("%Y-%m-%d %H:%M:%S")


def _add_days(value: datetime, days: int) -> datetime:
    """加/减天数（Java 的 DAY_OF_MONTH 加法会进位到月/年）。"""
    from datetime import timedelta

    return value + timedelta(days=int(days))


def _add_seconds(value: datetime, seconds: int) -> datetime:
    from datetime import timedelta

    return value + timedelta(seconds=int(seconds))


def _add_months(value: datetime, months: int) -> datetime:
    """加/减月份：月末溢出时向下取整（与 Java `Calendar.add(MONTH)` 一致）。"""
    total = value.year * 12 + (value.month - 1) + int(months)
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(value.day, _calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
