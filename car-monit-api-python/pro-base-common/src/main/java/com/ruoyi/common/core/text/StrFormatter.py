# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.text.StrFormatter

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/text/StrFormatter.java
"""
from __future__ import annotations

from typing import Any


class StrFormatter:
    """字符串格式化（把 {} 按顺序替换为参数）。

    【Java→Python】逐字符扫描的算法完全照搬（包含 \\ 转义语义），差异点：
    1) StringBuilder → list[str] + "".join（Python 的 str 不可变，无法原地 append）。
    2) Java 的 `sbuf.append(strPattern, start, end)` 是 CharSequence 的区间追加 →
       Python 用 strPattern[start:end]。
    3) `argIndex--` → `arg_index -= 1`（Python 的 for 循环变量可手动调整，
       但下一次迭代会被 range 覆盖，因此这里的写法与 Java 完全一致）。
    4) Convert.utf8Str(Object) → 本文件内的 _utf8_str 轻量实现，避免与 Convert 循环依赖。
    5) StringUtils.isEmpty(strPattern) → 本文件内的 _is_empty 轻量实现。
       原因：Java 的 ``StringUtils`` 依赖 ``StrFormatter``（格式化），
       若 Python 再反向 import StringUtils，会形成循环导入（Python 无 Java 的类加载顺序宽容度）。
    """

    EMPTY_JSON = "{}"
    C_BACKSLASH = "\\"
    C_DELIM_START = "{"
    C_DELIM_END = "}"

    @staticmethod
    def format(str_pattern: str, *arg_array: Any) -> str:
        if _is_empty(str_pattern) or len(arg_array) == 0:
            return str_pattern

        str_pattern_length = len(str_pattern)
        sbuf: list[str] = []
        handled_position = 0
        arg_index = 0
        while arg_index < len(arg_array):
            delim_index = str_pattern.find(StrFormatter.EMPTY_JSON, handled_position)
            if delim_index == -1:
                if handled_position == 0:
                    return str_pattern
                # 字符串模板剩余部分不再包含占位符，加入剩余部分后返回结果
                sbuf.append(str_pattern[handled_position:str_pattern_length])
                return "".join(sbuf)

            if delim_index > 0 and str_pattern[delim_index - 1] == StrFormatter.C_BACKSLASH:
                if delim_index > 1 and str_pattern[delim_index - 2] == StrFormatter.C_BACKSLASH:
                    # 转义符之前还有一个转义符，占位符依旧有效
                    sbuf.append(str_pattern[handled_position:delim_index - 1])
                    sbuf.append(_utf8_str(arg_array[arg_index]))
                    handled_position = delim_index + 2
                else:
                    # 占位符被转义
                    arg_index -= 1
                    sbuf.append(str_pattern[handled_position:delim_index - 1])
                    sbuf.append(StrFormatter.C_DELIM_START)
                    handled_position = delim_index + 1
            else:
                # 正常占位符
                sbuf.append(str_pattern[handled_position:delim_index])
                sbuf.append(_utf8_str(arg_array[arg_index]))
                handled_position = delim_index + 2
            arg_index += 1

        # 加入最后一个占位符后所有的字符
        sbuf.append(str_pattern[handled_position:len(str_pattern)])
        return "".join(sbuf)


def _is_empty(value: Any) -> bool:
    """StringUtils.isEmpty(str) 的轻量等价实现（仅处理字符串分支）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "null"
    return False


def _utf8_str(value: Any) -> str:
    """Convert.utf8Str(Object) 的等价实现：null → "null"，其余 String.valueOf。"""
    if value is None:
        return "null"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
