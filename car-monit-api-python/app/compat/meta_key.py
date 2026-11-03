# -*- coding: utf-8 -*-
"""Resolve a ported Python class to its key in ``app/compat/java_meta.py``.

Migrated from: (no Java source -- mirrors the reflection lookups of
                Jackson's ``ObjectMapper`` and MyBatis-Plus' ``TableInfoHelper``,
                both of which key everything by the Java FQCN)

Why this exists
---------------
The generated metadata tables are keyed by the Java fully-qualified class
name, e.g. ``com.ruoyi.base.domain.TrailBo``. The port keeps the Java package
path as the Python module path, so ``cls.__module__`` **already is** that
FQCN. Concatenating ``cls.__module__ + "." + cls.__name__`` therefore produces
``com.ruoyi.base.domain.TrailBo.TrailBo``, which is never present -- every
lookup then silently fell through to its default. That is why
``/base/sysutil/getByTrailBo`` emitted ``borderWeighingCaptureBo`` instead of
Jackson's ``borderWeighingCaptureBO``, and why ``@JsonFormat`` patterns were
never applied.

Resolution order
----------------
1. ``module + "." + name`` -- a module that hosts several classes (the Java
   source had nested/multiple top-level classes, so the key keeps both);
2. ``module``            -- the normal case, module path == FQCN;
3. ``name``              -- tables generated from the simple class name only.
"""
from __future__ import annotations

from typing import Any, Mapping

__all__ = ["meta_keys", "meta_get"]


def meta_keys(cls: type) -> tuple[str, ...]:
    """Candidate metadata keys of ``cls``, most specific first."""
    module = getattr(cls, "__module__", "") or ""
    name = getattr(cls, "__name__", "") or ""
    return tuple(key for key in (f"{module}.{name}", module, name) if key)


def meta_get(table: Mapping[str, Any], cls: type, default: Any = None) -> Any:
    """First value in ``table`` matching one of :func:`meta_keys`."""
    for key in meta_keys(cls):
        if key in table:
            return table[key]
    return default
