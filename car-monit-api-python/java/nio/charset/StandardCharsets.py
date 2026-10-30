# -*- coding: utf-8 -*-
"""java.nio.charset.StandardCharsets

【无 Java 源文件：JDK 类替身】（``java.nio.charset.StandardCharsets``）
业务代码用法（EsIndexManageService）：
    String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
    ... StreamUtils.copyToString(is, StandardCharsets.UTF_8);

【Java→Python 关键差异】
1) Java 的 ``StandardCharsets`` 是**常量类**，字段类型是 ``java.nio.charset.Charset``，
   ``Charset`` 在 IO API 里用于把字节解码成字符串。
2) Python 的 ``str.encode`` / ``bytes.decode`` 直接接受编码名字符串，
   因此替身把常量定义为**字符串**（``"utf-8"`` 等），调用处写法
   ``StandardCharsets.UTF_8`` 保持不变。
3) Java 的 ``Charset.toString()`` 返回规范名（``UTF-8``）；替身额外提供
   ``name()``（返回 ``UTF-8``）以便断言，字符串本身是小写（Python 编码名）。
"""

from __future__ import annotations

__all__ = ["StandardCharsets"]


class StandardCharsets(object):
    """``StandardCharsets`` 常量类的替身（值为 Python 编码名字符串）。"""

    #: 【Java→Python】Java 的 Charset 对象 → Python 编码名字符串
    UTF_8 = "utf-8"
    UTF_16 = "utf-16"
    UTF_16BE = "utf-16-be"
    UTF_16LE = "utf-16-le"
    US_ASCII = "ascii"
    ISO_8859_1 = "iso-8859-1"

    @staticmethod
    def nameOf(charset: str) -> str:
        """Java 的 ``Charset#name()``；替身用于把 "utf-8" 还原成 "UTF-8"。"""
        return str(charset).upper()
