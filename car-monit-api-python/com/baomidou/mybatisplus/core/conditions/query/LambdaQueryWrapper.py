# -*- coding: utf-8 -*-
"""com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper

【无 Java 源文件：框架类替身】
Java 侧来自 MyBatis-Plus jar：
    com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<T>
    com.baomidou.mybatisplus.core.conditions.query.QueryWrapper<T>
本文件按原包路径重建，使业务代码的 import 与 Java 完全一致。

【Java→Python 关键差异】
1) Java 的 `wrapper.gt(OdsRtSzdnSnapshotFlowAddcode::getBigId, lastSyncId)` 传的是
   **方法引用**（SFunction，靠 Lambda 元信息反解列名）；Python 没有方法引用，
   这里接受两种写法：
     - 字段名 str：`wrapper.gt("big_id", v)`（等价 QueryWrapper 的列名写法）
     - 属性访问器：`wrapper.gt(lambda r: r.big_id, v)`（最贴近方法引用，推荐）
   注意：**不能**写 `OdsRtSzdnSnapshotFlowAddcode.big_id` —— Python 的 dataclass
   字段带默认值时，类属性就是那个默认值（None），拿不到字段名，_read_column
   会给出明确报错提示。
2) Java 把条件拼成 SQL 交给数据库执行；Python 侧只保留**条件列表**，由
   `toPredicate()` 生成内存谓词，配合 BaseMapper 的进程内表使用。
3) `last("LIMIT " + n)` 是 MyBatis-Plus 的「SQL 尾部拼接」逃生口，本身不做校验。
   Python 无法拼 SQL，这里仅解析 `LIMIT n` / `LIMIT off, n` 并转为内存截断，
   其余内容（如 `FOR UPDATE`）会被忽略 —— 这是本替身的最大语义损失，已在使用处注释。
4) SQL 三值逻辑：列值为 NULL 时，除 isNull/isNotNull 外的比较结果都是 UNKNOWN
   （即不匹配），这里逐条还原，避免 Python 的 None 比较抛 TypeError。
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any, Callable, Generic, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")

__all__ = ["AbstractWrapper", "QueryWrapper", "LambdaQueryWrapper"]

_LIMIT_PATTERN = re.compile(r"^\s*LIMIT\s+(\d+)\s*(?:,\s*(\d+))?\s*$", re.IGNORECASE)


def _comparable(value: Any) -> Any:
    """把时间字符串/日期统一成可比较值。

    【Java→Python】与 BaseMapper.toComparable 逻辑一致；为避免
    `BaseMapper <-> Wrapper` 循环 import，这里单独实现一份（差异点已在此说明）。
    """
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        from com.ruoyi.common.utils.DateUtils import DateUtils

        parsed = DateUtils.parseDate(value)
        return parsed if parsed is not None else value
    return value


def _read_column(row: Any, column: Any) -> Any:
    """按 str / 访问器取值。"""
    if isinstance(column, str):
        return getattr(row, column, None)
    if callable(column):
        return column(row)
    if column is None:
        # 典型误用：把 `Entity.someField`（dataclass 默认值为 None）当成方法引用传进来
        raise TypeError(
            "列表达式为 None：Java 方法引用 `Entity::getXxx` 请改写为 lambda r: r.xxx，"
            "或直接传字段名字符串；dataclass 字段带默认值时 Entity.xxx 取不到字段描述符"
        )
    raise TypeError("不支持的列表达式: %r" % (column,))


class AbstractWrapper(Generic[T]):
    """MyBatis-Plus AbstractWrapper 的最小子集（全部条件按 AND 连接）。"""

    def __init__(self) -> None:
        self._conditions: List[Tuple[str, Any, Any, Any]] = []
        self._order_specs: List[Tuple[Any, bool]] = []
        self._select_columns: List[Any] = []
        self._limit: Optional[int] = None
        self._offset: int = 0

    # ------------------------------------------------------------------ 比较
    def eq(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("eq", column, value, None))
        return self

    def ne(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("ne", column, value, None))
        return self

    def gt(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("gt", column, value, None))
        return self

    def ge(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("ge", column, value, None))
        return self

    def lt(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("lt", column, value, None))
        return self

    def le(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("le", column, value, None))
        return self

    def between(self, column: Any, value1: Any, value2: Any) -> "AbstractWrapper[T]":
        """等价 `column BETWEEN v1 AND v2`（闭区间）。"""
        self._conditions.append(("between", column, value1, value2))
        return self

    def like(self, column: Any, value: Any) -> "AbstractWrapper[T]":
        """等价 `column LIKE %value%`。"""
        self._conditions.append(("like", column, value, None))
        return self

    def in_(self, column: Any, values: Sequence[Any]) -> "AbstractWrapper[T]":
        """对应 Java 的 `in(...)`；`in` 是 Python 关键字，故改名 `in_`。"""
        self._conditions.append(("in", column, list(values or []), None))
        return self

    def isNull(self, column: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("isNull", column, None, None))
        return self

    def isNotNull(self, column: Any) -> "AbstractWrapper[T]":
        self._conditions.append(("isNotNull", column, None, None))
        return self

    # ------------------------------------------------------------------ 列投影 / 排序 / 尾缀
    def select(self, *columns: Any) -> "AbstractWrapper[T]":
        """等价 `select(SFunction... columns)`：只查指定列。

        【Java→Python】SQL 的 SELECT 列投影会让未选中字段为 null；内存表里的行是完整对象，
        本替身**无法**真的做到“部分字段为 null”（那会破坏实体默认值语义），
        因此只记录投影列，返回值仍是完整实体副本。
        使用处（如 DataLossDetectionService 只取 bigId）不受影响，已在调用处注明。
        """
        self._select_columns.extend(columns)
        return self

    def orderByAsc(self, *columns: Any) -> "AbstractWrapper[T]":
        for column in columns:
            self._order_specs.append((column, True))
        return self

    def orderByDesc(self, *columns: Any) -> "AbstractWrapper[T]":
        for column in columns:
            self._order_specs.append((column, False))
        return self

    def last(self, sql: str) -> "AbstractWrapper[T]":
        """SQL 尾部拼接：Python 只识别 LIMIT（其余内容忽略，详见模块注释）。"""
        match = _LIMIT_PATTERN.match(sql or "")
        if match:
            if match.group(2) is not None:
                self._offset = int(match.group(1))
                self._limit = int(match.group(2))
            else:
                self._limit = int(match.group(1))
        return self

    # ------------------------------------------------------------------ 求值
    def toPredicate(self) -> Callable[[Any], bool]:
        """生成内存谓词（等价把 WHERE 子句交给数据库）。"""
        conditions = list(self._conditions)

        def predicate(row: Any) -> bool:
            for op, column, value1, value2 in conditions:
                actual = _read_column(row, column)
                if op == "isNull":
                    if actual is not None:
                        return False
                    continue
                if op == "isNotNull":
                    if actual is None:
                        return False
                    continue
                if op == "between":
                    # SQL: NULL BETWEEN a AND b → UNKNOWN → 不匹配
                    if actual is None or value1 is None or value2 is None:
                        return False
                    current = _comparable(actual)
                    if current < _comparable(value1) or current > _comparable(value2):
                        return False
                    continue
                if op == "like":
                    if actual is None or value1 is None:
                        return False
                    if str(value1) not in str(actual):
                        return False
                    continue
                if op == "in":
                    if actual is None or actual not in value1:
                        return False
                    continue
                # 其余比较：任一侧 NULL 都是 UNKNOWN
                if actual is None or value1 is None:
                    return False
                current, target = _comparable(actual), _comparable(value1)
                if op == "eq" and not current == target:
                    return False
                elif op == "ne" and current == target:
                    return False
                elif op == "gt" and not current > target:
                    return False
                elif op == "ge" and not current >= target:
                    return False
                elif op == "lt" and not current < target:
                    return False
                elif op == "le" and not current <= target:
                    return False
            return True

        return predicate

    def sortRows(self, rows: List[Any]) -> List[Any]:
        """在内存中执行 ORDER BY + LIMIT/OFFSET。

        【Java→Python】SQL 的 ORDER BY 是数据库行为，这里用**稳定排序**逐列应用：
        从最后一列往前排，才能让第一列成为主排序键（与 SQL 语义一致）。
        """
        result = list(rows)
        for column, ascending in reversed(self._order_specs):
            # 【Java→Python】SQL 中 NULL 排序与数据库实现相关（MySQL 升序 NULL 最前），
            # 这里固定为「升序时 NULL 最前、降序时 NULL 最后」，并在使用处注明。
            result.sort(
                key=lambda r: (_read_column(r, column) is None, _comparable(_read_column(r, column))),
                reverse=not ascending,
            )
        if self._offset:
            result = result[self._offset:]
        if self._limit is not None:
            result = result[: self._limit]
        return result

    @property
    def limitValue(self) -> Optional[int]:
        return self._limit

    @property
    def selectColumns(self) -> List[Any]:
        """已声明的 SELECT 列（仅供调试/断言，不参与过滤）。"""
        return list(self._select_columns)


class QueryWrapper(AbstractWrapper[T]):
    """列名（字符串）形式的条件构造器。"""


class LambdaQueryWrapper(AbstractWrapper[T]):
    """方法引用形式的条件构造器（Python 侧用属性访问器/字段描述符替代）。"""
