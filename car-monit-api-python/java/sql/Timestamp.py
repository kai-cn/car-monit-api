# -*- coding: utf-8 -*-
"""java.sql.Timestamp

【无 Java 源文件：JDK 类替身】
业务代码用法（optimization 包）：
    query.setEntime(java.sql.Timestamp.valueOf(startTime));
    query.setExtime(java.sql.Timestamp.valueOf(endTime));

【Java→Python 关键差异】
1) Java 的 `java.sql.Timestamp` **继承** `java.util.Date`，只是多了纳秒精度；
   本工程把 `java.util.Date` 统一映射为内置 `datetime`（全工程约定），
   因此 `Timestamp.valueOf("yyyy-MM-dd HH:mm:ss")` 直接返回 `datetime`，
   **不**再定义 `datetime` 的子类 —— 实体字段 `ZdataTrailFitting.entime/extime`
   本身就是 `Optional[datetime]`，只有返回同类型才能赋值。
2) `valueOf(String)` 要求 "yyyy-MM-dd HH:mm:ss[.fffffffff]"；Python 侧复用
   `DateUtils.parseDate`（支持多种模式），解析失败返回 None（Java 抛
   IllegalArgumentException，此处宽松化并已在调用处体现）。
3) `Timestamp` 的 `compareTo` / `getTime()` 在 Python 里由 `datetime` 的比较与
   `.timestamp()` 表达，无需额外方法。
4) **无参/带毫秒的构造器**：UnifiedQueryService 里写 `new java.sql.Timestamp(millis)`；
   Python 用 `__new__` 直接返回 `datetime`（而不是 `Timestamp` 实例），
   保证能直接赋给 `Optional[datetime]` 字段。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from com.ruoyi.common.utils.DateUtils import DateUtils

__all__ = ["Timestamp"]


class Timestamp(object):
    """`java.sql.Timestamp` 的替身（构造/静态工厂的产物都是 `datetime`）。"""

    def __new__(cls, millis: Optional[int] = None) -> datetime:
        """对应 `new Timestamp(long time)` / `new Timestamp()`。

        【Java→Python】直接返回 `datetime`（见模块注释第 1、4 条）。
        无参构造在 Java 里取“当前时间”，这里保持一致。
        """
        if millis is None:
            return datetime.now()
        return datetime.fromtimestamp(millis / 1000.0)

    @staticmethod
    def valueOf(text: str) -> Optional[datetime]:
        """对应 `static Timestamp valueOf(String s)`。

        【Java→Python】返回 `datetime`（见模块注释第 1 条）。
        """
        if text is None:
            return None
        # 【Java→Python】`valueOf` 只接受 "yyyy-MM-dd HH:mm:ss[.fff]"；
        # DateUtils.parseDate 支持的格式是其超集，这里保持“能解析就返回”。
        return DateUtils.parseDate(text)

    @staticmethod
    def from_(millis: int) -> datetime:
        """兼容旧写法：`Timestamp.from_(millis)` 等价于 `Timestamp(millis)`。

        【Java→Python】`from` 是 Python 关键字，方法名加下划线（同 `from_` 约定）。
        """
        return Timestamp(millis)
