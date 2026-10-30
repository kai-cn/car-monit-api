# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.RangeQueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.RangeQueryBuilder``。
本工程用法（EsQueryService.queryFromEs）：
    QueryBuilders.rangeQuery("snapshotTime").gte(formatDateTime(startTime))
    QueryBuilders.rangeQuery("snapshotTime").lt(formatDateTime(endTime.plusDays(1)))

【Java→Python】关键差异
1) Java 的边界方法有 ``from/gt/gte/to/lt/lte`` 五个（均链式返回 this）。
   【Java→Python】``from`` 是 Python **关键字**（``queryBuilder.from(...)`` 会直接
   ``SyntaxError``），只能改名 ``from_``；``gt/gte/lt/lte/to`` 不受影响。
2) 真实 ES 在服务端比较（数值/日期按 mapping 类型比较，字符串按字典序）；
   替身的文档值来自 ``JSON.toJSONString``，时间已是 ``"yyyy-MM-dd HH:mm:ss"``
   字符串，**字典序与时间序一致**，因此直接字符串比较即可。
3) 若文档值与边界类型不同（如 int vs str），先尝试原生比较，失败后退化为
   字符串比较；字段缺失或值为 null 时不命中（与 ES 行为一致）。
4) ``format(String)`` 在 optimization 包中被用来指定时间格式
   （``.format("yyyy-MM-dd HH:mm:ss")``）；替身**只保存不解析** ——
   ``_source`` 里的时间本来就是同格式字符串，直接字典序比较即等价。
5) ``timeZone`` / ``relation`` 本工程未使用，不实现。
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from org.elasticsearch.index.query.QueryBuilder import QueryBuilder, _MISSING, _field_value

__all__ = ["RangeQueryBuilder"]


class RangeQueryBuilder(QueryBuilder):
    """``range`` 查询的替身（gt/gte/lt/lte）。"""

    def __init__(self, field: str) -> None:
        self._field = field
        # 保存 (运算符, 边界值)，按添加顺序依次校验
        self._bounds: List[Tuple[str, Any]] = []
        #: ES 日期格式（如 "yyyy-MM-dd HH:mm:ss"）；仅记录，不参与比较
        self._format: Optional[str] = None

    # ------------------------------------------------------------------ 链式 setter
    def format(self, date_format: str) -> "RangeQueryBuilder":
        """对应 ``format(String)``：指定日期解析格式（替身只保存）。"""
        self._format = date_format
        return self

    def gt(self, value: Any) -> "RangeQueryBuilder":
        self._bounds.append(("gt", value))
        return self

    def gte(self, value: Any) -> "RangeQueryBuilder":
        self._bounds.append(("gte", value))
        return self

    def lt(self, value: Any) -> "RangeQueryBuilder":
        self._bounds.append(("lt", value))
        return self

    def lte(self, value: Any) -> "RangeQueryBuilder":
        self._bounds.append(("lte", value))
        return self

    def from_(self, value: Any) -> "RangeQueryBuilder":
        """对应 ``from(Object)``（等价 gte；from 是 Python 关键字，故加下划线）。"""
        return self.gte(value)

    def to(self, value: Any) -> "RangeQueryBuilder":
        """对应 ``to(Object)``（等价 lte）。"""
        return self.lte(value)

    # ------------------------------------------------------------------ 匹配
    def matches(self, document: Any) -> bool:
        actual = _field_value(document, self._field)
        if actual is _MISSING or actual is None:
            return False
        for operator, bound in self._bounds:
            if bound is None:
                continue
            comparison = self._compare(actual, bound)
            if comparison is None:
                # 不可比较（真实 ES 会抛 search_phase_execution_exception），
                # 这里保守地视为不命中，避免整个查询中断。
                return False
            if operator == "gt" and not comparison > 0:
                return False
            if operator == "gte" and not comparison >= 0:
                return False
            if operator == "lt" and not comparison < 0:
                return False
            if operator == "lte" and not comparison <= 0:
                return False
        return True

    @staticmethod
    def _compare(left: Any, right: Any) -> Optional[int]:
        """返回 -1/0/1；无法比较时返回 None。"""
        try:
            if left < right:
                return -1
            if left > right:
                return 1
            return 0
        except TypeError:
            pass
        try:
            left_text, right_text = str(left), str(right)
            if left_text < right_text:
                return -1
            if left_text > right_text:
                return 1
            return 0
        except Exception:  # noqa: BLE001 - 兜底：不可比较
            return None

    def __repr__(self) -> str:
        return "RangeQueryBuilder(field=%r, bounds=%r)" % (self._field, self._bounds)
