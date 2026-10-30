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
    """``jdbc:postgresql://h:p/db?...`` -> ``postgresql+psycopg://u:p@h:p/db``."""
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
    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self.engine.connect() as connection:
            yield connection

    def query(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as ordered dicts (column label -> value).

        ``sql`` is passed to SQLAlchemy ``text()`` verbatim: literal ``%`` is
        doubled by SQLAlchemy itself when building the ``pyformat`` statement,
        exactly like MyBatis hands the raw SQL to pgjdbc.
        """
        with self.engine.connect() as connection:
            result = connection.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings().all()]

    def query_scalars(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[Any]:
        """Run a SELECT returning a single column (MyBatis ``List<String>``)."""
        with self.engine.connect() as connection:
            result = connection.execute(text(sql), params or {})
            return [row[0] for row in result.fetchall()]

    def execute(self, sql: str, params: Optional[dict[str, Any]] = None) -> int:
        """Run INSERT/UPDATE/DELETE and return the affected row count."""
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
