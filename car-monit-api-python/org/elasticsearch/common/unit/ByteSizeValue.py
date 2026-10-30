# -*- coding: utf-8 -*-
"""org.elasticsearch.common.unit.ByteSizeValue

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.common.unit.ByteSizeValue`。

本工程用法（LargeScaleDataSyncService.buildBulkProcessor）：
    .setBulkSize(new ByteSizeValue(10L, ByteSizeUnit.MB))

【Java→Python 关键差异】
1) Java 构造器 `ByteSizeValue(long size, ByteSizeUnit unit)` → Python 两个位置参数。
2) `getBytes()` 返回 long → Python int。
3) 真实类还支持 `getKb()/getMb()` 与字符串解析（"10mb"），本工程未使用，不实现。
"""
from __future__ import annotations

from org.elasticsearch.common.unit.ByteSizeUnit import ByteSizeUnit

__all__ = ["ByteSizeValue"]


class ByteSizeValue(object):
    """`ByteSizeValue` 的替身。"""

    def __init__(self, size: int, unit: ByteSizeUnit) -> None:
        self._size = int(size)
        self._unit = unit

    def getBytes(self) -> int:
        """对应 `long getBytes()`：统一换算为字节数。"""
        return self._unit.toBytes(self._size)

    def __repr__(self) -> str:
        return "ByteSizeValue(%d%s)" % (self._size, self._unit)
