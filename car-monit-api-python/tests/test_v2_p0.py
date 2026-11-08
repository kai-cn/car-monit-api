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


# ---------------------------------------------------------------- P0-4 事务
class _SqliteConfig:
    """Database 的鸭子类型配置（绕开 application.yml / GaussDB 依赖）。"""

    jdbc_url = "jdbc:postgresql://localhost/x"
    db_username = ""
    db_password = ""
    pool_min_idle = 1
    pool_initial_size = 1
    pool_max_active = 2
    pool_max_wait_ms = 5000


def _sqlite_database(tmp_path):
    from sqlalchemy import create_engine

    from app.db.engine import Database

    database = Database(_SqliteConfig())
    database._engine = create_engine("sqlite:///" + str(tmp_path / "tx.db"))
    return database


def test_transaction_commit_rollback_and_visibility(tmp_path) -> None:
    database = _sqlite_database(tmp_path)
    database.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")

    with database.transaction():
        database.execute("INSERT INTO t (v) VALUES ('a')")
        rows = database.query("SELECT count(*) AS c FROM t")
        assert rows[0]["c"] == 1  # 事务内读可见未提交写（同连接语义）
    assert database.query("SELECT count(*) AS c FROM t")[0]["c"] == 1

    with pytest.raises(RuntimeError):
        with database.transaction():
            database.execute("INSERT INTO t (v) VALUES ('b')")
            raise RuntimeError("boom")
    assert [r["v"] for r in database.query("SELECT v FROM t")] == ["a"]

    # 嵌套 = REQUIRED 平铺：内层不提交，外层异常整体回滚
    with pytest.raises(RuntimeError):
        with database.transaction():
            with database.transaction():
                database.execute("INSERT INTO t (v) VALUES ('c')")
            raise RuntimeError("outer")
    assert database.query("SELECT count(*) AS c FROM t")[0]["c"] == 1


class _MemoryInsertMapper:
    """与全局类改写解耦（test_smoke 隔离修复）。

    test_phase2a 的 lifespan 会调用 ``install_mappers()``，经由
    ``app.db.base_mapper.install`` 把 com.baomidou BaseMapper 及各 Mapper
    **类**原地改写为真 SQL（进程级）；本组单测只验证事务编排，必须用
    自包含的内存 insert 与该全局状态解耦——否则会隐性依赖一条可达的
    GaussDB 连接（并往业务表写测试数据）。
    """

    def __init__(self) -> None:
        self.rows: list = []

    def insert(self, entity) -> int:
        self.rows.append(entity)
        return 1


def test_dataprocess_service_rolls_back_on_es_failure(monkeypatch) -> None:
    """Java ``@Transactional(rollbackFor=Exception.class)``：ES 失败 -> 整体回滚。"""
    import contextlib

    import app.db.engine as engine_mod
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )
    from com.ruoyi.mq.service.DataProcessService import DataProcessService

    events: list[str] = []

    class _FakeDatabase:
        @contextlib.contextmanager
        def transaction(self):
            events.append("begin")
            try:
                yield
                events.append("commit")
            except BaseException:
                events.append("rollback")
                raise

    monkeypatch.setattr(engine_mod, "get_database", lambda: _FakeDatabase())

    service = DataProcessService(mapper=_MemoryInsertMapper())
    service.esClient.available = False  # 模拟 ES 集群不可用
    data = OdsRtSzdnSnapshotFlowAddcode()
    data.setId("tx-1")
    with pytest.raises(RuntimeError, match="插入ES失败"):
        service.process(data)
    assert events == ["begin", "rollback"]


def test_dataprocess_service_commits_when_es_succeeds(monkeypatch) -> None:
    import contextlib

    import app.db.engine as engine_mod
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )
    from com.ruoyi.mq.service.DataProcessService import DataProcessService

    events: list[str] = []

    class _FakeDatabase:
        @contextlib.contextmanager
        def transaction(self):
            events.append("begin")
            try:
                yield
                events.append("commit")
            except BaseException:
                events.append("rollback")
                raise

    monkeypatch.setattr(engine_mod, "get_database", lambda: _FakeDatabase())

    service = DataProcessService(mapper=_MemoryInsertMapper())
    data = OdsRtSzdnSnapshotFlowAddcode()
    data.setId("tx-2")
    service.process(data)  # shim 模式：内存 Mapper + 内存 ES 均成功
    assert events == ["begin", "commit"]


# ---------------------------------------------------------------- P0-5 fail-fast
def test_startup_fail_fast_default_and_optout(monkeypatch) -> None:
    from app.runtime import startup_fail_fast

    monkeypatch.delenv("CAR_MONIT_STARTUP_FAIL_FAST", raising=False)
    assert startup_fail_fast() is True
    for value in ("false", "0", "no", "off"):
        monkeypatch.setenv("CAR_MONIT_STARTUP_FAIL_FAST", value)
        assert startup_fail_fast() is False


def test_known_missing_whitelist_covers_the_java_gaps() -> None:
    from app.db.registry import KNOWN_MISSING_STATEMENTS

    assert len(KNOWN_MISSING_STATEMENTS) == 6  # TODO(V2/决策①)：补 SQL 后同步删条目
    assert ("com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper"
            "#selectOdsLwzxsfsjFeeRecords01List") in KNOWN_MISSING_STATEMENTS
    assert ("com.ruoyi.base.mapper.ZdataTrailFittingMapper"
            "#selectZdataTrailFittingList") in KNOWN_MISSING_STATEMENTS


class _FakeMapperReport:
    mappers = statements = patched_methods = 23, 58, 58

    def __init__(self, missing: list[str], failed_files: list[str] | None = None) -> None:
        self.missing_statements = missing
        self.failed_files = failed_files or []
        self.orphan_statements: list[str] = []
        self.annotated_statements: list[str] = []

    def summary(self) -> str:
        return "fake report"


def test_install_persistence_fails_on_unexpected_missing(monkeypatch) -> None:
    import app.db.registry as registry_mod
    from app.main import _install_persistence

    monkeypatch.delenv("CAR_MONIT_STARTUP_FAIL_FAST", raising=False)
    monkeypatch.setattr(registry_mod, "install_mappers",
                        lambda: _FakeMapperReport(["com.ruoyi.base.mapper.FooMapper#bar"]))
    with pytest.raises(RuntimeError, match="unexpected_missing"):
        _install_persistence()


def test_install_persistence_fails_on_install_error(monkeypatch) -> None:
    import app.db.registry as registry_mod
    from app.main import _install_persistence

    monkeypatch.delenv("CAR_MONIT_STARTUP_FAIL_FAST", raising=False)

    def _boom():
        raise RuntimeError("no mapper XML was loaded")

    monkeypatch.setattr(registry_mod, "install_mappers", _boom)
    with pytest.raises(RuntimeError, match="no mapper XML"):
        _install_persistence()


def test_install_persistence_whitelisted_missing_only_warns(monkeypatch, caplog) -> None:
    import app.db.registry as registry_mod
    from app.main import _install_persistence

    monkeypatch.delenv("CAR_MONIT_STARTUP_FAIL_FAST", raising=False)
    monkeypatch.setattr(
        registry_mod, "install_mappers",
        lambda: _FakeMapperReport(
            ["com.ruoyi.base.mapper.ZdataTrailFittingMapper#selectZdataTrailFittingList"]))
    assert _install_persistence() == "fake report"  # 白名单内：仅告警不抛错


# ---------------------------------------------------------------- P0-6 密钥与端点收敛
def test_environment_resolves_value_placeholders(tmp_path, monkeypatch) -> None:
    from org.springframework.core.env.Environment import Environment

    config = tmp_path / "application.yml"
    config.write_text(
        "db:\n  password: ${MY_DB_PASSWORD:}\n  user: ${MY_DB_USER:admin}\n",
        encoding="utf-8")
    monkeypatch.delenv("MY_DB_PASSWORD", raising=False)
    monkeypatch.delenv("MY_DB_USER", raising=False)
    env = Environment([str(config)])
    assert env.getProperty("db.password") == ""  # 默认值为空串
    assert env.getProperty("db.user") == "admin"  # 默认值
    monkeypatch.setenv("MY_DB_PASSWORD", "s3cret")
    assert env.getProperty("db.password") == "s3cret"  # 环境变量最高优先


def test_environment_env_values_are_never_yaml_parsed(monkeypatch) -> None:
    """B1 回归：Spring 环境变量永远是原始字符串，不得按 YAML 标量改写。

    典型受害场景是口令占位符名恰好等于松弛名
    （``SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD``）：
    ``00123`` 被改成 ``123``、``true`` 变 ``True``、``null`` 变空串、
    含 ``" #"`` 被截断。这里逐一覆盖。
    """
    from org.springframework.core.env.Environment import Environment

    env = Environment([])
    cases = {
        "00123": "00123",
        "true": "true",
        "null": "null",
        "p@ss #word": "p@ss #word",
        "  spaced  ": "  spaced  ",  # 环境变量值两端空格同样不得 trim
    }
    for raw, expected in cases.items():
        monkeypatch.setenv("APP_PROBE_PASSWORD", raw)
        assert env.getProperty("app.probe.password") == expected
    # 目标类型转换仍按 @Value 语义工作（字符串原样、布尔/整数再转换）
    monkeypatch.setenv("APP_PROBE_PASSWORD", "true")
    assert env.value("${app.probe.password:false}", str) == "true"
    assert env.value("${app.probe.password:false}", bool) is True
    monkeypatch.setenv("APP_PROBE_PASSWORD", "00123")
    assert env.value("${app.probe.password:0}", int) == 123


def test_environment_local_overlay(tmp_path) -> None:
    from org.springframework.core.env.Environment import Environment

    config = tmp_path / "application.yml"
    config.write_text("db:\n  password: ${DB_PASSWORD:}\n", encoding="utf-8")
    (tmp_path / "application-local.yml").write_text(
        "db:\n  password: from-local\n", encoding="utf-8")
    env = Environment([str(config)])  # 显式传文件时不叠加 local（保持可测性）
    assert env.getProperty("db.password") == ""

    # 默认构造（config_files=None）才会叠加 local；用同目录文件模拟
    import org.springframework.core.env.Environment as env_mod

    original = env_mod._DEFAULT_CONFIG_FILES
    try:
        env_mod._DEFAULT_CONFIG_FILES = [str(config)]
        env2 = env_mod.Environment()
        assert env2.getProperty("db.password") == "from-local"
    finally:
        env_mod._DEFAULT_CONFIG_FILES = original


def test_packaged_yml_contains_no_literal_secrets() -> None:
    yml = ROOT / "pro-business-api" / "src" / "main" / "resources" / "application.yml"
    text = yml.read_text(encoding="utf-8")
    assert "OpenGauss@123" not in text
    assert "${SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD:}" in text
    assert "${ELASTICSEARCH_PASSWORD:}" in text


def test_docs_enabled_gating(monkeypatch) -> None:
    from app.runtime import docs_enabled

    monkeypatch.delenv("CAR_MONIT_DOCS_ENABLED", raising=False)
    monkeypatch.delenv("CAR_MONIT_RUNTIME", raising=False)
    assert docs_enabled() is True  # shim 默认开
    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    assert docs_enabled() is False  # prod 默认关
    monkeypatch.setenv("CAR_MONIT_DOCS_ENABLED", "true")
    assert docs_enabled() is True  # 显式开优先


def test_health_endpoints_and_config_gating(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.health import health_registry
    from app.main import app

    # 与全局探针解耦：更早的用例（test_phase2a 的 lifespan）会把 db 探针注册进
    # 进程级 health_registry 且不卸载；本用例验证"无组件 → UP"分支，临时清空
    # （monkeypatch 结束后恢复原 dict），避免隐性依赖可达的 GaussDB。
    monkeypatch.setattr(health_registry, "_probes", {})
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200  # in-process 无组件 → UP

    monkeypatch.setenv("CAR_MONIT_RUNTIME", "prod")
    monkeypatch.delenv("CAR_MONIT_HEALTH_VERBOSE", raising=False)
    body = client.get("/health").json()
    assert "config" not in body  # prod 默认不泄露中间件地址
    assert body.get("runtime") == "prod"
    monkeypatch.setenv("CAR_MONIT_HEALTH_VERBOSE", "true")
    assert "config" in client.get("/health").json()  # 显式 verbose 可见
