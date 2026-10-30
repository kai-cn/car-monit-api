# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.QueryBuilders

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.QueryBuilders``。
本工程用法（EsQueryService.queryFromEs）：
    QueryBuilders.boolQuery()
    QueryBuilders.matchQuery("vehiclePlate", vehiclePlate)
    QueryBuilders.rangeQuery("snapshotTime")
    QueryBuilders.termQuery("sectionCode", sectionCode)

【Java→Python】关键差异
1) Java 的 ``QueryBuilders`` 是**纯静态工厂类**（私有构造器）；
   Python 用 ``@staticmethod`` 表达，调用写法完全一致，不需要实例化。
2) Java 有上百个工厂方法（matchPhrase/terms/wildcard/nested/...）；
   本工程只用到 bool/match/range/term 四个，其余不实现。
"""

from __future__ import annotations

from typing import Any

from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.MatchQueryBuilder import MatchQueryBuilder
from org.elasticsearch.index.query.PrefixQueryBuilder import PrefixQueryBuilder
from org.elasticsearch.index.query.RangeQueryBuilder import RangeQueryBuilder
from org.elasticsearch.index.query.TermQueryBuilder import TermQueryBuilder
from org.elasticsearch.index.query.WildcardQueryBuilder import WildcardQueryBuilder

__all__ = ["QueryBuilders"]


class QueryBuilders(object):
    """``QueryBuilders`` 静态工厂替身。"""

    @staticmethod
    def boolQuery() -> BoolQueryBuilder:
        return BoolQueryBuilder()

    @staticmethod
    def matchQuery(field: str, text: Any) -> MatchQueryBuilder:
        return MatchQueryBuilder(field, text)

    @staticmethod
    def rangeQuery(field: str) -> RangeQueryBuilder:
        return RangeQueryBuilder(field)

    @staticmethod
    def termQuery(field: str, value: Any) -> TermQueryBuilder:
        return TermQueryBuilder(field, value)

    @staticmethod
    def prefixQuery(field: str, prefix: Any) -> PrefixQueryBuilder:
        """对应 ``prefixQuery(String, String)``（optimization 包车牌前缀匹配）。"""
        return PrefixQueryBuilder(field, prefix)

    @staticmethod
    def wildcardQuery(field: str, wildcard: Any) -> WildcardQueryBuilder:
        """对应 ``wildcardQuery(String, String)``（optimization 包模糊兜底）。"""
        return WildcardQueryBuilder(field, wildcard)
