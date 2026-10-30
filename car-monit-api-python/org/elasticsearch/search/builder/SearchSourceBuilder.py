# -*- coding: utf-8 -*-
"""org.elasticsearch.search.builder.SearchSourceBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.builder.SearchSourceBuilder``。
本工程用法（EsQueryService.queryFromEs）：
    SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
    sourceBuilder.query(boolQuery);
    sourceBuilder.from((page.getPageNum() - 1) * page.getPageSize());
    sourceBuilder.size(page.getPageSize());
    sourceBuilder.timeout(new TimeValue(30, TimeUnit.SECONDS));
    searchRequest.source(sourceBuilder);

【Java→Python】关键差异（**本工程最需要注意的一处关键字冲突**）
1) Java 的 ``from(int)`` 是方法名，而 ``from`` 在 Python 里是**关键字**：
   ``sourceBuilder.from(0)`` 会直接 ``SyntaxError``（``x.from`` 的属性访问被词法
   阶段拒绝）。因此转写为 ``from_(0)``，并在 ``EsQueryService.py`` 中同步改名。
   为降低迁移成本，替身额外提供 ``setFrom(int)``（语义相同）。
2) Java 的 ``size(int)`` / ``query(QueryBuilder)`` / ``timeout(TimeValue)``
   均链式返回 this；替身保持一致。
3) Java 的 ``from`` 缺省值为 0、``size`` 缺省值为 **10**（ES 服务端默认返回 10 条），
   替身沿用该默认值。
4) ``sort`` / ``trackTotalHits`` 在 optimization 包中被使用：
   - ``sort("snapshottime", SortOrder.DESC)``：替身**只记录不排序**
     （枚举无排序能力；详见下方使用处注释）；
   - ``trackTotalHits(true)``：真实 ES 要求精确总数时置 true；
     替身的 ``SearchHits.getTotalHits()`` 恒为精确值，因此只记录不参与计算。
5) ``aggregation`` / ``terminateAfter`` 由 LargeScaleQueryService 使用：
   - ``aggregation(AggregationBuilder)``：替身只记录构建器，由
     ``RestHighLevelClient.search`` 在**全部命中文档**上本地求值
     （见 ``search/aggregations/AggregationBuilder.py`` 的设计说明）；
   - ``terminateAfter(int)``：真实 ES 在**每个分片**命中 N 条后提前结束，
     影响性能与总数上界；替身只记录（进程内文档量远小于阈值，不影响结果）。
6) ``fetchSource(String[] includes, String[] excludes)`` 由 UnifiedExportService 使用：
   真实 ES 会在返回的 ``_source`` 里做字段裁剪（投影）；替身**只记录** includes/excludes，
   ``SearchHit.getSourceAsMap()`` 仍返回完整文档。对导出结果无影响——导出只读取
   includes 里的列，多出来的键不会被使用。
7) ``searchAfter`` / ``highlight`` / ``docValueField`` 等本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = ["SearchSourceBuilder"]


class SearchSourceBuilder(object):
    """``SearchSourceBuilder`` 的替身（query / from / size / timeout）。"""

    #: ES 默认返回条数（Java 侧由 SearchSourceBuilder.DEFAULT_FROM / DEFAULT_SIZE 决定）
    DEFAULT_FROM = 0
    DEFAULT_SIZE = 10

    def __init__(self) -> None:
        self._query: Optional[Any] = None
        self._from = SearchSourceBuilder.DEFAULT_FROM
        self._size = SearchSourceBuilder.DEFAULT_SIZE
        self._timeout: Optional[Any] = None
        #: 排序要求列表 [(field, SortOrder)]；替身不实际参与文档排序
        self._sorts: list = []
        #: 是否要求精确总数（对应 track_total_hits）
        self._track_total_hits: Optional[bool] = None
        #: 聚合构建器（按加入顺序）；由 RestHighLevelClient.search 本地求值
        self._aggregations: list = []
        #: 每个分片最多命中多少条后提前结束（防慢查询）；替身只记录
        self._terminate_after: Optional[int] = None
        #: _source 字段裁剪（includes）与排除（excludes）；替身只记录
        self._fetch_source: Optional[tuple] = None

    # ------------------------------------------------------------------ 链式 setter
    def query(self, query_builder: Any) -> "SearchSourceBuilder":
        """对应 ``query(QueryBuilder)``。"""
        self._query = query_builder
        return self

    def from_(self, from_index: int) -> "SearchSourceBuilder":
        """对应 ``from(int)``；因 from 是 Python 关键字，改名 from_。"""
        self._from = int(from_index)
        return self

    def setFrom(self, from_index: int) -> "SearchSourceBuilder":
        """``from(int)`` 的别名（便于逐字迁移/联想 Java 命名习惯）。"""
        return self.from_(from_index)

    def size(self, size: int) -> "SearchSourceBuilder":
        self._size = int(size)
        return self

    def timeout(self, time_value: Any) -> "SearchSourceBuilder":
        """对应 ``timeout(TimeValue)``；替身只保存，不真正超时。"""
        self._timeout = time_value
        return self

    def sort(self, field: str, order: Any = None) -> "SearchSourceBuilder":
        """对应 ``sort(String field, SortOrder order)``。

        【Java→Python】真实 ES 在服务端排序；替身只记录
        ``[(field, SortOrder)]``，``RestHighLevelClient`` 仍按插入顺序返回
        （等价于 ``_doc`` 顺序）—— 这是本替身对“排序”语义的唯一损失。
        """
        self._sorts.append((field, order))
        return self

    def trackTotalHits(self, track: bool) -> "SearchSourceBuilder":
        """对应 ``trackTotalHits(boolean)``；替身总数恒为精确值，仅记录。"""
        self._track_total_hits = bool(track)
        return self

    def aggregation(self, aggregation_builder: Any) -> "SearchSourceBuilder":
        """对应 ``aggregation(AggregationBuilder)``：返回 this。

        【Java→Python】聚合在 ``RestHighLevelClient.search`` 里对**全部命中文档**
        求值，因此与 ``from`` / ``size`` 无关（``size(0)`` 也能拿到聚合结果）。
        """
        self._aggregations.append(aggregation_builder)
        return self

    def terminateAfter(self, terminate_after: int) -> "SearchSourceBuilder":
        """对应 ``terminateAfter(int)``：返回 this。

        【Java→Python】ES 语义是“每个分片命中 N 条后提前结束”，属于**性能护栏**
        （宁可少返回也不拖慢集群）；替身不截断文档，只保存该参数。
        """
        self._terminate_after = int(terminate_after)
        return self

    def fetchSource(self, includes: Optional[list],
                    excludes: Optional[list]) -> "SearchSourceBuilder":
        """对应 ``fetchSource(String[] includes, String[] excludes)``：返回 this。

        【Java→Python】Java 传的是 ``COLUMNS.toArray(new String[0])`` 与 ``null``，
        对应 Python 的 list 与 None。真实 ES 会按 includes/excludes 裁剪 ``_source``；
        替身只记录（详见文件头第 6 条）。
        """
        self._fetch_source = (includes, excludes)
        return self

    # ------------------------------------------------------------------ getter
    def getQuery(self) -> Optional[Any]:
        return self._query

    def getFrom(self) -> int:
        return self._from

    def getSize(self) -> int:
        return self._size

    def getTimeout(self) -> Optional[Any]:
        return self._timeout

    def getSorts(self) -> list:
        """Java 无公开此方法；替身用于断言排序参数是否正确传递。"""
        return list(self._sorts)

    def getTrackTotalHits(self) -> Optional[bool]:
        """Java 无公开此方法；替身用于断言。"""
        return self._track_total_hits

    def getAggregationBuilders(self) -> list:
        """Java 侧为 ``aggregations()``（返回 AggregatorFactories.Builder）；替身返回 list。"""
        return list(self._aggregations)

    def getTerminateAfter(self) -> Optional[int]:
        """Java 无公开此方法；替身用于断言。"""
        return self._terminate_after

    def getFetchSource(self) -> Optional[tuple]:
        """Java 无公开此方法；替身用于断言 ``(includes, excludes)``。"""
        return self._fetch_source

    def __repr__(self) -> str:
        return ("SearchSourceBuilder(query=%r, from=%d, size=%d, timeout=%r, "
                "aggregations=%d, terminateAfter=%r, fetchSource=%r)" %
                (self._query, self._from, self._size, self._timeout,
                 len(self._aggregations), self._terminate_after,
                 self._fetch_source))
