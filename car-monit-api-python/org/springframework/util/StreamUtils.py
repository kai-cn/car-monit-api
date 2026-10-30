# -*- coding: utf-8 -*-
"""org.springframework.util.StreamUtils

【无 Java 源文件：框架类替身】
Java 侧来自 spring-core 的 ``org.springframework.util.StreamUtils``。
本工程用法（EsIndexManageService.buildSettingsAndMapping）：
    String mapping = StreamUtils.copyToString(is, StandardCharsets.UTF_8);

【Java→Python 关键差异】
1) Java 的 ``copyToString(InputStream, Charset)`` 内部用 ``StreamUtils.copyToByteArray``
   把整个流读进内存，再用指定字符集构造 String。
2) Python 替身调用 ``InputStream.readAll()`` 取字节，再 ``bytes.decode(charset)``。
3) Java 还有 ``copy(InputStream, OutputStream)`` / ``copyToByteArray`` 等，
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any

__all__ = ["StreamUtils"]


class StreamUtils(object):
    """``StreamUtils`` 静态工具类的替身。"""

    #: Java 的 ``StreamUtils.BUFFER_SIZE``（默认 8192）
    BUFFER_SIZE = 8192

    @staticmethod
    def copyToString(input_stream: Any, charset: str = "utf-8") -> str:
        """对应 ``copyToString(InputStream in, Charset charset)``。"""
        read_all = getattr(input_stream, "readAll", None)
        if callable(read_all):
            data = read_all()
        else:
            # 兼容任何“类文件对象”：直接 read()
            data = input_stream.read()
        if isinstance(data, str):
            return data
        return data.decode(charset)

    @staticmethod
    def copyToByteArray(input_stream: Any) -> bytes:
        """对应 ``copyToByteArray(InputStream in)``。"""
        read_all = getattr(input_stream, "readAll", None)
        if callable(read_all):
            return read_all()
        data = input_stream.read()
        return data.encode() if isinstance(data, str) else data
