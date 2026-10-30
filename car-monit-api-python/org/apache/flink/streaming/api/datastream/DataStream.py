# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.datastream.DataStream

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.datastream.DataStream<T>``。
本工程用法（VehicleTrackFlinkJob）：
    DataStream<StandardEvent> unifiedStream = cdcStream.union(rawDataStream);
    KeyedStream<StandardEvent, String> keyedStream = unifiedStream.keyBy(StandardEvent::getPlateKey);
    resultStream.addSink(new TrailResultSink());
    DataStream<Map<String,Object>> dictStream = env.addSource(new DictionarySourceFunction())
            .name("Redis 字典数据").setParallelism(1);

【Java→Python】关键差异（**替身没有运行时，这是最大的差异**）
1) Java 的 ``DataStream`` 只是一张**逻辑计划**（Transformation DAG）的句柄，
   真正跑数据的是 Flink 集群：``env.execute()`` 把 DAG 提交上去，
   Source 线程持续产数据、算子按 key 分区、定时器由系统时钟触发。
   Python 替身没有集群，改用「**惰性求值的本地流水线**」：
   ``_values()`` 递归向上游取值并执行算子；``env.execute()`` 触发一次。
2) **Source 不会被自动消费**：``FlinkKafkaConsumer`` 需要 Kafka，
   ``DictionarySourceFunction`` 是死循环，两者都不能在本地「跑起来」。
   因此 ``_values()`` 对 source 流返回 ``feed(...)`` 注入的元素
   （默认空列表），测试时用 ``feed`` 手动喂数据 —— 这与真实 Flink
   的「push 模型」不同，但足以验证处理逻辑。
3) Java 的算子都是**并行、乱序、按 key 分区**的；替身的 ``_values()``
   是**单线程、按输入顺序**的，key 分区仅通过
   ``RuntimeContext.setCurrentKey`` 模拟状态隔离（见 BroadcastConnectedStream）。
4) ``name(String)`` / ``setParallelism(int)`` 在 Java 里返回**新的**
   ``SingleOutputStreamOperator``（链式 API）；替身直接返回 self
   （同一个对象），调用写法不变。
5) ``addSink`` 在 Java 返回 ``DataStreamSink<T>``（不是 DataStream），
   替身同样返回独立对象，并自动登记到 env，供 ``execute()`` 发现。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, List, Optional

from org.apache.flink.configuration.Configuration import Configuration

__all__ = ["DataStream"]

log = logging.getLogger(__name__)


class DataStream(object):
    """``DataStream<T>`` 的替身（惰性求值的本地流水线）。"""

    def __init__(self, env: Any = None,
                 name: Optional[str] = None) -> None:
        self._env = env
        self._name = name
        self._parallelism: Optional[int] = None
        #: 对应 ``env.addSource(...)`` 产出的 Source 流
        self._source: Any = None
        #: 上游流（union 时多个；map/filter 时一个）
        self._upstream: List["DataStream"] = []
        #: 对应 ``.map(fn)`` 的算子（RichMapFunction 或普通可调用对象）
        self._mapper: Optional[Callable[[Any], Any]] = None
        self._mapper_opened = False
        #: 测试辅助：``feed`` 注入的元素（仅对 source / 叶子流有效）
        self._elements: List[Any] = []

    # ------------------------------------------------------------------ 链式 API
    def name(self, name: str) -> "DataStream":
        """对应 ``name(String)``：算子命名（返回 self）。"""
        self._name = name
        return self

    def setParallelism(self, parallelism: int) -> "DataStream":
        """对应 ``setParallelism(int)``：替身只记录，不改变执行方式。"""
        self._parallelism = int(parallelism)
        return self

    def getParallelism(self) -> Optional[int]:
        return self._parallelism

    def getName(self) -> Optional[str]:
        return self._name

    def map(self, mapper: Any) -> "DataStream":
        """对应 ``map(MapFunction<T,R>)``：产生新的算子流。"""
        result = DataStream(self._env, self._name)
        result._upstream = [self]
        result._mapper = mapper
        return result

    def union(self, other: "DataStream") -> "DataStream":
        """对应 ``union(DataStream<T>...)``：多流合并（类型必须相同）。"""
        result = DataStream(self._env, self._name)
        result._upstream = [self, other]
        return result

    def keyBy(self, key_selector: Any) -> Any:
        """对应 ``keyBy(KeySelector<T,K>)``：返回 KeyedStream。

        【Java→Python】Java 用方法引用 ``StandardEvent::getPlateKey``；
        Python 直接传可调用对象（``lambda e: e.getPlateKey()``），见业务代码。
        """
        from org.apache.flink.streaming.api.datastream.KeyedStream import KeyedStream

        return KeyedStream(self, key_selector)

    def broadcast(self, descriptor: Any) -> Any:
        """对应 ``broadcast(MapStateDescriptor)``：返回 BroadcastStream。"""
        from org.apache.flink.streaming.api.datastream.BroadcastStream import (
            BroadcastStream,
        )

        return BroadcastStream(self, descriptor)

    def addSink(self, sink: Any) -> Any:
        """对应 ``addSink(SinkFunction<T>)``：返回 DataStreamSink 并登记到 env。"""
        from org.apache.flink.streaming.api.datastream.DataStreamSink import (
            DataStreamSink,
        )

        return DataStreamSink(self._env, self, sink)

    # ------------------------------------------------------------------ 测试辅助
    def feed(self, elements: Iterable[Any]) -> "DataStream":
        """Java 没有此方法；替身用于**替代真实 Source**注入元素。"""
        self._elements.extend(elements)
        return self

    # ------------------------------------------------------------------ 求值
    def _values(self) -> List[Any]:
        """Java 没有此方法；替身用于**本地拉取**该流的全部元素。"""
        # Source 流：不自动消费外部系统，只返回 feed 注入的元素
        if self._source is not None:
            return list(self._elements)
        # map 算子
        if self._mapper is not None:
            function = self._mapper
            if not self._mapper_opened:
                # RichMapFunction 需要 open(Configuration)；普通函数没有 open
                open_method = getattr(function, "open", None)
                if callable(open_method):
                    open_method(Configuration())
                self._mapper_opened = True
            upstream_values = (self._upstream[0]._values()
                               if self._upstream else [])
            return [function.map(item) for item in upstream_values]
        # union / 其它多上游合并
        if self._upstream:
            values: List[Any] = []
            for stream in self._upstream:
                values.extend(stream._values())
            return values
        return list(self._elements)

    def __repr__(self) -> str:
        return "DataStream(name=%r, parallelism=%r)" % (self._name,
                                                        self._parallelism)
