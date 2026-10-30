# -*- coding: utf-8 -*-
"""java.time.format.DateTimeFormatter

【无 Java 源文件：JDK 类替身】（``java.time.format.DateTimeFormatter``）

【Java→Python】关键差异
1) ``DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")`` → 本替身保存 Java 格式串，
   内部复用 ``java.text.SimpleDateFormat._to_strftime`` 转成 strftime 串。
2) ``DateTimeFormatter`` 是**不可变且线程安全**的（与 SimpleDateFormat 相反），
   本替身只读字段，天然满足。
3) 只翻译本工程用到的 API：``ofPattern`` / ``format`` / ``parse``
   （其中 parse 在 Java 里属于 ``LocalDateTime.parse(text, formatter)`` 的重载）。
"""
from __future__ import annotations

from datetime import datetime

from java.text.SimpleDateFormat import _to_strftime

__all__ = ["DateTimeFormatter"]


class DateTimeFormatter:
    """``DateTimeFormatter`` 的最小等价实现。"""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self._py_pattern = _to_strftime(pattern)

    @staticmethod
    def ofPattern(pattern: str) -> "DateTimeFormatter":
        """对应 ``ofPattern(String pattern)``。"""
        return DateTimeFormatter(pattern)

    def format(self, temporal: datetime) -> str:
        """对应 ``format(TemporalAccessor)``。"""
        return temporal.strftime(self._py_pattern)

    def parse(self, text: str) -> datetime:
        """对应 ``LocalDateTime.parse(text, formatter)`` 中的解析动作。"""
        return datetime.strptime(text.strip(), self._py_pattern)
