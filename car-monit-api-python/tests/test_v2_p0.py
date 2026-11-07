# -*- coding: utf-8 -*-
"""V2 P0 修复回归测试（依据 docs/迁移审阅报告.md P0 清单）。

P0-2：CAR_MONIT_RUNTIME 运行时模式 —— prod 模式下替身“假成功”操作必须抛
:class:`ShimOperationError`；shim 模式（默认，conftest 已固定）行为与此前完全一致。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from app.runtime import RUNTIME_ENV, ShimOperationError, is_strict, runtime_mode

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- 模式解析
def test_runtime_mode_defaults_to_shim(monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_ENV, raising=False)
    assert runtime_mode() == "shim"
    assert is_strict() is False


@pytest.mark.parametrize("value", ["prod", "PROD", "production", "strict", " Prod "])
def test_runtime_mode_strict_aliases(monkeypatch, value: str) -> None:
    monkeypatch.setenv(RUNTIME_ENV, value)
    assert runtime_mode() == "prod"
    assert is_strict() is True


@pytest.mark.parametrize("value", ["shim", "", "junk", "dev", "test"])
def test_runtime_mode_shim_aliases(monkeypatch, value: str) -> None:
    monkeypatch.setenv(RUNTIME_ENV, value)
    assert runtime_mode() == "shim"
    assert is_strict() is False


# ---------------------------------------------------------------- Kafka
def test_kafka_send_fake_success_in_shim() -> None:
    from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate

    template = KafkaTemplate()
    future = template.send("topic", "key", "value")
    assert future.isDone() is True  # shim：假成功语义保持


def test_kafka_send_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate

    with pytest.raises(ShimOperationError, match="KafkaTemplate.send"):
        KafkaTemplate().send("topic", "key", "value")


# ---------------------------------------------------------------- Pulsar
def test_pulsar_send_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.apache.pulsar.client.api.Producer import Producer

    with pytest.raises(ShimOperationError, match="Pulsar"):
        Producer("persistent://public/default/t").send("v")


def test_pulsar_send_fake_success_in_shim() -> None:
    from org.apache.pulsar.client.api.Producer import Producer

    message_id = Producer("persistent://public/default/t").send("v")
    assert message_id is not None


# ---------------------------------------------------------------- RocketMQ
def test_rocketmq_send_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.apache.rocketmq.client.producer.DefaultMQProducer import DefaultMQProducer

    with pytest.raises(ShimOperationError, match="DefaultMQProducer.send"):
        DefaultMQProducer("group").send(None)


# ---------------------------------------------------------------- Elasticsearch
def _es_client():
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.client.RestClient import RestClient
    from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient

    return RestHighLevelClient(RestClient.builder(HttpHost("localhost", 9200, "http")))


def test_es_data_plane_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.elasticsearch.action.search.SearchRequest import SearchRequest

    client = _es_client()
    with pytest.raises(ShimOperationError, match="RestHighLevelClient.search"):
        client.search(SearchRequest("snapshot_flow"))
    from org.elasticsearch.action.index.IndexRequest import IndexRequest

    with pytest.raises(ShimOperationError, match="RestHighLevelClient.index"):
        client.index(IndexRequest("snapshot_flow"))


def test_es_indices_client_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.elasticsearch.client.indices.GetIndexRequest import GetIndexRequest

    client = _es_client()
    with pytest.raises(ShimOperationError, match="IndicesClient.exists"):
        client.indices().exists(GetIndexRequest("snapshot_flow"))


def test_es_low_level_client_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.elasticsearch.client.Request import Request

    client = _es_client()
    with pytest.raises(ShimOperationError, match="performRequest"):
        client.getLowLevelClient().performRequest(Request("GET", "/_ilm/policy/x"))


# ---------------------------------------------------------------- JdbcTemplate
def test_jdbc_template_noop_in_shim() -> None:
    from org.springframework.jdbc.core.JdbcTemplate import JdbcTemplate

    template = JdbcTemplate()
    assert template.update("REFRESH MATERIALIZED VIEW v") == 0
    assert template.getExecutedSql()


def test_jdbc_template_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from org.springframework.jdbc.core.JdbcTemplate import JdbcTemplate

    with pytest.raises(ShimOperationError, match="JdbcTemplate.update"):
        JdbcTemplate().update("SELECT 1")


# ---------------------------------------------------------------- Redis
def test_redis_write_works_in_shim() -> None:
    from com.ruoyi.common.core.redis.RedisCache import (
        _InMemoryRedisTemplate,
        RedisCache,
    )

    cache = RedisCache(_InMemoryRedisTemplate())
    cache.setCacheObject("k", "v")
    assert cache.getCacheObject("k") == "v"
    assert cache.deleteObject("k") is True


def test_redis_write_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from com.ruoyi.common.core.redis.RedisCache import (
        _InMemoryRedisTemplate,
        RedisCache,
    )
    from org.springframework.data.redis.core.RedisTemplate import RedisTemplate

    cache = RedisCache(_InMemoryRedisTemplate())
    with pytest.raises(ShimOperationError, match="opsForValue\\(\\)\\.set"):
        cache.setCacheObject("k", "v")
    with pytest.raises(ShimOperationError, match="delete"):
        cache.deleteObject("k")
    with pytest.raises(ShimOperationError):
        RedisTemplate().opsForValue().set("k", "v")


def test_redis_read_still_allowed_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from com.ruoyi.common.core.redis.RedisCache import (
        _InMemoryRedisTemplate,
        RedisCache,
    )

    cache = RedisCache(_InMemoryRedisTemplate())
    assert cache.getCacheObject("missing") is None  # 读不受影响
    assert cache.hasKey("missing") is False


# ---------------------------------------------------------------- Forest HTTP
def test_forest_http_rejected_in_prod(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_ENV, "prod")
    from com.ruoyi.base.domain.SuspiciousCarVO import SuspiciousCarVO
    from com.ruoyi.base.forest.HttpSysUtilApiService import (
        ForestHttpSysUtilApiService,
    )

    with pytest.raises(ShimOperationError, match="Forest"):
        ForestHttpSysUtilApiService().syncSuspiciousCarTask(SuspiciousCarVO())


# ---------------------------------------------------------------- 端到端：prod 模式下应用可启动且走降级路径
def test_app_boots_and_degrades_in_prod_mode() -> None:
    """子进程里以 prod 模式完整拉起 app：/health 200，ES 查询抛错后降级 200。

    这验证的是“prod 模式 = 中间件缺失时与 Java 一致的失败/降级路径”，
    而不是把整站打挂（EsIndexManageService.init 的 catch 已镜像 Java）。
    """
    code = (
        "import os\n"
        "os.environ['CAR_MONIT_RUNTIME'] = 'prod'\n"
        "os.environ['APP_SCHEDULER_ENABLED'] = 'false'\n"
        "import bootstrap\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "client = TestClient(app, raise_server_exceptions=False)\n"
        "r = client.get('/health')\n"
        "assert r.status_code == 200, r.text\n"
        "r2 = client.get('/api/v1/unified/snapshot/list', params={\n"
        "    'startTime': '2025-06-01 00:00:00', 'endTime': '2025-06-02 00:00:00'})\n"
        "assert r2.status_code == 200, r2.text\n"
        "body = r2.json()\n"
        "assert body.get('code') == 200 and body.get('data') == [], body\n"
        "print('PROD-BOOT-OK')\n"
    )
    env = dict(os.environ)
    env["CAR_MONIT_RUNTIME"] = "prod"
    env["APP_SCHEDULER_ENABLED"] = "false"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=180,
        env=env,
    )
    assert result.returncode == 0, (
        "prod 模式子进程失败:\nSTDOUT:\n%s\nSTDERR:\n%s" % (result.stdout, result.stderr))
    assert "PROD-BOOT-OK" in result.stdout


# ---------------------------------------------------------------- P0-3 Bean 生命周期
def test_beans_disabled_by_default(monkeypatch) -> None:
    from app import beans

    monkeypatch.delenv("APP_BEANS_ENABLED", raising=False)
    beans.shutdown_beans()
    assert beans.beans_enabled() is False
    note = beans.start_beans()
    assert "disabled" in note
    assert beans.is_started() is False


def test_beans_lifecycle_with_stubs(monkeypatch) -> None:
    from app import beans

    monkeypatch.setenv("APP_BEANS_ENABLED", "true")
    calls: list[str] = []

    class _Stub:
        def __init__(self) -> None:
            calls.append("init:" + type(self).__name__)

        def destroy(self) -> None:
            calls.append("destroy:" + type(self).__name__)

    class _BeanA(_Stub):
        pass

    class _BeanB(_Stub):
        pass

    beans.shutdown_beans()
    note = beans.start_beans((_BeanA, _BeanB))
    assert beans.is_started() is True
    assert "2 bean(s)" in note
    assert calls == ["init:_BeanA", "init:_BeanB"]
    assert beans.start_beans((_BeanA,)) == note  # 幂等
    beans.shutdown_beans()
    assert "destroy:_BeanA" in calls and "destroy:_BeanB" in calls
    assert beans.is_started() is False


def test_beans_real_classes_construct_and_destroy(monkeypatch) -> None:
    """shim + 内存 Mapper：fullSync 空表立即完成、重试线程首查为空后睡眠（daemon）。"""
    from app import beans

    monkeypatch.setenv("APP_BEANS_ENABLED", "true")
    beans.shutdown_beans()
    note = beans.start_beans()
    try:
        assert beans.is_started() is True
        names = beans.started_beans()
        assert any("SnapshotFlowSyncService" in n for n in names), names
        assert any("KafkaProducerService" in n for n in names), names
        assert any("ElasticsearchQueryService" in n for n in names), names
    finally:
        beans.shutdown_beans()
