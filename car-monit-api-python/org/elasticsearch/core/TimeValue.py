# -*- coding: utf-8 -*-
"""org.elasticsearch.core.TimeValue

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.core.TimeValue``。
本工程用法（EsQueryService.queryFromEs）：
    sourceBuilder.timeout(new org.elasticsearch.core.TimeValue(
            30, java.util.concurrent.TimeUnit.SECONDS));

【Java→Python】关键差异
1) Java 的构造器是 ``TimeValue(long time, TimeUnit unit)``（``TimeUnit`` 是
   ``java.util.concurrent.TimeUnit`` 枚举）；Python 侧沿用本工程既有的
   ``java.util.concurrent.TimeUnit`` 替身（枚举常量如 ``TimeUnit.SECONDS``）。
2) Java 的 ``TimeValue`` 会把不同单位**归一化**成毫秒/纳秒存储；
   ``getSeconds()`` / ``getMillis()`` 是换算后的整数（向下取整）。
   替身按同一规则换算，保证 ``getSeconds()`` 的结果与 Java 一致。
3) ``TimeValue.timeValueSeconds(long)`` / ``timeValueMillis(long)`` 等静态工厂：
   LargeScaleDataSyncService 用它设置 BulkProcessor 的 flushInterval 与退避初始值，
   替身补齐三个常用工厂（seconds/millis/minutes），均为 `new TimeValue(n, 对应单位)`。
"""

from __future__ import annotations

from java.util.concurrent.TimeUnit import TimeUnit

__all__ = ["TimeValue"]

#: 每种 TimeUnit 换算成毫秒的系数（与 Java TimeUnit.toMillis 一致）
# 【注意】本工程 TimeUnit 替身只定义到 NANOSECONDS/MILLISECONDS/... 六种单位，
# 缺 MICROSECONDS，所以这里也不列它（工程只用 SECONDS）。
_MILLIS_PER_UNIT = {
    TimeUnit.NANOSECONDS: 1.0 / 1000000,
    TimeUnit.MILLISECONDS: 1,
    TimeUnit.SECONDS: 1000,
    TimeUnit.MINUTES: 60 * 1000,
    TimeUnit.HOURS: 60 * 60 * 1000,
    TimeUnit.DAYS: 24 * 60 * 60 * 1000,
}


class TimeValue(object):
    """``TimeValue`` 的替身（time + unit，并提供换算 getter）。"""

    def __init__(self, time: float, unit: TimeUnit) -> None:
        self._time = time
        self._unit = unit

    # ------------------------------------------------------------------ getter
    def getTime(self) -> float:
        return self._time

    def getUnit(self) -> TimeUnit:
        return self._unit

    def getMillis(self) -> int:
        # Java 的 getMillis() 返回 long（截断小数）
        return int(self._time * _MILLIS_PER_UNIT.get(self._unit, 1))

    def getSeconds(self) -> int:
        # Java 的 getSeconds() 由毫秒再整除 1000（向下取整）
        return int(self.getMillis() / 1000)

    def millis(self) -> int:
        """``TimeValue.millis()`` 是 getMillis 的别名。"""
        return self.getMillis()

    # ------------------------------------------------------------------ 静态工厂
    @staticmethod
    def timeValueSeconds(seconds: int) -> "TimeValue":
        """对应 `static TimeValue timeValueSeconds(long seconds)`。"""
        return TimeValue(seconds, TimeUnit.SECONDS)

    @staticmethod
    def timeValueMillis(millis: int) -> "TimeValue":
        """对应 `static TimeValue timeValueMillis(long millis)`。"""
        return TimeValue(millis, TimeUnit.MILLISECONDS)

    @staticmethod
    def timeValueMinutes(minutes: int) -> "TimeValue":
        """对应 `static TimeValue timeValueMinutes(long minutes)`。"""
        return TimeValue(minutes, TimeUnit.MINUTES)

    def __repr__(self) -> str:
        return "TimeValue(%s, %s)" % (self._time, self._unit)
