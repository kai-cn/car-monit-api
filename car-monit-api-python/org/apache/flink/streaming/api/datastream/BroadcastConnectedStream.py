# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.datastream.BroadcastConnectedStream

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.datastream.BroadcastConnectedStream<IN1, IN2>``。
本工程用法（VehicleTrackFlinkJob 步骤 5）：
    DataStream<TrailResult> resultStream = keyedStream
            .connect(dictBroadcastStream)
            .process(new TrailAggregatorProcessFunction());

【Java→Python】关键差异（**本文件是整个 Flink 替身的执行核心**）
1) Java 的 ``BroadcastConnectedStream`` 也是逻辑计划节点，``process(fn)``
   只是把 ``KeyedBroadcastProcessFunction`` 挂到 DAG 上，真正执行靠集群。
   Python 替身额外提供一个 ``_ProcessStream``（**Java 里没有这个类**），
   它的 ``_values()`` 就是本地版的「算子执行器」：
       a) ``fn.open(Configuration())`` —— 与 Flink 首次启动算子时一致；
       b) 先喂**广播流**元素 → ``processBroadcastElement``（写广播状态）；
       c) 再喂**数据流**元素 → 按 keySelector 切 key →
          ``processElement``（读广播状态 + 读写键控状态）；
       d) 最后统一触发**所有已登记定时器** → ``onTimer``。
2) **执行顺序与真实 Flink 不同**：真实 Flink 里广播元素和数据元素
   是**乱序交错**到达的，只有在字典先到达时才能富化成功；替身固定
   「先全部广播、再全部数据」，因此**不会**复现「字典晚到导致丢失」
   这类时序问题（业务逻辑本身不受影响）。
3) **定时器被立即触发**：真实 Flink 要等系统时钟到达 timestamp 才回调；
   替身在数据流耗尽后**立即**以登记时的 (timestamp, key) 回调 onTimer，
   这样重试/超时逻辑可以在毫秒级验证完，而不必真的等 60 秒。
   ``onTimer`` 里再注册的定时器会在下一轮继续触发（最多 1000 轮，
   防止业务写法出现死循环把测试挂死）。
4) Java 的 ``process`` 有 4 个重载（KeyedBroadcastProcessFunction /
   BroadcastProcessFunction / KeyedCoProcessFunction / CoProcessFunction）；
   本工程只用 KeyedBroadcastProcessFunction，替身只实现该分支。
"""
from __future__ import annotations

import copy
import logging
from typing import Any, List

from org.apache.flink.configuration.Configuration import Configuration
from org.apache.flink.streaming.api.datastream.DataStream import DataStream
from org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction import (
    Context,
    KeyedBroadcastProcessFunction,
    OnTimerContext,
    ReadOnlyContext,
)
from org.apache.flink.util.Collector import Collector as UtilCollector

__all__ = ["BroadcastConnectedStream"]

log = logging.getLogger(__name__)

#: 定时器最多连触发多少轮（防止 onTimer 无脑注册新定时器造成死循环）
_MAX_TIMER_ROUNDS = 1000


class _SnapshotCollector(UtilCollector):
    """**Java 无此类**：模拟 Flink 在算子输出边界上的序列化拷贝。

    【Java→Python】真实 Flink 默认 `enableObjectReuse=false`：算子 `out.collect(obj)`
    后，记录会先**序列化**再经网络传给下游，下游拿到的是**副本**。
    若替身直接保留引用，业务里 `out.collect(new TrailResult(current.getLatestTrail()))`
    得到的结果会与键控状态里的 `TrailInfo` 共享同一个对象 —— 之后
    `appendPoint()` 一改，先前已输出的历史结果也会跟着变（Java 不会）。
    因此这里在 collect 时做一次 `deepcopy`，等价于 Java 的“输出即快照”。
    """

    def collect(self, record: Any) -> None:
        self._output.append(copy.deepcopy(record))


class BroadcastConnectedStream(object):
    """``BroadcastConnectedStream<IN1, IN2>`` 的替身。"""

    def __init__(self, keyed_stream: Any, broadcast_stream: Any) -> None:
        self._keyed_stream = keyed_stream
        self._broadcast_stream = broadcast_stream

    def process(self, process_function: KeyedBroadcastProcessFunction) -> Any:
        """对应 ``process(KeyedBroadcastProcessFunction)``。"""
        return _ProcessStream(self._keyed_stream._env, self._keyed_stream,
                              self._broadcast_stream, process_function)

    def __repr__(self) -> str:
        return "BroadcastConnectedStream(keyed=%r)" % (self._keyed_stream,)


class _ProcessStream(DataStream):
    """**Java 无此类**：本地执行 ``KeyedBroadcastProcessFunction`` 的算子节点。"""

    def __init__(self, env: Any, keyed_stream: Any, broadcast_stream: Any,
                 process_function: KeyedBroadcastProcessFunction) -> None:
        super(_ProcessStream, self).__init__(env, "BroadcastProcess")
        self._keyed_stream = keyed_stream
        self._broadcast_stream = broadcast_stream
        self._function = process_function
        self._opened = False

    # ------------------------------------------------------------------ 求值
    def _values(self) -> List[Any]:
        function = self._function
        if not self._opened:
            function.open(Configuration())
            self._opened = True

        runtime = function.getRuntimeContext()
        # 【Java→Python】用 _SnapshotCollector 而不是裸 Collector：见该类说明
        out = _SnapshotCollector()

        # ---------- b) 广播流：写广播状态（对应 processBroadcastElement） ----------
        broadcast_upstream = self._broadcast_stream.getUpstream()
        for record in broadcast_upstream._values():
            function.processBroadcastElement(record, Context(function), out)

        # ---------- c) 数据流：按 key 分区 + 处理 ----------
        key_selector = self._keyed_stream.getKeySelector()
        for record in self._keyed_stream._values():
            runtime.setCurrentKey(key_selector(record))
            function.processElement(record, ReadOnlyContext(function), out)

        # ---------- d) 定时器：数据耗尽后立即触发 ----------
        rounds = 0
        while function._timers and rounds < _MAX_TIMER_ROUNDS:
            rounds += 1
            pending = list(function._timers)
            function._timers = []
            for timestamp, key in pending:
                runtime.setCurrentKey(key)
                function.onTimer(timestamp, OnTimerContext(function), out)

        if rounds >= _MAX_TIMER_ROUNDS:
            log.warning("[Flink替身] 定时器触发轮次达到上限 %d，可能 onTimer 中存在"
                        "无终止的重试逻辑", _MAX_TIMER_ROUNDS)

        return out.getOutput()

    def __repr__(self) -> str:
        return "_ProcessStream(function=%r)" % (self._function,)
