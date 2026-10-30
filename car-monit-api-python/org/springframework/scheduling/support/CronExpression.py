# -*- coding: utf-8 -*-
"""org.springframework.scheduling.support.CronExpression

【无 Java 源文件：框架类替身】
Java 侧来自 spring-context 5.3：`org.springframework.scheduling.support.CronExpression`
（5.3 之前是已废弃的 `CronSequenceGenerator`）。本工程的三类 cron 都由它的
`next(Temporal)` 计算下一次执行时刻：

    @Scheduled(cron = "0 0/3 * * * ?")                              TrackTask
    @Scheduled(cron = "${consistency.reconcile.cron:0 30 2 * * ?}") GaussEsConsistencyService

【Java→Python 关键差异】
1) 六个字段完全相同（秒 分 时 日 月 周），也**只有六个**——Quartz 的七字段（带年）
   在这里是非法的，Spring 会抛 IllegalArgumentException。Python 侧同样拒绝。
2) Java 的 `parse` 对 null/空串/字段数不对抛 `IllegalArgumentException`；
   Python 没有受检异常体系，统一用 `ValueError`（`isValidExpression` 捕获它）。
3) 支持的语法子集（与 Spring 5.3 一致的部分）：
   - `*`  任意值；`?` 等价 `*`（只允许出现在「日」「周」字段，与 Spring 相同）
   - `n`  具体值；`a-b` 范围；`a,b,c` 列表；`a/b` 从 a 起每 b 一次；`*/b` 同上
   - 月份英文缩写 `JAN`~`DEC`；星期英文缩写 `SUN`~`SAT`（大小写不敏感）
   - 「日」字段的 `L`（当月最后一天）
   **不实现** Quartz 扩展：`W`（最近工作日）、`L-n`、`#`（第 n 个星期几）。
   遇到这些字符直接抛 ValueError —— 宁可启动失败，也不静默算错时间。
4) 星期编号：Spring 用 `getDayOfWeek().getValue() % 7`（周日=0，周一=1 … 周六=6）。
   Python 的 `date.isoweekday()` 是周一=1 … 周日=7，因此这里取 `% 7`；
   同时 `7` 也接受为周日（Spring 允许 0 和 7 都表示周日，解析时归一化为 0）。
5) 「日」与「周」的**与/或**语义按 Quartz 惯例（Spring 5.3 同样如此）：
   - 两者都受限 → **或**（任一天匹配即执行）
   - 只有一个受限 → 只看受限的那个
   本工程的 cron 里两者都是 `*`/`?`，所以该分支实际不会被触发，但语义必须正确，
   否则将来有人写 `0 0 0 1 * MON` 就会得到与 Java 不同的结果。
6) Java 的 `next` 接收 `Temporal`/`Instant`（带 ZoneId）；替身接收**本地朴素
   `datetime`**，等价于 JVM 默认时区下的 `LocalDateTime`（不处理夏令时跳变，
   与 Java 的 `CronTrigger` 用默认时区解析的行为一致）。
7) 搜索上限：Java 的 `next` 找不到匹配时返回 null（内部最多向前搜索 8 年）。
   Python 侧同样以 8 年为界，返回 None。
"""
from __future__ import annotations

import calendar
import datetime as _dt
from typing import Dict, FrozenSet, Iterable, Optional, Sequence, Set

__all__ = ["CronExpression", "CronField"]

#: JAN..DEC（Spring 的月份缩写，大小写不敏感）
_MONTH_NAMES: Dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: SUN..SAT（Spring/Quartz 的星期缩写，周日=0）
_DOW_NAMES: Dict[str, int] = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}


class CronField(object):
    """`CronField` 的替身：一个 cron 字段解析后的取值集合。"""

    __slots__ = ("values", "restricted", "lastDay", "text")

    def __init__(self, values: FrozenSet[int], restricted: bool,
                 text: str, last_day: bool = False) -> None:
        self.values = values          # 命中的取值集合
        self.restricted = restricted  # false = `*` / `?`（不限制）
        self.lastDay = last_day       # 「日」字段的 `L`
        self.text = text              # 原始文本，便于 toString / 报错

    def matches(self, value: int) -> bool:
        return value in self.values

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return "CronField(%r)" % self.text


def _value(token: str, low: int, high: int, field_name: str,
           names: Optional[Dict[str, int]] = None) -> int:
    """把单个 token（数字或英文缩写）转成 int，并做范围校验。"""
    text = token.strip()
    if not text:
        raise ValueError("cron 字段 %s 存在空项" % field_name)
    if names is not None:
        named = names.get(text.upper())
        if named is not None:
            return named
    try:
        number = int(text)
    except ValueError:
        raise ValueError("cron 字段 %s 含非法取值 %r" % (field_name, token))
    if number < low or number > high:
        raise ValueError("cron 字段 %s 的取值 %s 超出范围 [%s,%s]"
                         % (field_name, number, low, high))
    return number


def _parse_part(part: str, low: int, high: int, field_name: str,
                names: Optional[Dict[str, int]]) -> Set[int]:
    """解析 `a` / `a-b` / `a/b` / `a-b/s` / `*/s` 中的一段（列表已按逗号拆开）。"""
    for extension in ("W", "#", "L-"):
        # 【Java→Python】Quartz 扩展语法未实现：宁可报错，也不算出错误的时间点。
        if extension in part.upper():
            raise ValueError("cron 字段 %s 不支持 Quartz 扩展语法 %r" % (field_name, part))

    step = 1
    base = part
    if "/" in part:
        base, _, step_text = part.partition("/")
        try:
            step = int(step_text)
        except ValueError:
            raise ValueError("cron 字段 %s 的步长非法: %r" % (field_name, part))
        if step <= 0:
            raise ValueError("cron 字段 %s 的步长必须为正数: %r" % (field_name, part))

    if base in ("*", "?"):
        start, end = low, high
    elif "-" in base:
        left, _, right = base.partition("-")
        start = _value(left, low, high, field_name, names)
        end = _value(right, low, high, field_name, names)
        if start > end:
            raise ValueError("cron 字段 %s 的范围倒序: %r" % (field_name, part))
    else:
        start = _value(base, low, high, field_name, names)
        # `5` 只有单值；`5/10` 表示“从 5 起每 10”
        end = high if step != 1 else start

    return set(range(start, end + 1, step))


def _parse_field(raw: str, low: int, high: int, field_name: str,
                 names: Optional[Dict[str, int]] = None,
                 allow_last_day: bool = False) -> CronField:
    """解析一个完整的 cron 字段（`*`、`?`、列表、范围、步长、`L`）。"""
    text = (raw or "").strip()
    if not text:
        raise ValueError("cron 字段 %s 为空" % field_name)
    if text in ("*", "?"):
        return CronField(frozenset(range(low, high + 1)), False, text)
    if allow_last_day and text == "L":
        return CronField(frozenset(), True, text, last_day=True)
    if "." in text:
        # Spring 的秒字段按整数解析，不接受小数（`0.5` 会抛 IllegalArgumentException）
        raise ValueError("cron 字段 %s 不接受小数: %r" % (field_name, text))

    values: Set[int] = set()
    for part in text.split(","):
        values |= _parse_part(part, low, high, field_name, names)
    return CronField(frozenset(values), True, text)


class CronExpression(object):
    """Spring `CronExpression` 的替身（六字段：秒 分 时 日 月 周）。"""

    #: 与 Spring 一致：最多向前搜索 8 年，找不到即认为“永不触发”
    MAX_YEARS = 8

    __slots__ = ("pattern", "_second", "_minute", "_hour", "_dayOfMonth",
                 "_month", "_dayOfWeek")

    def __init__(self, fields: Sequence[str]) -> None:
        self.pattern = " ".join(fields)
        self._second = _parse_field(fields[0], 0, 59, "second")
        self._minute = _parse_field(fields[1], 0, 59, "minute")
        self._hour = _parse_field(fields[2], 0, 23, "hour")
        self._dayOfMonth = _parse_field(fields[3], 1, 31, "day-of-month",
                                        allow_last_day=True)
        self._month = _parse_field(fields[4], 1, 12, "month", names=_MONTH_NAMES)
        day_of_week = _parse_field(fields[5], 0, 7, "day-of-week", names=_DOW_NAMES)
        # 【Java→Python】Spring 允许 0 和 7 都表示周日，解析后统一归一化成 0
        if 7 in day_of_week.values:
            day_of_week = CronField(
                frozenset(0 if value == 7 else value for value in day_of_week.values),
                day_of_week.restricted, day_of_week.text)
        self._dayOfWeek = day_of_week

    # ---------------------------------------------------------------- 工厂
    @staticmethod
    def parse(expression: str) -> "CronExpression":
        """等价 `CronExpression.parse(String)`：字段数不是 6 就抛异常。"""
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("cron 表达式为空")
        fields = expression.split()
        if len(fields) != 6:
            raise ValueError("cron 表达式必须是 6 个字段（秒 分 时 日 月 周），实际 %s 个: %r"
                             % (len(fields), expression))
        return CronExpression(fields)

    @staticmethod
    def isValidExpression(expression: str) -> bool:
        """等价 `CronExpression.isValidExpression(String)`。"""
        try:
            CronExpression.parse(expression)
            return True
        except (ValueError, TypeError):
            return False

    # ---------------------------------------------------------------- 匹配
    def _dayMatches(self, day: _dt.date) -> bool:
        """「日」与「周」的匹配（两者都受限时取“或”，见文件头第 5 条）。"""
        dom_restricted = self._dayOfMonth.restricted
        dow_restricted = self._dayOfWeek.restricted
        if not dom_restricted and not dow_restricted:
            return True
        if dom_restricted:
            if self._dayOfMonth.lastDay:
                last_day = calendar.monthrange(day.year, day.month)[1]
                dom_match = day.day == last_day
            else:
                dom_match = self._dayOfMonth.matches(day.day)
        else:
            dom_match = True
        # isoweekday(): 周一=1 … 周日=7 —— 取模后与 Spring 的 周日=0 对齐
        dow_match = (self._dayOfWeek.matches(day.isoweekday() % 7)
                     if dow_restricted else True)
        if not dom_restricted:
            return dow_match
        if not dow_restricted:
            return dom_match
        return dom_match or dow_match

    # ---------------------------------------------------------------- 下一次
    def next_fire_time(self, after: Optional[_dt.datetime] = None) -> Optional[_dt.datetime]:
        """返回**严格晚于** `after` 的下一个匹配时刻；8 年内无匹配则返回 None。

        等价 `CronExpression.next(Temporal)`：Java 返回 `Temporal`，
        Python 直接返回 `datetime`（秒级精度，微秒归零）。
        """
        current = after if after is not None else _dt.datetime.now()
        # 与 Java 一致：从“下一秒”开始找（next 是严格大于）
        candidate = current.replace(microsecond=0) + _dt.timedelta(seconds=1)
        deadline = candidate + _dt.timedelta(days=366 * self.MAX_YEARS)

        while candidate < deadline:
            if not self._month.matches(candidate.month):
                # 跳到下个月 1 日 00:00:00
                year, month = candidate.year, candidate.month + 1
                if month > 12:
                    year, month = year + 1, 1
                candidate = _dt.datetime(year, month, 1)
                continue
            if not self._dayMatches(candidate.date()):
                # 跳到次日 00:00:00
                candidate = _dt.datetime.combine(
                    candidate.date() + _dt.timedelta(days=1), _dt.time(0, 0, 0))
                continue
            if not self._hour.matches(candidate.hour):
                candidate = (candidate + _dt.timedelta(hours=1)).replace(
                    minute=0, second=0)
                continue
            if not self._minute.matches(candidate.minute):
                candidate = (candidate + _dt.timedelta(minutes=1)).replace(second=0)
                continue
            if not self._second.matches(candidate.second):
                candidate += _dt.timedelta(seconds=1)
                continue
            return candidate
        return None

    def next(self, after: Optional[_dt.datetime] = None) -> Optional[_dt.datetime]:
        """`next_fire_time` 的别名（方法名与 Java 的 `next(Temporal)` 对齐）。"""
        return self.next_fire_time(after)

    # ---------------------------------------------------------------- 其他
    def toString(self) -> str:
        """等价 `toString()`：返回规范化后的表达式（字段间单空格）。"""
        return self.pattern

    def __str__(self) -> str:
        return self.pattern

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return "CronExpression(%r)" % self.pattern
