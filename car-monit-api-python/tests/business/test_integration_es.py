# -*- coding: utf-8 -*-
"""P2-3：真实 Elasticsearch 7.15 集成测试（默认跳过）。

开启方式（本机 ES 已起在 9200，xpack.security=false）：
    CAR_MONIT_TEST_ES=1 CAR_MONIT_ES_URL=http://127.0.0.1:9200 \
      python -m pytest tests/business/test_integration_es.py -q

CI 的 integration job 由 service container（elasticsearch:7.17.13）提供
服务并注入同组环境变量。

隔离设计：索引与 ILM 策略均带 ``car-monit-p2-it-`` 前缀并在夹具里清理，
不污染开发索引；各测试使用互不重叠的时间窗（六月/七月/八月），可任意
顺序单独执行。
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any
from urllib.parse import urlparse

import pytest

import bootstrap  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("CAR_MONIT_TEST_ES") != "1",
                       reason="需要真实 Elasticsearch：设置 CAR_MONIT_TEST_ES=1 开启"),
]

ES_URL = os.environ.get("CAR_MONIT_ES_URL", "http://127.0.0.1:9200")
PREFIX = "car-monit-p2-it-"
SNAPSHOT_INDEX = PREFIX + "snapshot"
ILM_POLICY = PREFIX + "ilm-policy"


def _make_client():
    """挂真实后端的 RestHighLevelClient（shared_es_backend 进程级共享）。"""
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.client.RestClient import RestClient
    from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient

    parsed = urlparse(ES_URL)
    return RestHighLevelClient(
        RestClient.builder(HttpHost(parsed.hostname or "127.0.0.1",
                                    parsed.port or 9200,
                                    parsed.scheme or "http")))


@pytest.fixture(scope="module")
def client():
    """模块级真实客户端；teardown 清理测试索引与 ILM 策略。"""
    had_url = "CAR_MONIT_ES_URL" in os.environ
    os.environ["CAR_MONIT_ES_URL"] = ES_URL
    instance = _make_client()
    assert instance.ping()
    yield instance
    low_level = instance._real.client
    for name in (SNAPSHOT_INDEX,):
        try:
            low_level.indices.delete(index=name)
        except Exception:  # noqa: BLE001 - 索引可能未建
            pass
    try:
        low_level.transport.perform_request("DELETE", "/_ilm/policy/" + ILM_POLICY)
    except Exception:  # noqa: BLE001 - 策略可能未建
        pass
    if not had_url:
        os.environ.pop("CAR_MONIT_ES_URL", None)


@pytest.fixture()
def manage_service(client, monkeypatch):
    """EsIndexManageService（测试索引名/分片/ILM 名全部走环境变量覆盖）。"""
    monkeypatch.setenv("ELASTICSEARCH_INDEX_SNAPSHOT", SNAPSHOT_INDEX)
    monkeypatch.setenv("ELASTICSEARCH_INDEX_SHARDS", "1")
    monkeypatch.setenv("ELASTICSEARCH_INDEX_REPLICAS", "0")
    monkeypatch.setenv("ELASTICSEARCH_INDEX_ILM_POLICY", ILM_POLICY)
    monkeypatch.setenv("ELASTICSEARCH_INDEX_AUTO_CREATE", "false")
    from com.ruoyi.base.service.optimization.EsIndexManageService import (
        EsIndexManageService,
    )

    return EsIndexManageService(esClient=client)


def _seed(client, doc_id: str, plate: str, org: str,
          when: _dt.datetime) -> None:
    """按 DataProcessService 的写入方式（IndexRequest + JSON.toJSONString）落一条。"""
    from com.alibaba.fastjson2.JSON import JSON
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )
    from org.elasticsearch.action.index.IndexRequest import IndexRequest
    from org.elasticsearch.client.RequestOptions import RequestOptions
    from org.elasticsearch.xcontent.XContentType import XContentType

    data = OdsRtSzdnSnapshotFlowAddcode()
    data.setPlatenumber(plate)
    data.setOrgname(org)
    data.setGantrycode("G-" + doc_id)
    data.setSnapshottime(when)
    request = (IndexRequest(SNAPSHOT_INDEX)
               .id(doc_id)
               .source(JSON.toJSONString(data), XContentType.JSON))
    client.index(request, RequestOptions.DEFAULT)


def _refresh(client) -> None:
    client._real.client.indices.refresh(index=SNAPSHOT_INDEX)


# ------------------------------------------------------------------ 索引管理
def test_index_lifecycle_and_mapping(client, manage_service) -> None:
    """建索引业务链路：exists → create（ngram mapping + _doc 包装兼容）→ 幂等 → 别名。"""
    from org.elasticsearch.client.RequestOptions import RequestOptions
    from org.elasticsearch.client.indices.GetIndexRequest import GetIndexRequest

    indices = client.indices()
    assert indices.exists(GetIndexRequest(SNAPSHOT_INDEX),
                          RequestOptions.DEFAULT) is False

    assert manage_service.createIndexIfAbsent(
        SNAPSHOT_INDEX, "es/index/snapshot_flow.json") is True
    assert indices.exists(GetIndexRequest(SNAPSHOT_INDEX),
                          RequestOptions.DEFAULT) is True
    # 幂等：已存在则跳过
    assert manage_service.createIndexIfAbsent(
        SNAPSHOT_INDEX, "es/index/snapshot_flow.json") is False

    # mapping 落到真实集群：ngram 子字段（统一查询的模糊检索依赖它）
    mapping = client._real.client.indices.get_mapping(
        index=SNAPSHOT_INDEX, include_type_name=True)
    props = mapping[SNAPSHOT_INDEX]["mappings"]["_doc"]["properties"]
    assert props["platenumber"]["fields"]["ngram"]["analyzer"] == "ngram_analyzer"
    assert props["platenumber"]["fields"]["keyword"]["type"] == "keyword"
    assert props["snapshottime"]["type"] == "date"

    # 别名（updateAliases 真实链路）
    assert manage_service.addAlias(SNAPSHOT_INDEX, PREFIX + "alias") is True
    aliases = client._real.client.indices.get_alias(index=SNAPSHOT_INDEX)
    assert PREFIX + "alias" in aliases[SNAPSHOT_INDEX]["aliases"]


# ------------------------------------------------------------------ 统一查询
def test_unified_query_es_chain_end_to_end(client, manage_service) -> None:
    """统一查询走 ES 的核心链路（用户点名的验收项）：路由 → DSL → ngram/term →
    分页/排序 → JSON.parseObject 反向化。"""
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )
    from com.ruoyi.base.service.optimization.UnifiedQueryService import (
        UnifiedQueryService,
    )

    manage_service.createIndexIfAbsent(SNAPSHOT_INDEX, "es/index/snapshot_flow.json")
    _seed(client, "u-1", "苏A12345", "南京管理中心",
          _dt.datetime(2026, 6, 1, 8, 0, 0))
    _seed(client, "u-2", "苏A12345", "南京管理中心",
          _dt.datetime(2026, 6, 2, 9, 30, 0))
    _seed(client, "u-3", "苏B67890", "苏州管理中心",
          _dt.datetime(2026, 6, 3, 10, 0, 0))
    _refresh(client)

    service = UnifiedQueryService(indexManageService=manage_service)
    data_source = UnifiedQueryService.DataSource.SNAPSHOT
    window = ("2026-06-01 00:00:00", "2026-06-30 23:59:59")

    # 3-6 字符 → ngram match（模糊检索核心路径）
    fuzzy = service.query(data_source, window[0], window[1],
                          {"platenumber": "苏A123"}, 1, 10)
    assert len(fuzzy) == 2
    assert all(isinstance(row, OdsRtSzdnSnapshotFlowAddcode) for row in fuzzy)
    assert {row.getPlatenumber() for row in fuzzy} == {"苏A12345"}
    # sort(snapshottime, DESC) 在真实 ES 生效
    assert fuzzy[0].getSnapshottime() > fuzzy[1].getSnapshottime()
    assert fuzzy[0].getOrgname() == "南京管理中心"

    # >=7 字符车牌 → term 精确匹配
    exact = service.query(data_source, window[0], window[1],
                          {"platenumber": "苏A12345"}, 1, 10)
    assert len(exact) == 2

    # 分页（from/size 翻译）
    page2 = service.query(data_source, window[0], window[1],
                          {"platenumber": "苏A12345"}, 2, 1)
    assert len(page2) == 1
    assert page2[0].getSnapshottime() == fuzzy[1].getSnapshottime()

    # 模糊字段不命中 → 空结果（不报错）
    miss = service.query(data_source, window[0], window[1],
                         {"platenumber": "粤Z999"}, 1, 10)
    assert miss == []


def test_missing_index_raises_parity_exception(client) -> None:
    """索引不存在：异常消息与替身逐字一致（UnifiedQueryService 靠它降级 MySQL）。"""
    from org.elasticsearch.ElasticsearchException import (
        ElasticsearchStatusException,
    )
    from org.elasticsearch.action.search.SearchRequest import SearchRequest
    from org.elasticsearch.client.RequestOptions import RequestOptions

    missing = PREFIX + "no-such-index"
    with pytest.raises(ElasticsearchStatusException) as exc_info:
        client.search(SearchRequest(missing), RequestOptions.DEFAULT)
    assert ("Elasticsearch exception [type=index_not_found_exception, "
            "reason=no such index [%s]]" % missing) == str(exc_info.value)


# -------------------------------------------------------------------- 导出
def test_bulk_and_scroll_export_chain(client, manage_service) -> None:
    """写入链路（bulkAsync + listener）与导出链路（Scroll 游标深翻页）。"""
    from java.util.concurrent.TimeUnit import TimeUnit
    from org.elasticsearch.action.bulk.BulkRequest import BulkRequest
    from org.elasticsearch.action.index.IndexRequest import IndexRequest
    from org.elasticsearch.action.search.ClearScrollRequest import (
        ClearScrollRequest,
    )
    from org.elasticsearch.action.search.SearchRequest import SearchRequest
    from org.elasticsearch.action.search.SearchScrollRequest import (
        SearchScrollRequest,
    )
    from org.elasticsearch.client.RequestOptions import RequestOptions
    from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
    from org.elasticsearch.search.Scroll import Scroll
    from org.elasticsearch.search.builder.SearchSourceBuilder import (
        SearchSourceBuilder,
    )
    from org.elasticsearch.search.sort.SortOrder import SortOrder
    from org.elasticsearch.core.TimeValue import TimeValue
    from org.elasticsearch.xcontent.XContentType import XContentType

    from com.alibaba.fastjson2.JSON import JSON
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )

    manage_service.createIndexIfAbsent(SNAPSHOT_INDEX, "es/index/snapshot_flow.json")

    # ---- bulkAsync 批量写入（LargeScaleDataSyncService 的写入方式）
    bulk = BulkRequest()
    for i in range(5):
        data = OdsRtSzdnSnapshotFlowAddcode()
        data.setPlatenumber("苏C900%02d" % i)
        data.setOrgname("沪R管理中心")
        data.setSnapshottime(_dt.datetime(2026, 7, 1, 12, 0, i))
        bulk.add(IndexRequest(SNAPSHOT_INDEX)
                 .id("scroll-%d" % i)
                 .source(JSON.toJSONString(data), XContentType.JSON))
    callbacks: list = []

    class _Listener:
        def onResponse(self, response: Any) -> None:
            callbacks.append(response)

        def onFailure(self, error: Any) -> None:
            raise error

    response = client.bulkAsync(bulk, RequestOptions.DEFAULT, _Listener())
    assert callbacks and callbacks[0] is response
    assert response.hasFailures() is False
    _refresh(client)

    # ---- Scroll 游标（UnifiedExportService.executeExportScroll 的请求形态）
    source_builder = (SearchSourceBuilder()
                      .query(QueryBuilders.boolQuery()
                             .filter(QueryBuilders.rangeQuery("snapshottime")
                                     .format("yyyy-MM-dd HH:mm:ss")
                                     .gte("2026-07-01 00:00:00")
                                     .lte("2026-07-31 23:59:59")))
                      .size(2)
                      .sort("snapshottime", SortOrder.DESC)
                      .timeout(TimeValue(120, TimeUnit.SECONDS)))
    request = (SearchRequest(SNAPSHOT_INDEX)
               .source(source_builder)
               .scroll(Scroll(TimeValue(5, TimeUnit.MINUTES))))
    first = client.search(request, RequestOptions.DEFAULT)
    scroll_id = first.getScrollId()
    assert scroll_id  # 真实 ES 返回服务端游标
    collected = list(first.getHits().getHits())
    while True:
        page = client.scroll(
            SearchScrollRequest(scroll_id)
            .scroll(Scroll(TimeValue(5, TimeUnit.MINUTES))),
            RequestOptions.DEFAULT)
        hits = page.getHits().getHits()
        if not hits:
            break
        collected.extend(hits)
    assert len(collected) == 5
    times = [_dt.datetime.strptime(
        hit.getSourceAsMap()["snapshottime"], "%Y-%m-%d %H:%M:%S")
        for hit in collected]
    assert times == sorted(times, reverse=True)  # 按时间倒序

    # 清理游标（导出 finally 块的形态）
    clear_request = ClearScrollRequest()
    clear_request.addScrollId(scroll_id)
    assert client.clearScroll(clear_request,
                              RequestOptions.DEFAULT).isSucceeded()


# -------------------------------------------------------------------- 聚合
def test_aggregation_stats_business_chain(client, manage_service) -> None:
    """LargeScaleQueryService.aggregationStats 业务方法端到端（terms + value_count）。"""
    from com.ruoyi.base.service.optimization.LargeScaleQueryService import (
        LargeScaleQueryService,
    )

    manage_service.createIndexIfAbsent(SNAPSHOT_INDEX, "es/index/snapshot_flow.json")
    for i in range(3):
        _seed(client, "a-1-%d" % i, "苏D%03d" % i, "皖K管理中心",
              _dt.datetime(2026, 8, 1, 9, 0, i))
    for i in range(2):
        _seed(client, "a-2-%d" % i, "苏E%03d" % i, "晋M管理中心",
              _dt.datetime(2026, 8, 2, 9, 0, i))
    _refresh(client)

    service = LargeScaleQueryService(indexManageService=manage_service)
    result = service.aggregationStats(
        "snapshot", "2026-08-01 00:00:00", "2026-08-31 23:59:59",
        "orgname", "gantrycode", None, 10)
    assert result == {"皖K管理中心": 3, "晋M管理中心": 2}


# --------------------------------------------------------------------- ILM
def test_ilm_policy_via_low_level_rest(client, manage_service) -> None:
    """ILM 策略走低层 REST（RestClient.performRequest → transport）：
    构造期 init() 已幂等创建；重复创建跳过；策略内容落到真实集群。"""
    assert manage_service.ilmPolicyName == ILM_POLICY
    assert manage_service.ilmPolicyExists(ILM_POLICY) is True
    assert manage_service.createIndexLifecyclePolicyIfAbsent(ILM_POLICY) is False

    raw = client._real.client.transport.perform_request(
        "GET", "/_ilm/policy/" + ILM_POLICY)
    assert ILM_POLICY in raw
    phases = raw[ILM_POLICY]["policy"]["phases"]
    assert phases["hot"]["actions"]["rollover"]["max_age"] == "30d"
    assert phases["delete"]["min_age"] == "365d"
