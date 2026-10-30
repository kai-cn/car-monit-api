# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.DateUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/DateUtils.java

【Java→Python】整体说明（本文件差异最集中）
1) Java 有两套时间类型：``java.util.Date``（毫秒时间戳）与 ``java.time.*``
   （LocalDateTime/LocalDate）。Python 统一用 ``datetime.datetime`` / ``datetime.date``，
   因此 ``toDate(LocalDateTime)`` 与 ``toDate(LocalDate)`` 两个重载合并为一个，
   按 isinstance 分派；``Date`` 与 ``datetime`` 一一对应。
2) ``SimpleDateFormat(pattern).format(date)`` → ``date.strftime(pattern)``，
   但格式串语法不同：``yyyy``→``%Y``、``MM``→``%m``、``dd``→``%d``、``HH``→``%H``、
   ``mm``→``%M``、``ss``→``%S``、``SSS``→``%f``（此处用 ``_to_strftime`` 转换，
   业务调用点仍按 Java 的 ``"yyyy-MM-dd HH:mm:ss"`` 传参，保持可读一致）。
3) ``parseDate(Object)`` 依赖 commons-lang3 的 ``DateUtils.parseDate(str, patterns)``：
   它会**按顺序尝试所有 pattern**，全部失败抛 ParseException。Python 用
   ``datetime.strptime`` 逐个尝试，全部失败返回 None（对齐 Java 的 catch → return null）。
   注意：Apache 的解析是 **lenient（宽松）** 的（如 "2018-13-40" 会进位），
   ``strptime`` 是严格解析，越界日期会直接失败 —— 这是行为差异，已按“失败返回 null”统一。
4) ``Date.getTime()`` → Python 用 ``datetime.timestamp() * 1000`` 得到毫秒；
   ``new Date(long)`` → ``datetime.fromtimestamp(ms / 1000)``。
5) ``ManagementFactory.getRuntimeMXBean().getStartTime()``（JVM 启动时间）
   → Python 无等价 API，这里用**本模块首次被 import 的时间**近似（进程内最接近的锚点）。
6) ``java.sql.Timestamp`` → ``datetime``（Python 的 datetime 自带微秒，Java 的 Timestamp
   自带纳秒），``getTimestamp()`` 按 Java 的 "yyyy-MM-dd HH:mm:ss.SSS" 精度截断到毫秒。
7) ``DateUtils extends org.apache.commons.lang3.time.DateUtils`` 继承来的
   addMinutes/addHours（以及本项目用到的 addDays/addYears 等）用 ``timedelta`` 实现。
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

# JVM 启动时间的替身：模块被首次 import 的时刻（见文件头说明 5）
_SERVER_START_TIME = time.time()


def _to_strftime(pattern: str) -> str:
    """把 Java 的 SimpleDateFormat 格式串转成 Python strftime 格式串。"""
    # 顺序敏感：先长后短，避免 "yyyy" 被 "yy" 提前替换
    replacements = [
        ("yyyy", "%Y"),
        ("yy", "%y"),
        ("MMMM", "%B"),
        ("MMM", "%b"),
        ("MM", "%m"),
        ("dd", "%d"),
        ("HH", "%H"),
        ("hh", "%I"),
        ("mm", "%M"),
        ("ss", "%S"),
        ("SSS", "%f"),
    ]
    result = pattern
    for java_token, py_token in replacements:
        result = result.replace(java_token, py_token)
    return result


def _to_millis(value: datetime) -> int:
    """对应 ``Date.getTime()``：返回 1970 起的毫秒数。"""
    return int(value.timestamp() * 1000)


def _from_millis(millis: int) -> datetime:
    """对应 ``new Date(long time)``。"""
    return datetime.fromtimestamp(millis / 1000.0)


class DateUtils:
    YYYY = "yyyy"

    YYYY_MM = "yyyy-MM"

    YYYY_MM_DD = "yyyy-MM-dd"

    YYYYMMDDHHMMSS = "yyyyMMddHHmmss"

    YYYY_MM_DD_HH_MM_SS = "yyyy-MM-dd HH:mm:ss"

    # 【Java→Python】Java 数组 → Python list，内容与顺序完全一致
    parsePatterns = [
        "yyyy-MM-dd", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm", "yyyy-MM",
        "yyyy/MM/dd", "yyyy/MM/dd HH:mm:ss", "yyyy/MM/dd HH:mm", "yyyy/MM",
        "yyyy.MM.dd", "yyyy.MM.dd HH:mm:ss", "yyyy.MM.dd HH:mm", "yyyy.MM",
    ]

    @staticmethod
    def getNowDate() -> datetime:
        """获取当前 Date 型日期（对应 ``new Date()``）。"""
        return datetime.now()

    @staticmethod
    def getDate() -> str:
        """获取当前日期，默认格式为 yyyy-MM-dd。"""
        return DateUtils.dateTimeNow(DateUtils.YYYY_MM_DD)

    @staticmethod
    def getTime() -> str:
        return DateUtils.dateTimeNow(DateUtils.YYYY_MM_DD_HH_MM_SS)

    @staticmethod
    def dateTimeNow(date_format: Optional[str] = None) -> str:
        """对应 ``dateTimeNow()`` 与 ``dateTimeNow(String format)`` 两个重载。"""
        if date_format is None:
            date_format = DateUtils.YYYYMMDDHHMMSS
        return DateUtils.parseDateToStr(date_format, datetime.now())

    @staticmethod
    def dateTime(*args: Any) -> Any:
        """三个 Java 重载合并：

        - ``dateTime(Date)``           → 传 1 个 datetime，返回 "yyyy-MM-dd" 字符串
        - ``dateTime()``               → 无参，返回 "yyyyMMdd" 字符串
        - ``dateTime(String,String)``  → 传 (format, ts)，把字符串按格式解析成 datetime

        【Java→Python】Java 靠参数类型选择重载；Python 用参数个数 + 类型分派。
        """
        if len(args) == 0:
            # dateTime() —— 日期路径，即 20180808
            return DateUtils._now_str("yyyyMMdd")
        if len(args) == 1:
            # dateTime(Date)
            value = args[0]
            return DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD, value)
        if len(args) == 2:
            # dateTime(String format, String ts)
            date_format, ts = args[0], args[1]
            try:
                return datetime.strptime(ts, _to_strftime(date_format))
            except ValueError as e:
                # Java: catch (ParseException e) { throw new RuntimeException(e); }
                raise RuntimeError(e) from e
        raise TypeError("dateTime() takes 0, 1 or 2 arguments")

    @staticmethod
    def parseDateToStr(date_format: str, value: datetime) -> str:
        """格式化：``new SimpleDateFormat(format).format(date)``。"""
        return value.strftime(_to_strftime(date_format))

    @staticmethod
    def datePath() -> str:
        """日期路径，即年/月/日，如 2018/08/08。"""
        return DateUtils._now_str("yyyy/MM/dd")

    @staticmethod
    def _now_str(pattern: str) -> str:
        # 对应 DateFormatUtils.format(now, pattern)
        return datetime.now().strftime(_to_strftime(pattern))

    @staticmethod
    def parseDate(value: Any) -> Optional[datetime]:
        """日期型字符串转化为日期（按 parsePatterns 顺序尝试，全部失败返回 null）。"""
        if value is None:
            return None
        text = str(value)
        for pattern in DateUtils.parsePatterns:
            try:
                return datetime.strptime(text, _to_strftime(pattern))
            except ValueError:
                continue
        # Java: catch (ParseException e) { return null; }
        return None

    @staticmethod
    def getServerStartDate() -> datetime:
        """获取服务器启动时间（JVM 启动时间 → 模块导入时间）。"""
        return _from_millis(int(_SERVER_START_TIME * 1000))

    @staticmethod
    def differentDaysByMillisecond(date1: datetime, date2: datetime) -> int:
        """计算相差天数。

        【Java→Python】Java 是 ``Math.abs((int)((t2 - t1) / 86400000))``：
        先转 int（向零截断）再取绝对值。Python 的 ``int()`` 同样是向零截断，
        因此顺序保持一致（先 int 再 abs）。
        """
        return abs(int((_to_millis(date2) - _to_millis(date1)) / (1000 * 3600 * 24)))

    @staticmethod
    def timeDistance(endDate: datetime, startTime: datetime) -> str:
        """计算时间差（天/小时/分钟）。

        【Java→Python】Java 的 ``/`` 对 long 是整数除法（向零截断），Python 的 ``//``
        对负数向下取整，故统一用 ``int(a / b)`` 保持“向零截断”语义。
        """
        nd = 1000 * 24 * 60 * 60
        nh = 1000 * 60 * 60
        nm = 1000 * 60
        # long ns = 1000;
        # 获得两个时间的毫秒时间差异
        diff = _to_millis(endDate) - _to_millis(startTime)
        # 计算差多少天
        day = int(diff / nd)
        # 计算差多少小时
        hour = int((diff % nd) / nh)
        # 计算差多少分钟
        minute = int((diff % nd % nh) / nm)
        return f"{day}天{hour}小时{minute}分钟"

    @staticmethod
    def toDate(temporal_accessor: Any) -> datetime:
        """``LocalDateTime`` / ``LocalDate`` → ``Date``（两个重载合并）。

        【Java→Python】Java 用系统时区把 LocalDateTime 转 Instant；
        Python 的 naive datetime 本身即“本地时间”，直接使用；
        若传入 date（无时分秒），补齐 00:00:00（对应 LocalTime.of(0,0,0)）。
        """
        if isinstance(temporal_accessor, datetime):
            return temporal_accessor
        if isinstance(temporal_accessor, date):
            return datetime(temporal_accessor.year, temporal_accessor.month,
                            temporal_accessor.day, 0, 0, 0)
        raise TypeError("toDate() expects datetime or date")

    @staticmethod
    def getTimestamp() -> datetime:
        """获取当前时间（截断到毫秒，对应 java.sql.Timestamp 的 .SSS 精度）。"""
        now = datetime.now()
        return now.replace(microsecond=(now.microsecond // 1000) * 1000)

    @staticmethod
    def getTimestampNew() -> datetime:
        """与 getTimestamp() 实现完全相同（Java 源码即重复实现，原样保留）。"""
        now = datetime.now()
        return now.replace(microsecond=(now.microsecond // 1000) * 1000)

    @staticmethod
    def formatDate(value: datetime) -> str:
        return DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD, value)

    @staticmethod
    def formatHour(value: datetime) -> str:
        return DateUtils.parseDateToStr("yyyy-MM-dd HH:00:00", value)

    @staticmethod
    def addMinutes(value: datetime, minutes: int) -> datetime:
        """继承自 commons-lang3 ``DateUtils.addMinutes``。"""
        return value + timedelta(minutes=minutes)

    @staticmethod
    def addHours(value: datetime, hours: int) -> datetime:
        """继承自 commons-lang3 ``DateUtils.addHours``。"""
        return value + timedelta(hours=hours)

    # ---------------- 以下为 commons-lang3 DateUtils 中本项目可能用到的同族方法 ----------------
    @staticmethod
    def addDays(value: datetime, days: int) -> datetime:
        return value + timedelta(days=days)

    @staticmethod
    def addSeconds(value: datetime, seconds: int) -> datetime:
        return value + timedelta(seconds=seconds)

    @staticmethod
    def addMilliseconds(value: datetime, milliseconds: int) -> datetime:
        """等价 `Calendar.add(Calendar.MILLISECOND, n)`。

        【Java→Python】commons-lang3 的 DateUtils 没有 addMilliseconds，
        该方法是为转写 `Calendar#add(Calendar.MILLISECOND, n)` 补充的。
        """
        return value + timedelta(milliseconds=milliseconds)

    @staticmethod
    def addYears(value: datetime, years: int) -> datetime:
        """对应 commons-lang3 的 addYears（按日历年增减，2/29 会落到 2/28）。"""
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(year=value.year + years, day=28)
