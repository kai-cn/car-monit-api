# -*- coding: utf-8 -*-
"""java.time.LocalDateTime

【无 Java 源文件：JDK 类替身】（``java.time.LocalDateTime``）

【Java→Python】关键差异
1) Java 的 ``LocalDateTime`` **没有时区**，与 Python 的 **naive datetime** 语义一致；
   因此本替身直接 **继承 datetime**，这样既能用 Java 风格方法，
   又能被 ``DateUtils.toDate()`` 等按 ``isinstance(x, datetime)`` 的判断接住。
2) Java 的 ``LocalDateTime`` 是**不可变**的；datetime 本身也不可变，
   所有 ``minusXxx/plusXxx`` 都返回**新对象**（与 Java 一致，不要当成原地修改）。
3) 只翻译本工程用到的 API：``now`` / ``parse`` / ``format`` / ``minusDays`` /
   ``plusDays`` / ``minusHours`` / ``plusHours`` / ``minusMinutes`` / ``plusMinutes`` /
   ``minusMonths`` / ``plusMonths`` / ``withDayOfMonth`` / ``withHour`` / ``withMinute`` /
   ``withSecond`` / ``isBefore`` / ``isAfter`` / ``isEqual`` / 常用 getter / ``toString``。
   其中 ``plusMonths/minusMonths`` 必须做**月末日 clamp**（Java: 1-31 加 1 个月 → 2-28/2-29），
   Python 的 ``timedelta`` 无“月”单位，只能按日历手工换算。
4) ``LocalDateTime.parse(text, formatter)`` 的解析交给
   ``java.time.format.DateTimeFormatter.parse``（strptime）；格式串不匹配抛 ValueError
   （Java: DateTimeParseException）。
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Optional, Union

__all__ = ["LocalDateTime"]


def _wrap(value: datetime) -> "LocalDateTime":
    """把 datetime 结果重新包装成 LocalDateTime（保持 Java 的返回类型）。"""
    return LocalDateTime(value.year, value.month, value.day,
                         value.hour, value.minute, value.second, value.microsecond)


def _as_datetime(value: Union["LocalDateTime", datetime]) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError("expected LocalDateTime/datetime, got " + type(value).__name__)


class LocalDateTime(datetime):
    """``LocalDateTime`` 的等价实现（继承 datetime，无时区）。"""

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def now() -> "LocalDateTime":
        """对应 ``LocalDateTime.now()``：系统默认时区的本地时间。"""
        return _wrap(datetime.now())

    @staticmethod
    def of(year: int, month: int, day: int, hour: int = 0, minute: int = 0,
           second: int = 0, nano_of_second: int = 0) -> "LocalDateTime":
        """对应 ``LocalDateTime.of(...)``（nanoOfSecond 按微秒截断）。"""
        return LocalDateTime(year, month, day, hour, minute, second,
                             nano_of_second // 1000)

    @staticmethod
    def parse(text: str, formatter: Optional[object] = None) -> "LocalDateTime":
        """对应 ``LocalDateTime.parse(CharSequence, DateTimeFormatter)``。"""
        if formatter is None:
            # Java: parse(text) 走 ISO_LOCAL_DATE_TIME；Python 的 fromisoformat 与之一致
            return _wrap(datetime.fromisoformat(text.strip()))
        return _wrap(formatter.parse(text))  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ 加减
    def minusDays(self, days: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) - timedelta(days=days))

    def plusDays(self, days: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) + timedelta(days=days))

    def minusHours(self, hours: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) - timedelta(hours=hours))

    def plusHours(self, hours: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) + timedelta(hours=hours))

    def minusMinutes(self, minutes: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) - timedelta(minutes=minutes))

    def plusMinutes(self, minutes: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) + timedelta(minutes=minutes))

    def minusSeconds(self, seconds: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) - timedelta(seconds=seconds))

    def plusSeconds(self, seconds: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self) + timedelta(seconds=seconds))

    def minusMonths(self, months: int) -> "LocalDateTime":
        """对应 ``minusMonths(n)``（= ``plusMonths(-n)``）。"""
        return self.plusMonths(-months)

    def plusMonths(self, months: int) -> "LocalDateTime":
        """对应 ``plusMonths(n)``。

        【Java→Python】Java 的规则：目标月份没有该日时取**当月最后一天**
        （如 2024-01-31 + 1 月 = 2024-02-29，2023-01-31 + 1 月 = 2023-02-28）。
        ``datetime.replace(month=...)`` 遇到 2 月 30/31 日会直接抛 ValueError，
        因此必须先用 ``calendar.monthrange`` 取出目标月天数再 clamp。
        """
        dt = _as_datetime(self)
        # 把 (year, month) 折算成“绝对月序”做加减，避免 12→1 的跨年判断
        total = dt.year * 12 + (dt.month - 1) + months
        year, month_index = divmod(total, 12)
        month = month_index + 1
        last_day = monthrange(year, month)[1]
        return _wrap(dt.replace(year=year, month=month,
                                day=min(dt.day, last_day)))

    # ------------------------------------------------------------- with 系列
    # 【Java→Python】Java 的 withXxx 返回新对象；datetime.replace 同样返回新对象，语义一致。
    def withDayOfMonth(self, day: int) -> "LocalDateTime":
        """对应 ``withDayOfMonth(int)``；日期越界时 Python 抛 ValueError（Java: DateTimeException）。"""
        return _wrap(_as_datetime(self).replace(day=day))

    def withHour(self, hour: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self).replace(hour=hour))

    def withMinute(self, minute: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self).replace(minute=minute))

    def withSecond(self, second: int) -> "LocalDateTime":
        return _wrap(_as_datetime(self).replace(second=second))

    # ------------------------------------------------------------------ 比较
    def isBefore(self, other: "LocalDateTime") -> bool:
        return _as_datetime(self) < _as_datetime(other)

    def isAfter(self, other: "LocalDateTime") -> bool:
        return _as_datetime(self) > _as_datetime(other)

    def isEqual(self, other: "LocalDateTime") -> bool:
        return _as_datetime(self) == _as_datetime(other)

    # ------------------------------------------------------------------ 输出
    def format(self, formatter: object) -> str:
        """对应 ``format(DateTimeFormatter)``。"""
        return formatter.format(self)  # type: ignore[attr-defined]

    def toString(self) -> str:
        """对应 ``toString()``：ISO-8601（``2025-11-01T08:30:00``）。"""
        return _as_datetime(self).isoformat()

    # ------------------------------------------------------------------ getter
    def getYear(self) -> int:
        return self.year

    def getMonthValue(self) -> int:
        return self.month

    def getDayOfMonth(self) -> int:
        return self.day

    def getHour(self) -> int:
        return self.hour

    def getMinute(self) -> int:
        return self.minute

    def getSecond(self) -> int:
        return self.second
