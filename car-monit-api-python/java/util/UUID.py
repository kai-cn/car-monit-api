# -*- coding: utf-8 -*-
"""java.util.UUID

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：`java.util.UUID`。业务代码用到：
    UUID.randomUUID().toString().replace("-", "")
    UUID.randomUUID().toString().substring(0, 8)

【Java→Python 关键差异】
1) Python 的 `uuid.uuid4()` 返回 UUID 对象，`str()` 得到**带横线**的小写形式，
   与 Java 的 `UUID.toString()` 完全一致（8-4-4-4-12）。
2) Java 的 UUID 是 128 位整数类型，有 `getMostSignificantBits()` 等方法；
   本替身只实现本工程用到的 `toString()`/`toString()` 链式操作。
3) `equals`/`hashCode` 在 Python 里由 UUID 对象自身的 __eq__/__hash__ 提供。
"""
from __future__ import annotations

import uuid as _uuid

__all__ = ["UUID"]


class _JavaUUID(object):
    """`UUID.toString()` 的 Java 风格包装（Python 侧不直接暴露 uuid.UUID）。"""

    def __init__(self, value: _uuid.UUID) -> None:
        self._value = value

    def toString(self) -> str:
        return str(self._value)

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _JavaUUID):
            return self._value == other._value
        return False

    def __hash__(self) -> int:
        return hash(self._value)


class UUID(object):
    """`java.util.UUID` 的静态工厂子集。"""

    @staticmethod
    def randomUUID() -> _JavaUUID:
        return _JavaUUID(_uuid.uuid4())

    @staticmethod
    def fromString(name: str) -> _JavaUUID:
        return _JavaUUID(_uuid.UUID(name))
