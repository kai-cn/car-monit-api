# -*- coding: utf-8 -*-
"""MyBatis-Plus ``BaseMapper`` CRUD executed as real SQL.

Migrated from: com.baomidou.mybatisplus.core.injector.methods.*
                (SelectById / SelectList / SelectCount / Insert / UpdateById /
                 Delete / DeleteByIds / SelectByMap ...)
                + com.baomidou.mybatisplus.core.metadata.TableInfoHelper

The ported ``BaseMapper`` (``com/baomidou/mybatisplus/core/mapper/BaseMapper.py``)
keeps an in-process table so the 215 mirrored business files can be imported
without a database. Phase 2 swaps those methods for SQL by *patching the class
in place*: instances created by the business services keep working and the
mirrored files stay untouched.

SQL shape follows MyBatis-Plus defaults:

* column name == field name (``tableUnderline`` turns ``bigId`` into
  ``big_id``, and the ported entities already use snake_case field names);
* ``insert`` / ``updateById`` skip ``null`` fields (``FieldStrategy.NOT_NULL``);
* the primary key is never part of the ``SET`` clause;
* ``map-underscore-to-camel-case`` is applied on the way back.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

from app.db.engine import Database, get_database
from app.db.snowflake import assign_uuid, next_id
from app.db.xml_mapper import map_row
from app.runtime import reject_shim_operation

log = logging.getLogger(__name__)

__all__ = ["install", "uninstall", "build_where_from_wrapper"]

_INSTALLED: dict[str, Any] = {}


# --------------------------------------------------------------------------- helpers
def _entity_cls(mapper: Any) -> type:
    entity_cls = getattr(mapper, "entity_cls", None)
    if entity_cls is None:
        raise RuntimeError(f"{type(mapper).__name__} has no entity type bound")
    return entity_cls


def _columns(mapper: Any) -> list[str]:
    return [field_info.name for field_info in mapper._tableFields()]


def _select_list_sql(mapper: Any, columns: Optional[list[str]] = None) -> str:
    projection = ", ".join(columns) if columns else ", ".join(_columns(mapper))
    return f"SELECT {projection} FROM {mapper.getTableName()}"


def _column_name(column: Any) -> str:
    """Wrapper column expression -> SQL column (``SFunction`` substitute)."""
    if isinstance(column, str):
        return column
    if callable(column):
        names = getattr(getattr(column, "__code__", None), "co_names", ())
        for name in names:
            if name.startswith("_"):
                continue
            if name.startswith("get") and len(name) > 3:
                from com.ruoyi.common.core.domain.JavaBean import _decapitalize, camel_to_snake

                return camel_to_snake(_decapitalize(name[3:]))
            return name
        raise TypeError("cannot resolve the column of a callable wrapper argument")
    raise TypeError(f"unsupported wrapper column expression: {column!r}")


def build_where_from_wrapper(wrapper: Any,
                             binder: Callable[[Any], str]) -> str:
    """Translate ``QueryWrapper`` conditions into a ``WHERE`` clause."""
    conditions = getattr(wrapper, "_conditions", None)
    if conditions is None:
        raise TypeError(f"{type(wrapper).__name__} is not a supported Wrapper")
    clauses: list[str] = []
    for op, column, value1, value2 in conditions:
        name = _column_name(column)
        if op == "isNull":
            clauses.append(f"{name} IS NULL")
        elif op == "isNotNull":
            clauses.append(f"{name} IS NOT NULL")
        elif op == "between":
            clauses.append(f"{name} BETWEEN {binder(value1)} AND {binder(value2)}")
        elif op == "like":
            clauses.append(f"{name} LIKE {binder(f'%{value1}%')}")
        elif op == "in":
            values = list(value1 or [])
            if not values:
                # MP emits `IN ()` which the database rejects; keep the failure visible
                clauses.append(f"{name} IN (NULL)")
            else:
                placeholders = ", ".join(binder(item) for item in values)
                clauses.append(f"{name} IN ({placeholders})")
        elif op == "eq":
            clauses.append(f"{name} = {binder(value1)}")
        elif op == "ne":
            clauses.append(f"{name} <> {binder(value1)}")
        elif op == "gt":
            clauses.append(f"{name} > {binder(value1)}")
        elif op == "ge":
            clauses.append(f"{name} >= {binder(value1)}")
        elif op == "lt":
            clauses.append(f"{name} < {binder(value1)}")
        elif op == "le":
            clauses.append(f"{name} <= {binder(value1)}")
        else:
            raise TypeError(f"unsupported wrapper operator: {op}")
    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


def build_order_by(wrapper: Any) -> str:
    specs = getattr(wrapper, "_order_specs", None) or []
    if not specs:
        return ""
    parts = [f"{_column_name(column)} {'ASC' if ascending else 'DESC'}"
             for column, ascending in specs]
    return " ORDER BY " + ", ".join(parts)


def _entity_conditions(mapper: Any, entity: Any,
                       binder: Callable[[Any], str]) -> list[str]:
    clauses: list[str] = []
    for field_info in mapper._tableFields():
        value = getattr(entity, field_info.name, None)
        if value is None:
            # same as <if test="x != null"> in the generated XML
            continue
        clauses.append(f"{field_info.name} = {binder(value)}")
    return clauses


def _new_binder() -> tuple[Callable[[Any], str], dict[str, Any]]:
    params: dict[str, Any] = {}

    def bind(value: Any) -> str:
        name = f"w{len(params)}"
        params[name] = value
        return f":{name}"

    return bind, params


def _query(mapper: Any, sql: str, params: dict[str, Any],
           columns: Optional[list[str]] = None) -> list[Any]:
    rows = _database().query(sql, params or None)
    entity_cls = _entity_cls(mapper)
    if columns:
        projected = set(columns)
        for row in rows:
            for name in list(row.keys()):
                if name not in projected:
                    row[name] = None
    return [map_row(row, entity_cls) for row in rows]


_DATABASE_OVERRIDE: Optional[Database] = None


def _database() -> Database:
    return _DATABASE_OVERRIDE or get_database()


# --------------------------------------------------------------------------- CRUD
def _select_by_id(self: Any, pk: Any) -> Any:
    column = self.getPkName()
    sql = f"{_select_list_sql(self)} WHERE {column} = :pk"
    rows = _query(self, sql, {"pk": pk})
    return rows[0] if rows else None


def _select_batch_ids(self: Any, id_list: Iterable[Any]) -> list[Any]:
    values = list(id_list or [])
    if not values:
        return []
    bind, params = _new_binder()
    placeholders = ", ".join(bind(value) for value in values)
    sql = f"{_select_list_sql(self)} WHERE {self.getPkName()} IN ({placeholders})"
    return _query(self, sql, params)


def _select_one(self: Any, query: Any = None) -> Any:
    rows = _select_list(self, query)
    return rows[0] if rows else None


def _select_list(self: Any, query: Any = None) -> list[Any]:
    bind, params = _new_binder()
    projection: Optional[list[str]] = None
    if query is None:
        sql = _select_list_sql(self)
    elif hasattr(query, "_conditions"):
        selected = getattr(query, "_select_columns", None) or []
        if selected:
            projection = [_column_name(column) for column in selected]
        sql = _select_list_sql(self, projection)
        sql += build_where_from_wrapper(query, bind)
        sql += build_order_by(query)
        limit = getattr(query, "_limit", None)
        offset = getattr(query, "_offset", 0) or 0
        if limit is not None:
            sql += f" LIMIT {bind(limit)}"
        if offset:
            sql += f" OFFSET {bind(offset)}"
    elif isinstance(query, dict):
        sql = _select_list_sql(self)
        clauses = [f"{name} = {bind(value)}" for name, value in query.items()]
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
    elif callable(query) and not hasattr(query, "_tableFields"):
        # A bare predicate cannot be pushed down; the ported in-memory filter is
        # the only faithful option, so the whole table is read once.
        # P2-4：prod 模式拒绝——真实库上这是无界全表扫描（报告 Q12）。
        reject_shim_operation(
            "BaseMapper.selectList(<predicate>)",
            "（谓词无法下推，会整表读取后在 Python 过滤；请改写为 Wrapper/XML 条件。）")
        log.warning("%s.selectList(<predicate>) reads the full table", type(self).__name__)
        return [row for row in _query(self, _select_list_sql(self), {}) if query(row)]
    else:
        sql = _select_list_sql(self)
        clauses = _entity_conditions(self, query, bind)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
    return _query(self, sql, params, projection)


def _select_count(self: Any, query: Any = None) -> int:
    bind, params = _new_binder()
    sql = f"SELECT count(0) FROM {self.getTableName()}"
    if query is None:
        pass
    elif hasattr(query, "_conditions"):
        sql += build_where_from_wrapper(query, bind)
    elif isinstance(query, dict):
        clauses = [f"{name} = {bind(value)}" for name, value in query.items()]
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
    elif callable(query) and not hasattr(query, "_tableFields"):
        # P2-4：同 selectList——prod 模式拒绝无界全表扫描。
        reject_shim_operation(
            "BaseMapper.selectCount(<predicate>)",
            "（谓词无法下推，会整表读取后在 Python 计数；请改写为 Wrapper/XML 条件。）")
        log.warning("%s.selectCount(<predicate>) reads the full table", type(self).__name__)
        return sum(1 for row in _query(self, _select_list_sql(self), {}) if query(row))
    else:
        clauses = _entity_conditions(self, query, bind)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
    rows = _database().query(sql, params or None)
    if not rows:
        return 0
    return int(list(rows[0].values())[0] or 0)


def _select_by_map(self: Any, column_map: dict) -> list[Any]:
    if not column_map:
        return _select_list(self, None)
    bind, params = _new_binder()
    clauses = [f"{name} = {bind(value)}" for name, value in column_map.items()]
    sql = f"{_select_list_sql(self)} WHERE " + " AND ".join(clauses)
    return _query(self, sql, params)


def _assign_id(self: Any, entity: Any) -> None:
    """``@TableId(type = IdType.ASSIGN_UUID / ASSIGN_ID / AUTO)``."""
    key = self.getPkName()
    if getattr(entity, key, None) not in (None, ""):
        return
    id_type = self.getIdType()
    if id_type == "ASSIGN_UUID":
        setattr(entity, key, assign_uuid())
    elif id_type == "AUTO":
        # The database fills it (identity column); MP reads it back through
        # `useGeneratedKeys`, which we cannot do without RETURNING.
        log.debug("%s: IdType.AUTO leaves the primary key to the database",
                  type(self).__name__)
    else:
        setattr(entity, key, next_id())


def _insert_columns(self: Any, entity: Any) -> list[str]:
    key = self.getPkName()
    names: list[str] = []
    for field_info in self._tableFields():
        if field_info.name == key and self.getIdType() == "AUTO":
            continue
        if getattr(entity, field_info.name, None) is None:
            continue
        names.append(field_info.name)
    return names


def _insert(self: Any, entity: Any) -> int:
    _assign_id(self, entity)
    bind, params = _new_binder()
    columns = _insert_columns(self, entity)
    placeholders = ", ".join(bind(getattr(entity, name)) for name in columns)
    sql = (f"INSERT INTO {self.getTableName()} ({', '.join(columns)}) "
           f"VALUES ({placeholders})")
    return _database().execute(sql, params)


def _insert_or_update(self: Any, entity: Any) -> int:
    key = self.getPkName()
    pk = getattr(entity, key, None)
    if pk is not None:
        existing = _select_by_id(self, pk)
        if existing is not None:
            return _update_by_id(self, entity)
    return _insert(self, entity)


def _update_by_id(self: Any, entity: Any) -> int:
    key = self.getPkName()
    pk = getattr(entity, key, None)
    if pk is None:
        # MP throws: "can not execute. because can not find column for id"
        raise RuntimeError(
            f"{type(self).__name__}.updateById: primary key '{key}' is null")
    bind, params = _new_binder()
    assignments: list[str] = []
    for field_info in self._tableFields():
        if field_info.name == key:
            continue
        value = getattr(entity, field_info.name, None)
        if value is None:
            # FieldStrategy.NOT_NULL
            continue
        assignments.append(f"{field_info.name} = {bind(value)}")
    if not assignments:
        return 0
    sql = (f"UPDATE {self.getTableName()} SET {', '.join(assignments)} "
           f"WHERE {key} = {bind(pk)}")
    return _database().execute(sql, params)


def _delete_by_id(self: Any, pk: Any) -> int:
    sql = f"DELETE FROM {self.getTableName()} WHERE {self.getPkName()} = :pk"
    return _database().execute(sql, {"pk": pk})


def _delete_batch_ids(self: Any, id_list: Iterable[Any]) -> int:
    values = list(id_list or [])
    if not values:
        return 0
    bind, params = _new_binder()
    placeholders = ", ".join(bind(value) for value in values)
    sql = f"DELETE FROM {self.getTableName()} WHERE {self.getPkName()} IN ({placeholders})"
    return _database().execute(sql, params)


def _delete_by_map(self: Any, column_map: dict) -> int:
    if not column_map:
        return 0
    bind, params = _new_binder()
    clauses = [f"{name} = {bind(value)}" for name, value in column_map.items()]
    sql = f"DELETE FROM {self.getTableName()} WHERE " + " AND ".join(clauses)
    return _database().execute(sql, params)


_METHODS = {
    "selectById": _select_by_id,
    "selectBatchIds": _select_batch_ids,
    "selectOne": _select_one,
    "selectList": _select_list,
    "selectCount": _select_count,
    "selectByMap": _select_by_map,
    "insert": _insert,
    "insertOrUpdate": _insert_or_update,
    "updateById": _update_by_id,
    "deleteById": _delete_by_id,
    "deleteBatchIds": _delete_batch_ids,
    "deleteByMap": _delete_by_map,
}


def install(db: Optional[Database] = None) -> list[str]:
    """Patch ``BaseMapper`` so every mapper talks to the database."""
    global _DATABASE_OVERRIDE
    if _INSTALLED:
        return sorted(_INSTALLED)
    if db is not None:
        _DATABASE_OVERRIDE = db
    from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper

    for name, function in _METHODS.items():
        _INSTALLED[name] = getattr(BaseMapper, name)
        setattr(BaseMapper, name, function)
    log.info("BaseMapper CRUD bound to GaussDB (%d methods)", len(_INSTALLED))
    return sorted(_INSTALLED)


def uninstall() -> None:
    """Restore the in-memory implementation (used by the unit tests)."""
    global _DATABASE_OVERRIDE
    if not _INSTALLED:
        return
    from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper

    for name, function in _INSTALLED.items():
        setattr(BaseMapper, name, function)
    _INSTALLED.clear()
    _DATABASE_OVERRIDE = None
