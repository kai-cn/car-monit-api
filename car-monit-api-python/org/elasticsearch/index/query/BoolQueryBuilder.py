# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.BoolQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.BoolQueryBuilder``。
本工程用法（EsQueryService.queryFromEs）：
    BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
    boolQuery.must(QueryBuilders.matchQuery("vehiclePlate", vehiclePlate).fuzziness("AUTO"));
    boolQuery.filter(QueryBuilders.rangeQuery("snapshotTime").gte(...));
    boolQuery.filter(QueryBuilders.termQuery("sectionCode", sectionCode));
    sourceBuilder.query(boolQuery);

【Java→Python】关键差异
1) Java 的 ``must/filter/should/mustNot`` 都是**可变参数**（``QueryBuilder...``）；
   Python 用 ``*queries`` 表达，调用写法 ``boolQuery.must(q)`` 完全一致。
   另外 Java 还有接受 ``Iterable`` 的重载，Python 用 ``_extend`` 内部兼容。
2) **must 与 filter 的区别**（真实 ES）：两者都要求命中，但 must 参与打分、
   filter 不参与打分且可缓存。替身不做打分，两者在 ``matches`` 里等价处理；
   保留两个独立列表仅为忠实反映原代码的分组意图（便于断言）。
3) ``should`` 默认“至少命中一个”（minimumShouldMatch 缺省 1）；替身按此实现。
4) ``adjustPureNegative`` / ``minimumNumberShouldMatch`` 等高级选项未实现。
"""

from __future__ import annotations

from typing import Any, Iterable, List

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder

__all__ = ["BoolQueryBuilder"]


def _extend(target: List[QueryBuilder], queries: Iterable[Any]) -> None:
    """把可变参数展开进列表（兼容 Java 的数组与 Iterable 两种重载）。"""
    for query in queries:
        if isinstance(query, (list, tuple)):
            target.extend(query)
        else:
            target.append(query)


class BoolQueryBuilder(QueryBuilder):
    """``bool`` 查询的替身（must / filter / should / mustNot）。"""

    def __init__(self) -> None:
        self._must: List[QueryBuilder] = []
        self._filter: List[QueryBuilder] = []
        self._should: List[QueryBuilder] = []
        self._must_not: List[QueryBuilder] = []
        self._minimum_should_match = 1

    # ------------------------------------------------------------------ 链式 setter
    def must(self, *queries: Any) -> "BoolQueryBuilder":
        _extend(self._must, queries)
        return self

    def filter(self, *queries: Any) -> "BoolQueryBuilder":
        # 【Java→Python】方法名 filter 与内置函数同名无碍（它是实例方法）
        _extend(self._filter, queries)
        return self

    def should(self, *queries: Any) -> "BoolQueryBuilder":
        _extend(self._should, queries)
        return self

    def mustNot(self, *queries: Any) -> "BoolQueryBuilder":
        _extend(self._must_not, queries)
        return self

    def minimumShouldMatch(self, value: int) -> "BoolQueryBuilder":
        self._minimum_should_match = int(value)
        return self

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        for query in self._must:
            if not query.matches(document):
                return False
        for query in self._filter:
            if not query.matches(document):
                return False
        for query in self._must_not:
            if query.matches(document):
                return False
        if self._should:
            matched = sum(1 for query in self._should if query.matches(document))
            if matched < self._minimum_should_match:
                return False
        return True

    # ------------------------------------------------------------------ 测试辅助
    def mustClauses(self) -> List[QueryBuilder]:
        """Java 没有公开此方法；替身用于断言分组是否正确。"""
        return list(self._must)

    def filterClauses(self) -> List[QueryBuilder]:
        return list(self._filter)

    def shouldClauses(self) -> List[QueryBuilder]:
        return list(self._should)

    def mustNotClauses(self) -> List[QueryBuilder]:
        return list(self._must_not)

    def __repr__(self) -> str:
        return ("BoolQueryBuilder(must=%d, filter=%d, should=%d, mustNot=%d)" %
                (len(self._must), len(self._filter), len(self._should),
                 len(self._must_not)))
