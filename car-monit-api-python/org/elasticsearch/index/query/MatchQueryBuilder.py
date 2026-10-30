# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.MatchQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.MatchQueryBuilder``。
本工程用法（EsQueryService.queryFromEs）：
    QueryBuilders.matchQuery("vehiclePlate", vehiclePlate).fuzziness("AUTO")

【Java→Python】关键差异
1) Java 的 ``fuzziness(Object)`` 是链式方法，接受 ``"AUTO"`` 字符串或数值；
   替身保存该值，只在 ``matches()`` 里区分“模糊/精确”。
2) **匹配语义是本替身对 ES 的近似**：真实 ES 的 ``match`` 会按字段的
   analyzer 分词，``fuzziness=AUTO`` 走 Levenshtein 编辑距离（按词长 0/1/2）。
   替身没有分词器与词典，采用“**子串包含**（忽略大小写）”近似模糊匹配、
   “全等（忽略大小写）”近似非模糊匹配。对车牌子串检索这一场景足够；
   若将来需要真正的编辑距离，可在 ``_fuzzy_equals`` 里补充。
3) 字段不存在（unmapped）或值为 null 时**不命中**（与 ES 行为一致）。
4) Java 的 ``operator`` / ``analyzer`` / ``boost`` / ``minimumShouldMatch`` 等
   本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder, _MISSING, _field_value

__all__ = ["MatchQueryBuilder"]


class MatchQueryBuilder(QueryBuilder):
    """``match`` 查询的替身。"""

    def __init__(self, field: str, value: Any) -> None:
        self._field = field
        self._value = value
        self._fuzziness: Any = None

    # ------------------------------------------------------------------ 链式 setter
    def fuzziness(self, fuzziness: Any) -> "MatchQueryBuilder":
        """对应 ``fuzziness(Object fuzziness)``；工程传 ``"AUTO"``。"""
        self._fuzziness = fuzziness
        return self

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        actual = _field_value(document, self._field)
        if actual is _MISSING or actual is None:
            return False
        text = str(actual).lower()
        query = "" if self._value is None else str(self._value).lower()
        if self._is_fuzzy():
            # 近似：子串包含（见模块注释第 2 条）
            return query in text
        return query == text

    def _is_fuzzy(self) -> bool:
        if self._fuzziness is None:
            return False
        if isinstance(self._fuzziness, str):
            # ES 接受 "AUTO" / "0" / "1" / "2"；非 "0" 即视为启用模糊
            return self._fuzziness.strip().upper() not in ("", "0")
        return int(self._fuzziness) > 0

    def __repr__(self) -> str:
        return "MatchQueryBuilder(field=%r, value=%r, fuzziness=%r)" % (
            self._field, self._value, self._fuzziness)
