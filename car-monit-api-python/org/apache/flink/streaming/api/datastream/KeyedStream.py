# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.datastream.KeyedStream

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.datastream.KeyedStream<T, KEY>``。
本工程用法（VehicleTrackFlinkJob 步骤 4~5）：
    KeyedStream<StandardEvent, String> keyedStream = unifiedStream
            .keyBy(StandardEvent::getPlateKey);
    DataStream<TrailResult> resultStream = keyedStream
            .connect(dictBroadcastStream)
            .process(new TrailAggregatorProcessFunction());

【Java→Python】关键差异
1) **方法引用 ``StandardEvent::getPlateKey``**：Java 用方法引用表达
   ``KeySelector<T, K>``；Python 没有方法引用语法，转写时改成
   ``lambda event: event.getPlateKey()``（见业务文件 main）。
2) Java 的 ``keyBy`` 会让后续算子**按 key 分区并行**，每个 key 有独立的
   键控状态；Python 替身只在执行时对每条记录调用 keySelector 并
   ``setCurrentKey``，用**同一个算子实例 + 按 key 分桶的状态表**模拟，
   单线程串行处理（详见 DataStream 差异说明）。
3) ``KeyedStream`` 在 Java 里是 ``DataStream`` 的**子类**；替身同样继承，
   因此 ``KeyedStream`` 也能 ``addSink`` / ``union``。
4) ``connect(BroadcastStream)`` 返回 ``BroadcastConnectedStream``
   （Java 泛型 <T, KEY, IN2>）；替身不表达泛型。
"""
from __future__ import annotations

from typing import Any, Callable

from org.apache.flink.streaming.api.datastream.DataStream import DataStream

__all__ = ["KeyedStream"]


class KeyedStream(DataStream):
    """``KeyedStream<T, KEY>`` 的替身。"""

    def __init__(self, upstream: DataStream,
                 key_selector: Callable[[Any], Any]) -> None:
        super(KeyedStream, self).__init__(upstream._env, upstream.getName())
        # 键控流与上游元素完全相同，只是「分区规则」不同
        self._upstream = [upstream]
        self._key_selector = key_selector

    # ------------------------------------------------------------------ API
    def getKeySelector(self) -> Callable[[Any], Any]:
        """Java 无公开 getter；替身用于执行器取 key。"""
        return self._key_selector

    def connect(self, broadcast_stream: Any) -> Any:
        """对应 ``connect(BroadcastStream<R>)``：返回 BroadcastConnectedStream。"""
        from org.apache.flink.streaming.api.datastream.BroadcastConnectedStream import (
            BroadcastConnectedStream,
        )

        return BroadcastConnectedStream(self, broadcast_stream)

    def __repr__(self) -> str:
        return "KeyedStream(upstream=%r)" % (self._upstream[0],)
