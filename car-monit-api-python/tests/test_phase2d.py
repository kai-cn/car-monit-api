# -*- coding: utf-8 -*-
"""Phase 2d: the ES shim additions (aggregation + scroll) and the services built on them.

The ``org.elasticsearch.*`` shims are in-process emulations, so "index a few
documents then aggregate them" is a complete, deterministic test of the DSL
surface used by ``LargeScaleQueryService`` / ``ProgressiveQueryArchitectureService``.
"""
from __future__ import annotations

from typing import Iterator

import json

import pytest

from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.action.index.IndexRequest import IndexRequest
from org.elasticsearch.action.search.ClearScrollRequest import ClearScrollRequest
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchScrollRequest import SearchScrollRequest
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.search.Scroll import Scroll
from org.elasticsearch.search.aggregations.AggregationBuilders import AggregationBuilders
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder
from org.elasticsearch.xcontent.XContentType import XContentType
from java.util.concurrent.TimeUnit import TimeUnit

_INDEX = "snapshot_flow"


@pytest.fixture()
def client() -> Iterator[RestHighLevelClient]:
    RestHighLevelClient.resetStore()
    instance = RestHighLevelClient(
        RestClient.builder(HttpHost("127.0.0.1", 9200, "http")))
    yield instance
    RestHighLevelClient.resetStore()


def _index(client: RestHighLevelClient, documents) -> None:
    for position, document in enumerate(documents):
        request = IndexRequest(_INDEX)
        request.id(str(position))
        request.source(json.dumps(document, ensure_ascii=False), XContentType.JSON)
        client.index(request)


# ---------------------------------------------------------------- aggregation
def test_terms_aggregation_orders_by_count_then_key_and_truncates(
        client: RestHighLevelClient) -> None:
    _index(client, [
        {"platenumber": "B", "orgname": "O1"},
        {"platenumber": "A", "orgname": "O1"},
        {"platenumber": "A", "orgname": "O2"},
        {"platenumber": "C"},              # orgname 缺失 -> 不进 orgname 桶
    ])

    source = SearchSourceBuilder()
    source.query(QueryBuilders.boolQuery())
    source.size(0)
    source.aggregation(AggregationBuilders.terms("group_by_platenumber")
                       .field("platenumber.keyword")
                       .size(10)
                       .subAggregation(AggregationBuilders.count("total_count")
                                       .field("_id")))

    response = client.search(SearchRequest(_INDEX).source(source))
    # size(0) -> 只取聚合，不返回文档
    assert response.getHits().getHits() == []
    assert int(response.getHits().getTotalHits()) == 4

    terms = response.getAggregations().get("group_by_platenumber")
    # 计数倒序（A=2）；同计数按 key 升序（B 在 C 前）
    assert [(b.getKeyAsString(), b.getDocCount()) for b in terms.getBuckets()] == [
        ("A", 2), ("B", 1), ("C", 1),
    ]
    first = terms.getBuckets()[0]
    assert first.getAggregations().get("total_count").getValue() == 2


def test_terms_aggregation_skips_missing_and_reports_other_doc_count(
        client: RestHighLevelClient) -> None:
    _index(client, [
        {"orgname": "O1"}, {"orgname": "O2"}, {"orgname": "O3"}, {},
    ])

    source = SearchSourceBuilder()
    source.size(0)
    source.aggregation(AggregationBuilders.terms("group_by_orgname")
                       .field("orgname.keyword")
                       .size(2))

    terms = client.search(SearchRequest(_INDEX).source(source)) \
        .getAggregations().get("group_by_orgname")
    assert len(terms.getBuckets()) == 2
    # 三个桶各 1 条，截断掉 1 个桶 -> other = 1；缺失 orgname 的文档不计
    assert terms.getSumOtherDocCount() == 1


def test_value_count_on_a_field_counts_only_non_null(
        client: RestHighLevelClient) -> None:
    _index(client, [
        {"platenumber": "A", "gantrycode": "G1"},
        {"platenumber": "A", "gantrycode": ""},
        {"platenumber": "A"},
    ])

    source = SearchSourceBuilder()
    source.size(0)
    source.aggregation(AggregationBuilders.terms("group_by_platenumber")
                       .field("platenumber.keyword")
                       .size(10)
                       .subAggregation(AggregationBuilders.count("gantry_count")
                                       .field("gantrycode")))

    terms = client.search(SearchRequest(_INDEX).source(source)) \
        .getAggregations().get("group_by_platenumber")
    bucket = terms.getBuckets()[0]
    assert bucket.getDocCount() == 3
    # "" 在 ES 里**是**一个值（只有 null/缺失才算 missing）
    assert bucket.getAggregations().get("gantry_count").getValue() == 2


def test_aggregation_is_independent_of_from_and_size(
        client: RestHighLevelClient) -> None:
    _index(client, [{"platenumber": "A"}, {"platenumber": "A"},
                    {"platenumber": "B"}])

    source = SearchSourceBuilder()
    source.from_(2)          # 只看第 3 条文档
    source.size(1)
    source.aggregation(AggregationBuilders.terms("group_by_platenumber")
                       .field("platenumber.keyword"))

    response = client.search(SearchRequest(_INDEX).source(source))
    assert len(response.getHits().getHits()) == 1
    terms = response.getAggregations().get("group_by_platenumber")
    # 聚合覆盖全部 3 条命中，与 from/size 无关
    assert [(b.getKeyAsString(), b.getDocCount()) for b in terms.getBuckets()] == [
        ("A", 2), ("B", 1)]


# --------------------------------------------------------------------- scroll
def _scroll_source(batch_size: int) -> SearchSourceBuilder:
    source = SearchSourceBuilder()
    source.query(QueryBuilders.boolQuery())
    source.size(batch_size)
    return source


def test_scroll_walks_the_whole_result_set_then_returns_empty(
        client: RestHighLevelClient) -> None:
    _index(client, [{"platenumber": "P%d" % i} for i in range(5)])

    request = SearchRequest(_INDEX)
    request.source(_scroll_source(2))
    request.scroll(Scroll(TimeValue(5, TimeUnit.MINUTES)))

    batches = []
    response = client.search(request)
    scroll_id = response.getScrollId()
    assert scroll_id is not None
    batches.append(len(response.getHits().getHits()))
    while response.getHits().getHits():
        scroll_request = SearchScrollRequest(scroll_id)
        scroll_request.scroll(Scroll(TimeValue(5, TimeUnit.MINUTES)))
        response = client.scroll(scroll_request)
        scroll_id = response.getScrollId() or scroll_id
        batches.append(len(response.getHits().getHits()))

    # 2 + 2 + 1 + 0：最后一批为空是循环终止条件
    assert batches == [2, 2, 1, 0]
    # 每批的总命中数都等于全量（与 Java 侧读 getTotalHits().value 一致）
    assert int(response.getHits().getTotalHits()) == 5
    RestHighLevelClient.resetStore()


def test_clear_scroll_releases_the_cursor(client: RestHighLevelClient) -> None:
    _index(client, [{"platenumber": "P%d" % i} for i in range(3)])

    request = SearchRequest(_INDEX)
    request.source(_scroll_source(1))
    request.scroll(Scroll(TimeValue(5, TimeUnit.MINUTES)))
    scroll_id = client.search(request).getScrollId()

    clear_request = ClearScrollRequest()
    clear_request.addScrollId(scroll_id)
    cleared = client.clearScroll(clear_request)
    assert cleared.isSucceeded() is True
    assert cleared.getNumFreed() == 1

    # 清理后再 scroll：对应 ES 的 SearchContextMissingException
    with pytest.raises(ValueError):
        client.scroll(SearchScrollRequest(scroll_id))


def test_plain_search_has_no_scroll_id_and_empty_aggregations(
        client: RestHighLevelClient) -> None:
    _index(client, [{"platenumber": "A"}])
    source = SearchSourceBuilder()
    response = client.search(SearchRequest(_INDEX).source(source))
    assert response.getScrollId() is None
    # Java 的 getAggregations() 恒非 null
    assert response.getAggregations().get("absent") is None
