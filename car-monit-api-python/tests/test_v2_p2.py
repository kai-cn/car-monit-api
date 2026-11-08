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


def test_codec_unrecognized_returns_miss() -> None:
    """H3：无法识别的内容返回未命中（None），不能把原始字符串当缓存值。"""
    from app.middleware.real_redis import decode

    assert decode(b"not-json") is None
    assert decode(b"") is None
    assert decode(None) is None


def test_codec_fastjson_long_and_dates() -> None:
    """H3：FastJson 的 123L、毫秒时间戳、文本日期都能还原到实体字段类型。"""
    import datetime as _dt

    from app.middleware.real_redis import decode

    from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (
        OdsSzdnProvinceBorderVehicleWeightNewstructure,
    )
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )

    # 真实 Java Redis 里的非标准 JSON：52650L
    weight = decode(
        b'{"@type":"com.ruoyi.base.domain.'
        b'OdsSzdnProvinceBorderVehicleWeightNewstructure","vehicleWeight":52650L}')
    assert isinstance(weight, OdsSzdnProvinceBorderVehicleWeightNewstructure)
    assert weight.getVehicleWeight() == 52650

    # 毫秒时间戳（fastjson 默认 Date 写法）+ 文本日期（yyyy-MM-dd HH:mm:ss）
    snapshot = decode(
        '{"@type":"com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode",'
        '"snapshottime":1699999999999,'
        '"receivedtime":"2026-01-02 03:04:05"}')
    assert isinstance(snapshot, OdsRtSzdnSnapshotFlowAddcode)
    assert snapshot.getSnapshottime() == _dt.datetime.fromtimestamp(1699999999.999)
    assert snapshot.getReceivedtime() == _dt.datetime(2026, 1, 2, 3, 4, 5)

    # 裸标量写法
    assert decode(b"123L") == 123
    assert decode(b"new Date(1699999999999)") == _dt.datetime.fromtimestamp(1699999999.999)


def test_codec_type_whitelist_blocks_arbitrary_reflection(monkeypatch) -> None:
    """H3：@type 反射只允许 com.ruoyi / org.springframework，白名单外只返回 dict。"""
    import dataclasses
    import sys
    import types

    from app.middleware.real_redis import decode

    module = types.ModuleType("evil_redis_payload")

    @dataclasses.dataclass
    class Evil:
        pwned: str = ""

    Evil.__module__ = "evil_redis_payload"
    module.Evil = Evil
    monkeypatch.setitem(sys.modules, "evil_redis_payload", module)

    restored = decode(b'{"@type":"evil_redis_payload.Evil","pwned":"yes"}')
    assert isinstance(restored, dict)
    assert not isinstance(restored, Evil)
    assert restored == {"pwned": "yes"}  # @type 被剥离


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
# ------------------------------------------------------- H2 熔断窗口回归
class _Clock:
    """可手动推进的 monotonic 时钟（避免测试里真的 sleep 60 秒）。"""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


def test_redis_breaker_refreshes_window_on_every_failure(monkeypatch) -> None:
    """连续两个窗口：探测失败后必须重新计时，而不是每次调用都直连。"""
    import redis as redis_py

    from app.middleware.real_redis import RealRedisTemplate

    clock = _Clock()
    monkeypatch.setattr("app.middleware.breaker.time", clock)

    class _Broken:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, key):
            self.calls += 1
            raise redis_py.ConnectionError("down")

    client = _Broken()
    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="memory",
                                 client=client)

    assert template.opsForValue().get("k") is None
    assert client.calls == 1 and template.degraded is True
    clock.now = 30.0
    assert template.opsForValue().get("k") is None
    assert client.calls == 1                      # 窗口内不直连
    clock.now = 61.0
    assert template.opsForValue().get("k") is None
    assert client.calls == 2                      # 半开探测一次
    clock.now = 62.0
    assert template.opsForValue().get("k") is None
    assert client.calls == 2                      # 失败后重新计时，不再直连
    clock.now = 122.0
    assert template.opsForValue().get("k") is None
    assert client.calls == 3                      # 第二个窗口的探测


def test_redis_half_open_allows_only_one_probe(monkeypatch) -> None:
    import threading

    import redis as redis_py

    from app.middleware.real_redis import RealRedisTemplate

    clock = _Clock()
    monkeypatch.setattr("app.middleware.breaker.time", clock)

    class _Blocking:
        def __init__(self) -> None:
            self.calls = 0
            self.entered = threading.Event()
            self.release = threading.Event()

        def get(self, key):
            self.calls += 1
            self.entered.set()
            self.release.wait(5)
            raise redis_py.ConnectionError("down")

    client = _Blocking()
    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="memory",
                                 client=client)
    template.opsForValue().get("k")                # 首次失败 → 熔断
    clock.now = 61.0

    results: list = []
    thread = threading.Thread(
        target=lambda: results.append(template.opsForValue().get("k")))
    thread.start()
    assert client.entered.wait(3)                  # 探测已在途
    assert template.opsForValue().get("k") is None  # 并发调用直接走内存
    assert client.calls == 2                        # 只放行一个真实探测
    client.release.set()
    thread.join(5)
    assert results == [None]
    assert template.degraded is True


def test_es_breaker_refreshes_window_on_every_failure(monkeypatch) -> None:
    import elasticsearch.exceptions as es_exc

    from app.middleware.real_es import RealEsBackend

    clock = _Clock()
    monkeypatch.setattr("app.middleware.breaker.time", clock)

    class _Broken:
        def __init__(self) -> None:
            self.calls = 0

        def ping(self):
            self.calls += 1
            raise es_exc.ConnectionError("N/A", "down", None)

    client = _Broken()
    backend = RealEsBackend("http://127.0.0.1:1", fallback="memory", client=client)

    assert backend.ping(memory=lambda: True) is True
    assert client.calls == 1 and backend.degraded is True
    clock.now = 30.0
    assert backend.ping(memory=lambda: True) is True
    assert client.calls == 1
    clock.now = 61.0
    assert backend.ping(memory=lambda: True) is True
    assert client.calls == 2
    clock.now = 62.0
    assert backend.ping(memory=lambda: True) is True
    assert client.calls == 2                       # 失败后重新计时
    clock.now = 122.0
    assert backend.ping(memory=lambda: True) is True
    assert client.calls == 3


def test_kafka_breaker_refreshes_window_on_every_failure(monkeypatch) -> None:
    from confluent_kafka import KafkaError

    from app.middleware.real_kafka import RealKafkaProducer

    clock = _Clock()
    monkeypatch.setattr("app.middleware.breaker.time", clock)

    class _Broken:
        def __init__(self) -> None:
            self.calls = 0

        def produce(self, topic, key, value, on_delivery):
            self.calls += 1
            on_delivery(KafkaError(KafkaError._ALL_BROKERS_DOWN, "down"), None)

        def flush(self, timeout=None):
            return 0

    client = _Broken()
    producer = RealKafkaProducer("127.0.0.1:1", fallback="memory", client=client)

    # 首条真实发送：送达回调同步报错 → 熔断，但本条仍是失败 future（不静默重投）
    producer.send("t", "k", "v", memory=lambda: "memory-ok")
    assert client.calls == 1 and producer.degraded is True
    clock.now = 30.0
    assert producer.send("t", "k", "v", memory=lambda: "memory-ok") == "memory-ok"
    assert client.calls == 1
    clock.now = 61.0
    producer.send("t", "k", "v", memory=lambda: "memory-ok")
    assert client.calls == 2
    clock.now = 62.0
    assert producer.send("t", "k", "v", memory=lambda: "memory-ok") == "memory-ok"
    assert client.calls == 2                       # 失败后重新计时
    clock.now = 122.0
    producer.send("t", "k", "v", memory=lambda: "memory-ok")
    assert client.calls == 3


def test_es_response_decimals_are_parsed_exactly() -> None:
    """H1 回归：真实 ES 响应用 parse_float=Decimal，金额不先降成 float。"""
    from decimal import Decimal

    from app.middleware.real_es import _DECIMAL_SERIALIZER, _build_search_response
    from com.alibaba.fastjson2.JSON import JSON
    from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01

    raw = _DECIMAL_SERIALIZER.loads(
        '{"hits":{"total":{"value":1},"hits":[{"_index":"fee_records","_id":"1",'
        '"_score":1.0,"_source":{"fee":1.50,'
        '"payfee":12345678901234567890.12}}]}}')
    source_map = raw["hits"]["hits"][0]["_source"]
    assert isinstance(source_map["fee"], Decimal)
    assert str(source_map["fee"]) == "1.50"

    response = _build_search_response(raw, with_scroll=False)
    source_text = response.getHits().getHits()[0].getSourceAsString()
    assert '"fee":1.50' in source_text
    entity = JSON.parseObject(source_text, OdsLwzxsfsjFeeRecords01)
    assert entity.getFee() == Decimal("1.50")
    assert entity.getPayfee() == Decimal("12345678901234567890.12")


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


# ============================================================== Kafka 适配（P2-4）
def test_kafka_fallback_policy_env_and_runtime_default(monkeypatch) -> None:
    from app.middleware.real_kafka import kafka_fallback_policy

    monkeypatch.delenv("CAR_MONIT_KAFKA_FALLBACK", raising=False)
    monkeypatch.delenv("CAR_MONIT_RUNTIME", raising=False)
    assert kafka_fallback_policy() == "memory"  # shim 默认降级
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    assert kafka_fallback_policy() == "error"  # prod 默认抛错（Java 宕机语义）
    monkeypatch.setenv("CAR_MONIT_KAFKA_FALLBACK", "memory")
    assert kafka_fallback_policy() == "memory"  # 显式覆盖


def test_kafka_consumer_conf_from_props(monkeypatch) -> None:
    from app.middleware.real_kafka import consumer_conf_from_props

    monkeypatch.setenv("CAR_MONIT_KAFKA_URL", "127.0.0.1:9092")
    conf = consumer_conf_from_props({
        "bootstrap.servers": "prod-kafka:9092",  # env 覆盖（真实集群唯一事实源）
        "group.id": "flink-cdc-consumer",
        "auto.offset.reset": "latest",
        "enable.auto.commit": "false",
    })
    assert conf == {
        "bootstrap.servers": "127.0.0.1:9092",
        "group.id": "flink-cdc-consumer",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    }


def test_simple_string_schema_replaces_invalid_utf8() -> None:
    """Java new String(bytes, UTF_8) 语义：非法序列替换为 U+FFFD，不抛错。"""
    from org.apache.flink.api.common.serialization.SimpleStringSchema import (
        SimpleStringSchema,
    )

    schema = SimpleStringSchema()
    assert schema.deserialize(b"\xff\xfe\xfa") == "\ufffd\ufffd\ufffd"
    assert schema.deserialize("正常".encode()) == "正常"


class _SyncFailProducer:
    """produce() 同步抛 KafkaException 的假客户端。"""

    def __init__(self, error_code: int) -> None:
        self._error_code = error_code

    def produce(self, **kwargs):
        from confluent_kafka import KafkaError, KafkaException

        raise KafkaException(KafkaError(self._error_code, "test failure"))

    def flush(self, timeout=None):
        return 0


class _DeliveryFailProducer:
    """送达回调报错的假客户端（同步触发 on_delivery）。"""

    def __init__(self, error_code: int) -> None:
        self._error_code = error_code

    def produce(self, topic, key, value, on_delivery):
        from confluent_kafka import KafkaError

        on_delivery(KafkaError(self._error_code, "test failure"), None)

    def flush(self, timeout=None):
        return 0


def test_kafka_sync_failure_trips_memory() -> None:
    from confluent_kafka import KafkaError

    from app.middleware.real_kafka import RealKafkaProducer

    backend = RealKafkaProducer(
        "127.0.0.1:1", fallback="memory",
        client=_SyncFailProducer(KafkaError._ALL_BROKERS_DOWN))
    assert backend.degraded is False
    result = backend.send("t", "k", "v", memory=lambda: "memory-ok")
    assert result == "memory-ok"
    assert backend.degraded is True


def test_kafka_sync_failure_error_policy_raises() -> None:
    from confluent_kafka import KafkaError, KafkaException

    from app.middleware.real_kafka import RealKafkaProducer

    backend = RealKafkaProducer(
        "127.0.0.1:1", fallback="error",
        client=_SyncFailProducer(KafkaError._ALL_BROKERS_DOWN))
    with pytest.raises(KafkaException):
        backend.send("t", "k", "v", memory=lambda: "memory-ok")


def test_kafka_sync_deterministic_failure_no_trip() -> None:
    """produce() 的同步确定性错误（消息超限的客户端侧拦截）：只失败该条，不熔断。"""
    from confluent_kafka import KafkaError

    from app.middleware.real_kafka import RealKafkaProducer

    backend = RealKafkaProducer(
        "127.0.0.1:1", fallback="memory",
        client=_SyncFailProducer(KafkaError.MSG_SIZE_TOO_LARGE))
    errors: list = []
    backend.send("t", "k", "v",
                 memory=lambda: pytest.fail("确定性错误不应降级")).addCallback(
        lambda _r: None, lambda e: errors.append(str(e)))
    assert backend.degraded is False
    assert len(errors) == 1 and "MSG_SIZE_TOO_LARGE" in errors[0]


def test_kafka_delivery_outage_trips_but_deterministic_does_not() -> None:
    from confluent_kafka import KafkaError

    from app.middleware.real_kafka import RealKafkaProducer

    # 疑似不可用（broker 全不可达）→ 熔断 + 该条进失败 future
    outage = RealKafkaProducer(
        "127.0.0.1:1", fallback="memory",
        client=_DeliveryFailProducer(KafkaError._ALL_BROKERS_DOWN))
    errors: list = []
    outage.send("t", "k", "v", memory=lambda: "m").addCallback(
        lambda _r: None, lambda e: errors.append(str(e)))
    assert outage.degraded is True
    assert len(errors) == 1 and "ALL_BROKERS_DOWN" in errors[0]

    # 确定性错误（消息超限）→ 只失败该条，不熔断
    deterministic = RealKafkaProducer(
        "127.0.0.1:1", fallback="memory",
        client=_DeliveryFailProducer(KafkaError.MSG_SIZE_TOO_LARGE))
    errors2: list = []
    deterministic.send("t", "k", "v", memory=lambda: "m").addCallback(
        lambda _r: None, lambda e: errors2.append(str(e)))
    assert deterministic.degraded is False
    assert len(errors2) == 1 and "MSG_SIZE_TOO_LARGE" in errors2[0]


def test_kafka_send_success_future_completes() -> None:
    from org.springframework.kafka.support.SendResult import SendResult

    from app.middleware.real_kafka import RealKafkaProducer

    class _FakeMsg:
        def topic(self):
            return "topic-x"

        def partition(self):
            return 0

        def offset(self):
            return 7

    class _OkProducer:
        def produce(self, topic, key, value, on_delivery):
            on_delivery(None, _FakeMsg())

        def flush(self, timeout=None):
            return 0

    backend = RealKafkaProducer("127.0.0.1:9092", fallback="error",
                                client=_OkProducer())
    got: list = []
    backend.send("topic-x", "k", {"a": 1}, memory=lambda: None).addCallback(
        lambda r: got.append(r), lambda e: pytest.fail(str(e)))
    assert len(got) == 1
    result = got[0]
    assert isinstance(result, SendResult)
    assert result.getRecordMetadata().offset() == 7
    assert result.getProducerRecord() == ("topic-x", "k", {"a": 1})


# ------------------------------------------------------- H6 优雅关闭
def test_real_adapters_close_underlying_clients() -> None:
    from app.middleware.real_es import RealEsBackend
    from app.middleware.real_redis import RealRedisTemplate

    class _Closable:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    redis_client = _Closable()
    template = RealRedisTemplate("redis://127.0.0.1:1/0", fallback="memory",
                                 client=redis_client)
    template.close()
    template.close()
    assert redis_client.closed == 2  # 幂等：重复关闭不报错

    es_client = _Closable()
    backend = RealEsBackend("http://127.0.0.1:1", fallback="memory",
                            client=es_client)
    backend.close()
    assert es_client.closed == 1


def test_shutdown_middleware_covers_all_backends(monkeypatch) -> None:
    """H6：Kafka/ES/Redis/DB 都被关闭，且重复调用安全。"""
    import app.db.engine as engine
    import app.middleware as middleware
    import app.middleware.real_es as real_es
    import app.middleware.real_kafka as real_kafka
    import com.ruoyi.common.core.redis.RedisCache as redis_cache

    calls: list[str] = []
    monkeypatch.setattr(real_kafka, "close_shared_kafka_producer",
                        lambda: calls.append("kafka"))
    monkeypatch.setattr(real_es, "close_shared_es_backend",
                        lambda: calls.append("es"))
    monkeypatch.setattr(redis_cache, "close_shared_redis_template",
                        lambda: calls.append("redis"))
    monkeypatch.setattr(engine, "close_database",
                        lambda: calls.append("db"))

    middleware.shutdown_middleware()
    middleware.shutdown_middleware()
    assert calls == ["kafka", "es", "redis", "db",
                     "kafka", "es", "redis", "db"]


def test_kafka_mount_factory(monkeypatch) -> None:
    from app.middleware.real_kafka import RealKafkaProducer
    from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate

    monkeypatch.delenv("CAR_MONIT_KAFKA_URL", raising=False)
    assert KafkaTemplate()._real is None  # 未设 URL：纯替身

    monkeypatch.setenv("CAR_MONIT_KAFKA_URL", "127.0.0.1:9092")
    template = KafkaTemplate()
    assert isinstance(template._real, RealKafkaProducer)
    assert KafkaTemplate()._real is template._real  # 进程级共享（等价单例 Bean）

    monkeypatch.delenv("CAR_MONIT_KAFKA_URL", raising=False)
    assert KafkaTemplate()._real is None  # URL 变化重建


def test_kafka_real_backend_bypasses_p0_guard(monkeypatch) -> None:
    """prod 模式 + 真实后端挂载：send 不再触发 P0-2 拒绝（不再是假操作）。"""
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    monkeypatch.setenv("CAR_MONIT_KAFKA_URL", "127.0.0.1:9092")

    from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate

    template = KafkaTemplate()

    class _StubBackend:
        def send(self, topic, key, value, memory):
            return "real-ok"

    template._real = _StubBackend()
    assert template.send("topic", "key", "value") == "real-ok"
