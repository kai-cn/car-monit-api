# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.PrefixQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.PrefixQueryBuilder``。
本工程用法（ElasticsearchQueryService.buildPlateQuery）：
    QueryBuilders.prefixQuery("platenumber_keyword", plateNumber.toUpperCase());

【Java→Python】关键差异
1) ``prefix`` 在 ES 中是**词条前缀**匹配（作用于倒排索引的词条，不分词）；
   替身没有倒排索引，退化为对 ``_source`` 字段值的 ``startswith`` 比较，
   语义与 ``LIKE 'xxx%'`` 等价 —— 对 ``keyword`` 字段足够准确。
2) ES 的 ``prefix`` 大小写敏感（``keyword`` 字段不经过 analyzer）；替身同样
   **不做** lower() 归一，由调用方自行 ``toUpperCase()``（原代码正是这么做的）。
3) 字段缺失或值为 null 时不命中（与 ES 行为一致）。
"""

from __future__ import annotations

from typing import Any

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder, _MISSING, _field_value

__all__ = ["PrefixQueryBuilder"]


class PrefixQueryBuilder(QueryBuilder):
    """``prefix`` 查询的替身。"""

    def __init__(self, field: str, prefix: Any) -> None:
        self._field = field
        self._prefix = prefix

    # ------------------------------------------------------------------ 链式 setter
    def caseInsensitive(self, value: bool = True) -> "PrefixQueryBuilder":
        """对应 ES 7.10+ 的 ``caseInsensitive(boolean)``；本工程未使用，保留以防切换。"""
        self._case_insensitive = bool(value)
        return self

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        actual = _field_value(document, self._field)
        if actual is _MISSING or actual is None:
            return False
        text = str(actual)
        prefix = "" if self._prefix is None else str(self._prefix)
        return text.startswith(prefix)

    def __repr__(self) -> str:
        return "PrefixQueryBuilder(field=%r, prefix=%r)" % (self._field, self._prefix)
