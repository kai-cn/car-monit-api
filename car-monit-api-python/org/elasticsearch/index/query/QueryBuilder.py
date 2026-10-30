# -*- coding: utf-8 -*-
"""org.elasticsearch.index.query.QueryBuilder

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.index.query.QueryBuilder``。
本工程只把它当作 ``BoolQueryBuilder.must/filter`` 的参数类型使用。

【Java→Python】关键差异
1) Java 的 ``QueryBuilder`` 是**抽象类**（实现 ``ToXContentObject``、``Writeable``），
   子类负责序列化成查询 DSL；替身不需要序列化，改为提供**进程内匹配方法**
   ``matches(document)``，由 ``RestHighLevelClient.search`` 直接调用。
   这是替身与原框架最大的语义差异：真实 ES 在服务端计算命中，替身在客户端计算。
2) Java 的 ``QueryBuilder`` 有 ``queryName(String)`` / ``boost(float)`` 等通用方法；
   本工程未使用，不实现。
3) 模块级工具函数 ``_field_value`` 对应 Java 里 Lucene 的“按字段名取值”逻辑：
   支持 ``a.b`` 形式的点号路径；字段缺失返回 ``_MISSING`` 哨兵
   （**必须区分“字段不存在”和“字段值为 null”**，因为 ES 对 unmapped 字段
   的 term/range/match 查询一律不命中）。
"""

from __future__ import annotations

from typing import Any

__all__ = ["QueryBuilder", "_MISSING", "_field_value"]

#: 字段缺失哨兵（与“值为 None”区分）
_MISSING = object()


class QueryBuilder(object):
    """查询条件基类；子类必须实现 ``matches(document)``。"""

    def matches(self, document: Any) -> bool:  # pragma: no cover - 抽象方法
        """返回该条件是否命中文档（``document`` 为 ``_source`` 解析出的 dict）。"""
        raise NotImplementedError(
            "QueryBuilder.matches 必须由子类实现: " + type(self).__name__)

    def getName(self) -> str:
        """测试辅助：返回具体查询类型名（Java 无此方法）。"""
        return type(self).__name__

    def __repr__(self) -> str:
        return "%s()" % type(self).__name__


def _field_value(document: Any, field: str) -> Any:
    """按 ES 字段名取值；支持点号路径，缺失返回 ``_MISSING``。

    【Java→Python】**多字段（multi-field）兜底**：真实 ES 的 mapping 里
    ``platenumber`` 常带 ``.keyword`` / ``.ngram`` 子字段，查询 ``platenumber.keyword``
    能命中；但 ``_source`` 里只存父字段 ``platenumber``，子字段是索引期衍生的。
    本替身只读 ``_source``，因此当完整路径缺失时，若末段是 ``keyword`` / ``ngram``，
    回退到父路径取值 —— 否则原代码里所有 ``field.keyword`` 查询都会命中不到。
    """
    if not isinstance(document, dict):
        return _MISSING
    current: Any = document
    for part in str(field).split("."):
        if not isinstance(current, dict) or part not in current:
            # 【Java→Python】子字段（.keyword/.ngram）回退到父字段
            suffix = str(field).rsplit(".", 1)
            if len(suffix) == 2 and suffix[1] in ("keyword", "ngram"):
                return _field_value(document, suffix[0])
            return _MISSING
        current = current[part]
    return current
