# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.functions.RichMapFunction

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.functions.RichMapFunction<IN, OUT>``。
本工程用法（VehicleTrackFlinkJob，两个内部类继承它）：
    private static class CDCEventParser extends RichMapFunction<String, StandardEvent> {
        @Override public StandardEvent map(String json) throws Exception { ... }
    }
    private static class RawEventParser extends RichMapFunction<String, StandardEvent> { ... }

【Java→Python】关键差异
1) Java 的 ``RichMapFunction`` 是**抽象类**（继承 ``AbstractRichFunction``），
   子类**必须**实现 ``map(IN)``；``open(Configuration)`` / ``close()`` 有默认空实现。
   Python 用普通类 + ``NotImplementedError`` 表达抽象方法（本工程没有用
   ``abc.ABC``，因为子类只覆盖 map，用不到抽象基类的元类机制）。
2) ``throws Exception`` 是受检异常声明，Python 无此概念，异常直接向上抛。
3) ``getRuntimeContext()`` 在 Java 里由运行时注入后才能调用；替身返回
   本地 RuntimeContext（惰性创建），因此子类里即使调用也不会 NPE。
"""
from __future__ import annotations

from typing import Any, Optional

from org.apache.flink.api.common.functions.RuntimeContext import RuntimeContext
from org.apache.flink.configuration.Configuration import Configuration

__all__ = ["RichMapFunction"]


class RichMapFunction(object):
    """``RichMapFunction<IN, OUT>`` 的替身。"""

    def __init__(self) -> None:
        self._runtime_context: Optional[RuntimeContext] = None

    # ------------------------------------------------------------------ 生命周期
    def open(self, parameters: Configuration) -> None:
        """对应 ``open(Configuration)``：默认空实现。"""
        return None

    def close(self) -> None:
        """对应 ``close()``：默认空实现。"""
        return None

    # ------------------------------------------------------------------ 核心
    def map(self, value: Any) -> Any:
        """对应 ``map(IN value)``：子类必须实现。"""
        raise NotImplementedError("RichMapFunction.map 必须由子类实现")

    # ------------------------------------------------------------------ 上下文
    def getRuntimeContext(self) -> RuntimeContext:
        """对应 ``getRuntimeContext()``（Java 由运行时注入）。"""
        if self._runtime_context is None:
            self._runtime_context = RuntimeContext()
        return self._runtime_context

    def __call__(self, value: Any) -> Any:
        # Python 便捷写法：让函数对象可直接调用（Java 里必须走运行时调用 map）
        return self.map(value)

    def __repr__(self) -> str:
        return "%s()" % type(self).__name__
