# -*- coding: utf-8 -*-
"""Spring MVC argument binding.

Migrated from: pro-base-common/.../core/controller/BaseController.java
                (``@InitBinder`` + ``@ModelAttribute`` behaviour)

Spring binds a controller parameter that has no annotation as a *model
attribute*: every matching request parameter is converted to the target type
and pushed through the setter. This module reproduces that for the ported
dataclass entities:

* the parameter name is matched against the Java property name
  (``carNo``), the Python field name (``car_no``) and a case-insensitive
  fallback (acronyms such as ``gantryCaptureBO``);
* unknown request parameters are ignored (Spring only reports binding errors
  for known fields);
* an empty string becomes ``null`` for non-String targets (Spring's
  ``StringToNumber``/``StringToDate`` converters do the same);
* ``Date``/``LocalDate`` values go through ``DateUtils.parseDate``, exactly
  like ``BaseController.initBinder``.
* a field whose declared type is another dataclass is bound recursively, and
  ``List<Bean>`` binds each element -- Jackson's nested deserialisation
  (``@RequestBody TrailInfo`` -> ``ZdataTrailTracks`` + ``List<TrailBo>``).

A conversion failure raises :class:`BindingError`, which the dispatcher turns
into an HTTP 400 -- Spring's ``BindException`` behaviour.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import types
import typing
from decimal import Decimal
from typing import Any, Mapping, Optional, get_args, get_origin

from com.ruoyi.common.core.domain.JavaBean import snake_to_camel
from com.ruoyi.common.utils.DateUtils import DateUtils

__all__ = ["BindingError", "bind_bean", "bind_value", "coerce"]


class BindingError(ValueError):
    """Equivalent of ``org.springframework.validation.BindException``."""

    def __init__(self, field: str, value: Any, target: Any) -> None:
        super().__init__(f"Failed to convert property value of type '{type(value).__name__}' "
                         f"to required type for property '{field}'")
        self.field = field
        self.value = value
        self.target = target


_HINT_CACHE: dict[type, dict[str, Any]] = {}


def _type_hints(cls: type) -> dict[str, Any]:
    cached = _HINT_CACHE.get(cls)
    if cached is None:
        try:
            cached = typing.get_type_hints(cls)
        except Exception:
            cached = {field.name: field.type for field in dataclasses.fields(cls)}
        _HINT_CACHE[cls] = cached
    return cached


def _unwrap(annotation: Any) -> Any:
    """``Optional[int]`` / ``int | None`` -> ``int``."""
    origin = get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        return args[0] if args else str
    return annotation


def _first(raw: Any) -> Any:
    """Multi-value request parameters behave like ``getParameter`` (first wins)."""
    if isinstance(raw, (list, tuple)):
        return raw[0] if raw else None
    return raw


def _lookup(params: Mapping[str, Any], field_name: str, first: bool = True) -> Any:
    """Find a value by Java property name, Python field name, then case-insensitively.

    ``first`` collapses a multi-value *request parameter* to its first element
    (``getParameter`` semantics).  It must stay ``False`` for a JSON body:
    Jackson binds ``List<Bean> trailList`` to the whole array, so collapsing
    would hand ``coerce`` a single object and silently lose the elements.
    """
    java_name = snake_to_camel(field_name)
    for candidate in (java_name, field_name):
        if candidate in params:
            return _first(params[candidate]) if first else params[candidate]
    lowered = {str(key).lower(): value for key, value in params.items()}
    for candidate in (java_name.lower(), field_name.lower()):
        if candidate in lowered:
            return _first(lowered[candidate]) if first else lowered[candidate]
    return None


def coerce(value: Any, annotation: Any, field: str = "") -> Any:
    """Convert a request value to the declared Java type of a field."""
    target = _unwrap(annotation)

    if target in (Any, typing.Any, None):
        return value
    if isinstance(target, str):  # forward reference that could not be resolved
        return value

    if target is str:
        return value if isinstance(value, str) else str(value)

    if value == "":
        # Spring: empty string -> null for every non-String target
        return None

    try:
        if target is bool:
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            # Spring's StringToBooleanConverter accepts true/on/yes/1 and false/off/no/0
            if text in ("true", "on", "yes", "1"):
                return True
            if text in ("false", "off", "no", "0"):
                return False
            raise ValueError(text)
        if target is int:
            if isinstance(value, bool):
                raise ValueError(value)
            return int(float(value)) if isinstance(value, float) else int(str(value).strip())
        if target is float:
            return float(value)
        if target is Decimal:
            return Decimal(str(value).strip())
        if target is _dt.datetime:
            parsed = DateUtils.parseDate(value) if isinstance(value, str) else value
            if parsed is None:
                raise ValueError(value)
            return parsed if isinstance(parsed, _dt.datetime) else _dt.datetime.combine(parsed, _dt.time())
        if target is _dt.date:
            parsed = DateUtils.parseDate(value) if isinstance(value, str) else value
            if parsed is None:
                raise ValueError(value)
            return parsed.date() if isinstance(parsed, _dt.datetime) else parsed
        if target is _dt.time:
            return _dt.time.fromisoformat(str(value))
        if dataclasses.is_dataclass(target):
            # 【Java→Python】Jackson 按字段声明类型递归反序列化嵌套对象；
            # 这里用 dataclass 目标类完成同样的递归（值不是对象时原样返回）。
            return bind_json(target, value) if isinstance(value, dict) else value
        origin = get_origin(target)
        if origin in (list, set, frozenset, tuple):
            items = value if isinstance(value, (list, tuple)) else str(value).split(",")
            element_type = get_args(target)[0] if get_args(target) else str
            converted = [coerce(item, element_type, field) for item in items if item != ""]
            return converted if origin is not tuple else tuple(converted)
        if origin is dict:
            return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as error:
        if isinstance(error, BindingError):
            raise
        raise BindingError(field, value, target) from error
    return value


def bind_bean(cls: type, params: Mapping[str, Any]) -> Any:
    """Instantiate ``cls`` and populate it from request parameters."""
    bean = cls()
    if not params or not dataclasses.is_dataclass(cls):
        return bean
    hints = _type_hints(cls)
    for field_info in dataclasses.fields(cls):
        raw = _lookup(params, field_info.name)
        if raw is None:
            continue
        setattr(bean, field_info.name, coerce(raw, hints.get(field_info.name, field_info.type), field_info.name))
    return bean


def bind_value(raw: Any, annotation: Any, name: str = "") -> Any:
    """Bind a single ``@PathVariable`` / ``@RequestParam`` value."""
    return coerce(raw, annotation, name)


def bind_json(cls: type, payload: Any) -> Any:
    """Bind a ``@RequestBody`` payload (JSON object) to a dataclass entity."""
    if not isinstance(payload, dict):
        return payload
    bean = cls()
    hints = _type_hints(cls)
    for field_info in dataclasses.fields(cls):
        raw = _lookup(payload, field_info.name, first=False)
        if raw is None:
            continue
        setattr(bean, field_info.name, coerce(raw, hints.get(field_info.name, field_info.type), field_info.name))
    return bean
