# -*- coding: utf-8 -*-
"""java.util.concurrent.ConcurrentHashMap

【无 Java 源文件：框架类替身】
业务代码典型用法（DataReliabilityService / DelayMonitoringService）：
    private final ConcurrentHashMap<String, MessageMeta> pendingMessages = new ConcurrentHashMap<>();
    pendingMessages.put(id, meta); pendingMessages.get(id); pendingMessages.remove(id);
    pendingMessages.containsKey(id); pendingMessages.size(); pendingMessages.values();

【Java→Python 关键差异】
1) Python 的 dict 在 CPython 下因 GIL 天然是“单个操作原子”的，不需要分段锁；
   但 Java 的 `putIfAbsent`/`computeIfAbsent` 是**原子复合操作**，Python 的
   `setdefault` 在含函数调用时可能重复计算，因此这里用 Lock 包一层还原原子性。
2) Java 的 `size()`/`isEmpty()` 是方法，Python dict 是 `len()`/真值判断；
   为了调用处不改写，替身保留 `size()` 方法（注意与 dict 内置 `__len__` 并存）。
3) Java 的 `get()` 不存在返回 null → Python 返回 None。
4) `keySet()/values()/entrySet()` 返回的是**视图**（Java 的弱一致视图）；
   这里返回浅拷贝的 list/set，避免调用方迭代时被并发修改。
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, Set

# 区分 `remove(K)` 与 `remove(K,V)` 两个重载的哨兵值
_MISSING = object()


class ConcurrentHashMap(dict):
    """`java.util.concurrent.ConcurrentHashMap<K,V>` 的替身（继承 dict 保留迭代能力）。"""

    def __init__(self, initial: Optional[Dict[Any, Any]] = None) -> None:
        super().__init__(initial or {})
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ 读写
    def put(self, key: Any, value: Any) -> Any:
        """返回旧值（不存在返回 None），与 Java 一致。"""
        with self._lock:
            previous = self.get(key)
            self[key] = value
            return previous

    def putIfAbsent(self, key: Any, value: Any) -> Any:
        with self._lock:
            if key in self:
                return self[key]
            self[key] = value
            return None

    def computeIfAbsent(self, key: Any, mapping_function: Callable[[Any], Any]) -> Any:
        """原子“缺则计算并放入”（Java 8 的 computeIfAbsent）。"""
        with self._lock:
            if key in self:
                return self[key]
            value = mapping_function(key)
            if value is not None:
                self[key] = value
            return value

    def computeIfPresent(self, key: Any, remapping_function: Callable[[Any, Any], Any]) -> Any:
        with self._lock:
            if key not in self:
                return None
            value = remapping_function(key, self[key])
            if value is None:
                self.pop(key, None)
            else:
                self[key] = value
            return value

    def putAll(self, other: Dict[Any, Any]) -> None:
        with self._lock:
            self.update(other)

    def remove(self, key: Any, value: Any = _MISSING) -> Any:
        """`remove(K)` 与 `remove(K,V)` 两个重载：Python 用哨兵值区分。"""
        with self._lock:
            if key not in self:
                return None
            previous = self[key]
            if value is not _MISSING and previous != value:
                return None
            del self[key]
            return previous

    def getOrDefault(self, key: Any, default_value: Any) -> Any:
        return self.get(key, default_value)

    def containsKey(self, key: Any) -> bool:
        return key in self

    def containsValue(self, value: Any) -> bool:
        return value in self.values()

    # ------------------------------------------------------------------ 视图
    def size(self) -> int:
        return len(self)

    def isEmpty(self) -> bool:
        return len(self) == 0

    def keySet(self) -> Set[Any]:
        return set(self.keys())

    def values(self) -> List[Any]:  # type: ignore[override]
        """Java 的 values() 是集合视图；这里返回 list 快照（迭代安全）。"""
        return list(super().values())

    def entrySet(self) -> List[Any]:
        """返回 (key, value) 列表快照，调用方可按 Java 的 entry.getKey()/getValue() 使用。"""
        return list(self.items())

    def forEach(self, action: Callable[[Any, Any], None]) -> None:
        for key, value in list(self.items()):
            action(key, value)

    def clear(self) -> None:
        with self._lock:
            super().clear()
