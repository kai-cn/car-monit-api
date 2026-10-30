# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.functions.source.SourceFunction

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.functions.source.SourceFunction<T>``。
本工程用法（VehicleTrackFlinkJob.DictionarySourceFunction）：
    private static class DictionarySourceFunction implements SourceFunction<Map<String, Object>> {
        private volatile boolean isRunning = true;
        @Override public void run(SourceContext<Map<String, Object>> ctx) throws Exception {
            while (isRunning) { ctx.collect(new HashMap<>()); TimeUnit.MINUTES.sleep(10); }
        }
        @Override public void cancel() { isRunning = false; ... }
    }

【Java→Python】关键差异
1) Java 的 ``SourceFunction`` 是**接口**，内部还有嵌套接口 ``SourceContext<T>``
   （``collect(T)`` / ``collectWithTimestamp(T, long)`` / ``emitWatermark`` /
   ``markAsTemporarilyIdle`` / ``getCheckpointLock``）。本工程只用到
   ``collect``，替身只实现该方法，其余显式省略（调用即 AttributeError，
   与“接口里没有”等价）。
2) **``run`` 是阻塞方法**：真实 Flink 会把它放在独立的 Source 线程里跑，
   由 ``cancel()`` 通知退出。Python 替身不做线程调度，``run`` 只由本地
   执行器**按需**调用；``DictionarySourceFunction.run`` 里是 `while(isRunning)`
   + 10 分钟 sleep 的**死循环**，因此 ``StreamExecutionEnvironment.execute()``
   绝不自动调用 source.run（详见 StreamExecutionEnvironment 的差异说明）。
3) Java 的 ``volatile boolean isRunning`` 依赖 JMM 可见性；Python 的 GIL
   保证单个属性读写的原子性，业务代码里的 ``isRunning`` 直接写成普通属性，
   语义等价（见业务文件注释）。
"""
from __future__ import annotations

from typing import Any, List

__all__ = ["SourceFunction"]


class SourceContext(object):
    """``SourceFunction.SourceContext<T>`` 的替身（只实现 collect）。"""

    def __init__(self, function: "SourceFunction") -> None:
        self._function = function
        #: Java 由运行时把元素推给下游；替身先累积到列表，供测试读取
        self._output: List[Any] = []

    def collect(self, element: Any) -> None:
        """对应 ``collect(T element)``：向下游发射一条记录。"""
        self._output.append(element)

    # ------------------------------------------------------------------ 测试辅助
    def getOutput(self) -> List[Any]:
        """Java 没有此方法；替身用于断言 Source 发射了什么。"""
        return self._output

    def __repr__(self) -> str:
        return "SourceContext(size=%d)" % len(self._output)


class SourceFunction(object):
    """``SourceFunction<T>`` 的替身：子类必须实现 ``run`` / ``cancel``。"""

    # 【Java→Python】Java 的 SourceContext 是**嵌套接口**，这里以类属性暴露，
    # 使业务代码 `SourceContext[...]` 的引用路径与 Java 的 `SourceFunction.SourceContext` 对应。
    SourceContext = SourceContext

    def run(self, ctx: SourceContext) -> None:
        """对应 ``void run(SourceContext<T> ctx)``。"""
        raise NotImplementedError("SourceFunction.run 必须由子类实现")

    def cancel(self) -> None:
        """对应 ``void cancel()``。"""
        raise NotImplementedError("SourceFunction.cancel 必须由子类实现")

    def __repr__(self) -> str:
        return "%s()" % type(self).__name__
