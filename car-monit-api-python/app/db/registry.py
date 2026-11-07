# -*- coding: utf-8 -*-
"""Mapper registry: load the XML files, then bind every statement to its interface.

Migrated from: org.apache.ibatis.session.Configuration
                (``mapperRegistry`` / ``mappedStatements`` / ``resultMaps`` /
                 ``sqlFragments``)
                + org.springframework.context.annotation.ClassPathBeanDefinitionScanner

``mybatis-plus.mapper-locations`` is ``classpath*:com/ruoyi/base/**/xml/*Mapper.xml``,
so the XML files are read from the mirrored ``src/main/java`` tree (they live
next to the mapper interfaces in the original project and are copied into
``target/classes`` by the Maven resource plugin).

At the end of :meth:`MapperRegistry.install` every statement id is compared with
the methods declared on the mapper interface. A method without an XML statement
keeps the in-memory implementation written by the port, which is exactly the
kind of silent divergence a migration must surface -- those are reported by
:class:`InstallReport`.
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence

from app.compat.java_meta import ANNOTATED_STATEMENTS, MAPPERS
from app.db.engine import Database, get_database
from app.db.proxy import create_statement_method, import_class, resolve_type
from app.db.xml_mapper import (
    MapperXml,
    SqlError,
    Statement,
    load_mapper_xml,
    text_statement,
)

log = logging.getLogger(__name__)

__all__ = ["MapperRegistry", "InstallReport", "get_registry", "install_mappers"]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# XML 的唯一真相是 Java 源码树；Python 发布物通过 tools/sync_mapper_xml.py
# 把副本放进 ``pro-business-api/src/main/resources``（P0-1），独立部署时只有
# 副本可用。两侧都在时，Python 树的 classpath 根排在父工程**之后**加载、
# 同名 namespace 后写覆盖，因此**随包副本优先生效**（副本与源逐字节一致，
# 由 tools/check_mappers.py 的同步校验保证不漂移）。
_JAVA_ROOT = _PROJECT_ROOT.parent
_MODULE_ROOTS = ("pro-business-api", "pro-base-common")
_CLASSPATH_ROOTS = tuple(
    base / module / "src" / "main" / source_set
    for base in (_JAVA_ROOT, _PROJECT_ROOT)
    for module in _MODULE_ROOTS
    for source_set in ("java", "resources")
)
_DEFAULT_LOCATIONS = "classpath*:com/ruoyi/base/**/xml/*Mapper.xml"


@dataclass
class InstallReport:
    """What :meth:`MapperRegistry.install` changed (printed at startup)."""

    mappers: int = 0
    statements: int = 0
    patched_methods: int = 0
    missing_statements: list[str] = field(default_factory=list)
    orphan_statements: list[str] = field(default_factory=list)
    annotated_statements: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed_files and not self.missing_statements

    def summary(self) -> str:
        return (f"{self.mappers} mapper(s), {self.statements} statement(s) "
                f"({len(self.annotated_statements)} from annotations), "
                f"{self.patched_methods} method(s) bound to SQL")


class MapperRegistry:
    """Holds every parsed ``MapperXml`` and the merged SQL fragment index."""

    def __init__(self, root: Optional[Path] = None,
                 locations: Optional[str] = None,
                 db: Optional[Database] = None) -> None:
        self.root = Path(root) if root else _PROJECT_ROOT
        self.locations = locations or _DEFAULT_LOCATIONS
        self._db = db
        self.mapper_xmls: dict[str, MapperXml] = {}
        self.statements: dict[str, Statement] = {}
        self.fragments: dict[str, Sequence[Any]] = {}
        self._loaded = False
        self._installed: Optional[InstallReport] = None

    # ------------------------------------------------------------------ loading
    def load(self) -> "MapperRegistry":
        if self._loaded:
            return self
        pattern = self._relative_pattern(self.locations)
        paths: list[Path] = []
        for classpath_root in self._classpath_roots():
            base = classpath_root
            if not base.is_dir():
                continue
            paths.extend(sorted(base.glob(pattern)))
        seen: set[Path] = set()
        for path in paths:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                mapper_xml = load_mapper_xml(path)
            except SqlError as error:
                log.warning("mapper XML skipped: %s", error)
                continue
            if not mapper_xml.namespace:
                log.warning("%s: <mapper> without namespace ignored", path.name)
                continue
            self.mapper_xmls[mapper_xml.namespace] = mapper_xml
            for fragment_id, nodes in mapper_xml.fragments.items():
                self.fragments[fragment_id] = nodes
                self.fragments[f"{mapper_xml.namespace}.{fragment_id}"] = nodes
            for statement_id, statement in mapper_xml.statements.items():
                self.statements[f"{mapper_xml.namespace}.{statement_id}"] = statement
        self._loaded = True
        log.info("loaded %d mapper XML(s), %d statement(s)",
                 len(self.mapper_xmls), len(self.statements))
        return self

    def _classpath_roots(self) -> Iterator[Path]:
        """``classpath*:`` in a Maven build = every module's source roots."""
        yield self.root
        for classpath_root in _CLASSPATH_ROOTS:
            yield classpath_root

    @staticmethod
    def _relative_pattern(locations: str) -> str:
        pattern = locations.split(",")[0].strip()
        for prefix in ("classpath*:", "classpath:"):
            if pattern.startswith(prefix):
                pattern = pattern[len(prefix):]
        # ``**/xml/*Mapper.xml`` style patterns work with Path.glob as-is
        return pattern.lstrip("/")

    # ------------------------------------------------------------------ lookup
    def statement(self, full_id: str) -> Optional[Statement]:
        return self.statements.get(full_id)

    def mapper_xml(self, namespace: str) -> Optional[MapperXml]:
        return self.mapper_xmls.get(namespace)

    # ------------------------------------------------------------------ binding
    def install(self, db: Optional[Database] = None) -> InstallReport:
        if self._installed is not None:
            return self._installed
        self.load()
        report = InstallReport()
        namespaces = sorted(set(self.mapper_xmls) | set(ANNOTATED_STATEMENTS))
        for namespace in namespaces:
            mapper_cls = self._import_mapper(namespace)
            if mapper_cls is None:
                report.failed_files.append(namespace)
                continue
            report.mappers += 1
            mapper_xml = self.mapper_xmls.get(namespace)
            entity_cls = self._entity_of(mapper_cls)
            declared = MAPPERS.get(namespace, {})
            bound: set[str] = set()

            for statement_id, statement in (mapper_xml.statements.items() if mapper_xml else ()):
                meta = declared.get(statement_id)
                result_map = self._result_map_of(mapper_xml, statement)
                method = create_statement_method(
                    statement, self.fragments, meta, entity_cls, result_map, db or self._db)
                setattr(mapper_cls, statement_id, method)
                bound.add(statement_id)
                report.patched_methods += 1
                report.statements += 1
                if declared and statement_id not in declared:
                    report.orphan_statements.append(statement.full_id)

            # ``@Select`` / ``@Update`` written on the interface itself
            for method_name, entry in ANNOTATED_STATEMENTS.get(namespace, {}).items():
                if method_name in bound:
                    continue
                meta = declared.get(method_name)
                statement = text_statement(
                    namespace, method_name, entry["kind"], entry["sql"],
                    parameter_type=None, result_type=(meta or {}).get("returns"))
                setattr(mapper_cls, method_name,
                        create_statement_method(statement, self.fragments, meta,
                                                entity_cls, None, db or self._db))
                self.statements.setdefault(statement.full_id, statement)
                bound.add(method_name)
                report.patched_methods += 1
                report.statements += 1
                report.annotated_statements.append(statement.full_id)

            for method_name in declared:
                if method_name in bound:
                    continue
                if _inherited_from_base_mapper(mapper_cls, method_name):
                    continue
                # No XML, no annotation: MyBatis throws
                # ``BindingException: Invalid bound statement (not found)``.
                setattr(mapper_cls, method_name,
                        _invalid_bound_statement(namespace, method_name))
                report.missing_statements.append(f"{namespace}#{method_name}")
                log.warning("%s#%s has no statement (neither XML nor annotation): "
                            "calling it raises like MyBatis", namespace, method_name)
        self._installed = report
        if not self.mapper_xmls:
            # P0-1（docs/迁移审阅报告.md）：独立部署 Python 目录时父工程不存在，
            # XML 必须随包发布（pro-business-api/src/main/resources/...，由
            # tools/sync_mapper_xml.py 同步）。0 个 XML 意味着所有 Mapper 都会
            # 退回“移植期臆造实现”并返回空数据 —— 这是静默错误，必须拒绝启动。
            raise SqlError(
                "no mapper XML was loaded: the Python package must ship its "
                "mapper XMLs under pro-business-api/src/main/resources "
                "(run tools/sync_mapper_xml.py to sync them from the Java tree); "
                "refusing to continue with zero statements")
        log.info("mapper registry: %s", report.summary())
        if report.orphan_statements:
            log.warning("%d XML statement(s) have no matching mapper method: %s",
                        len(report.orphan_statements),
                        ", ".join(report.orphan_statements[:5]))
        return report

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _import_mapper(namespace: str) -> Optional[type]:
        mapper_cls = import_class(namespace)
        if mapper_cls is None:
            log.error("cannot import mapper %s", namespace)
        return mapper_cls

    @staticmethod
    def _entity_of(mapper_cls: type) -> Optional[type]:
        try:
            instance = mapper_cls()
        except Exception as error:  # noqa: BLE001 - a mapper must have a no-arg ctor
            log.warning("cannot instantiate %s: %s", mapper_cls.__name__, error)
            return None
        return getattr(instance, "entity_cls", None)

    def _result_map_of(self, mapper_xml: MapperXml, statement: Statement) -> Any:
        if not statement.result_map_id:
            return None
        result_map = mapper_xml.result_maps.get(statement.result_map_id)
        if result_map is None:
            # cross-namespace reference: "com.foo.BarMapper.BarResult"
            for other in self.mapper_xmls.values():
                result_map = other.result_maps.get(statement.result_map_id)
                if result_map is not None:
                    break
        return result_map


def _invalid_bound_statement(namespace: str, method_name: str):
    """Reproduce ``BindingException: Invalid bound statement (not found)``."""
    full_id = f"{namespace}.{method_name}"

    def missing(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(f"Invalid bound statement (not found): {full_id}")

    missing.__name__ = method_name
    missing.__doc__ = f"# Java: {full_id} -- declared without XML/annotation"
    return missing


def _inherited_from_base_mapper(mapper_cls: type, method_name: str) -> bool:
    """``selectById`` & friends are implemented once, in ``BaseMapper``."""
    for klass in mapper_cls.__mro__:
        if klass.__name__ == "BaseMapper":
            return hasattr(klass, method_name)
    return False


_registry: Optional[MapperRegistry] = None


def get_registry() -> MapperRegistry:
    global _registry
    if _registry is None:
        _registry = MapperRegistry()
    return _registry


def install_mappers(db: Optional[Database] = None) -> InstallReport:
    """Load the XMLs and patch both ``BaseMapper`` and the concrete mappers."""
    from app.db import base_mapper

    database = db or get_database()
    base_mapper.install(database)
    return get_registry().install(database)


def resolve_entity(type_name: Optional[str], default: Optional[type] = None) -> Any:
    """Public helper used by tests and tools."""
    return resolve_type(type_name, default)
