# -*- coding: utf-8 -*-
"""Mapper method -> SQL statement dispatcher (``MapperProxy`` + ``MapperMethod``).

Migrated from: org.apache.ibatis.binding.MapperProxy
                org.apache.ibatis.binding.MapperMethod
                org.apache.ibatis.session.defaults.DefaultSqlSession

``MapperMethod`` decides what a mapper method call means:

    XML statement id      -> build BoundSql, run it, convert the result
    ``@Param`` names      -> the parameter map MyBatis exposes to ``#{}``
    single un-annotated   -> the argument itself is the parameter object
    return ``List<X>``    -> list[X] ([] when the statement returns no row)
    return ``X``          -> X or None; more than one row is an error
    return ``int``        -> affected row count

PageHelper is applied here as well: the *first* SELECT after
``BaseController.startPage()`` is counted, clamped and paginated.
"""
from __future__ import annotations

import importlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Mapping, Optional, Sequence

from com.ruoyi.common.utils.PageUtils import PageUtils
from app.db.engine import Database, get_database
from app.db.pagination import (
    PageRequest,
    add_pagination,
    build_count_sql,
    clamp_page_number,
    current_page_request,
)
from app.db.xml_mapper import (
    ParamObject,
    ResultMap,
    Statement,
    coerce_value,
    map_row,
    statement_returns_single,
)

log = logging.getLogger(__name__)

__all__ = ["create_statement_method", "build_param_object", "resolve_type",
           "import_class"]

_SCALARS: dict[str, type] = {
    "string": str,
    "java.lang.string": str,
    "str": str,
    "long": int,
    "integer": int,
    "int": int,
    "short": int,
    "java.lang.long": int,
    "java.lang.integer": int,
    "double": float,
    "float": float,
    "java.lang.double": float,
    "java.lang.float": float,
    "bigdecimal": float,
    "java.math.bigdecimal": float,
    "boolean": bool,
    "java.lang.boolean": bool,
    "date": datetime,
    "java.util.date": datetime,
    "timestamp": datetime,
    "java.sql.timestamp": datetime,
    "localdatetime": datetime,
    "java.time.localdatetime": datetime,
    "localdate": date,
    "java.time.localdate": date,
    "java.sql.date": date,
    "map": dict,
    "java.util.map": dict,
    "hashmap": dict,
    "java.util.hashmap": dict,
}

# Return types that are read from the first column instead of mapped to a bean
_SCALAR_RESULTS = (str, int, float, bool, Decimal, date, datetime)


def import_class(full_name: str) -> Optional[type]:
    """Import ``a.b.C`` -- the migration keeps one module per Java class."""
    module_name, _, class_name = full_name.rpartition(".")
    for candidate in (full_name, module_name):
        try:
            module = importlib.import_module(candidate)
        except ImportError:
            continue
        resolved = getattr(module, class_name, None)
        if resolved is not None:
            return resolved
    return None


def resolve_type(type_name: Optional[str], default: Optional[type] = None) -> Any:
    """Resolve ``resultType`` / ``resultMap type`` / ``parameterType`` to a type."""
    if not type_name:
        return default
    cleaned = type_name.strip()
    if "<" in cleaned:
        # List<Xxx> -> the element type is what map_row needs
        cleaned = cleaned[cleaned.index("<") + 1: cleaned.rindex(">")].strip()
    lowered = cleaned.lower()
    if lowered in _SCALARS:
        return _SCALARS[lowered]
    simple_name = cleaned.rsplit(".", 1)[-1]
    if cleaned.startswith("com."):
        resolved = import_class(cleaned)
        if resolved is None:
            log.warning("cannot import result type %s", cleaned)
            return default
        return resolved
    for package in ("com.ruoyi.base.domain", "com.ruoyi.base.domain.bo",
                    "com.ruoyi.base.domain.vo", "com.ruoyi.common.core.domain"):
        resolved = import_class(f"{package}.{simple_name}")
        if resolved is not None:
            return resolved
    if default is not None and getattr(default, "__name__", "") == simple_name:
        return default
    log.debug("unresolved type %r, falling back to %r", type_name, default)
    return default


def _is_bean(value: Any) -> bool:
    if value is None or isinstance(value, (str, bytes, int, float, bool, list, tuple,
                                           dict, set, frozenset)):
        return False
    return hasattr(type(value), "__dataclass_fields__") or hasattr(value, "getClass")


def build_param_object(method_meta: Optional[Mapping[str, Any]],
                       args: Sequence[Any],
                       kwargs: Mapping[str, Any]) -> ParamObject:
    """Reproduce ``ParamNameResolver`` + ``useActualParamName``."""
    declared = list((method_meta or {}).get("params") or [])
    values: dict[str, Any] = {}
    primary: Any = None
    for index, value in enumerate(args):
        java_name = declared[index][0] if index < len(declared) else f"param{index + 1}"
        annotated = declared[index][2] if index < len(declared) else None
        values[annotated or java_name] = value
        values.setdefault(java_name, value)
        values.setdefault(f"param{index + 1}", value)
        values.setdefault(f"arg{index}", value)
    values.update(kwargs)
    if len(args) == 1 and not kwargs and len(declared) <= 1:
        annotated = declared[0][2] if declared else None
        if annotated is None and _is_bean(args[0]):
            # MyBatis: the single argument *is* the parameter object
            primary = args[0]
    return ParamObject(values, primary)


def _database_of(db: Optional[Database]) -> Database:
    return db or get_database()


def _count_rows(database: Database, sql: str, bindings: dict[str, Any]) -> int:
    rows = database.query(build_count_sql(sql), bindings or None)
    if not rows:
        return 0
    return int(list(rows[0].values())[0] or 0)


def execute_statement(statement: Statement,
                      fragments: Mapping[str, Sequence[Any]],
                      params: ParamObject,
                      method_meta: Optional[Mapping[str, Any]],
                      entity_cls: Optional[type],
                      result_map: Optional[ResultMap],
                      db: Optional[Database] = None) -> Any:
    database = _database_of(db)
    rendered = statement.render(params, fragments)
    sql = rendered.sql
    bindings = rendered.bindings

    page: Optional[PageRequest] = None
    if statement.kind == "select":
        page = current_page_request()

    if page is not None:
        total = _count_rows(database, sql, bindings)
        page_num = clamp_page_number(page, total)
        sql, bindings = add_pagination(sql, page, page_num, bindings)
        # PageInfo reads the total from the PageHelper thread local
        PageUtils.set_page_total(total)
        log.debug("PageHelper: pageNum=%s pageSize=%s total=%s", page_num, page.page_size, total)

    target_type = resolve_type(statement.result_type, entity_cls)
    if result_map is not None:
        target_type = resolve_type(result_map.type_name, target_type)

    if statement.kind != "select":
        return database.execute(sql, bindings or None)

    rows = database.query(sql, bindings or None)
    log.debug("%s: %d row(s)", statement.full_id, len(rows))

    if target_type is dict:
        return rows if not statement_returns_single(_returns(method_meta)) else (rows[0] if rows else None)
    if isinstance(target_type, type) and issubclass(target_type, _SCALAR_RESULTS):
        scalars = [coerce_value(list(row.values())[0], target_type) for row in rows]
        if statement_returns_single(_returns(method_meta)):
            return scalars[0] if scalars else None
        return scalars

    mapped = [map_row(row, target_type, result_map) for row in rows] if target_type else rows
    if statement_returns_single(_returns(method_meta)):
        if len(mapped) > 1:
            raise RuntimeError(
                f"Expected one result (or null) to be returned by selectOne(), "
                f"but found: {len(mapped)} ({statement.full_id})")
        return mapped[0] if mapped else None
    return mapped


def _returns(method_meta: Optional[Mapping[str, Any]]) -> Optional[str]:
    return (method_meta or {}).get("returns")


def create_statement_method(statement: Statement,
                            fragments: Mapping[str, Sequence[Any]],
                            method_meta: Optional[Mapping[str, Any]],
                            entity_cls: Optional[type],
                            result_map: Optional[ResultMap],
                            db: Optional[Database] = None) -> Callable[..., Any]:
    """Build the function that replaces the mapper method (``MapperProxy``)."""

    def statement_method(self: Any, *args: Any, **kwargs: Any) -> Any:
        params = build_param_object(method_meta, args, kwargs)
        return execute_statement(statement, fragments, params, method_meta,
                                 entity_cls, result_map, db)

    statement_method.__name__ = statement.statement_id
    statement_method.__qualname__ = f"{statement.namespace}.{statement.statement_id}"
    statement_method.__doc__ = (
        f"# Java: {statement.namespace}#{statement.statement_id}\n"
        f"MyBatis statement from {statement.resource}."
    )
    # Keep the original signature visible to help()/IDE: (self, *args)
    statement_method.__mybatis_statement__ = statement.full_id  # type: ignore[attr-defined]
    return statement_method
