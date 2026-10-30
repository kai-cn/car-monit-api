# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.TermQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.TermQueryBuilder``。
本工程用法（EsQueryService.queryFromEs）：
    QueryBuilders.termQuery("sectionCode", sectionCode)
    QueryBuilders.termQuery("manageCenterCode", manageCenterCode)
    QueryBuilders.termQuery("gantryCode", gantryCode)

【Java→Python】关键差异
1) ``term`` 是**不分词、不分析**的精确匹配；替身用 ``str(actual) == str(value)``
   做宽松相等（真实 ES 对 ``text`` 字段做 term 查询会因分词而命中不到，
   本替身不模拟 analyzer 差异，实际工程里这类字段应为 ``keyword``）。
2) Java 的 ``termQuery(String, Object)`` 把值统一视为 ``FieldValue``；
   Python 侧直接保存原值，比较时字符串化，避免 ``1`` 与 ``"1"`` 判不相等
   （MySQL/ES 中编号字段经常混用两种类型）。
3) 字段缺失或值为 null 时不命中。
"""

from __future__ import annotations

from typing import Any

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder, _MISSING, _field_value

__all__ = ["TermQueryBuilder"]


class TermQueryBuilder(QueryBuilder):
    """``term`` 查询的替身。"""

    def __init__(self, field: str, value: Any) -> None:
        self._field = field
        self._value = value

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        actual = _field_value(document, self._field)
        if actual is _MISSING or actual is None:
            return False
        return str(actual) == str(self._value)

    def __repr__(self) -> str:
        return "TermQueryBuilder(field=%r, value=%r)" % (self._field, self._value)
