# -*- coding: utf-8 -*-
"""PageHelper 1.4.7 behaviour.

Migrated from: com.ruoyi.common.utils.PageUtils (extends PageHelper)
                + PageDomain / TableSupport
                + PageInterceptor / AbstractHelperDialect

What PageHelper does to the *first* statement executed after
``PageHelper.startPage(...)``:

1. run ``SELECT count(0) FROM ( <original without ORDER BY> ) tmp_count``;
2. with ``reasonable=true`` clamp ``pageNum`` to ``[1, pages]``;
3. append ``LIMIT ? OFFSET ?`` to the original statement;
4. expose the count to ``new PageInfo(list).getTotal()``.

Steps 1-4 are reproduced here. The count reaches ``PageInfo`` through the
already-ported ``PageUtils.set_page_total`` hook, so no business file changes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from com.ruoyi.common.utils.PageUtils import PageUtils

__all__ = [
    "PageRequest",
    "current_page_request",
    "strip_order_by",
    "build_count_sql",
    "add_pagination",
    "clamp_page_number",
]

_ORDER_BY = "ORDER BY"


@dataclass
class PageRequest:
    page_num: int
    page_size: int
    order_by: str = ""
    reasonable: bool = True


def current_page_request() -> Optional[PageRequest]:
    """Read ``PageHelper``'s thread local (set by ``BaseController.startPage``).

    The context is consumed by the first SELECT, exactly like PageHelper's
    interceptor, but ``total`` stays readable for ``getDataTable``.
    """
    context = PageUtils._context() if hasattr(PageUtils, "_context") else None
    if context is None or getattr(context, "consumed", False):
        return None
    if context.page_size is None:
        return None
    context.consumed = True  # type: ignore[attr-defined]
    page_num = context.page_num if context.page_num and context.page_num > 0 else 1
    return PageRequest(
        page_num=int(page_num),
        page_size=int(context.page_size),
        order_by=(context.order_by or "").strip(),
        reasonable=bool(context.reasonable),
    )


def _scan_order_by(sql: str) -> int:
    """Return the index of the top-level ``ORDER BY`` or -1."""
    depth = 0
    in_single = False
    in_double = False
    index = 0
    length = len(sql)
    upper = sql.upper()
    found = -1
    while index < length:
        char = sql[index]
        if in_single:
            if char == "'":
                if index + 1 < length and sql[index + 1] == "'":
                    index += 2
                    continue
                in_single = False
            index += 1
            continue
        if in_double:
            if char == '"':
                in_double = False
            index += 1
            continue
        if char == "'":
            in_single = True
        elif char == '"':
            in_double = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and upper.startswith(_ORDER_BY, index):
            previous = sql[index - 1] if index else " "
            if not (previous.isalnum() or previous == "_"):
                found = index
                index += len(_ORDER_BY)
                continue
        index += 1
    return found


def strip_order_by(sql: str) -> str:
    """Remove the top-level ``ORDER BY`` (PageHelper's COUNT rewrite does this)."""
    index = _scan_order_by(sql)
    return sql if index < 0 else sql[:index].rstrip()


def build_count_sql(sql: str) -> str:
    """``SELECT count(0) FROM ( <sql without order by> ) tmp_count``."""
    return f"SELECT count(0) FROM (\n{strip_order_by(sql)}\n) tmp_count"


def clamp_page_number(page: PageRequest, total: int) -> int:
    """PageHelper ``reasonable``: pageNum is clamped to the last page."""
    if not page.reasonable or page.page_size <= 0:
        return max(1, page.page_num)
    pages = (total + page.page_size - 1) // page.page_size
    if pages <= 0:
        return 1
    return min(max(1, page.page_num), pages)


def add_pagination(sql: str, page: PageRequest, page_num: int,
                   params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Append the request ``orderBy`` and ``LIMIT/OFFSET`` bind parameters."""
    if page.order_by:
        sql = _inject_order_by(sql, page.order_by)
    offset = (max(1, page_num) - 1) * page.page_size
    bound = dict(params)
    bound["page_limit"] = page.page_size
    bound["page_offset"] = offset
    return f"{sql.rstrip()}\n LIMIT :page_limit OFFSET :page_offset", bound


def _inject_order_by(sql: str, order_by: str) -> str:
    """``PageHelper.startPage(n, s, orderBy)`` semantics.

    When the statement already has an ``ORDER BY`` PageHelper's
    ``OrderByParser`` prepends the requested columns to the existing list, so
    the request never *replaces* an explicit business ordering.
    """
    index = _scan_order_by(sql)
    if index < 0:
        return f"{sql.rstrip()}\n ORDER BY {order_by}"
    # insert right after the "ORDER BY" keyword
    head = sql[: index + len(_ORDER_BY)]
    tail = sql[index + len(_ORDER_BY):]
    return f"{head} {order_by},{tail}"


_ = re  # kept for future dialect-specific rewrites
