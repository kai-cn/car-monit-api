# -*- coding: utf-8 -*-
"""java.util.function.Function

【无 Java 源文件：JDK 类替身】
Java 侧来自 JDK：`java.util.function.Function<T, R>`（函数式接口）：
    R apply(T t);

本工程用法（LargeScaleDataSyncService 的 SyncTask.idExtractor）：
    Function<Object, String> idExtractor;
    String id = task.idExtractor.apply(record);

【Java→Python 关键差异】
1) Python 的函数本身就是一等对象，绝大多数场景直接传 `lambda`/函数即可，
   不需要包一层；但**调用点**是 `idExtractor.apply(x)`，若不建替身就得把调用点
   改成 `idExtractor(x)`，会偏离 Java 源码。为保持调用点逐字一致，这里提供
   包装类（`apply` 方法与 `__call__` 同时可用）。
2) Java 的 `andThen/compose/identity` 本工程未使用，仅补 `identity()` 以便对照。
3) 泛型 T/R 在 Python 中无运行时约束，省略。
"""
from __future__ import annotations

from typing import Any, Callable

__all__ = ["Function"]


class Function(object):
    """`Function<T,R>` 的替身：包装任意 callable。"""

    def __init__(self, fn: Callable[[Any], Any]) -> None:
        self._fn = fn

    def apply(self, value: Any) -> Any:
        """对应 `R apply(T t)`。"""
        return self._fn(value)

    def __call__(self, value: Any) -> Any:
        """【Java→Python】lambda 直接调用也成立（等价 apply）。"""
        return self._fn(value)

    @staticmethod
    def identity() -> "Function":
        """对应 `static <T> Function<T,T> identity()`。"""
        return Function(lambda value: value)

    def __repr__(self) -> str:
        return "Function(%r)" % (self._fn,)
