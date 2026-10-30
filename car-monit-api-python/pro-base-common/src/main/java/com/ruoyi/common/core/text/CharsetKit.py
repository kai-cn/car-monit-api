# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.text.CharsetKit

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/text/CharsetKit.java
"""
from __future__ import annotations

import locale
import sys
from typing import Optional

from com.ruoyi.common.utils.StringUtils import StringUtils


class CharsetKit:
    """字符集工具类。

    【Java→Python】
    1) java.nio.charset.Charset → Python 用“编码名字符串”（str.encode/decode 的 encoding 参数）。
       Charset.forName("GBK") 在 Java 中总是可用；Python 的 gbk 编解码器由标准库提供，同样可用。
    2) Charset.defaultCharset() → Python 没有全局默认字符集，这里用
       ``sys.getdefaultencoding()``（恒为 utf-8），并在 systemCharset() 中退化为
       locale.getpreferredencoding()，以贴近“系统字符集”的语义。
    3) `new String(source.getBytes(src), dest)` → ``source.encode(src).decode(dest)``。
    4) 常量 CHARSET_XXX 由 Charset 对象改为编码名字符串。
    """

    ISO_8859_1 = "ISO-8859-1"
    UTF_8 = "UTF-8"
    GBK = "GBK"

    CHARSET_ISO_8859_1 = "iso-8859-1"
    CHARSET_UTF_8 = "utf-8"
    CHARSET_GBK = "gbk"

    @staticmethod
    def charset(charset: Optional[str]) -> str:
        """转换为 Charset 对象（Python 中即编码名）。"""
        return "utf-8" if StringUtils.isEmpty(charset) else str(charset)

    @staticmethod
    def convert(source: str, src_charset: Optional[str], dest_charset: Optional[str]) -> str:
        """转换字符串的字符集编码。"""
        if src_charset is None:
            src_charset = CharsetKit.CHARSET_ISO_8859_1
        if dest_charset is None:
            dest_charset = CharsetKit.CHARSET_UTF_8
        if StringUtils.isEmpty(source) or src_charset.lower() == dest_charset.lower():
            return source
        return source.encode(src_charset).decode(dest_charset)

    @staticmethod
    def systemCharset() -> str:
        """系统字符集编码。

        【Java→Python】Java 的默认字符集由 -Dfile.encoding 决定；
        Python 3 的 str 恒为 Unicode，默认编码 sys.getdefaultencoding() 固定 "utf-8"，
        因此另提供 locale 偏好编码以表达“操作系统字符集”。
        """
        return locale.getpreferredencoding(False) or sys.getdefaultencoding()
