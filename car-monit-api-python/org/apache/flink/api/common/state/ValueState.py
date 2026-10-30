# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.ValueState

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.ValueState<T>``。
本工程用法（VehicleTrackFlinkJob）：
    TrailState current = trailState.value();      // 未初始化返回 null
    if (current == null) current = new TrailState();
    ...
    trailState.update(current);

【Java→Python】关键差异
1) Java 的 ``ValueState`` 是**接口**，实现由 Flink 运行时按 key 提供；
   Python 侧用具体类表达，内部以 ``(状态名, 当前 key)`` 为索引访问
   ``RuntimeContext`` 的字典 —— 这样同一个 ValueState 句柄在不同 key 下
   自然隔离，与键控状态语义一致。
2) ``value()`` 在未赋值时返回 ``null`` → Python 返回 ``None``；
   ``update(null)`` 在 Java 里等价 ``clear()``，替身同样处理。
3) Java 的 ``ValueState`` 还继承 ``State``（``clear()``）；替身直接提供。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["ValueState"]


class ValueState(object):
    """``ValueState<T>`` 的替身（按当前 key 存取）。"""

    def __init__(self, store: Dict[tuple, Any], name: str, context: Any) -> None:
        #: 共享存储：{(状态名, key): value}
        self._store = store
        self._name = name
        #: RuntimeContext（提供 currentKey）
        self._context = context

    def _index(self) -> tuple:
        return (self._name, self._context.currentKey())

    # ------------------------------------------------------------------ 读写
    def value(self) -> Optional[Any]:
        """对应 ``value()``：未初始化返回 None（Java: null）。"""
        return self._store.get(self._index())

    def update(self, value: Any) -> None:
        """对应 ``update(T value)``；传 None 等价 clear()。"""
        if value is None:
            self.clear()
            return
        self._store[self._index()] = value

    def clear(self) -> None:
        self._store.pop(self._index(), None)

    def __repr__(self) -> str:
        return "ValueState(name=%r, key=%r)" % (self._name,
                                                self._context.currentKey())
