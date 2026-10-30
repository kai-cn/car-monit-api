# -*- coding: utf-8 -*-
"""org.elasticsearch.common.unit.ByteSizeUnit

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.common.unit.ByteSizeUnit`（枚举）。

本工程用法（LargeScaleDataSyncService.buildBulkProcessor）：
    .setBulkSize(new ByteSizeValue(10L, ByteSizeUnit.MB))

【Java→Python 关键差异】
1) Java 的 `ByteSizeUnit` 是**枚举**，成员自带换算因子：
   BYTES(1) / KB(1024) / MB(1024^2) / GB / TB / PB。
   Python 侧用模块级常量对象表达枚举成员（本工程只用到 MB）。
2) `toBytes(long)` 返回 long → Python int。
"""
from __future__ import annotations

__all__ = ["ByteSizeUnit"]


class ByteSizeUnit(object):
    """`ByteSizeUnit` 的替身（仅保留换算因子与 toBytes）。"""

    def __init__(self, name: str, factor: int) -> None:
        self._name = name
        self._factor = factor

    def toBytes(self, size: int) -> int:
        """对应 `long toBytes(long size)`。"""
        return int(size) * self._factor

    @property
    def factor(self) -> int:
        return self._factor

    def __repr__(self) -> str:
        return "ByteSizeUnit.%s" % self._name


# 枚举成员（Java: ByteSizeUnit.BYTES / KB / MB / GB / TB / PB）
ByteSizeUnit.BYTES = ByteSizeUnit("BYTES", 1)
ByteSizeUnit.KB = ByteSizeUnit("KB", 1024)
ByteSizeUnit.MB = ByteSizeUnit("MB", 1024 ** 2)
ByteSizeUnit.GB = ByteSizeUnit("GB", 1024 ** 3)
ByteSizeUnit.TB = ByteSizeUnit("TB", 1024 ** 4)
ByteSizeUnit.PB = ByteSizeUnit("PB", 1024 ** 5)
