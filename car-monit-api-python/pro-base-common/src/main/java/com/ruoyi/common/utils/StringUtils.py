# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.StringUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/StringUtils.java
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Collection, Iterable, Optional, Sequence

from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.text.StrFormatter import StrFormatter

_NULLSTR = ""
SEPARATOR = "_"
ASTERISK = "*"


class StringUtils:
    """字符串工具类（Java 侧 extends org.apache.commons.lang3.StringUtils）。

    【Java→Python】总体差异：
    1) Java 继承 Apache commons-lang3 并**重载** isEmpty/isNotEmpty：Collection、Object[]、
       Map、String 四个版本 → Python 无重载，统一在 isEmpty() 内部按类型分派；
       判断顺序必须是“str → Mapping → Collection/Sequence”，否则 str 会被当成集合。
    2) Apache 的 isBlank/isNotEmpty/getUUID 等静态方法在 Python 中重写实现。
    3) `Character.isWhitespace(c)` 与 Python 的 str.isspace() 判定集合不同
       （如 U+00A0：Java 为 false，Python 为 true），此处按 Java 语义显式列出空白字符。
    4) Spring 的 AntPathMatcher（?、*、**）→ 本文件用正则模拟，语义一致。
    5) Apache 的 split(str, separatorChars) 把第二参数视为**字符集合**（不是正则），且丢弃空串。
    """

    # ------------------------------------------------------------ 基础判断
    @staticmethod
    def getUUID() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def nvl(value: Any, default_value: Any) -> Any:
        return value if value is not None else default_value

    @staticmethod
    def isEmpty(value: Any) -> bool:
        """对应 isEmpty(String) / isEmpty(Collection) / isEmpty(Map) / isEmpty(Object[])。"""
        if value is None:
            return True
        if isinstance(value, str):
            # Java: isNull(str) || "".equals(str.trim())
            return value.strip() == _NULLSTR
        if isinstance(value, dict):
            return len(value) == 0
        if isinstance(value, (list, tuple, set, frozenset, range)):
            return len(value) == 0
        # 其它对象（含 Java 数组的等价物）一律非空
        return False

    @staticmethod
    def isNotEmpty(value: Any) -> bool:
        return not StringUtils.isEmpty(value)

    @staticmethod
    def isNull(obj: Any) -> bool:
        return obj is None

    @staticmethod
    def isNotNull(obj: Any) -> bool:
        return obj is not None

    @staticmethod
    def isArray(object_: Any) -> bool:
        # 【Java→Python】Java 用 getClass().isArray() 判断原生数组；
        # Python 中对应 list/tuple/bytearray。
        return object_ is not None and isinstance(object_, (list, tuple, bytearray))

    @staticmethod
    def trim(text: Optional[str]) -> str:
        return "" if text is None else text.strip()

    @staticmethod
    def isBlank(text: Optional[str]) -> bool:
        return text is None or text.strip() == ""

    @staticmethod
    def isNotBlank(text: Optional[str]) -> bool:
        return not StringUtils.isBlank(text)

    # ------------------------------------------------------------ 截取/隐藏
    @staticmethod
    def hide(text: Any, start_include: int, end_exclude: int) -> str:
        """替换指定字符串的指定区间内字符为 "*"。"""
        if StringUtils.isEmpty(text):
            return _NULLSTR
        text = str(text)
        str_length = len(text)
        if start_include > str_length:
            return _NULLSTR
        if end_exclude > str_length:
            end_exclude = str_length
        if start_include > end_exclude:
            return _NULLSTR
        chars = list(text)
        for i in range(str_length):
            chars[i] = ASTERISK if start_include <= i < end_exclude else chars[i]
        return "".join(chars)

    @staticmethod
    def substring(text: Optional[str], start: int, end: Optional[int] = None) -> str:
        """对应 substring(String,int) 与 substring(String,int,int) 两个重载。"""
        if text is None:
            return _NULLSTR
        if end is None:
            if start < 0:
                start = len(text) + start
            if start < 0:
                start = 0
            if start > len(text):
                return _NULLSTR
            return text[start:]

        if end < 0:
            end = len(text) + end
        if start < 0:
            start = len(text) + start
        if end > len(text):
            end = len(text)
        if start > end:
            return _NULLSTR
        if start < 0:
            start = 0
        if end < 0:
            end = 0
        return text[start:end]

    @staticmethod
    def hasText(text: Optional[str]) -> bool:
        return text is not None and len(text) > 0 and StringUtils._containsText(text)

    @staticmethod
    def _containsText(text: str) -> bool:
        # Java Character.isWhitespace 的等价字符集合（不含 U+00A0，与 Python isspace() 不同）
        for ch in text:
            if ch not in " \t\n\u000B\f\r\u001C\u001D\u001E\u001F":
                return True
        return False

    @staticmethod
    def length(text: Optional[str]) -> int:
        return 0 if text is None else len(text)

    # ------------------------------------------------------------ 格式化
    @staticmethod
    def format(template: str, *params: Any) -> str:
        if len(params) == 0 or StringUtils.isEmpty(template):
            return template
        return StrFormatter.format(template, *params)

    @staticmethod
    def ishttp(link: Optional[str]) -> bool:
        return StringUtils.startsWithAny(link, Constants.HTTP, Constants.HTTPS)

    @staticmethod
    def startsWithAny(text: Optional[str], *prefixes: str) -> bool:
        if text is None:
            return False
        return any(text.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def containsIgnoreCase(text: Any, search: Any) -> bool:
        if text is None or search is None:
            return False
        return str(search).lower() in str(text).lower()

    @staticmethod
    def indexOfIgnoreCase(text: Optional[str], search: Optional[str]) -> int:
        if text is None or search is None:
            return -1
        return text.lower().find(search.lower())

    # ------------------------------------------------------------ 集合转换
    @staticmethod
    def str2Set(text: str, sep: str) -> set[str]:
        return set(StringUtils.str2List(text, sep, True, False))

    @staticmethod
    def str2List(text: str, sep: str, filter_blank: bool, trim: bool) -> list[str]:
        result: list[str] = []
        if StringUtils.isEmpty(text):
            return result
        if filter_blank and StringUtils.isBlank(text):
            return result
        # 【Java→Python】Java 的 str.split(sep) 中 sep 是正则且丢弃尾部空串 → _java_split
        for item in _java_split(sep, text):
            if filter_blank and StringUtils.isBlank(item):
                continue
            if trim:
                item = item.strip()
            result.append(item)
        return result

    @staticmethod
    def containsAny(collection: Collection[str], *array: str) -> bool:
        if StringUtils.isEmpty(collection) or len(array) == 0:
            return False
        return any(item in collection for item in array)

    @staticmethod
    def containsAnyIgnoreCase(text: Any, *search_texts: Any) -> bool:
        if StringUtils.isEmpty(text) or len(search_texts) == 0:
            return False
        return any(StringUtils.containsIgnoreCase(text, item) for item in search_texts)

    # ------------------------------------------------------------ 命名转换
    @staticmethod
    def toUnderScoreCase(text: Optional[str]) -> Optional[str]:
        """驼峰转下划线命名（算法逐行照搬）。"""
        if text is None:
            return None
        sb: list[str] = []
        pre_char_is_upper = True
        curre_char_is_upper = True
        nexte_char_is_upper = True
        for i in range(len(text)):
            c = text[i]
            pre_char_is_upper = text[i - 1].isupper() if i > 0 else False
            curre_char_is_upper = c.isupper()
            if i < len(text) - 1:
                nexte_char_is_upper = text[i + 1].isupper()
            if pre_char_is_upper and curre_char_is_upper and not nexte_char_is_upper:
                sb.append(SEPARATOR)
            elif i != 0 and not pre_char_is_upper and curre_char_is_upper:
                sb.append(SEPARATOR)
            sb.append(c.lower())
        return "".join(sb)

    @staticmethod
    def inStringIgnoreCase(text: Optional[str], *strs: Optional[str]) -> bool:
        if text is not None and strs is not None:
            for item in strs:
                if text.lower() == StringUtils.trim(item).lower():
                    return True
        return False

    @staticmethod
    def convertToCamelCase(name: Optional[str]) -> str:
        if name is None or len(name) == 0:
            return ""
        if "_" not in name:
            return name[0:1].upper() + name[1:]
        result: list[str] = []
        for camel in _java_split("_", name):
            if len(camel) == 0:
                continue
            result.append(camel[0:1].upper())
            result.append(camel[1:].lower())
        return "".join(result)

    @staticmethod
    def toCamelCase(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        if SEPARATOR not in text:
            return text
        text = text.lower()
        sb: list[str] = []
        upper_case = False
        for c in text:
            if c == SEPARATOR:
                upper_case = True
            elif upper_case:
                sb.append(c.upper())
                upper_case = False
            else:
                sb.append(c)
        return "".join(sb)

    # ------------------------------------------------------------ 路径匹配
    @staticmethod
    def matches(text: Optional[str], patterns: Optional[list[str]]) -> bool:
        if StringUtils.isEmpty(text) or StringUtils.isEmpty(patterns):
            return False
        return any(StringUtils.isMatch(pattern, text) for pattern in patterns)

    @staticmethod
    def isMatch(pattern: str, url: str) -> bool:
        """Spring AntPathMatcher.match 的等价实现。

        【Java→Python】Ant 语义：`?`=单个字符、`*`=一层路径内任意字符（不跨 /）、
        `**`=任意层路径。Python 的 fnmatch 中 `*` 会跨 `/`，语义不同，故用正则还原。
        """
        regex = _ant_to_regex(pattern)
        return re.fullmatch(regex, url) is not None

    @staticmethod
    def cast(obj: Any) -> Any:
        """Java 的强制类型转换在 Python 中是空操作（动态类型）。"""
        return obj

    @staticmethod
    def join(elements: Any, separator: Optional[str] = None) -> Optional[str]:
        """对应 commons-lang3 继承来的 ``join(Iterable/Object[], String)``。

        【Java→Python】Apache 的 join 对 null 元素按空串处理（不写 "null"），
        分隔符为 null 时用空串；这里保持一致。
        """
        if elements is None:
            return None
        sep = "" if separator is None else separator
        return sep.join("" if item is None else str(item) for item in elements)

    # ------------------------------------------------------------ 补齐/切分
    @staticmethod
    def padl(value: Any, size: int, pad_char: str = "0") -> str:
        """对应 padl(Number,int) 与 padl(String,int,char)。

        Number 版本等价于 padl(num.toString(), size, '0')。
        """
        text = Convert_like_to_string(value)
        if text is None:
            return pad_char * size
        length = len(text)
        if length <= size:
            return pad_char * (size - length) + text
        return text[length - size:length]

    @staticmethod
    def stringToList(content: Optional[str]) -> list[str]:
        if StringUtils.isNotEmpty(content):
            contents = _java_split(Constants.CHAR_COMMA, content)
            if len(contents) > 0:
                return list(contents)
        return []


def Convert_like_to_string(value: Any) -> Optional[str]:
    """padl(Number) 中的 num.toString()：None 保持 None，其余转字符串。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _java_split(pattern: str, text: str) -> list[str]:
    """Java String.split(pattern)（参数是正则，且丢弃尾部空串）。"""
    parts = re.split(pattern, text)
    end = len(parts)
    while end > 0 and parts[end - 1] == "":
        end -= 1
    return parts[:end]


def _ant_to_regex(pattern: str) -> str:
    """把 Ant 风格路径转换为 Python 正则。"""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


# Java 中的 split(String, String separatorChars) 是“按字符集合切分”，此处提供等价实现
def apache_split(text: Optional[str], separator_chars: Optional[str]) -> list[str]:
    if text is None:
        return []
    if separator_chars is None:
        return text.split()
    if separator_chars == "":
        return list(text)
    pattern = "[" + re.escape(separator_chars) + "]"
    parts = [item for item in re.split(pattern, text) if item != ""]
    return parts
