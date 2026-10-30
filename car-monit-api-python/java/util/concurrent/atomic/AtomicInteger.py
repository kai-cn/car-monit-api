# -*- coding: utf-8 -*-
"""java.util.concurrent.atomic.AtomicInteger / AtomicLong

【无 Java 源文件：框架类替身】
业务代码典型用法：线程池命名计数器
    private final AtomicInteger counter = new AtomicInteger(0);
    thread.setName("...-" + counter.incrementAndGet());

【Java→Python 关键差异】
1) Java 的原子类是**无锁 CAS**（靠 Unsafe/VarHandle），Python 没有等价原语；
   这里用 `threading.Lock` 保护“读-改-写”，语义等价（线程安全），性能不是重点。
2) Java 的 `get()`/`set()` → Python 同名方法（不能写成属性，否则调用处要改）。
3) Java 的 `toString()` 返回数字字符串，本替身用 `__str__` 还原。
"""
from __future__ import annotations

import threading
from typing import Optional

__all__ = ["AtomicInteger", "AtomicLong"]


class AtomicInteger(object):
    """`java.util.concurrent.atomic.AtomicInteger` 的替身。"""

    def __init__(self, initial_value: int = 0) -> None:
        self._value = int(initial_value)
        self._lock = threading.Lock()

    def get(self) -> int:
        return self._value

    def set(self, new_value: int) -> None:
        with self._lock:
            self._value = int(new_value)

    def lazySet(self, new_value: int) -> None:
        """Java 的 lazySet 不保证立即可见；Python 用普通赋值近似。"""
        self._value = int(new_value)

    def getAndSet(self, new_value: int) -> int:
        with self._lock:
            previous = self._value
            self._value = int(new_value)
            return previous

    def compareAndSet(self, expect: int, update: int) -> bool:
        with self._lock:
            if self._value == expect:
                self._value = int(update)
                return True
            return False

    def incrementAndGet(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    def getAndIncrement(self) -> int:
        with self._lock:
            previous = self._value
            self._value += 1
            return previous

    def decrementAndGet(self) -> int:
        with self._lock:
            self._value -= 1
            return self._value

    def getAndDecrement(self) -> int:
        with self._lock:
            previous = self._value
            self._value -= 1
            return previous

    def addAndGet(self, delta: int) -> int:
        with self._lock:
            self._value += int(delta)
            return self._value

    def getAndAdd(self, delta: int) -> int:
        with self._lock:
            previous = self._value
            self._value += int(delta)
            return previous

    def __str__(self) -> str:
        return str(self._value)


class AtomicLong(AtomicInteger):
    """`java.util.concurrent.atomic.AtomicLong` 的替身（行为与 AtomicInteger 相同）。"""
