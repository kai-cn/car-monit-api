# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.BroadcastState

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.BroadcastState<K, V>``。
本工程用法（VehicleTrackFlinkJob.processBroadcastElement）：
    ctx.getBroadcastState(dictStateDesc).put(entry.getKey(), (Map<String, Object>) entry.getValue());

【Java→Python】关键差异
1) 广播状态**不是键控状态**：整条算子链共享一份 Map，所有 key 看到同一份字典。
   替身因此用**单个 dict**（按描述符 name 挂在运行时上下文中），
   不使用 ``currentKey`` 分桶。
2) Java 的 ``BroadcastState`` 只在 ``processBroadcastElement`` 的 Context 里
   可写（``ReadOnlyBroadcastState`` 只在 processElement 里只读）。
   替身用两个类表达该约束：``BroadcastState``（可写）与
   ``ReadOnlyBroadcastState``（只读视图，写操作直接抛 AttributeError）。
3) 泛型在 Python 运行时擦除，put 时**不校验** value 类型；
   Java 里 ``(Map<String, Object>) entry.getValue()`` 的强制转换失败会抛
   ClassCastException，Python 侧对应“拿到什么就是什么”（见业务代码注释）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

__all__ = ["BroadcastState", "ReadOnlyBroadcastState"]


class ReadOnlyBroadcastState(object):
    """``ReadOnlyBroadcastState<K, V>`` 的替身（只读视图）。"""

    def __init__(self, store: Dict[str, Dict[Any, Any]], name: str) -> None:
        self._store = store
        self._name = name

    def _current(self) -> Dict[Any, Any]:
        return self._store.setdefault(self._name, {})

    # ------------------------------------------------------------------ 只读
    def get(self, key: Any) -> Any:
        return self._current().get(key)

    def contains(self, key: Any) -> bool:
        return key in self._current()

    def entries(self) -> List[Tuple[Any, Any]]:
        return list(self._current().items())

    def isEmpty(self) -> bool:
        return len(self._current()) == 0

    def __len__(self) -> int:
        return len(self._current())

    def __repr__(self) -> str:
        return "ReadOnlyBroadcastState(name=%r, size=%d)" % (self._name, len(self))


class BroadcastState(ReadOnlyBroadcastState):
    """``BroadcastState<K, V>`` 的替身（在只读视图上增加写能力）。"""

    def put(self, key: Any, value: Any) -> None:
        self._current()[key] = value

    def putAll(self, entries: Dict[Any, Any]) -> None:
        self._current().update(entries)

    def remove(self, key: Any) -> Any:
        return self._current().pop(key, None)

    def clear(self) -> None:
        self._store.pop(self._name, None)

    def __repr__(self) -> str:
        return "BroadcastState(name=%r, size=%d)" % (self._name, len(self))
