# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.WildcardQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.WildcardQueryBuilder``。
本工程用法（ElasticsearchQueryService / UnifiedQueryService）：
    QueryBuilders.wildcardQuery("platenumber_keyword", "*" + plateNumber.toUpperCase() + "*");
    QueryBuilders.wildcardQuery("entollstationname", "*" + stationName + "*");

【Java→Python】关键差异
1) ES 的 ``wildcard`` 支持 ``*``（任意多字符）与 ``?``（单字符）两个通配符，
   **不支持正则**；Python 用 ``fnmatch`` 的 ``*`` / ``?`` 语义与之一致
   （``fnmatch`` 另外支持 ``[seq]``，本替身在文档注释中声明该扩展差异）。
2) 真实 ES 的 wildcard 默认对词条匹配（``keyword`` 字段即整串）；
   替身对 ``_source`` 整串做 fnmatch，等价于 ``LIKE`` 的 ``%``/``_``。
3) ``wildcard`` 大小写敏感；替身同样不归一，由调用方 ``toUpperCase()``。
4) 字段缺失或值为 null 时不命中（与 ES 行为一致）。
"""

from __future__ import annotations

import fnmatch
from typing import Any

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder, _MISSING, _field_value

__all__ = ["WildcardQueryBuilder"]


class WildcardQueryBuilder(QueryBuilder):
    """``wildcard`` 查询的替身（fnmatch 实现）。"""

    def __init__(self, field: str, wildcard: Any) -> None:
        self._field = field
        self._wildcard = wildcard

    # ------------------------------------------------------------------ 链式 setter
    def caseInsensitive(self, value: bool = True) -> "WildcardQueryBuilder":
        """对应 ES 7.10+ 的 ``caseInsensitive(boolean)``；本工程未使用。"""
        self._case_insensitive = bool(value)
        return self

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        actual = _field_value(document, self._field)
        if actual is _MISSING or actual is None:
            return False
        pattern = "" if self._wildcard is None else str(self._wildcard)
        # 【Java→Python】fnmatchcase 区分大小写（等同于 ES keyword 字段语义）
        return fnmatch.fnmatchcase(str(actual), pattern)

    def __repr__(self) -> str:
        return "WildcardQueryBuilder(field=%r, wildcard=%r)" % (self._field, self._wildcard)
