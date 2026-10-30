# -*- coding: utf-8 -*-
"""org.springframework.jdbc.core.JdbcTemplate

【无 Java 源文件：框架类替身】
业务代码用法（optimization 包）：
    @Autowired(required = false) private JdbcTemplate jdbcTemplate;
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql, startDate, endDate);
    int affected = jdbcTemplate.update(sql);
    jdbcTemplate.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ...");

【Java→Python 关键差异】
1) Java 的 `JdbcTemplate` 由 Spring 用 `DataSource` 构造并管理连接池；
   Python 侧**没有真实数据库连接**，替身只在内存里记录已执行的 SQL，
   并按“预设结果”返回 —— 目的是让 service 的代码路径（缓存命中/未命中、
   `jdbcTemplate == null` 的降级分支）都能被完整执行与断言。
2) `@Autowired(required = false)` 表示该 Bean **可能不存在**；Python 侧对应
   构造器参数默认 `None`（缺省即“容器里没有这个 Bean”，走降级分支）。
3) Java 的 `queryForList(String, Object...)` 用 `?` 占位符 + 变长参数；
   Python 侧保留同样的 `(sql, *args)` 形状（不做真正的参数绑定）。
4) Java 的 `update(String)` 返回受影响行数；替身返回预设值（默认 0）。
5) 真实实现会抛 `DataAccessException`；替身不抛，业务代码里的
   `try/catch (Exception e)` 分支需通过 `failOn` 开关显式触发（见测试辅助）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["JdbcTemplate"]


class JdbcTemplate(object):
    """`JdbcTemplate` 的进程内替身（记录 SQL + 可编排返回值）。"""

    def __init__(self, dataSource: Any = None) -> None:
        #: Java: `JdbcTemplate(DataSource dataSource)`
        self.dataSource = dataSource
        #: 已执行的 SQL 记录：[(方法名, sql, args)]
        self.executed: List[tuple] = []
        #: 预设查询结果：{sql: [ {...}, ... ]}
        self._query_results: Dict[str, List[Dict[str, Any]]] = {}
        #: 预设更新行数
        self._update_count: int = 0
        #: 非空时，任何调用都抛该异常（用于验证 catch 分支）
        self.failOn: Optional[Exception] = None

    # ------------------------------------------------------------------ 查询
    def queryForList(self, sql: str, *args: Any) -> List[Dict[str, Any]]:
        """对应 `queryForList(String sql, Object... args)`。"""
        self._record("queryForList", sql, args)
        # 【Java→Python】返回**副本**，避免调用方改动替身内部数据
        return [dict(row) for row in self._query_results.get(sql, [])]

    def queryForObject(self, sql: str, *args: Any) -> Any:
        """对应 `queryForObject(String sql, Class<T> requiredType, Object... args)`。"""
        self._record("queryForObject", sql, args)
        rows = self._query_results.get(sql, [])
        return rows[0] if rows else None

    # ------------------------------------------------------------------ 更新
    def update(self, sql: str, *args: Any) -> int:
        """对应 `update(String sql, Object... args)`：返回受影响行数。"""
        self._record("update", sql, args)
        return self._update_count

    def execute(self, sql: str, *args: Any) -> None:
        """对应 `execute(String sql)`：用于 DDL / REFRESH 等无返回语句。"""
        self._record("execute", sql, args)
        return None

    # ------------------------------------------------------------------ 内部
    def _record(self, method: str, sql: str, args: Any) -> None:
        self.executed.append((method, sql, args))
        if self.failOn is not None:
            # 模拟 DataAccessException：业务代码的 catch 分支由此触发
            raise self.failOn

    # ------------------------------------------------------------------ 测试辅助
    def setQueryResult(self, sql: str, rows: List[Dict[str, Any]]) -> "JdbcTemplate":
        """Java 无此方法；替身用于编排 `queryForList` 的返回值。"""
        self._query_results[sql] = [dict(row) for row in rows]
        return self

    def setUpdateCount(self, count: int) -> "JdbcTemplate":
        """Java 无此方法；替身用于编排 `update` 的返回值。"""
        self._update_count = int(count)
        return self

    def getExecutedSql(self) -> List[str]:
        """Java 无此方法；替身用于断言执行过哪些 SQL。"""
        return [item[1] for item in self.executed]

    def __repr__(self) -> str:
        return "JdbcTemplate(executed=%d)" % len(self.executed)
