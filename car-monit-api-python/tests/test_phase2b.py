# -*- coding: utf-8 -*-
"""Phase 2b: the MyBatis XML engine, without touching a database.

Every statement of every mapper XML is rendered twice -- once with an empty
parameter object (all ``<if>`` blocks false) and once with dummy values (all
``<if>`` blocks true) -- which is the cheapest possible proof that the OGNL
subset, ``<where>``, ``<foreach>`` and ``#{}`` parsing cover the real files.
"""
from __future__ import annotations

import re

import pytest

from app.compat.java_meta import MAPPERS
from app.db.registry import MapperRegistry
from app.db.xml_mapper import (
    ParamObject,
    ResultMap,
    map_row,
    statement_returns_single,
)

_BIND_LEFT = re.compile(r"#\{")
_INTERP_LEFT = re.compile(r"\$\{")


class _DummyParams(ParamObject):
    """Anything the XML asks for is present, with a plausible value."""

    def __init__(self, collections: bool = True) -> None:
        super().__init__({}, None)
        self._collections = collections

    def lookup(self, name: str):
        lowered = name.lower()
        if lowered.endswith("list") or lowered.endswith("ids"):
            return ["0001", "0002"] if self._collections else []
        return "1"



@pytest.fixture(scope="module")
def registry() -> MapperRegistry:
    return MapperRegistry().load()


def test_every_mapper_xml_is_loaded(registry: MapperRegistry) -> None:
    assert len(registry.mapper_xmls) == 22, sorted(registry.mapper_xmls)
    assert set(registry.mapper_xmls) <= set(MAPPERS), "XML namespace without a mapper interface"


def test_statement_ids_exist_on_the_interfaces(registry: MapperRegistry) -> None:
    for full_id in registry.statements:
        namespace, _, statement_id = full_id.rpartition(".")
        assert statement_id in MAPPERS[namespace], full_id


def test_statements_render_with_empty_parameters(registry: MapperRegistry) -> None:
    # every <if> is false and every <foreach> sees an empty list
    empty = _DummyParams(collections=False)
    for full_id, statement in registry.statements.items():
        rendered = statement.render(empty, registry.fragments)
        assert rendered.sql.strip(), full_id
        assert not _BIND_LEFT.search(rendered.sql), full_id
        assert not _INTERP_LEFT.search(rendered.sql), full_id


def test_null_foreach_collection_raises(registry: MapperRegistry) -> None:
    """MyBatis throws ``The expression 'uuidList' evaluated to a null value``."""
    from app.db.xml_mapper import SqlError

    statement = registry.statement(
        "com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper"
        ".selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByUuidList")
    assert statement is not None
    with pytest.raises(SqlError):
        statement.render(ParamObject({}, None), registry.fragments)


def test_statements_render_with_all_conditions_true(registry: MapperRegistry) -> None:
    dummy = _DummyParams()
    rendered_foreach = 0
    for full_id, statement in registry.statements.items():
        rendered = statement.render(dummy, registry.fragments)
        assert rendered.sql.strip(), full_id
        assert not _BIND_LEFT.search(rendered.sql), full_id
        if "in (:p" in rendered.sql.lower():
            rendered_foreach += 1
    assert rendered_foreach >= 1, "the <foreach> statements are never rendered"


def test_where_clause_is_trimmed(registry: MapperRegistry) -> None:
    statement = registry.statement(
        "com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper"
        ".selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList")
    assert statement is not None
    sql = statement.render(ParamObject({}, statement_entity(statement)), registry.fragments).sql
    assert "WHERE" not in sql.upper(), sql
    assert "and" not in sql.lower().split("from")[-1], sql


def statement_entity(statement) -> object:
    """The empty entity of the statement's own parameter type."""
    from app.db.proxy import resolve_type

    entity_cls = resolve_type(statement.parameter_type)
    return entity_cls() if isinstance(entity_cls, type) else None


def test_foreach_expands_one_placeholder_per_item(registry: MapperRegistry) -> None:
    statement = registry.statement(
        "com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper"
        ".selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByUuidList")
    assert statement is not None
    params = ParamObject({"uuidList": ["a", "b", "c"]}, None)
    rendered = statement.render(params, registry.fragments)
    assert "in (:p0,:p1,:p2)" in rendered.sql.lower(), rendered.sql
    assert rendered.bindings == {"p0": "a", "p1": "b", "p2": "c"}


def test_result_map_columns_match_entity_fields(registry: MapperRegistry) -> None:
    from com.ruoyi.common.core.domain.JavaBean import _resolve_field

    checked = 0
    for namespace, mapper_xml in registry.mapper_xmls.items():
        for result_map in mapper_xml.result_maps.values():
            entity_cls = _resolve_entity_class(result_map)
            if entity_cls is None:
                continue
            for mapping in result_map.columns:
                assert _resolve_field(entity_cls, mapping.property) is not None, \
                    f"{result_map.type_name}.{mapping.property}"
                checked += 1
    assert checked > 500


def _resolve_entity_class(result_map: ResultMap):
    from app.db.proxy import resolve_type

    resolved = resolve_type(result_map.type_name)
    return resolved if isinstance(resolved, type) else None


def test_row_mapping_uses_the_result_map_and_camel_case() -> None:
    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    result_map = ResultMap(
        map_id="OdsSzdnGantryResult",
        type_name="OdsSzdnGantry",
        columns=[_column("gantryCode", "gantry_code"), _column("isVirtual", "is_virtual")],
    )
    row = {"gantry_code": "G001", "gantry_name": "K1+200", "is_virtual": "0",
           "mileage": 120, "unknown_column": "ignored"}
    entity = map_row(row, OdsSzdnGantry, result_map)
    assert entity.gantry_code == "G001"
    assert entity.gantry_name == "K1+200"      # auto-mapped by camel case
    assert entity.is_virtual == "0"
    assert entity.mileage == "120"             # String in Java -> str
    assert not hasattr(entity, "unknown_column")


def _column(prop: str, column: str):
    from app.db.xml_mapper import ColumnMapping

    return ColumnMapping(prop, column)


def test_statement_returns_single() -> None:
    assert statement_returns_single("List<OdsSzdnGantry>") is False
    assert statement_returns_single("OdsSzdnGantry") is True
    assert statement_returns_single("int") is True


def test_property_lookup_invokes_java_bean_getters() -> None:
    """``#{isVirtual}`` binds the value, never the ``isVirtual()`` method.

    ``JavaBean.__getattr__`` answers ``isXxx``/``getXxx`` with a closure, exactly
    like the Java method; MyBatis' ``Reflector`` invokes the getter. A closure
    that leaked into ``#{}`` reached psycopg as ``cannot adapt type 'function'``
    (seen on ``GET /base/vehicleweight/map``).
    """
    from app.db.expr import _get_property
    from app.db.xml_mapper import property_of
    from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

    entity = OdsSzdnGantry(gantry_code="G001", is_virtual="0")
    for reader in (property_of, _get_property):
        value = reader(entity, "isVirtual")
        assert not callable(value), reader.__module__
        assert value == "0", reader.__module__
