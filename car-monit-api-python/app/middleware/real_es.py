# -*- coding: utf-8 -*-
"""真实 Elasticsearch REST/DSL 适配（P2-3，docs/迁移审阅报告.md）。

背景
----
此前 ES 相关类全部是进程内替身（查询在客户端 ``matches()`` 执行、文档存
类属性 ``_INDICES``）。本模块在设置 ``CAR_MONIT_ES_URL``
（如 ``http://127.0.0.1:9200``）后，把 ``RestHighLevelClient`` /
``IndicesClient`` / ``RestClient.performRequest`` 的请求翻译成真实
REST/DSL 发给 ES 7.15+（elasticsearch-py 7.17 客户端），响应再重建回
替身的 ``SearchResponse`` 等对象——业务代码零改动。

QueryBuilder → DSL 翻译
-----------------------
覆盖业务用到的全部构建器：bool（must/filter/should/must_not +
minimum_should_match）/ term / range（bounds→gte/gt/lte/lt + format）/
match / prefix / wildcard；source：from/size/timeout/sort/
track_total_hits/terminate_after/_source(includes,excludes)/aggs
（terms + value_count，含子聚合）。

与替身语义的对齐点（差异均有据可查）：
* ``minimum_should_match``：替身在 should 非空时恒按 1 生效；翻译时显式
  写进 DSL（真实 ES 7 在"有 must/filter + should"时服务端默认 0，会令
  should 形同虚设——显式 1 才是业务代码的 OR 语义）。
* ``track_total_hits``：只翻译业务显式设置的值（GaussEsConsistencyService
  显式 ``trackTotalHits(True)`` 保证对账精确）。未设置时真实 ES 默认
  10000 截断 + ``relation=gte``，而替身恒精确——该差异只影响
  UnifiedQueryService 的 debug 日志 totalHits，不影响业务返回。
* 索引不存在：NotFoundError → 重建为与替身逐字一致的
  ``index_not_found_exception``（UnifiedQueryService 靠它触发 MySQL 降级）。
* 建索引：classpath 里的 mapping JSON 把 settings+mappings 整体包在顶层
  ``_doc`` 下（6.x 风格），ES 7.x 建索引体只认 settings/mappings/aliases
  根键，翻译层剥掉包装后建索引（Java HLRC 的 fromXContent 同样会摊平）；
  剥掉后即 7.x/8.x 规范形态，无兼容包袱。

降级语义（与 real_redis 一致）
------------------------------
* ``CAR_MONIT_ES_FALLBACK=error``（prod 模式默认）：连接失败**抛错**——
  对齐 Java 的 IOException 传播（UnifiedQueryService 会捕获并降级 MySQL）；
* ``CAR_MONIT_ES_FALLBACK=memory``（shim 模式默认）：首次连接失败后**熔断**，
  本后端后续请求全部回落进程内替身实现（读写一致），每 60 秒半开重试，
  恢复后自动切回。**降级期间的写入不会回灌真实 ES**；降级期的查询读到的是
  进程内数据（通常为空），不会触发业务的 MySQL 降级——生产用 error 策略
  才有"ES 宕机 → 查询降级 MySQL"的 Java 对等行为；
* 确定性错误（索引不存在 / 上下文失效 / 索引已存在）**不触发熔断**，
  两种策略下都照常抛出——它们不是服务不可用，降级反而会掩盖问题。

线程安全：elasticsearch-py 客户端自带连接池线程安全；熔断标志仅做
尽力而为的原子性（竞争最坏结果是多打一条日志/多一次重试）。
"""
from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import elasticsearch as es_py
import elasticsearch.exceptions as es_exceptions
from elasticsearch.serializer import JSONSerializer

from app.middleware.breaker import CircuitBreaker

from org.elasticsearch.ElasticsearchException import index_not_found_exception
from org.elasticsearch.action.bulk.BulkItemResponse import BulkItemResponse
from org.elasticsearch.action.bulk.BulkResponse import BulkResponse
from org.elasticsearch.action.index.IndexResponse import IndexResponse
from org.elasticsearch.action.search.ClearScrollResponse import ClearScrollResponse
from org.elasticsearch.action.search.SearchResponse import SearchResponse
from org.elasticsearch.action.support.master.AcknowledgedResponse import (
    AcknowledgedResponse,
)
from org.elasticsearch.client.Response import HttpEntity, Response, StatusLine
from org.elasticsearch.client.indices.CreateIndexResponse import CreateIndexResponse
from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.MatchQueryBuilder import MatchQueryBuilder
from org.elasticsearch.index.query.PrefixQueryBuilder import PrefixQueryBuilder
from org.elasticsearch.index.query.RangeQueryBuilder import RangeQueryBuilder
from org.elasticsearch.index.query.TermQueryBuilder import TermQueryBuilder
from org.elasticsearch.index.query.WildcardQueryBuilder import WildcardQueryBuilder
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.SearchHits import SearchHits
from org.elasticsearch.search.aggregations.Aggregations import Aggregations
from org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms import (
    ParsedStringTerms,
)
from org.elasticsearch.search.aggregations.bucket.terms.Terms import Terms
from org.elasticsearch.search.aggregations.bucket.terms.TermsAggregationBuilder import (
    TermsAggregationBuilder,
)
from org.elasticsearch.search.aggregations.metrics.ValueCount import ValueCount
from org.elasticsearch.search.aggregations.metrics.ValueCountAggregationBuilder import (
    ValueCountAggregationBuilder,
)

__all__ = [
    "RealEsBackend",
    "es_fallback_policy",
    "shared_es_backend",
    "time_value_str",
    "translate_aggregation",
    "translate_query",
    "translate_source",
]

log = logging.getLogger(__name__)

#: 熔断后多久半开重试真实 ES（秒）
_RETRY_SECONDS = 60.0


class _DecimalJSONSerializer(JSONSerializer):
    """H1：响应解析阶段保留十进制精度。

    elasticsearch-py 默认 ``json.loads`` 会把 ``1.50`` 变成 float ``1.5``；
    金额字段在重建 ``SearchHit`` 之前就已丢 scale。这里只在**读响应**时启用
    ``parse_float=Decimal``，写请求仍走父类（Decimal 由父类 default 转 float）。
    """

    def loads(self, s: Any) -> Any:
        try:
            return json.loads(s, parse_float=Decimal)
        except (ValueError, TypeError) as error:
            raise es_exceptions.SerializationError(s, error)


#: 进程共享的响应反序列化器（无状态，可安全复用）
_DECIMAL_SERIALIZER = _DecimalJSONSerializer()


def _dump_source(value: Any) -> str:
    """``_source`` → JSON 文本；Decimal 输出精确十进制（不降级为 float）。"""
    from com.alibaba.fastjson2.JSON import JSON

    return JSON.toJSONString(value)


#: ``no such index [xxx]`` 的 reason 解析（保持替身的异常消息逐字一致）
_NO_SUCH_INDEX = re.compile(r"no such index \[([^\]]+)\]")


def es_fallback_policy() -> str:
    """降级策略：``CAR_MONIT_ES_FALLBACK`` 显式优先；默认 prod=error / shim=memory。"""
    explicit = (os.environ.get("CAR_MONIT_ES_FALLBACK") or "").strip().lower()
    if explicit in ("memory", "error"):
        return explicit
    from app.runtime import is_strict

    return "error" if is_strict() else "memory"


# --------------------------------------------------------------------- 翻译
def time_value_str(time_value: Any) -> Optional[str]:
    """``TimeValue`` 替身 → ES 的时长字符串（统一毫秒形式，如 ``30000ms``）。"""
    if time_value is None:
        return None
    return "%dms" % time_value.millis()


def _order_name(order: Any) -> str:
    """``SortOrder`` 替身 → DSL 的 ``asc`` / ``desc``。"""
    if order is None:
        return "asc"  # Java sort(field) 单参重载默认 ASC
    to_string = getattr(order, "toString", None)
    name = to_string() if callable(to_string) else str(order)
    return name.lower()


def translate_query(query: Any) -> Dict[str, Any]:
    """QueryBuilder 替身树 → ES Query DSL（递归）。"""
    if isinstance(query, BoolQueryBuilder):
        body: Dict[str, Any] = {}
        for clause_key, clauses in (("must", query._must),
                                    ("filter", query._filter),
                                    ("should", query._should),
                                    ("must_not", query._must_not)):
            if clauses:
                body[clause_key] = [translate_query(c) for c in clauses]
        if query._should:
            # 替身契约：should 非空时 minimum_should_match 生效（默认 1）。
            # 真实 ES 7 在存在 must/filter 时服务端默认 0（should 可选），
            # 显式写出才与业务 OR 语义一致（见模块 docstring）。
            body["minimum_should_match"] = int(query._minimum_should_match)
        return {"bool": body}
    if isinstance(query, TermQueryBuilder):
        return {"term": {query._field: query._value}}
    if isinstance(query, RangeQueryBuilder):
        range_body: Dict[str, Any] = {op: value for op, value in query._bounds}
        date_format = getattr(query, "_format", None)
        if date_format:
            range_body["format"] = date_format
        return {"range": {query._field: range_body}}
    if isinstance(query, MatchQueryBuilder):
        if getattr(query, "_fuzziness", None) is None:
            return {"match": {query._field: query._value}}
        return {"match": {query._field: {"query": query._value,
                                         "fuzziness": query._fuzziness}}}
    if isinstance(query, PrefixQueryBuilder):
        return {"prefix": {query._field: query._prefix}}
    if isinstance(query, WildcardQueryBuilder):
        wildcard: Dict[str, Any] = {"value": query._wildcard}
        if getattr(query, "_case_insensitive", None):
            wildcard["case_insensitive"] = True
        return {"wildcard": {query._field: wildcard}}
    raise TypeError("ES 适配无法翻译查询构建器: %r" % (query,))


def translate_aggregation(builder: Any) -> Dict[str, Any]:
    """AggregationBuilder 替身 → ES 聚合 DSL（含子聚合）。

    注意：``value_count`` 统计的字段为 ``_id`` 时真实 ES 会拒绝
    （Field [_id] is not supported）——Java 原工程同样如此，属对等行为；
    业务调用方传入真实 countField 时不受影响。
    """
    if isinstance(builder, TermsAggregationBuilder):
        body: Dict[str, Any] = {"terms": {"field": builder.getField(),
                                          "size": builder.getSize()}}
    elif isinstance(builder, ValueCountAggregationBuilder):
        body = {"value_count": {"field": builder.getField()}}
    else:
        raise TypeError("ES 适配无法翻译聚合构建器: %r" % (builder,))
    sub_builders = builder.getSubAggregations()
    if sub_builders:
        body["aggs"] = {sub.getName(): translate_aggregation(sub)
                        for sub in sub_builders}
    return body


def translate_source(builder: Any) -> Dict[str, Any]:
    """``SearchSourceBuilder`` 替身 → search 请求体。"""
    body: Dict[str, Any] = {}
    if builder is None:
        return body
    query = builder.getQuery()
    if query is not None:
        body["query"] = translate_query(query)
    body["from"] = builder.getFrom()
    body["size"] = builder.getSize()
    timeout = builder.getTimeout()
    if timeout is not None:
        body["timeout"] = time_value_str(timeout)
    sorts = builder.getSorts()
    if sorts:
        body["sort"] = [{field: {"order": _order_name(order)}}
                        for field, order in sorts]
    track_total_hits = builder.getTrackTotalHits()
    if track_total_hits is not None:
        # 只翻译显式设置（未设置时遵循真实 ES 的 10000 截断默认，见模块 docstring）
        body["track_total_hits"] = track_total_hits
    terminate_after = builder.getTerminateAfter()
    if terminate_after is not None:
        body["terminate_after"] = terminate_after
    fetch_source = builder.getFetchSource()
    if fetch_source is not None:
        includes, excludes = fetch_source
        source_filter: Dict[str, Any] = {}
        if includes:
            source_filter["includes"] = list(includes)
        if excludes:
            source_filter["excludes"] = list(excludes)
        if source_filter:
            body["_source"] = source_filter
    aggregation_builders = builder.getAggregationBuilders()
    if aggregation_builders:
        body["aggs"] = {agg.getName(): translate_aggregation(agg)
                        for agg in aggregation_builders}
    return body


# ------------------------------------------------------------------ 响应重建
def _build_search_response(raw: Dict[str, Any],
                           with_scroll: bool) -> SearchResponse:
    """ES 原始响应 → 替身 ``SearchResponse``（业务代码零改动地继续读）。"""
    hits_raw = raw.get("hits") or {}
    inner_hits = hits_raw.get("hits") or []
    hits = [
        SearchHit(hit.get("_index", ""), str(hit.get("_id")),
                  _dump_source(hit.get("_source") or {}),
                  hit.get("_score") if hit.get("_score") is not None else 1.0)
        for hit in inner_hits
    ]
    total_raw = hits_raw.get("total") or {}
    if isinstance(total_raw, dict):
        total = int(total_raw.get("value", len(hits)))
    else:
        total = int(total_raw or len(hits))
    return SearchResponse(
        SearchHits(hits, total),
        took=int(raw.get("took", 0)),
        timed_out=bool(raw.get("timed_out", False)),
        aggregations=_build_aggregations(raw.get("aggregations") or {}),
        scroll_id=(raw.get("_scroll_id") if with_scroll else None))


def _build_aggregations(aggregations: Dict[str, Any]) -> Aggregations:
    """ES 聚合响应 → 替身聚合对象（terms 桶 + value_count，递归子聚合）。

    ES 响应里桶的子聚合与 ``key`` / ``doc_count`` 平铺同级（不在 "aggs" 键下），
    重建时要把其余键挑出来递归。
    """
    result: Dict[str, Any] = {}
    for name, agg_body in (aggregations or {}).items():
        if not isinstance(agg_body, dict):
            continue
        if "buckets" in agg_body:
            buckets = []
            for bucket in agg_body.get("buckets") or []:
                sub = {key: value for key, value in bucket.items()
                       if key not in ("key", "key_as_string", "doc_count",
                                      "doc_count_error")}
                buckets.append(Terms.Bucket(
                    bucket.get("key"), int(bucket.get("doc_count", 0)),
                    _build_aggregations(sub)))
            terms = ParsedStringTerms(name, buckets)
            terms.setSumOtherDocCount(int(agg_body.get("sum_other_doc_count", 0)))
            result[name] = terms
        elif "value" in agg_body:
            result[name] = ValueCount(name, int(agg_body["value"]))
        else:
            log.warning("[ES适配] 未识别的聚合结果类型，已跳过：%s", name)
    return Aggregations(result)


def _error_type(error: Any) -> str:
    info = getattr(error, "info", None)
    if isinstance(info, dict):
        inner = info.get("error")
        if isinstance(inner, dict):
            return str(inner.get("type") or "")
    return str(getattr(error, "error", "") or "")


def _as_index_not_found(error: Any,
                        indices: List[str]) -> Exception:
    """NotFoundError → 与替身逐字一致的 index_not_found_exception。"""
    info = getattr(error, "info", None)
    reason = ""
    if isinstance(info, dict):
        inner = info.get("error")
        if isinstance(inner, dict):
            reason = str(inner.get("reason") or "")
    matched = _NO_SUCH_INDEX.search(reason) if reason else None
    if matched:
        return index_not_found_exception(matched.group(1))
    return index_not_found_exception(indices[0] if indices else "_all")


# --------------------------------------------------------------------- 后端
class RealEsBackend:
    """真实 Elasticsearch 后端（elasticsearch-py 7.17，兼容 ES 7.15 服务端）。

    与 Redis 适配同构：``_run`` 统一调度真实调用与降级；构造**不建连**
    （elasticsearch-py 惰性连接），首次请求才触达服务。
    """

    def __init__(self, url: str, fallback: Optional[str] = None,
                 client: Optional[Any] = None) -> None:
        self._url = url
        self._fallback = fallback or es_fallback_policy()
        self.client = client or es_py.Elasticsearch(
            [url], timeout=30, max_retries=0, retry_on_timeout=False,
            serializer=_DECIMAL_SERIALIZER)
        self._breaker = CircuitBreaker(_RETRY_SECONDS)

    # ------------------------------------------------------------- dispatch
    def _run(self, description: str, real: Callable[[], Any],
             memory: Callable[[], Any]) -> Any:
        allowed, probe = self._breaker.acquire()
        if not allowed:
            return memory()
        try:
            result = real()
        except es_exceptions.ConnectionError as error:
            if self._fallback == "error":
                if probe:
                    self._breaker.release_probe()
                raise
            # H2：失败分支无条件刷新窗口计时（包括半开探测失败）
            first = self._breaker.failure()
            log.warning("[ES适配] %s %s，熔断降级为进程内替身（%.0fs 后半开重试；"
                        "降级期间的写入不会回灌真实 ES）: %s",
                        description, "失败" if first else "半开探测仍失败",
                        _RETRY_SECONDS, error)
            return memory()
        except BaseException:
            # 确定性错误（索引不存在 / 上下文失效等）不是服务不可用：
            # 释放探测名额后原样抛出，不改变熔断状态
            if probe:
                self._breaker.release_probe()
            raise
        if self._breaker.success():
            log.info("[ES适配] 真实 ES 已恢复（%s）", self._url)
        return result

    @property
    def degraded(self) -> bool:
        """当前是否处于熔断降级（供健康检查/测试观察）。"""
        return self._breaker.degraded

    # ----------------------------------------------------------------- 连接
    def ping(self, memory: Callable[[], bool]) -> bool:
        def real() -> bool:
            return bool(self.client.ping())

        return self._run("RestHighLevelClient.ping", real, memory)

    # ----------------------------------------------------------------- 写入
    def index(self, request: Any, memory: Callable[[], Any]) -> IndexResponse:
        source = request.getSource()

        def real() -> IndexResponse:
            if source is None:
                raise ValueError("IndexRequest.source 不能为空")
            kwargs: Dict[str, Any] = {"index": request.index(), "body": source}
            if request.getId() is not None:
                kwargs["id"] = request.getId()
            raw = self.client.index(**kwargs)
            result = str(raw.get("result", "created")).upper()
            return IndexResponse(raw.get("_index", request.index()),
                                 str(raw.get("_id", request.getId() or "")),
                                 "UPDATED" if result == "UPDATED" else "CREATED",
                                 int(raw.get("_version", 1)))

        return self._run("RestHighLevelClient.index", real, memory)

    def bulkAsync(self, request: Any, listener: Any,
                  memory: Callable[[], Any]) -> BulkResponse:
        actions = request.requests()

        def real() -> BulkResponse:
            if not actions:
                response = BulkResponse([])
                if listener is not None:
                    listener.onResponse(response)
                return response
            lines: List[str] = []
            for action in actions:
                meta: Dict[str, Any] = {"_index": action.index()}
                if action.getId() is not None:
                    meta["_id"] = action.getId()
                lines.append(json.dumps({"index": meta}, ensure_ascii=False))
                lines.append(action.getSource() or "{}")
            raw = self.client.bulk(body="\n".join(lines) + "\n")
            items: List[BulkItemResponse] = []
            for entry in raw.get("items", []):
                item = entry.get("index") or next(iter(entry.values()), {})
                error = item.get("error")
                item_id = item.get("_id")
                items.append(BulkItemResponse(
                    str(item_id) if item_id is not None else None,
                    bool(error),
                    str(error) if error else None))
            response = BulkResponse(items)
            if listener is not None:
                listener.onResponse(response)
            return response

        return self._run("RestHighLevelClient.bulkAsync", real, memory)

    # ----------------------------------------------------------------- 查询
    def search(self, request: Any, memory: Callable[[], Any]) -> SearchResponse:
        body = translate_source(request.getSource())
        kwargs: Dict[str, Any] = {"body": body}
        indices = request.indices()
        if indices:
            kwargs["index"] = indices
        scroll = request.getScroll()
        if scroll is not None:
            kwargs["scroll"] = time_value_str(scroll.keepAlive())

        def real() -> SearchResponse:
            try:
                raw = self.client.search(**kwargs)
            except es_exceptions.NotFoundError as error:
                # 索引不存在是确定性错误（不熔断），保持替身异常契约
                raise _as_index_not_found(error, indices)
            return _build_search_response(raw, with_scroll=scroll is not None)

        return self._run("RestHighLevelClient.search", real, memory)

    def scroll(self, request: Any, memory: Callable[[], Any]) -> SearchResponse:
        scroll_id = request.scrollId()
        keep_alive = request.getScroll()
        kwargs: Dict[str, Any] = {"scroll_id": scroll_id}
        if keep_alive is not None and keep_alive.keepAlive() is not None:
            kwargs["scroll"] = time_value_str(keep_alive.keepAlive())

        def real() -> SearchResponse:
            try:
                raw = self.client.scroll(**kwargs)
            except es_exceptions.RequestError as error:
                if _error_type(error) == "search_context_missing_exception":
                    # 对应替身的 SearchContextMissingException 语义
                    raise ValueError(
                        "No search context found for id [%s]" % scroll_id)
                raise
            return _build_search_response(raw, with_scroll=True)

        return self._run("RestHighLevelClient.scroll", real, memory)

    def clearScroll(self, request: Any,
                    memory: Callable[[], Any]) -> ClearScrollResponse:
        scroll_ids = [sid for sid in request.getScrollIds() if sid]

        def real() -> ClearScrollResponse:
            if not scroll_ids:
                return ClearScrollResponse(True, 0)
            raw = self.client.clear_scroll(scroll_id=scroll_ids)
            return ClearScrollResponse(bool(raw.get("succeeded", True)),
                                       int(raw.get("num_freed", 0)))

        return self._run("RestHighLevelClient.clearScroll", real, memory)

    # ------------------------------------------------------------ 索引管理
    def indices_exists(self, request: Any, memory: Callable[[], bool]) -> bool:
        names = list(request.indices())

        def real() -> bool:
            if not names:
                return True
            return bool(self.client.indices.exists(index=names))

        return self._run("IndicesClient.exists", real, memory)

    def indices_create(self, request: Any,
                       memory: Callable[[], Any]) -> CreateIndexResponse:
        body: Dict[str, Any] = {}
        if request.getSource():
            body = json.loads(request.getSource())
            # classpath 的 mapping JSON 把 settings+mappings 整体包在顶层 "_doc"
            # 下（6.x 风格）；ES 7.x 建索引体只认 settings/mappings/aliases 根键，
            # 这里剥掉包装（Java HLRC 的 fromXContent 解析 source 时同样会摊平）。
            if set(body.keys()) == {"_doc"} and isinstance(body.get("_doc"), dict):
                body = body["_doc"]
            mappings = body.get("mappings")
            if (isinstance(mappings, dict) and set(mappings.keys()) == {"_doc"}
                    and isinstance(mappings.get("_doc"), dict)):
                body["mappings"] = mappings["_doc"]
        if request.getSettings():
            extra = json.loads(request.getSettings())
            if isinstance(extra.get("index"), dict):
                # 嵌套形式摊平为 "index.xxx" 键，与 mapping JSON 的扁平 settings 兼容合并
                nested = extra.pop("index")
                extra.update({"index." + key: value
                              for key, value in nested.items()})
            body.setdefault("settings", {}).update(extra)

        def real() -> CreateIndexResponse:
            try:
                self.client.indices.create(index=request.index(), body=body)
            except es_exceptions.RequestError as error:
                if "resource_already_exists_exception" in str(
                        getattr(error, "error", "")):
                    # 对应替身的 ResourceAlreadyExistsException 语义
                    raise ValueError("resource_already_exists_exception: index [%s]"
                                     % request.index())
                raise
            return CreateIndexResponse(request.index(), True)

        return self._run("IndicesClient.create", real, memory)

    def indices_delete(self, request: Any,
                       memory: Callable[[], Any]) -> AcknowledgedResponse:
        names = list(request.indices())

        def real() -> AcknowledgedResponse:
            try:
                self.client.indices.delete(index=names)
            except es_exceptions.NotFoundError as error:
                raise _as_index_not_found(error, names)
            return AcknowledgedResponse(True)

        return self._run("IndicesClient.delete", real, memory)

    def indices_updateAliases(self, request: Any,
                              memory: Callable[[], Any]) -> AcknowledgedResponse:
        def _actions() -> List[Dict[str, Any]]:
            from org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest import (
                AliasActions,
            )

            actions: List[Dict[str, Any]] = []
            for action in request.getAliasActions():
                if action.getType() is AliasActions.Type.REMOVE_INDEX:
                    for index_name in action.getIndices():
                        actions.append({"remove_index": {"index": index_name}})
                    continue
                kind = "add" if action.getType() is AliasActions.Type.ADD else "remove"
                for index_name in action.getIndices():
                    for alias_name in action.getAliases():
                        actions.append({kind: {"index": index_name,
                                               "alias": alias_name}})
            return actions

        def real() -> AcknowledgedResponse:
            actions = _actions()
            if actions:
                self.client.indices.update_aliases(body={"actions": actions})
            return AcknowledgedResponse(True)

        return self._run("IndicesClient.updateAliases", real, memory)

    # ------------------------------------------------------------ 低层 REST
    def performRequest(self, request: Any,
                       memory: Callable[[], Any]) -> Response:
        method = (request.getMethod() or "GET").upper()
        endpoint = request.getEndpoint() or ""
        entity = request.getJsonEntity()

        def real() -> Response:
            payload = json.loads(entity) if entity else None
            # Transport.perform_request 不像生成端点那样自动带 Content-Type，
            # 有请求体时必须显式设置，否则 ES 返回 406
            headers = {"Content-Type": "application/json"} if payload else None
            try:
                # elasticsearch-py 的 Transport 对非 2xx 抛异常；Java 低层
                # RestClient 返回带状态码的 Response。这里翻译回 Response 形态，
                # 业务（ilmPolicyExists）两条路都判定"不存在"。
                result = self.client.transport.perform_request(
                    method, endpoint, headers=headers, body=payload)
            except es_exceptions.NotFoundError:
                return Response(StatusLine(404),
                                HttpEntity('{"error":"resource_not_found_exception"}'))
            body_text = json.dumps(result if result is not None else {},
                                   ensure_ascii=False)
            return Response(StatusLine(200), HttpEntity(body_text))

        return self._run("RestClient.performRequest", real, memory)

    # ------------------------------------------------------------ 生命周期
    def close(self) -> None:
        """H6：关闭 elasticsearch-py 连接池。"""
        try:
            self.client.close()
        except Exception:  # noqa: BLE001 - 关闭期尽力而为，不阻断应用退出
            log.warning("[ES适配] 关闭连接池异常（忽略）", exc_info=True)


# -------------------------------------------------------------------- 工厂
_SHARED_ES: Dict[str, Any] = {"url": None, "backend": None}


def shared_es_backend() -> Optional[RealEsBackend]:
    """进程级共享后端：``CAR_MONIT_ES_URL`` 未设 → ``None``（纯替身模式）。

    URL 变化时重建（与 shared_redis_template 同语义）；业务多处构造
    ``RestHighLevelClient`` 时共享同一个连接池（Java 里它们注入的是同一个 Bean）。
    """
    url = (os.environ.get("CAR_MONIT_ES_URL") or "").strip()
    if not url:
        _SHARED_ES["url"] = None
        _SHARED_ES["backend"] = None
        return None
    if _SHARED_ES["url"] != url or _SHARED_ES["backend"] is None:
        _SHARED_ES["url"] = url
        _SHARED_ES["backend"] = RealEsBackend(url)
    return _SHARED_ES["backend"]


def close_shared_es_backend() -> None:
    """H6：关闭并重置进程级 ES 后端（应用优雅停机用，幂等）。"""
    backend = _SHARED_ES.get("backend")
    _SHARED_ES["url"] = None
    _SHARED_ES["backend"] = None
    close = getattr(backend, "close", None)
    if callable(close):
        close()
