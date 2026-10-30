# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.MapState

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.MapState<UK, UV>``。
本工程**未直接使用** ``MapState``（广播字典用的是 ``BroadcastState``）；
本文件仅为键控 Map 状态提供最小替身，供后续迁移使用。

【Java→Python】关键差异
1) Java 的 MapState 是键控状态（每个 key 一份 Map）；Python 用
   ``RuntimeContext`` 的 ``{(状态名, key): dict}`` 表达。
2) ``entries()`` 在 Java 返回 ``Iterable<Map.Entry<K,V>>``；Python 返回
   ``dict.items()`` 的列表（语义相同，``for k, v in ...`` 即可）。
3) ``iterator()`` / ``keys()`` / ``values()`` / ``isEmpty()`` / ``contains``
   一并实现，保持 Flink 接口的可用性。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

__all__ = ["MapState"]


class MapState(object):
    """``MapState<UK, UV>`` 的替身。"""

    def __init__(self, store: dict, name: str, context: Any) -> None:
        self._store = store
        self._name = name
        self._context = context

    def _current(self) -> Dict[Any, Any]:
        return self._store.setdefault((self._name, self._context.currentKey()), {})

    # ------------------------------------------------------------------ 读写
    def put(self, key: Any, value: Any) -> None:
        self._current()[key] = value

    def putAll(self, entries: Dict[Any, Any]) -> None:
        self._current().update(entries)

    def get(self, key: Any) -> Any:
        return self._current().get(key)

    def contains(self, key: Any) -> bool:
        return key in self._current()

    def remove(self, key: Any) -> Any:
        return self._current().pop(key, None)

    def entries(self) -> List[Tuple[Any, Any]]:
        """对应 ``entries()``：Java 返回 Iterable<Map.Entry>，这里返回 (k, v) 列表。"""
        return list(self._current().items())

    def keys(self) -> List[Any]:
        return list(self._current().keys())

    def values(self) -> List[Any]:
        return list(self._current().values())

    def isEmpty(self) -> bool:
        return len(self._current()) == 0

    def clear(self) -> None:
        self._store.pop((self._name, self._context.currentKey()), None)

    def __len__(self) -> int:
        return len(self._current())

    def __repr__(self) -> str:
        return "MapState(name=%r, key=%r, size=%d)" % (
            self._name, self._context.currentKey(), len(self))
