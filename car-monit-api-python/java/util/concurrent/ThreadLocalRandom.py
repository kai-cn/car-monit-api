# -*- coding: utf-8 -*-
"""java.util.concurrent.ThreadLocalRandom

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：``java.util.concurrent.ThreadLocalRandom``。
本工程用法（DeviceDataSimulator）：
    private final ThreadLocalRandom random = ThreadLocalRandom.current();
    random.nextInt(DEVICES.size());          // [0, bound)
    random.nextInt(1, 10);                   // [origin, bound)
    random.nextDouble(1.0, 49.0);            // [origin, bound)
    random.nextBoolean();

【Java→Python】关键差异
1) Java 的 ``ThreadLocalRandom`` 每个线程一个实例、**无种子可设**（内部用
   Thread 的 probe 做种子）；Python 的 ``random`` 模块是全局共享的实例，
   这里每个 ``current()`` 调用返回一个绑定 ``random.Random`` 的对象，
   并用 ``SystemRandom`` 取种子，避免多线程下同一秒内产生相同序列。
2) **Java 是重载（overload），Python 没有重载**：``nextInt(int bound)`` 与
   ``nextInt(int origin, int bound)`` 合并为 ``nextInt(a, b=None)``，
   只传一个参数时按 ``[0, a)`` 处理，与 Java 的两个重载一一对应。
3) 边界语义与 Java 一致：**左闭右开**（``nextInt(1, 10)`` 取 1~9）。
   Java 在 ``origin >= bound`` 时抛 IllegalArgumentException，
   这里抛 ValueError（对应 RuntimeException）。
"""
from __future__ import annotations

import random as _random

__all__ = ["ThreadLocalRandom"]


class ThreadLocalRandom(object):
    """``ThreadLocalRandom`` 的替身（每个实例持有独立的 Random 状态）。"""

    def __init__(self) -> None:
        # 【Java→Python】Java 用线程内 probe 做种子；这里用系统熵源播种
        self._random = _random.Random(_random.SystemRandom().getrandbits(64))

    @staticmethod
    def current() -> "ThreadLocalRandom":
        """对应 ``ThreadLocalRandom.current()``。

        【Java→Python】Java 返回**当前线程**的单例；Python 没有 ThreadLocal 语义，
        这里每次返回新实例（随机数生成器本身无状态依赖，行为等价）。
        """
        return ThreadLocalRandom()

    # ------------------------------------------------------------------ 整数
    def nextInt(self, a: int, b: int = None) -> int:
        """``nextInt(bound)`` / ``nextInt(origin, bound)`` 两个重载的合并写法。"""
        if b is None:
            bound = int(a)
            if bound <= 0:
                raise ValueError("bound must be positive")
            return self._random.randrange(0, bound)
        origin, bound = int(a), int(b)
        if origin >= bound:
            # Java: IllegalArgumentException("bound must be greater than origin")
            raise ValueError("bound must be greater than origin")
        return self._random.randrange(origin, bound)

    def nextLong(self, a: int = None, b: int = None) -> int:
        """``nextLong()`` / ``nextLong(bound)`` / ``nextLong(origin, bound)``。"""
        if a is None:
            return self._random.getrandbits(64) - (1 << 63)
        if b is None:
            bound = int(a)
            if bound <= 0:
                raise ValueError("bound must be positive")
            return self._random.randrange(0, bound)
        origin, bound = int(a), int(b)
        if origin >= bound:
            raise ValueError("bound must be greater than origin")
        return self._random.randrange(origin, bound)

    # ------------------------------------------------------------------ 浮点
    def nextDouble(self, a: float = None, b: float = None) -> float:
        """``nextDouble()`` / ``nextDouble(bound)`` / ``nextDouble(origin, bound)``。"""
        if a is None:
            return self._random.random()
        if b is None:
            bound = float(a)
            if bound <= 0:
                raise ValueError("bound must be positive")
            return self._random.random() * bound
        origin, bound = float(a), float(b)
        if origin >= bound:
            raise ValueError("bound must be greater than origin")
        return origin + self._random.random() * (bound - origin)

    # ------------------------------------------------------------------ 布尔
    def nextBoolean(self) -> bool:
        return self._random.getrandbits(1) == 1

    def __repr__(self) -> str:
        return "ThreadLocalRandom()"
