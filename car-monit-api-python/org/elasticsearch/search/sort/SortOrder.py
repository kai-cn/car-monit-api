# -*- coding: utf-8 -*-
"""org.elasticsearch.search.sort.SortOrder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.sort.SortOrder``。

本工程用法（ElasticsearchQueryService / UnifiedQueryService）：
    sourceBuilder.sort("snapshottime", SortOrder.DESC);

【Java→Python】关键差异
1) Java 的 ``SortOrder`` 是**枚举**（``ASC`` / ``DESC``）；Python 同样用类属性
   表达两个枚举常量，调用写法 ``SortOrder.DESC`` 逐字一致。
2) **顺序语义不变**：ASC = 升序、DESC = 降序。替身不做真实排序
   —— ``SearchSourceBuilder`` 仅记录排序要求，``RestHighLevelClient`` 返回
   文档时保持插入顺序（与真实 ES 的 ``_doc`` 兜底顺序一致），已在使用处注释。
"""

from __future__ import annotations

__all__ = ["SortOrder"]


class _SortOrder(object):
    """排序方向（``SortOrder`` 枚举常量的类型）。"""

    def __init__(self, name: str) -> None:
        self._name = name

    def toString(self) -> str:
        """对应 ``Enum#name()``。"""
        return self._name

    def __repr__(self) -> str:
        return "SortOrder.%s" % self._name


class SortOrder(object):
    """``SortOrder`` 枚举的替身（只包含 ASC / DESC）。"""

    ASC = _SortOrder("ASC")
    DESC = _SortOrder("DESC")

    @staticmethod
    def values():
        return [SortOrder.ASC, SortOrder.DESC]

    @staticmethod
    def valueOf(name: str):
        for order in SortOrder.values():
            if order.toString() == name:
                return order
        raise ValueError("No enum constant SortOrder.%s" % name)
