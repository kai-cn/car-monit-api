# -*- coding: utf-8 -*-
"""java.lang.String

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：`java.lang.String`。Python 的 str 已经覆盖了绝大多数方法
（length()→len 除外），因此本文件只补齐 **Java 特有且语义不同** 的几处：

    String.format("%04d%02d%02d", y, m, d)
    String.valueOf(obj)                 # null → "null"
    String.join(",", list)
    dataId.hashCode()                   # Java 字符串哈希算法（见 javaStringHashCode）

【Java→Python 关键差异】
1) Java 的 `String.format` 与 Python 的 `%` 运算符高度相似（%s/%d/%f/%02x），
   但 Java 的 `%n` 是平台换行符、`%,d` 是千分位；这里做最小适配（%n → \n）。
   `String.format` 对标 Java 的 **Formatter**，不是 `str.format`（`{}` 占位符）。
2) `String.valueOf(null)` 返回字符串 "null"（不是空串），这是 Java 里
   `"" + null` 得到 "null" 的根源；Python 的 str(None) 也返回 "None"，
   **两者不同**，所以这里显式返回 "null"。
3) Java 的 `String.hashCode()` 是固定算法 `s[0]*31^(n-1) + ... + s[n-1]`
   （32 位有符号 int 溢出）；Python 的 `hash(str)` 每个进程加盐随机，
   **绝不能**用来替代，否则消息 ID 每次运行都不同。故提供 javaStringHashCode。
"""
from __future__ import annotations

from typing import Any, Iterable

__all__ = ["String", "javaStringHashCode"]


def javaStringHashCode(text: str) -> int:
    """还原 Java `String.hashCode()`：h = 31*h + c，按 32 位有符号整数溢出。"""
    if text is None:
        return 0
    result = 0
    for char in text:
        result = (31 * result + ord(char)) & 0xFFFFFFFF
    # 转成 32 位有符号 int（Java 的 int 范围）
    if result >= 0x80000000:
        result -= 0x100000000
    return result


class String(object):
    """`java.lang.String` 的静态方法子集。"""

    @staticmethod
    def format(format_string: str, *args: Any) -> str:
        """等价 `String.format(fmt, args...)`（% 风格，不是 str.format）。"""
        # Java 的 %n 是“平台换行符”；Python 的 % 不支持
        normalized = format_string.replace("%n", "\n")
        return normalized % args

    @staticmethod
    def valueOf(value: Any) -> str:
        """等价 `String.valueOf(Object)`：null → "null"。"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def join(delimiter: str, elements: Iterable[str]) -> str:
        """等价 `String.join(delimiter, elements)`。"""
        return delimiter.join(str(element) for element in elements)
