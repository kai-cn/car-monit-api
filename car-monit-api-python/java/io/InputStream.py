# -*- coding: utf-8 -*-
"""java.io.InputStream

【无 Java 源文件：JDK 类替身】（``java.io.InputStream``）
业务代码用法（EsIndexManageService.buildSettingsAndMapping）：
    try (InputStream is = resource.getInputStream()) {
        String mapping = StreamUtils.copyToString(is, StandardCharsets.UTF_8);
        ...
    }

【Java→Python 关键差异】
1) Java 的 ``InputStream`` 是**抽象字节流**，必须 `close()`（try-with-resources
   自动关闭）；Python 的等价物是 ``io.BytesIO`` 或任何二进制文件对象，
   用 `with` 语句自动关闭。替身包装 ``io.BytesIO`` 并实现上下文管理器协议，
   因此 ``with resource.getInputStream() as is:`` 与原代码写法一致。
2) Java 的 ``read()` 返回 0-255 的 int，读完返回 **-1**；Python 的
   ``BytesIO.read()`` 返回 bytes，读完返回 **b""**。替身保留 Java 语义
   （``read()`` 返回 int，-1 表示结束），并提供 ``readAll()`` 返回全部字节。
3) Java 的 ``read(byte[] b)`` 把数据填进调用方数组并返回读取长度；
   替身在 Python 里无意义（bytes 不可变），不实现。
"""

from __future__ import annotations

import io
from typing import Optional

__all__ = ["InputStream"]


class InputStream(object):
    """``InputStream`` 的替身（包装 ``io.BytesIO``）。"""

    def __init__(self, data: bytes = b"") -> None:
        self._buffer = io.BytesIO(data)
        self._closed = False

    # ------------------------------------------------------------------ 读取
    def read(self) -> int:
        """对应 ``int read()``：返回 0-255，流结束返回 -1。"""
        byte = self._buffer.read(1)
        return -1 if not byte else byte[0]

    def readAll(self) -> bytes:
        """Java 无此方法；替身一次取出剩余全部字节（供 StreamUtils 使用）。"""
        return self._buffer.read()

    def available(self) -> int:
        """对应 ``available()``：可读取的字节数估计值。"""
        current = self._buffer.tell()
        self._buffer.seek(0, io.SEEK_END)
        end = self._buffer.tell()
        self._buffer.seek(current)
        return end - current

    # ------------------------------------------------------------------ 生命周期
    def close(self) -> None:
        """对应 ``close()``；重复关闭无副作用（与 Java 一致）。"""
        self._closed = True
        self._buffer.close()

    def __enter__(self) -> "InputStream":
        # 【Java→Python】try-with-resources → `with ... as ...:`
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> Optional[bool]:
        self.close()
        return None

    def __repr__(self) -> str:
        return "InputStream(closed=%s)" % self._closed
