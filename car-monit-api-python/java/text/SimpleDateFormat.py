# -*- coding: utf-8 -*-
"""java.text.SimpleDateFormat

【无 Java 源文件：JDK 类替身】（``java.text.SimpleDateFormat``）

【Java→Python】关键差异
1) 格式串语法不同：Java 用 ``yyyy-MM-dd HH:mm:ss``，Python 用 ``%Y-%m-%d %H:%M:%S``；
   本替身内置 ``_to_strftime`` 做转换（与 DateUtils 内的同名逻辑一致、互相独立，
   避免 JDK 替身反向依赖业务工具类）。
2) ``format(Date)`` → ``datetime.strftime``；``parse(String)`` → ``datetime.strptime``，
   Java 的 ``ParseException`` → Python 的 ``ValueError``（均为受检/运行时异常）。
3) Java 的 SimpleDateFormat **非线程安全**（内部 Calendar 被共享修改）；
   Python 的 strftime/strptime 是无状态的，本替身天然线程安全 —— 这是行为差异，
   但不影响“同一格式串、同一时刻得到同一字符串”的业务结果。
4) 只翻译本工程用到的 API：构造器、format、parse。

模式字母对照（本项目实际出现的组合）：
    yyyy→%Y  yy→%y  MMMM→%B  MMM→%b  MM→%m  dd→%d
    HH→%H   hh→%I  mm→%M   ss→%S  SSS→%f
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

__all__ = ["SimpleDateFormat"]


def _to_strftime(pattern: str) -> str:
    """Java SimpleDateFormat 格式串 → Python strftime 格式串。"""
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


class SimpleDateFormat:
    """``new SimpleDateFormat(pattern)`` 的最小等价实现。"""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self._py_pattern = _to_strftime(pattern)

    def format(self, date: Optional[datetime]) -> str:
        """对应 ``format(Date date)``。"""
        if date is None:
            raise TypeError("SimpleDateFormat.format(None)")
        return date.strftime(self._py_pattern)

    def parse(self, text: str) -> datetime:
        """对应 ``parse(String source)``；失败抛 ValueError（Java: ParseException）。"""
        return datetime.strptime(text.strip(), self._py_pattern)

    def toPattern(self) -> str:
        """对应 ``toPattern()``：返回原始 Java 格式串。"""
        return self.pattern
