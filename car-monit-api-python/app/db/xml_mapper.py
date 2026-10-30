# -*- coding: utf-8 -*-
"""MyBatis 3 mapper XML engine.

Migrated from: org.apache.ibatis.builder.xml.XMLMapperBuilder
                org.apache.ibatis.scripting.xmltags.*  (IfSqlNode / WhereSqlNode /
                    ForeachSqlNode / StaticTextSqlNode / IncludeSqlNode)
                org.apache.ibatis.builder.SqlSourceBuilder      (``#{}`` parsing)
                org.apache.ibatis.executor.resultset.DefaultResultSetHandler

The 22 mapper XML files of this project only use a small subset of the DTD:

    <resultMap> <sql> <include> <select> <update> <if> <where> <foreach> CDATA

There is no ``${}``, no ``<choose>/<trim>/<set>/<bind>`` and no nested
``<resultMap>``. Everything below is scoped to that subset, plus ``<choose>``
and ``<trim>`` because they cost ~40 lines and keep the engine honest.

Two behaviours are easy to get wrong and are reproduced explicitly:

* ``DynamicContext`` joins every rendered node with a single space
  (``new StringJoiner(" ")``), so a missing space between an ``<if>`` block and
  the surrounding text cannot happen. We do the same.
* ``<where>`` strips a leading ``AND`` / ``OR`` of the *whole* rendered block
  (``WhereSqlNode``), and emits nothing at all when the block is empty.

``#{}`` becomes ``:p0`` / ``:p1`` ... positional bind parameters, which is what
SQLAlchemy ``text()`` expects.
"""
from __future__ import annotations

import logging
import re
import typing
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional, Sequence

from app.db.expr import evaluate

log = logging.getLogger(__name__)

__all__ = [
    "ColumnMapping",
    "ResultMap",
    "Statement",
    "MapperXml",
    "RenderedSql",
    "ParamObject",
    "SqlError",
    "load_mapper_xml",
    "text_statement",
    "map_row",
    "coerce_value",
]

_BIND_RE = re.compile(r"#\{\s*([^,}\s]+)\s*(?:,[^{}]*)?\}")
_INTERP_RE = re.compile(r"\$\{\s*([^,}\s]+)\s*(?:,[^{}]*)?\}")

_LEADING_BOOLEAN_RE = re.compile(r"^\s*(?:AND|OR)\b", re.IGNORECASE)

_STATEMENT_TAGS = ("select", "insert", "update", "delete")


class SqlError(RuntimeError):
    """Raised when an XML construct cannot be rendered."""


# --------------------------------------------------------------------------- model
@dataclass(frozen=True)
class ColumnMapping:
    """``<result property="gantryCode" column="gantry_code"/>``."""

    property: str
    column: str


@dataclass
class ResultMap:
    """``<resultMap type="...Xxx" id="XxxResult">``."""

    map_id: str
    type_name: str
    columns: list[ColumnMapping] = field(default_factory=list)


@dataclass
class RenderedSql:
    sql: str
    bindings: dict[str, Any] = field(default_factory=dict)


class ParamObject:
    """The ``parameterObject`` MyBatis hands to a statement.

    ``values``  holds ``@Param`` names (plus ``param1..paramN``); ``primary`` is
    the single argument of a one-argument mapper method -- either an entity
    (property lookups go through ``JavaBean``) or a scalar already registered
    under its Java parameter name.
    """

    def __init__(self, values: Optional[dict[str, Any]] = None, primary: Any = None) -> None:
        self.values = values or {}
        self.primary = primary

    # MyBatis: a missing map key yields null, never a KeyError
    def lookup(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        lowered = name.lower()
        for key, value in self.values.items():
            if key.lower() == lowered:
                return value
        if self.primary is None:
            return None
        return property_of(self.primary, name)

    def __contains__(self, name: str) -> bool:
        return name in self.values

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass
class Statement:
    namespace: str
    statement_id: str
    kind: str                       # select | insert | update | delete
    parameter_type: Optional[str] = None
    result_type: Optional[str] = None
    result_map_id: Optional[str] = None
    nodes: list["_Node"] = field(default_factory=list)
    resource: str = ""

    @property
    def full_id(self) -> str:
        return f"{self.namespace}.{self.statement_id}"

    def render(self, params: ParamObject,
               fragments: Mapping[str, Sequence["_Node"]]) -> RenderedSql:
        context = _Context(params, fragments)
        for node in self.nodes:
            node.render(context)
        return RenderedSql(_join(context.chunks), context.bindings)


@dataclass
class MapperXml:
    namespace: str
    resource: str
    result_maps: dict[str, ResultMap] = field(default_factory=dict)
    fragments: dict[str, list["_Node"]] = field(default_factory=dict)
    statements: dict[str, Statement] = field(default_factory=dict)


# --------------------------------------------------------------------------- helpers
def property_of(target: Any, name: str) -> Any:
    """Read ``name`` from a Mapping / dataclass / JavaBean / plain object."""
    if target is None:
        return None
    if isinstance(target, Mapping):
        if name in target:
            return target[name]
        lowered = name.lower()
        for key, value in target.items():
            if str(key).lower() == lowered:
                return value
        return None
    if isinstance(target, (str, bytes, int, float, bool, Decimal, date, datetime)):
        getter = getattr(target, name, None)
        return getter if getter is not None else None
    try:
        value = getattr(target, name)
    except AttributeError:
        pass
    else:
        # ``JavaBean.__getattr__`` answers ``getXxx``/``isXxx`` with the *method*,
        # mirroring Java. MyBatis' Reflector invokes the getter, so a method object
        # must never end up as a bound parameter (it would reach the driver as
        # "cannot adapt type 'function'").
        return value() if callable(value) else value
    getter = getattr(target, f"get{name[:1].upper()}{name[1:]}", None)
    if callable(getter):
        return getter()
    # Java Bean property name -> Python field (gantryCaptureBO -> gantry_capture_bo)
    from com.ruoyi.common.core.domain.JavaBean import _resolve_field

    field_name = _resolve_field(type(target), name)
    return getattr(target, field_name) if field_name else None


def _join(chunks: Iterable[str]) -> str:
    """``DynamicContext`` semantics: whitespace-only chunks vanish, the rest is
    separated by one space."""
    parts = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
    return " ".join(parts)


class _Context:
    """Rendering state: output buffer, bindings and the foreach scope stack."""

    def __init__(self, params: ParamObject,
                 fragments: Mapping[str, Sequence["_Node"]]) -> None:
        self.params = params
        self.fragments = fragments
        self.chunks: list[str] = []
        self.bindings: dict[str, Any] = {}
        self.scopes: list[dict[str, Any]] = []
        self._counter = 0

    # ---------------------------------------------------------------- buffer
    def emit(self, text: str) -> None:
        if text:
            self.chunks.append(text)

    class _Capture:
        def __init__(self, context: "_Context") -> None:
            self._context = context
            self._saved: list[str] = []

        def __enter__(self) -> "_Context":
            self._saved = self._context.chunks
            self._context.chunks = []
            return self._context

        def __exit__(self, *_exc: Any) -> None:
            self.captured = self._context.chunks
            self._context.chunks = self._saved

    def capture(self) -> "_Context._Capture":
        return _Context._Capture(self)

    # ---------------------------------------------------------------- lookup
    def resolve(self, path: str) -> Any:
        head, _, tail = path.partition(".")
        value: Any = _MISSING
        for scope in reversed(self.scopes):
            if head in scope:
                value = scope[head]
                break
        if value is _MISSING:
            value = self.params.lookup(head)
        if tail:
            for part in tail.split("."):
                value = property_of(value, part)
        return value

    def bind(self, path: str) -> str:
        name = f"p{self._counter}"
        self._counter += 1
        self.bindings[name] = self.resolve(path)
        return f":{name}"

    def push(self, scope: dict[str, Any]) -> None:
        self.scopes.append(scope)

    def pop(self) -> None:
        self.scopes.pop()


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<missing>"


_MISSING = _Missing()


# --------------------------------------------------------------------------- nodes
class _Node:
    def render(self, context: _Context) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class _TextNode(_Node):
    def __init__(self, text: str) -> None:
        self.text = text

    def render(self, context: _Context) -> None:
        text = self.text
        if "#{" in text:
            text = _BIND_RE.sub(lambda m: context.bind(m.group(1)), text)
        if "${" in text:
            text = _INTERP_RE.sub(lambda m: _stringify(context.resolve(m.group(1))), text)
        context.emit(text)


class _IfNode(_Node):
    def __init__(self, test: str, children: list[_Node]) -> None:
        self.test = test
        self.children = children

    def render(self, context: _Context) -> None:
        if evaluate(self.test, context.resolve):
            for child in self.children:
                child.render(context)


class _WhereNode(_Node):
    def __init__(self, children: list[_Node]) -> None:
        self.children = children

    def render(self, context: _Context) -> None:
        content = _render_block(context, self.children)
        if not content:
            return
        stripped = _LEADING_BOOLEAN_RE.sub("", content)
        context.emit(f"WHERE {stripped}")


class _SetNode(_Node):
    def __init__(self, children: list[_Node]) -> None:
        self.children = children

    def render(self, context: _Context) -> None:
        content = _render_block(context, self.children)
        if not content:
            return
        if content.endswith(","):
            content = content[:-1]
        context.emit(f"SET {content}")


class _TrimNode(_Node):
    def __init__(self, prefix: str, suffix: str, prefix_overrides: str,
                 suffix_overrides: str, children: list[_Node]) -> None:
        self.prefix = prefix
        self.suffix = suffix
        self.prefix_overrides = [item for item in prefix_overrides.split("|") if item]
        self.suffix_overrides = [item for item in suffix_overrides.split("|") if item]
        self.children = children

    def render(self, context: _Context) -> None:
        content = _render_block(context, self.children)
        for token in self.prefix_overrides:
            if content[: len(token)].upper() == token.upper():
                content = content[len(token):]
                break
        for token in self.suffix_overrides:
            if content[-len(token):].upper() == token.upper():
                content = content[: -len(token)]
                break
        content = content.strip()
        if not content:
            return
        context.emit(f"{self.prefix}{content}{self.suffix}")


class _ChooseNode(_Node):
    def __init__(self, whens: list[tuple[str, list[_Node]]],
                 otherwise: Optional[list[_Node]]) -> None:
        self.whens = whens
        self.otherwise = otherwise

    def render(self, context: _Context) -> None:
        for test, children in self.whens:
            if evaluate(test, context.resolve):
                for child in children:
                    child.render(context)
                return
        for child in self.otherwise or []:
            child.render(context)


class _ForeachNode(_Node):
    def __init__(self, collection: str, item: str, index: Optional[str],
                 open_token: str, separator: str, close_token: str,
                 children: list[_Node]) -> None:
        self.collection = collection
        self.item = item
        self.index = index
        self.open_token = open_token
        self.separator = separator
        self.close_token = close_token
        self.children = children

    def render(self, context: _Context) -> None:
        items = context.params.lookup(self.collection)
        if items is None and self.collection == "collection":
            items = context.params.lookup("list")
        if items is None:
            raise SqlError(f"<foreach collection=\"{self.collection}\"> is null")
        if isinstance(items, Mapping):
            entries: list[tuple[Any, Any]] = list(items.items())
        elif isinstance(items, (str, bytes)):
            raise SqlError("<foreach> needs a collection, got a string")
        else:
            entries = list(enumerate(items))
        rendered: list[str] = []
        for key, value in entries:
            scope = {self.item: value}
            if self.index:
                scope[self.index] = key
            context.push(scope)
            try:
                piece = _render_block(context, self.children)
            finally:
                context.pop()
            if piece:
                rendered.append(piece)
        if not rendered:
            return
        body = self.separator.join(rendered)
        context.emit(f"{self.open_token}{body}{self.close_token}")


class _IncludeNode(_Node):
    def __init__(self, refid: str, properties: dict[str, str],
                 children: list[_Node]) -> None:
        self.refid = refid
        self.properties = properties
        self.children = children

    def render(self, context: _Context) -> None:
        nodes = context.fragments.get(self.refid)
        if nodes is None:
            raise SqlError(f"<include refid=\"{self.refid}\"> not found")
        scope = dict(self.properties)
        if scope:
            context.push(scope)
        try:
            for node in nodes:
                node.render(context)
        finally:
            if scope:
                context.pop()


def _render_block(context: _Context, children: Sequence[_Node]) -> str:
    capture = context.capture()
    with capture:
        for child in children:
            child.render(context)
    return _join(capture.captured)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# --------------------------------------------------------------------------- parsing
def text_statement(namespace: str, statement_id: str, kind: str, sql: str,
                   parameter_type: Optional[str] = None,
                   result_type: Optional[str] = None,
                   resource: str = "@annotation") -> Statement:
    """Statement built from ``@Select`` / ``@Update`` SQL (no dynamic tags)."""
    return Statement(
        namespace=namespace,
        statement_id=statement_id,
        kind=kind,
        parameter_type=parameter_type,
        result_type=result_type,
        result_map_id=None,
        nodes=[_TextNode(sql)],
        resource=resource,
    )


def load_mapper_xml(path: str | Path) -> MapperXml:
    """Parse one mapper XML file (``XMLMapperBuilder``)."""
    file_path = Path(path)
    try:
        root = ElementTree.fromstring(file_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise SqlError(f"{file_path.name}: {error}") from error
    if root.tag != "mapper":
        raise SqlError(f"{file_path.name}: root element is <{root.tag}>, expected <mapper>")
    namespace = root.get("namespace") or ""
    mapper = MapperXml(namespace=namespace, resource=file_path.name)

    for element in root:
        tag = element.tag
        if tag == "resultMap":
            result_map = ResultMap(map_id=element.get("id") or "",
                                   type_name=element.get("type") or "")
            for child in element:
                if child.tag in ("result", "id"):
                    prop = child.get("property")
                    column = child.get("column")
                    if prop and column:
                        result_map.columns.append(ColumnMapping(prop, column))
                elif child.tag in ("association", "collection", "discriminator"):
                    log.warning("%s: <%s> in resultMap %s is not supported",
                                file_path.name, child.tag, result_map.map_id)
            mapper.result_maps[result_map.map_id] = result_map
        elif tag == "sql":
            mapper.fragments[element.get("id") or ""] = _build_children(element)
        elif tag in _STATEMENT_TAGS:
            statement = Statement(
                namespace=namespace,
                statement_id=element.get("id") or "",
                kind=tag,
                parameter_type=element.get("parameterType"),
                result_type=element.get("resultType"),
                result_map_id=element.get("resultMap"),
                nodes=_build_children(element),
                resource=file_path.name,
            )
            mapper.statements[statement.statement_id] = statement
        elif tag in ("cache", "cache-ref"):
            log.debug("%s: <%s> ignored (no second-level cache in Python)", file_path.name, tag)
        else:
            log.warning("%s: unknown element <%s> ignored", file_path.name, tag)
    return mapper


def _build_children(element: ElementTree.Element) -> list[_Node]:
    nodes: list[_Node] = []
    if element.text:
        nodes.append(_TextNode(element.text))
    for child in element:
        nodes.append(_build_node(child))
        if child.tail:
            nodes.append(_TextNode(child.tail))
    return nodes


def _build_node(element: ElementTree.Element) -> _Node:
    tag = element.tag
    if tag == "if":
        return _IfNode(element.get("test") or "", _build_children(element))
    if tag == "where":
        return _WhereNode(_build_children(element))
    if tag == "set":
        return _SetNode(_build_children(element))
    if tag == "trim":
        return _TrimNode(
            prefix=element.get("prefix") or "",
            suffix=element.get("suffix") or "",
            prefix_overrides=element.get("prefixOverrides") or "",
            suffix_overrides=element.get("suffixOverrides") or "",
            children=_build_children(element),
        )
    if tag == "choose":
        whens: list[tuple[str, list[_Node]]] = []
        otherwise: Optional[list[_Node]] = None
        for child in element:
            if child.tag == "when":
                whens.append((child.get("test") or "", _build_children(child)))
            elif child.tag == "otherwise":
                otherwise = _build_children(child)
        return _ChooseNode(whens, otherwise)
    if tag == "foreach":
        return _ForeachNode(
            collection=element.get("collection") or "list",
            item=element.get("item") or "item",
            index=element.get("index"),
            open_token=element.get("open") or "",
            separator=element.get("separator") or "",
            close_token=element.get("close") or "",
            children=_build_children(element),
        )
    if tag == "include":
        properties = {
            child.get("name") or "": child.get("value") or ""
            for child in element if child.tag == "property"
        }
        return _IncludeNode(element.get("refid") or "", properties, _build_children(element))
    if tag in ("selectKey", "bind"):
        raise SqlError(f"<{tag}> is not supported by the Python mapper engine")
    # Unknown tag: keep the text so nothing silently disappears
    log.warning("unknown dynamic tag <%s> treated as static text", tag)
    return _TextNode("".join(element.itertext()))


# --------------------------------------------------------------------------- results
_TYPE_HINT_CACHE: dict[type, dict[str, Any]] = {}


def _entity_field_types(entity_cls: type) -> dict[str, Any]:
    cached = _TYPE_HINT_CACHE.get(entity_cls)
    if cached is not None:
        return cached
    try:
        hints = typing.get_type_hints(entity_cls)
    except Exception:  # noqa: BLE001 - a forward ref we cannot resolve
        hints = dict(getattr(entity_cls, "__annotations__", {}) or {})
    _TYPE_HINT_CACHE[entity_cls] = hints
    return hints


def _unwrap_optional(hint: Any) -> Any:
    origin = typing.get_origin(hint)
    if origin is None:
        return hint
    if origin is typing.Union or str(origin) == "types.UnionType":
        args = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return hint


def coerce_value(value: Any, hint: Any) -> Any:
    """Convert a DBAPI value to the Java field type (JDBC ``ResultSet.getXxx``)."""
    if value is None:
        return None
    hint = _unwrap_optional(hint)
    if hint in (Any, None, typing.Any, object):
        return value
    try:
        if hint is str:
            return _to_java_string(value)
        if hint is bool:
            if isinstance(value, str):
                return value.strip().lower() in ("1", "t", "true", "y", "yes")
            return bool(value)
        if hint is int:
            if isinstance(value, Decimal):
                return int(value)
            if isinstance(value, str):
                return int(value.strip() or 0)
            return int(value)
        if hint is float:
            return float(value)
        if hint is Decimal:
            return value if isinstance(value, Decimal) else Decimal(str(value))
        if hint is datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return datetime.combine(value, time.min)
            if isinstance(value, str):
                from com.ruoyi.common.utils.DateUtils import DateUtils

                return DateUtils.parseDate(value)
            return value
        if hint is date:
            if isinstance(value, datetime):
                return value.date()
            return value
        if hint is bytes:
            return value.encode("utf-8") if isinstance(value, str) else bytes(value)
    except (TypeError, ValueError, ArithmeticError):
        log.debug("cannot coerce %r to %s", value, hint)
        return value
    return value


def _to_java_string(value: Any) -> str:
    """``ResultSet.getString()``: timestamps keep the driver's text form."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, datetime):
        text = value.strftime("%Y-%m-%d %H:%M:%S")
        if value.microsecond:
            text += f".{value.microsecond:06d}".rstrip("0")
        return text
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def map_row(row: Mapping[str, Any], entity_cls: type,
            result_map: Optional[ResultMap] = None) -> Any:
    """Build one entity from a row (``DefaultResultSetHandler.createResultObject``).

    ``resultMap`` columns are applied first, then -- exactly like MyBatis'
    default ``autoMappingBehavior=PARTIAL`` -- every remaining column is mapped
    through ``map-underscore-to-camel-case``.
    """
    from com.ruoyi.common.core.domain.JavaBean import _resolve_field

    hints = _entity_field_types(entity_cls)
    lookup = {str(key).lower(): value for key, value in row.items()}
    entity = entity_cls()
    used: set[str] = set()

    for mapping in (result_map.columns if result_map else ()):
        key = mapping.column.lower()
        if key not in lookup:
            continue
        used.add(key)
        field_name = _resolve_field(entity_cls, mapping.property) or mapping.property
        setattr(entity, field_name, coerce_value(lookup[key], hints.get(field_name)))

    for column_lower, value in lookup.items():
        if column_lower in used:
            continue
        field_name = _resolve_field(entity_cls, column_lower)
        if field_name is None:
            # MyBatis simply ignores unmapped columns under PARTIAL auto-mapping
            continue
        setattr(entity, field_name, coerce_value(value, hints.get(field_name)))

    return entity


def statement_returns_single(returns: Optional[str]) -> bool:
    """``List<X>`` -> list; every other return type is a single object."""
    if not returns:
        return True
    text = returns.strip()
    return not (text.startswith("List<") or text.startswith("Collection<")
                or text.startswith("Set<"))
