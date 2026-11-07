# -*- coding: utf-8 -*-
"""GaussDB (PostgreSQL wire protocol) connection pool.

Migrated from: application.yml ``spring.datasource.dynamic.druid``
                + ``dynamic-datasource`` (single ``master`` datasource)

Mapping:
    Druid initial-size / min-idle   -> QueuePool pool_size
    Druid maxActive                 -> pool_size + max_overflow
    Druid maxWait (ms)              -> pool_timeout (s)
    Druid validationQuery           -> pool_pre_ping
    dynamic-datasource ``master``   -> the only engine (there is no @DS usage)

The JDBC URL keeps the Java query string (``characterEncoding``,
``serverTimezone`` ...). Those are MySQL-oriented parameters the PostgreSQL
driver ignores; they are stripped, only ``currentSchema`` is honoured.

Two driver-level differences with pgjdbc are compensated here, both inside
:meth:`Database._create_engine`:

* openGauss/GaussDB reports an ``openGauss 3.0.0`` version banner that
  SQLAlchemy refuses to parse -> :func:`install_gaussdb_version_shim`.
* psycopg sends strings with the *unknown* OID while pgjdbc sends ``varchar``,
  which makes ``concat('%', ?, '%')`` fail to resolve -> ``StrDumperVarchar``.
"""
from __future__ import annotations

import logging
import re
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Optional
from urllib.parse import quote

from psycopg.types.string import StrDumperVarchar
from sqlalchemy import create_engine, event, text
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine import Connection, Engine

from app.settings import Settings, settings as default_settings

log = logging.getLogger(__name__)

__all__ = [
    "Database",
    "get_database",
    "jdbc_to_sqlalchemy_url",
    "install_gaussdb_version_shim",
]

#: 线程本地的事务上下文（P0-4，@Transactional 等价物）。
#: FastAPI 的同步 handler 跑在 worker 线程里，每个线程至多一个未决事务。
_TX_LOCAL = threading.local()

_JDBC_PREFIXES = ("jdbc:postgresql://", "jdbc:opengauss://", "jdbc:gaussdb://")

# openGauss 3.0 is wire/feature compatible with PostgreSQL 9.2; pgjdbc 42.2.x
# (the driver the Java project uses) supports 8.2+, so that is the level the
# Java side has always been talking to.
_GAUSS_SERVER_VERSION = (9, 2, 4)
_GAUSS_SERVER_RE = re.compile(r"(?:openGauss|GaussDB)", re.I)


def install_gaussdb_version_shim() -> None:
    """Teach SQLAlchemy to accept the ``openGauss`` server version banner.

    ``SELECT version()`` on GaussDB/openGauss returns
    ``(openGauss 3.0.0 build 02c14696) compiled at ...`` instead of
    ``PostgreSQL 9.2.4 ...``. SQLAlchemy's ``first_connect`` hook calls
    ``PGDialect._get_server_version_info``, which asserts on the missing
    ``PostgreSQL`` prefix and aborts the very first connection.

    The Java side never noticed because pgjdbc only reads the numeric part.
    We therefore report the PostgreSQL level GaussDB 3.0 implements. The hook
    is installed once per process and is a no-op for real PostgreSQL servers.
    """
    if getattr(PGDialect, "_gaussdb_shim", False):
        return
    original = PGDialect._get_server_version_info

    def _get_server_version_info(self, connection):
        banner = connection.exec_driver_sql("select pg_catalog.version()").scalar() or ""
        if _GAUSS_SERVER_RE.search(banner):
            return _GAUSS_SERVER_VERSION
        return original(self, connection)

    PGDialect._get_server_version_info = _get_server_version_info
    PGDialect._gaussdb_shim = True


install_gaussdb_version_shim()


def jdbc_to_sqlalchemy_url(jdbc_url: str, username: str, password: str) -> str:
    """``jdbc:postgresql://h:p/db?...`` -> ``postgresql+psycopg://u:p@h:p/db``。

    TODO(V2/决策④)：JDBC URL query 串（含 ``currentSchema``）当前被整体丢弃——
    若生产 GaussDB 依赖 ``currentSchema`` 定位业务表（而非每条 SQL 写全限定名/
    ``TABLE_SCHEMAS``），需要在这里解析并传给 psycopg（``options=-csearch_path=..``）。
    生产 ``search_path`` 到底是什么属 docs/迁移审阅报告.md §6.2 D5 待业主确认项，
    确认后若需支持请补解析 + 单测。
    """
    raw = jdbc_url.strip()
    for prefix in _JDBC_PREFIXES:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    head, _, _query = raw.partition("?")
    netloc, _, database = head.partition("/")
    credentials = ""
    if username:
        credentials = quote(username, safe="")
        if password:
            credentials += ":" + quote(password, safe="")
        credentials += "@"
    return f"postgresql+psycopg://{credentials}{netloc}/{database}"


def _install_pgjdbc_string_dumper(engine: Engine) -> None:
    """Bind ``str`` parameters as ``varchar``, mirroring pgjdbc's ``setString``.

    psycopg's default string dumper uses the *unknown* OID and leaves the type
    to the server. That resolution fails inside variadic functions, and every
    LIKE clause in this project's XML mappers is written as
    ``like concat('%', #{name}, '%')``:

        psycopg.errors.ProgrammingError: could not determine data type of parameter $1

    pgjdbc sends ``Oid.VARCHAR`` for ``setString``, so the Java service has
    always executed ``concat(text, varchar, text)``. Registering
    ``StrDumperVarchar`` per connection restores that behaviour; integers,
    booleans and decimals keep their inferred types.
    """

    @event.listens_for(engine, "connect")
    def _register_string_dumper(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        dbapi_connection.adapters.register_dumper(str, StrDumperVarchar)


class Database:
    """Thin wrapper over a SQLAlchemy engine (singleton per process)."""

    def __init__(self, config: Optional[Settings] = None) -> None:
        self._config = config or default_settings
        self._engine: Optional[Engine] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ engine
    @property
    def url(self) -> str:
        return jdbc_to_sqlalchemy_url(
            self._config.jdbc_url, self._config.db_username, self._config.db_password
        )

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    self._engine = self._create_engine()
        return self._engine

    def _create_engine(self) -> Engine:
        pool_size = max(1, self._config.pool_min_idle or self._config.pool_initial_size)
        max_active = max(pool_size, self._config.pool_max_active)
        max_wait_ms = self._config.pool_max_wait_ms
        engine = create_engine(
            self.url,
            pool_size=pool_size,
            max_overflow=max_active - pool_size,
            pool_timeout=(max_wait_ms / 1000) if max_wait_ms and max_wait_ms > 0 else 30,
            pool_pre_ping=True,
            echo=False,
            # pgjdbc defaults to connectTimeout=10s; without it an unreachable
            # host would block the worker thread for minutes.
            connect_args={"connect_timeout": 10},
        )
        _install_pgjdbc_string_dumper(engine)
        log.info("GaussDB pool ready: %s (pool=%s, max=%s)", _safe_url(self.url), pool_size, max_active)
        return engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # ------------------------------------------------------------------ queries
    @staticmethod
    def _ambient_connection() -> Optional[Connection]:
        """当前线程是否存在未决事务（P0-4）。"""
        return getattr(_TX_LOCAL, "connection", None)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """事务上下文（P0-4，Spring ``@Transactional`` 的 REQUIRED 传播等价物）。

        * 上下文内的 :meth:`query` / :meth:`query_scalars` / :meth:`execute`
          自动复用同一连接并加入本事务（未提交的写对同事务内的读可见）；
        * 正常退出提交、异常回滚（含 ``rollbackFor = Exception.class`` 语义）；
        * 嵌套调用复用外层事务（不设 savepoint，等价 REQUIRED 平铺）。

        目前唯一的使用方是 ``DataProcessService.process``（Java 侧全工程唯一的
        ``@Transactional`` 方法：MySQL 插入 + ES 写入同事务，ES 失败回滚 MySQL）。
        """
        existing = self._ambient_connection()
        if existing is not None:
            yield existing  # REQUIRED：加入外层事务
            return
        with self.engine.begin() as connection:
            _TX_LOCAL.connection = connection
            try:
                yield connection
            finally:
                _TX_LOCAL.connection = None

    def query(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as ordered dicts (column label -> value).

        ``sql`` is passed to SQLAlchemy ``text()`` verbatim: literal ``%`` is
        doubled by SQLAlchemy itself when building the ``pyformat`` statement,
        exactly like MyBatis hands the raw SQL to pgjdbc.
        """
        connection = self._ambient_connection()
        if connection is not None:
            return self._query_rows(connection, sql, params)
        with self.engine.connect() as connection:
            return self._query_rows(connection, sql, params)

    @staticmethod
    def _query_rows(connection: Connection, sql: str,
                    params: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        result = connection.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]

    def query_scalars(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[Any]:
        """Run a SELECT returning a single column (MyBatis ``List<String>``)."""
        connection = self._ambient_connection()
        if connection is not None:
            result = connection.execute(text(sql), params or {})
            return [row[0] for row in result.fetchall()]
        with self.engine.connect() as connection:
            result = connection.execute(text(sql), params or {})
            return [row[0] for row in result.fetchall()]

    def execute(self, sql: str, params: Optional[dict[str, Any]] = None) -> int:
        """Run INSERT/UPDATE/DELETE and return the affected row count.

        在 :meth:`transaction` 上下文内不自行提交（由外层统一提交/回滚）。
        """
        connection = self._ambient_connection()
        if connection is not None:
            result = connection.execute(text(sql), params or {})
            return result.rowcount if result.rowcount is not None else 0
        with self.engine.begin() as connection:
            result = connection.execute(text(sql), params or {})
            return result.rowcount if result.rowcount is not None else 0

    # ------------------------------------------------------------------ health
    def ping(self) -> str:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"


def _safe_url(url: str) -> str:
    """Drop the password before logging."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _credentials, _, host = rest.rpartition("@")
    return f"{scheme}://***@{host}"


_database: Optional[Database] = None
_database_lock = threading.Lock()


def get_database() -> Database:
    global _database
    if _database is None:
        with _database_lock:
            if _database is None:
                _database = Database()
    return _database
