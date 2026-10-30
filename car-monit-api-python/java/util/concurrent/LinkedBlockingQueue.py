# -*- coding: utf-8 -*-
"""java.util.concurrent.LinkedBlockingQueue

【无 Java 源文件：JDK 类替身】（``java.util.concurrent.LinkedBlockingQueue``）
业务代码用法（CompositeQueryOptimizationService）：
    new ThreadPoolExecutor(
            POOL_SIZE, POOL_SIZE, 60L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(1000),          // 有界队列，容量 1000
            new ThreadPoolExecutor.CallerRunsPolicy()
    );

【Java→Python 关键差异】
1) Java 的 ``LinkedBlockingQueue`` 是**线程安全的有界/无界阻塞队列**（FIFO，
   内部两把锁分别保护 take/put）。Python 用 ``collections.deque`` + ``threading.Lock``
   实现同样的线程安全与 FIFO 语义。
2) **容量语义**：
   - ``new LinkedBlockingQueue<>(1000)`` → 有界，满时 ``put`` 阻塞、``offer`` 返回 false
   - 无参 ``new LinkedBlockingQueue<>()`` → 容量 ``Integer.MAX_VALUE``（近似无界）
   替身用 ``capacity=None`` 表示无界（对应 Java 的 Integer.MAX_VALUE）。
3) **阻塞等待**：``put`` 在队满时阻塞当前线程，``take`` 在队空时阻塞。
   替身用 ``threading.Condition`` 实现，语义与 Java 一致。
4) Java 的 ``BlockingQueue`` 接口方法很多（``add``/``offer``/``put``/``take``/
   ``poll``/``peek``/``drainTo``/...），本工程只作为线程池构造参数使用，
   替身实现常用子集，并在 ``ThreadPoolExecutor`` 替身里以“容量”参与拒绝策略判断。
"""

from __future__ import annotations

import collections
import threading
from typing import Any, List, Optional

__all__ = ["LinkedBlockingQueue"]


class LinkedBlockingQueue(object):
    """``LinkedBlockingQueue<E>`` 的替身（FIFO + 线程安全 + 可选容量）。"""

    def __init__(self, capacity: Optional[int] = None) -> None:
        # 【Java→Python】无参构造 = Integer.MAX_VALUE 容量；这里用 None 表示“无界”
        self._capacity = None if capacity is None else int(capacity)
        self._items: "collections.deque[Any]" = collections.deque()
        self._condition = threading.Condition(threading.Lock())

    # ------------------------------------------------------------------ 入队
    def add(self, item: Any) -> bool:
        """队满时抛 RuntimeError（Java 抛 IllegalStateException）。"""
        if not self.offer(item):
            raise RuntimeError("Queue full")
        return True

    def offer(self, item: Any) -> bool:
        """非阻塞入队：成功 True，队满 False。"""
        with self._condition:
            if self._is_full():
                return False
            self._items.append(item)
            self._condition.notify_all()
            return True

    def put(self, item: Any) -> None:
        """阻塞入队：队满时等待。"""
        with self._condition:
            while self._is_full():
                self._condition.wait()
            self._items.append(item)
            self._condition.notify_all()

    # ------------------------------------------------------------------ 出队
    def poll(self) -> Optional[Any]:
        """非阻塞出队：队空返回 None。"""
        with self._condition:
            if not self._items:
                return None
            return self._items.popleft()

    def take(self) -> Any:
        """阻塞出队：队空时等待。"""
        with self._condition:
            while not self._items:
                self._condition.wait()
            return self._items.popleft()

    def peek(self) -> Optional[Any]:
        with self._condition:
            return self._items[0] if self._items else None

    def drainTo(self, target: List[Any]) -> int:
        """把全部元素转移到 target（对应 ``drainTo(Collection)``），返回转移数量。"""
        with self._condition:
            count = len(self._items)
            target.extend(self._items)
            self._items.clear()
            self._condition.notify_all()
            return count

    # ------------------------------------------------------------------ 查询
    def size(self) -> int:
        with self._condition:
            return len(self._items)

    def isEmpty(self) -> bool:
        with self._condition:
            return not self._items

    def remainingCapacity(self) -> int:
        """对应 ``remainingCapacity()``；无界队列返回 Java 的 Integer.MAX_VALUE。"""
        with self._condition:
            if self._capacity is None:
                return 2147483647
            return max(0, self._capacity - len(self._items))

    def clear(self) -> None:
        with self._condition:
            self._items.clear()
            self._condition.notify_all()

    # ------------------------------------------------------------------ 内部
    def _is_full(self) -> bool:
        return self._capacity is not None and len(self._items) >= self._capacity

    def __len__(self) -> int:
        return self.size()

    def __repr__(self) -> str:
        return "LinkedBlockingQueue(capacity=%r, size=%d)" % (self._capacity, self.size())
