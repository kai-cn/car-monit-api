# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction<KS, IN1, IN2, OUT>``。
本工程用法（VehicleTrackFlinkJob.TrailAggregatorProcessFunction）：
    private static class TrailAggregatorProcessFunction extends
            KeyedBroadcastProcessFunction<String, StandardEvent, Map<String, Object>, TrailResult> {
        public void open(Configuration parameters) { ... }
        public void processElement(StandardEvent e, ReadOnlyContext ctx, Collector<TrailResult> out) { ... }
        public void processBroadcastElement(Map<String,Object> d, Context ctx, Collector<TrailResult> out) { ... }
        public void onTimer(long ts, OnTimerContext ctx, Collector<TrailResult> out) { ... }
    }

【Java→Python】关键差异（**本替身最需要小心的部分**）
1) **Java 的四个嵌套 Context 类型**：
     - ``Context``（广播侧，可写广播状态；仅 processBroadcastElement 用）
     - ``ReadOnlyContext``（数据侧，只读广播状态；仅 processElement 用）
     - ``OnTimerContext``（定时器侧，可读写广播状态 + 可注册新定时器）
     - ``TimerService``（由 ``ctx.timerService()`` 返回）
   Python 无法表达“按方法区分的接口”，替身用 4 个独立类，
   但**由本地执行器决定传哪一个**（见 BroadcastConnectedStream），
   调用方写法与 Java 完全一致。
2) **定时器没有真实时钟**：Java 的 ``registerProcessingTimeTimer(ts)`` 把
   (timestamp, key) 注册到运行时，由 Flink 在系统时间到达 ts 时回调 onTimer。
   Python 替身只把 (ts, key) 记到 ``_timers`` 列表，由本地执行器在
   **所有数据元素处理完之后**统一触发（不等待真实时间流逝）。
   业务代码里 ``System.currentTimeMillis() + 60_000`` 的写法因此完全保留，
   但断言时不要依赖“真的等了 60 秒”。
3) **广播状态是算子级共享**（非键控）：替身用 ``_broadcast_store``
   单份 dict 表达；``ReadOnlyContext`` 返回只读视图，写操作会 AttributeError，
   与 Java 的类型约束等价。
4) **键控状态按 key 分桶**：由 ``getRuntimeContext().setCurrentKey(...)``
   在执行器里切换，业务代码看到的 ``trailState.value()`` 已经是
   当前车牌对应的那份状态（见 RuntimeContext 的差异说明）。
5) Java 的 ``getRuntimeContext()`` 继承自 ``AbstractRichFunction``；
   ``open(Configuration)`` / ``close()`` 有默认空实现，替身保持一致。
"""
from __future__ import annotations

import time
from typing import Any, List, Optional, Tuple

from org.apache.flink.api.common.functions.RuntimeContext import RuntimeContext
from org.apache.flink.api.common.state.BroadcastState import (
    BroadcastState,
    ReadOnlyBroadcastState,
)
from org.apache.flink.configuration.Configuration import Configuration

__all__ = [
    "KeyedBroadcastProcessFunction",
    "TimerService",
    "ReadOnlyContext",
    "Context",
    "OnTimerContext",
]


class TimerService(object):
    """``KeyedBroadcastProcessFunction.TimerService`` 的替身。"""

    def __init__(self, function: "KeyedBroadcastProcessFunction") -> None:
        self._function = function

    def currentProcessingTime(self) -> int:
        """对应 ``currentProcessingTime()``：返回当前系统毫秒时间戳。"""
        return int(time.time() * 1000)

    def currentWatermark(self) -> int:
        """对应 ``currentWatermark()``：本工程未使用，返回 Long.MIN_VALUE 语义。"""
        return -(2 ** 63)

    def registerProcessingTimeTimer(self, timestamp: int) -> None:
        """对应 ``registerProcessingTimeTimer(long)``：按当前 key 登记定时器。"""
        # 【Java→Python】真实 Flink 按 key 去重并交由定时器线程触发；
        # 替身只入队，由 BroadcastConnectedStream 在数据流耗尽后统一触发。
        key = self._function.getRuntimeContext().currentKey()
        self._function._timers.append((int(timestamp), key))

    def deleteProcessingTimeTimer(self, timestamp: int) -> None:
        """对应 ``deleteProcessingTimeTimer(long)``。"""
        key = self._function.getRuntimeContext().currentKey()
        target = (int(timestamp), key)
        self._function._timers = [t for t in self._function._timers if t != target]

    def __repr__(self) -> str:
        return "TimerService(pending=%d)" % len(self._function._timers)


class _KeyedContext(object):
    """四个 Context 的公共基类（持有当前 key 与 timerService）。"""

    def __init__(self, function: "KeyedBroadcastProcessFunction") -> None:
        self._function = function

    def getCurrentKey(self) -> Any:
        """对应 ``getCurrentKey()``。"""
        return self._function.getRuntimeContext().currentKey()

    def timerService(self) -> TimerService:
        """对应 ``timerService()``。"""
        return TimerService(self._function)

    def __repr__(self) -> str:
        return "%s(currentKey=%r)" % (type(self).__name__, self.getCurrentKey())


class ReadOnlyContext(_KeyedContext):
    """``ReadOnlyContext``：processElement 的上下文（广播状态只读）。"""

    def getBroadcastState(self, descriptor: Any) -> ReadOnlyBroadcastState:
        return ReadOnlyBroadcastState(self._function._broadcast_store,
                                      descriptor.getName())


class Context(_KeyedContext):
    """``Context``：processBroadcastElement 的上下文（广播状态可写）。"""

    def getBroadcastState(self, descriptor: Any) -> BroadcastState:
        return BroadcastState(self._function._broadcast_store,
                              descriptor.getName())


class OnTimerContext(_KeyedContext):
    """``OnTimerContext``：onTimer 的上下文（可写广播状态 + 可注册定时器）。"""

    def getBroadcastState(self, descriptor: Any) -> BroadcastState:
        return BroadcastState(self._function._broadcast_store,
                              descriptor.getName())

    def timeDomain(self) -> str:
        """对应 ``timeDomain()``（本工程未使用）。"""
        return "PROCESSING_TIME"


class KeyedBroadcastProcessFunction(object):
    """``KeyedBroadcastProcessFunction<KS, IN1, IN2, OUT>`` 的替身。"""

    # 【Java→Python】Java 的上下文类型是**嵌套接口**，这里以类属性暴露，
    # 使业务代码的 `ReadOnlyContext` / `Context` / `OnTimerContext` 引用路径
    # 与 Java 的 `KeyedBroadcastProcessFunction.ReadOnlyContext` 等一一对应。
    ReadOnlyContext = ReadOnlyContext
    Context = Context
    OnTimerContext = OnTimerContext

    def __init__(self) -> None:
        self._runtime_context: Optional[RuntimeContext] = None
        #: 广播状态存储：{描述符名: {key: value}}（算子级共享，非键控）
        self._broadcast_store = {}
        #: 待触发定时器：[(timestamp, key)]
        self._timers: List[Tuple[int, Any]] = []

    # ------------------------------------------------------------------ 生命周期
    def open(self, parameters: Configuration) -> None:
        """对应 ``open(Configuration)``：默认空实现。"""
        return None

    def close(self) -> None:
        """对应 ``close()``：默认空实现。"""
        return None

    # ------------------------------------------------------------------ 核心
    def processElement(self, value: Any, ctx: ReadOnlyContext,
                       out: Any) -> None:
        """对应 ``processElement(IN1, ReadOnlyContext, Collector<OUT>)``。"""
        raise NotImplementedError("KeyedBroadcastProcessFunction.processElement 必须由子类实现")

    def processBroadcastElement(self, value: Any, ctx: Context,
                                out: Any) -> None:
        """对应 ``processBroadcastElement(IN2, Context, Collector<OUT>)``。"""
        raise NotImplementedError(
            "KeyedBroadcastProcessFunction.processBroadcastElement 必须由子类实现")

    def onTimer(self, timestamp: int, ctx: OnTimerContext, out: Any) -> None:
        """对应 ``onTimer(long, OnTimerContext, Collector<OUT>)``：默认空实现。"""
        return None

    # ------------------------------------------------------------------ 上下文
    def getRuntimeContext(self) -> RuntimeContext:
        """对应 ``getRuntimeContext()``（Java 由运行时注入）。"""
        if self._runtime_context is None:
            self._runtime_context = RuntimeContext()
        return self._runtime_context

    def __repr__(self) -> str:
        return "%s(pendingTimers=%d)" % (type(self).__name__, len(self._timers))
