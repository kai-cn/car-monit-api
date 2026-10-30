# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.ListState

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.ListState<T>``。
本工程用法（VehicleTrackFlinkJob）：
    pendingQueue.add(pending);
    Iterator<PendingEvent> it = pendingQueue.get().iterator();
    while (it.hasNext()) { PendingEvent p = it.next(); it.remove(); ... }
    for (PendingEvent p : retryList) pendingQueue.add(p);

【Java→Python】关键差异（**迭代器 remove 的坑**）
1) Java 的 ``get()`` 返回 ``Iterable<T>``，其 ``iterator()`` **支持 remove()**，
   原代码靠 ``it.remove()`` 边遍历边删除。
   Python 的 list 迭代器**不支持删除**（会抛 RuntimeError: dictionary/list
   changed size during iteration），因此转写时必须显式改成
   “先快照、再 clear、再逐个处理”：
       pending_list = list(self.pendingQueue.get())
       self.pendingQueue.clear()
       for pending in pending_list: ...
   语义与 Java 完全等价（Java 也是逐个从状态里移除后再判断）。
2) ``get()`` 返回**实时列表**（不是副本），与 Flink 的 ListState 视图语义一致；
   调用方若需要快照必须自己 ``list(...)``。
3) ``update(List)`` / ``addAll(List)`` 一并实现（Flink 接口里有）。
"""
from __future__ import annotations

from typing import Any, Iterable, List

__all__ = ["ListState"]


class ListState(object):
    """``ListState<T>`` 的替身（按当前 key 存取）。"""

    def __init__(self, store: dict, name: str, context: Any) -> None:
        #: 共享存储：{(状态名, key): list}
        self._store = store
        self._name = name
        self._context = context

    def _current(self) -> List[Any]:
        return self._store.setdefault((self._name, self._context.currentKey()), [])

    # ------------------------------------------------------------------ 读写
    def get(self) -> List[Any]:
        """对应 ``get()``：返回**实时**列表（Java: Iterable）。"""
        return self._current()

    def add(self, value: Any) -> None:
        self._current().append(value)

    def addAll(self, values: Iterable[Any]) -> None:
        self._current().extend(values)

    def update(self, values: Iterable[Any]) -> None:
        """对应 ``update(List<T>)``：整体替换。"""
        self._store[(self._name, self._context.currentKey())] = list(values)

    def clear(self) -> None:
        self._store.pop((self._name, self._context.currentKey()), None)

    def __len__(self) -> int:
        return len(self.get())

    def __repr__(self) -> str:
        return "ListState(name=%r, key=%r, size=%d)" % (
            self._name, self._context.currentKey(), len(self.get()))
