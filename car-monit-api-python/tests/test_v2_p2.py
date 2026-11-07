# -*- coding: utf-8 -*-
"""V2 P2 回归测试：真实 Redis / Elasticsearch 适配（单元层：翻译 + 降级语义，
不依赖真实服务——真实联调见 tests/business/test_integration_*.py）。"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

import pytest

import bootstrap  # noqa: F401


# --------------------------------------------------------------------- codec
def test_codec_entity_round_trip_with_atype() -> None:
    from app.middleware.real_redis import decode, encode

    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    entity = OdsSzdnGantry()
    entity.setId("g-1")
    entity.setGantryCode("G001")
    entity.setGantryName("测试门架")
    raw = encode(entity)
    # FastJson WriteClassName 形态：@type + camelCase 字段
    assert raw.startswith(b'{"@type":"com.ruoyi.base.domain.OdsSzdnGantry"')
    assert b'"gantryCode":"G001"' in raw
    restored = decode(raw)
    assert isinstance(restored, OdsSzdnGantry)
    assert restored.getId() == "g-1"
    assert restored.getGantryCode() == "G001"
    assert restored.getGantryName() == "测试门架"


def test_codec_scalar_decimal_datetime() -> None:
    from app.middleware.real_redis import decode, encode

    assert decode(encode("abc")) == "abc"
    assert decode(encode(5)) == 5
    assert decode(encode(True)) is True
    assert decode(encode(Decimal("1.50"))) == "1.50"  # 字符串保精度（fastjson2 可还原 BigDecimal）
    stamp = _dt.datetime(2026, 1, 2, 3, 4, 5)
    assert decode(encode(stamp)) == "2026-01-02 03:04:05"
    # 实体里的 Decimal/datetime 字段经类型提示还原
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    record = OdsLwzxsfsjFeeRecords01()
    record.setFee(Decimal("1.50"))
    record.setTranstime(stamp)
    restored = decode(encode(record))
    assert isinstance(restored, OdsLwzxsfsjFeeRecords01)
    assert restored.getFee() == Decimal("1.50")
    assert restored.getTranstime() == stamp


def test_codec_non_json_passthrough() -> None:
    from app.middleware.real_redis import decode

    assert decode(b"not-json") == "not-json"
    assert decode(None) is None


# ------------------------------------------------------------------ fallback
class _BrokenClient:
    """所有命令都抛 ConnectionError 的假客户端。"""

    def __getattr__(self, name):
        def _boom(*args, **kwargs):
            import redis as redis_py

            raise redis_py.ConnectionError("connection refused (test)")

        return _boom


def test_fallback_memory_policy_trips_to_memory() -> None:
    from app.middleware.real_redis import RealRedisTemplate

    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="memory",
                                 client=_BrokenClient())
    assert template.degraded is False
    template.opsForValue().set("k", "v")  # 熔断 + 内存降级
    assert template.degraded is True
    assert template.opsForValue().get("k") == "v"  # 降级期间读写一致（内存）
    cache_keys = template.keys("*")
    assert cache_keys == {"k"}


def test_fallback_error_policy_raises() -> None:
    import redis as redis_py

    from app.middleware.real_redis import RealRedisTemplate

    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="error",
                                 client=_BrokenClient())
    with pytest.raises(redis_py.ConnectionError):
        template.opsForValue().set("k", "v")


def test_fallback_policy_env_and_runtime_default(monkeypatch) -> None:
    from app.middleware.real_redis import redis_fallback_policy

    monkeypatch.delenv("CAR_MONIT_REDIS_FALLBACK", raising=False)
    monkeypatch.delenv("CAR_MONIT_RUNTIME", raising=False)
    assert redis_fallback_policy() == "memory"  # shim 默认降级
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    assert redis_fallback_policy() == "error"  # prod 默认抛错（Java 宕机语义）
    monkeypatch.setenv("CAR_MONIT_REDIS_FALLBACK", "memory")
    assert redis_fallback_policy() == "memory"  # 显式覆盖


# ------------------------------------------------------------------- factory
def test_shared_template_factory_switches_by_env(monkeypatch) -> None:
    from app.middleware.real_redis import RealRedisTemplate
    from com.ruoyi.common.core.redis.RedisCache import (
        _InMemoryRedisTemplate,
        shared_redis_template,
    )

    monkeypatch.delenv("CAR_MONIT_REDIS_URL", raising=False)
    assert isinstance(shared_redis_template(), _InMemoryRedisTemplate)

    monkeypatch.setenv("CAR_MONIT_REDIS_URL", "redis://127.0.0.1:6379/0")
    template = shared_redis_template()
    assert isinstance(template, RealRedisTemplate)

    monkeypatch.delenv("CAR_MONIT_REDIS_URL", raising=False)
    assert isinstance(shared_redis_template(), _InMemoryRedisTemplate)  # URL 变化重建

    # RedisCache / defaultRedisTemplate / defaultStringRedisTemplate 三处同一实例
    from com.ruoyi.common.core.redis.RedisCache import RedisCache
    from org.springframework.data.redis.core.RedisTemplate import defaultRedisTemplate
    from org.springframework.data.redis.core.StringRedisTemplate import (
        defaultStringRedisTemplate,
    )

    monkeypatch.setenv("CAR_MONIT_REDIS_URL", "redis://127.0.0.1:6379/0")
    shared = shared_redis_template()
    assert RedisCache().redisTemplate is shared
    assert defaultRedisTemplate() is shared
    assert defaultStringRedisTemplate() is shared


# ============================================================== ES 适配（P2-3）
def test_es_translate_query_tree() -> None:
    from app.middleware.real_es import translate_query
    from org.elasticsearch.index.query.QueryBuilders import QueryBuilders

    bool_query = (QueryBuilders.boolQuery()
                  .filter(QueryBuilders.rangeQuery("snapshottime")
                          .format("yyyy-MM-dd HH:mm:ss")
                          .gte("2026-01-01 00:00:00")
                          .lte("2026-02-01 00:00:00"))
                  .must(QueryBuilders.termQuery("platenumber.keyword", "苏A12345"))
                  .mustNot(QueryBuilders.matchQuery("orgname.ngram", "南京"))
                  .should(QueryBuilders.wildcardQuery("roadname.keyword", "*G42*")))
    dsl = translate_query(bool_query)
    assert dsl["bool"]["must"] == [{"term": {"platenumber.keyword": "苏A12345"}}]
    range_dsl = dsl["bool"]["filter"][0]["range"]["snapshottime"]
    assert range_dsl == {"gte": "2026-01-01 00:00:00",
                         "lte": "2026-02-01 00:00:00",
                         "format": "yyyy-MM-dd HH:mm:ss"}
    assert dsl["bool"]["must_not"] == [{"match": {"orgname.ngram": "南京"}}]
    assert dsl["bool"]["should"] == [
        {"wildcard": {"roadname.keyword": {"value": "*G42*"}}}]
    # 替身契约：should 非空时 minimum_should_match 生效（真实 ES 服务端在有
    # must/filter 时默认 0，显式写出才保住业务 OR 语义）
    assert dsl["bool"]["minimum_should_match"] == 1

    assert translate_query(
        QueryBuilders.prefixQuery("platenumber.keyword", "苏A")) == \
        {"prefix": {"platenumber.keyword": "苏A"}}


def test_es_translate_source_and_time_value() -> None:
    from java.util.concurrent.TimeUnit import TimeUnit
    from org.elasticsearch.core.TimeValue import TimeValue
    from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
    from org.elasticsearch.search.builder.SearchSourceBuilder import (
        SearchSourceBuilder,
    )
    from org.elasticsearch.search.sort.SortOrder import SortOrder

    from app.middleware.real_es import time_value_str, translate_source

    assert time_value_str(TimeValue(5, TimeUnit.MINUTES)) == "300000ms"

    builder = (SearchSourceBuilder()
               .query(QueryBuilders.boolQuery()
                      .filter(QueryBuilders.rangeQuery("snapshottime")
                              .format("yyyy-MM-dd HH:mm:ss")
                              .gte("2026-01-01 00:00:00")
                              .lte("2026-02-01 00:00:00")))
               .from_(20).size(10)
               .sort("snapshottime", SortOrder.DESC)
               .timeout(TimeValue(30, TimeUnit.SECONDS))
               .trackTotalHits(True)
               .fetchSource(["big_id", "platenumber"], None))
    body = translate_source(builder)
    assert body["from"] == 20
    assert body["size"] == 10
    assert body["sort"] == [{"snapshottime": {"order": "desc"}}]
    assert body["timeout"] == "30000ms"
    assert body["track_total_hits"] is True
    assert body["_source"] == {"includes": ["big_id", "platenumber"]}
    assert "terminate_after" not in body  # 未设置的不翻译（track 同理，见上）


def test_es_translate_aggregations() -> None:
    from org.elasticsearch.search.aggregations.AggregationBuilders import (
        AggregationBuilders,
    )

    from app.middleware.real_es import translate_aggregation

    agg = (AggregationBuilders.terms("group_by_orgname")
           .field("orgname.keyword").size(5)
           .subAggregation(AggregationBuilders.count("total_count")
                           .field("big_id")))
    dsl = translate_aggregation(agg)
    assert dsl["terms"] == {"field": "orgname.keyword", "size": 5}
    assert dsl["aggs"]["total_count"] == {"value_count": {"field": "big_id"}}


# ------------------------------------------------------------------ ES 降级
class _BrokenEsClient:
    """所有请求都抛 ConnectionError 的假 ES 客户端。"""

    def __getattr__(self, name):
        def _boom(*args, **kwargs):
            import elasticsearch.exceptions as es_exc

            raise es_exc.ConnectionError(
                "N/A", "connection refused (test)", None)

        return _boom


def test_es_fallback_memory_policy_degrades() -> None:
    from app.middleware.real_es import RealEsBackend

    backend = RealEsBackend("http://127.0.0.1:1", fallback="memory",
                            client=_BrokenEsClient())
    assert backend.degraded is False
    marker = []
    result = backend.ping(memory=lambda: marker.append(1) or True)
    assert result is True  # 熔断后回落替身语义
    assert marker == [1]
    assert backend.degraded is True


def test_es_fallback_error_policy_raises() -> None:
    import elasticsearch.exceptions as es_exc

    from app.middleware.real_es import RealEsBackend

    backend = RealEsBackend("http://127.0.0.1:1", fallback="error",
                            client=_BrokenEsClient())
    with pytest.raises(es_exc.ConnectionError):
        backend.ping(memory=lambda: True)


def test_es_fallback_policy_env_and_runtime_default(monkeypatch) -> None:
    from app.middleware.real_es import es_fallback_policy

    monkeypatch.delenv("CAR_MONIT_ES_FALLBACK", raising=False)
    monkeypatch.delenv("CAR_MONIT_RUNTIME", raising=False)
    assert es_fallback_policy() == "memory"  # shim 默认降级
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    assert es_fallback_policy() == "error"  # prod 默认抛错（Java 宕机语义）
    monkeypatch.setenv("CAR_MONIT_ES_FALLBACK", "memory")
    assert es_fallback_policy() == "memory"  # 显式覆盖


def test_es_missing_index_raises_parity_exception_without_trip() -> None:
    """索引不存在是确定性错误：不触发熔断，且异常消息与替身逐字一致。"""
    import elasticsearch.exceptions as es_exc

    from app.middleware.real_es import RealEsBackend
    from org.elasticsearch.ElasticsearchException import (
        ElasticsearchStatusException,
    )
    from org.elasticsearch.action.search.SearchRequest import SearchRequest

    class _MissingIndexClient:
        def search(self, **kwargs):
            raise es_exc.NotFoundError(
                404, "index_not_found_exception",
                {"error": {"type": "index_not_found_exception",
                           "reason": "no such index [snapshot_flow]"},
                 "status": 404})

    backend = RealEsBackend("http://127.0.0.1:9200", fallback="memory",
                            client=_MissingIndexClient())
    with pytest.raises(ElasticsearchStatusException) as exc_info:
        backend.search(SearchRequest("snapshot_flow"), memory=lambda: None)
    assert "no such index [snapshot_flow]" in str(exc_info.value)
    assert backend.degraded is False  # 确定性错误 ≠ 服务不可用


# ------------------------------------------------------------- ES 挂载工厂
def _make_es_client():
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.client.RestClient import RestClient
    from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient

    return RestHighLevelClient(
        RestClient.builder(HttpHost("127.0.0.1", 9200, "http")))


def test_es_backend_mounts_by_env(monkeypatch) -> None:
    from app.middleware.real_es import RealEsBackend

    monkeypatch.delenv("CAR_MONIT_ES_URL", raising=False)
    assert _make_es_client()._real is None  # 未设 URL：纯替身

    monkeypatch.setenv("CAR_MONIT_ES_URL", "http://127.0.0.1:9200")
    client = _make_es_client()
    assert isinstance(client._real, RealEsBackend)

    monkeypatch.delenv("CAR_MONIT_ES_URL", raising=False)
    assert _make_es_client()._real is None  # URL 变化重建


def test_es_real_backend_bypasses_p0_guard(monkeypatch) -> None:
    """prod 模式 + 真实后端挂载：search 不再触发 P0-2 拒绝（不再是假操作）。"""
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    monkeypatch.setenv("CAR_MONIT_ES_URL", "http://127.0.0.1:9200")

    from org.elasticsearch.action.search.SearchRequest import SearchRequest

    client = _make_es_client()

    class _StubBackend:
        def search(self, request, memory):
            return "real-ok"

    client._real = _StubBackend()
    assert client.search(SearchRequest("snapshot_flow")) == "real-ok"


# ------------------------------------------- 决策④默认：JDBC currentSchema 透传
def test_jdbc_current_schema_passthrough() -> None:
    from app.db.engine import jdbc_to_sqlalchemy_url

    # 无 query：URL 原样（跟随数据库用户默认 search_path，同 Java 未配置）
    plain = jdbc_to_sqlalchemy_url(
        "jdbc:postgresql://db-host:5432/monit", "user", "pass")
    assert plain == "postgresql+psycopg://user:pass@db-host:5432/monit"

    # currentSchema → psycopg options=-csearch_path=..（pgjdbc 同义行为）
    schema = jdbc_to_sqlalchemy_url(
        "jdbc:postgresql://db-host:5432/monit?currentSchema=jl_data01&ssl=false",
        "user", "pass")
    assert schema == ("postgresql+psycopg://user:pass@db-host:5432/monit"
                      "?options=-csearch_path%3Djl_data01")

    # 多 schema 逗号列表原样透传（search_path 支持逗号分隔）
    multi = jdbc_to_sqlalchemy_url(
        "jdbc:opengauss://h:5432/d?currentSchema=a,b", "u", "p")
    assert multi.endswith("?options=-csearch_path%3Da%2Cb")

    # 其余 query 参数依旧忽略
    ignored = jdbc_to_sqlalchemy_url(
        "jdbc:postgresql://db-host:5432/monit?ssl=false", "u", "p")
    assert ignored == "postgresql+psycopg://u:p@db-host:5432/monit"
