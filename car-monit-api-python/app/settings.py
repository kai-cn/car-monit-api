# -*- coding: utf-8 -*-
"""Typed access to ``application.yml`` (Spring ``@Value`` equivalent).

Migrated from: pro-business-api/src/main/resources/application.yml

The Java service has no ``@ConfigurationProperties`` class: every consumer
uses ``@Value("${key:default}")``. The ported business classes already call
``org.springframework.core.env.Environment#value`` (see
``CompositeQueryOptimizationService``), so this module is only a typed facade
over the *same* Environment singleton -- there is exactly one configuration
source, exactly like Spring.

Priority order (identical to Spring):
    environment variables (SYNC_BATCH_SIZE)
      > application.yml
      > the inline default inside the placeholder
"""
from __future__ import annotations

import re
from typing import Any, Optional

from org.springframework.core.env.Environment import Environment, getEnvironment

__all__ = ["Settings", "settings"]

# spring.redis.lettuce.pool.max-wait is written as "-1ms" in application.yml
_MILLIS_RE = re.compile(r"^(-?\d+)\s*(ms|s|m)?$")

_REASON_UNITS = {"ms": 1, "s": 1000, "m": 60_000, None: 1}


class Settings:
    """Facade over ``org.springframework.core.env.Environment``."""

    def __init__(self, environment: Optional[Environment] = None) -> None:
        self._env = environment or getEnvironment()

    # ------------------------------------------------------------------ raw
    def raw(self, key: str, default: Any = None) -> Any:
        return self._env.getProperty(key, default)

    def text(self, key: str, default: str = "") -> str:
        value = self._env.getProperty(key, default)
        return default if value is None else str(value)

    def integer(self, key: str, default: int = 0) -> int:
        value = self._env.getProperty(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def boolean(self, key: str, default: bool = False) -> bool:
        value = self._env.getProperty(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in ("true", "1", "yes", "y", "on")

    def millis(self, key: str, default: int = 0) -> int:
        """Parse ``60000`` / ``-1ms`` / ``100ms`` into milliseconds."""
        value = self._env.getProperty(key, default)
        if isinstance(value, bool) or value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)
        match = _MILLIS_RE.match(str(value).strip())
        if not match:
            return default
        return int(match.group(1)) * _REASON_UNITS[match.group(2)]

    def placeholder(self, expression: str, target_type: type = str) -> Any:
        """Resolve ``${key:default}`` exactly like ``@Value``."""
        return self._env.value(expression, target_type)

    # ------------------------------------------------------------------ server
    @property
    def server_port(self) -> int:
        return self.integer("server.port", 9901)

    @property
    def context_path(self) -> str:
        path = self.text("server.servlet.context-path", "/")
        return "" if path == "/" else path.rstrip("/")

    @property
    def worker_threads(self) -> int:
        """P1-2：``app.server.worker-threads``——anyio 线程池令牌数（等价 Tomcat max-threads）。

        README 此前提到该配置但从未实现（报告 Q3）；默认 40 与 anyio 缺省一致。
        """
        return max(1, self.integer("app.server.worker-threads", 40))

    # ------------------------------------------------------------------ datasource
    @property
    def jdbc_url(self) -> str:
        return self.text(
            "spring.datasource.dynamic.datasource.master.url",
            "jdbc:postgresql://127.0.0.1:5432/RuoYi",
        )

    @property
    def db_username(self) -> str:
        return self.text("spring.datasource.dynamic.datasource.master.username", "")

    @property
    def db_password(self) -> str:
        return self.text("spring.datasource.dynamic.datasource.master.password", "")

    @property
    def db_driver(self) -> str:
        return self.text(
            "spring.datasource.dynamic.datasource.master.driver-class-name",
            "org.postgresql.Driver",
        )

    # Druid pool settings (druid.* is the global block in application.yml)
    @property
    def pool_initial_size(self) -> int:
        return self.integer("spring.datasource.dynamic.druid.initial-size", 5)

    @property
    def pool_min_idle(self) -> int:
        return self.integer("spring.datasource.dynamic.druid.min-idle", 5)

    @property
    def pool_max_active(self) -> int:
        return self.integer("spring.datasource.dynamic.druid.maxActive", 20)

    @property
    def pool_max_wait_ms(self) -> int:
        return self.integer("spring.datasource.dynamic.druid.maxWait", 60_000)

    @property
    def pool_validation_query(self) -> str:
        return self.text("spring.datasource.dynamic.druid.validationQuery", "SELECT 1")

    @property
    def p6spy_enabled(self) -> bool:
        """``spring.datasource.dynamic.p6spy``: print the fully expanded SQL."""
        return self.boolean("spring.datasource.dynamic.p6spy", False)

    # ------------------------------------------------------------------ mybatis
    @property
    def mapper_locations(self) -> str:
        return self.text(
            "mybatis-plus.mapper-locations",
            "classpath*:com/ruoyi/base/**/xml/*Mapper.xml",
        )

    @property
    def type_aliases_package(self) -> str:
        return self.text("mybatis-plus.type-aliases-package", "com.ruoyi.base.domain")

    @property
    def map_underscore_to_camel_case(self) -> bool:
        return self.boolean("mybatis-plus.configuration.map-underscore-to-camel-case", True)

    @property
    def call_setters_on_nulls(self) -> bool:
        return self.boolean("mybatis-plus.configuration.call-setters-on-nulls", True)

    # ------------------------------------------------------------------ redis
    @property
    def redis_host(self) -> str:
        return self.text("spring.redis.host", "127.0.0.1")

    @property
    def redis_port(self) -> int:
        return self.integer("spring.redis.port", 6379)

    @property
    def redis_database(self) -> int:
        return self.integer("spring.redis.database", 0)

    @property
    def redis_password(self) -> Optional[str]:
        value = self.raw("spring.redis.password", None)
        return None if value in (None, "") else str(value)

    @property
    def redis_pool_max_active(self) -> int:
        return self.integer("spring.redis.lettuce.pool.max-active", 8)

    @property
    def redis_pool_max_idle(self) -> int:
        return self.integer("spring.redis.lettuce.pool.max-idle", 8)

    @property
    def redis_pool_max_wait_ms(self) -> int:
        return self.millis("spring.redis.lettuce.pool.max-wait", -1)

    @property
    def redis_cluster_nodes(self) -> str:
        """``rediscluster.clusterNodes`` -- used by the JedisCluster dictionary cache."""
        return self.text("rediscluster.clusterNodes", "")

    # ------------------------------------------------------------------ kafka
    @property
    def kafka_bootstrap_servers(self) -> str:
        return self.text("spring.kafka.bootstrap-servers", "localhost:9092")

    # ------------------------------------------------------------------ elasticsearch
    @property
    def es_scheme(self) -> str:
        return self.text("elasticsearch.scheme", "http")

    @property
    def es_host(self) -> str:
        return self.text("elasticsearch.host", "localhost")

    @property
    def es_port(self) -> int:
        return self.integer("elasticsearch.port", 9200)

    @property
    def es_username(self) -> Optional[str]:
        value = self.raw("elasticsearch.username", None)
        return None if value in (None, "") else str(value)

    @property
    def es_password(self) -> Optional[str]:
        value = self.raw("elasticsearch.password", None)
        return None if value in (None, "") else str(value)

    @property
    def es_connection_timeout_ms(self) -> int:
        return self.integer("elasticsearch.connection-timeout", 30_000)

    @property
    def es_socket_timeout_ms(self) -> int:
        return self.integer("elasticsearch.socket-timeout", 30_000)

    @property
    def es_index_snapshot(self) -> str:
        return self.text("elasticsearch.index.snapshot", "snapshot_flow")

    @property
    def es_index_fee(self) -> str:
        return self.text("elasticsearch.index.fee", "fee_records")

    @property
    def es_index_trail(self) -> str:
        return self.text("elasticsearch.index.trail", "trail_fitting")

    @property
    def es_index_auto_create(self) -> bool:
        return self.boolean("elasticsearch.index.auto-create", False)

    # ------------------------------------------------------------------ misc
    @property
    def is_localhost(self) -> str:
        """``isLocalhost: local`` -- "local" or "prod" deployment marker."""
        return self.text("isLocalhost", "local")

    @property
    def sys_base_url(self) -> str:
        return self.text("sysbaseUrl", "http://223.84.150.189:26066/prod-api")

    @property
    def export_dir(self) -> str:
        return self.text("optimization.export.dir", "/data/export")

    @property
    def consistency_reconcile_enabled(self) -> bool:
        return self.boolean("consistency.reconcile.enabled", False)

    @property
    def scheduler_enabled(self) -> bool:
        """Mirror ``@EnableScheduling``: tasks are on unless explicitly disabled."""
        return self.boolean("app.scheduler.enabled", True)

    # ------------------------------------------------------------------ health
    def describe(self) -> dict:
        """Safe subset for ``/health`` (never expose credentials)."""
        return {
            "server.port": self.server_port,
            "datasource": _redact_jdbc(self.jdbc_url),
            "redis": f"{self.redis_host}:{self.redis_port}/{self.redis_database}",
            "elasticsearch": f"{self.es_scheme}://{self.es_host}:{self.es_port}",
            "kafka": self.kafka_bootstrap_servers,
            "isLocalhost": self.is_localhost,
            "scheduler.enabled": self.scheduler_enabled,
        }


def _redact_jdbc(url: str) -> str:
    """Drop the query string (it may carry credentials) from a JDBC URL."""
    return url.split("?", 1)[0]


settings = Settings()
