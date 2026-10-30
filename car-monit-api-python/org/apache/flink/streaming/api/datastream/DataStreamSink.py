# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.datastream.DataStreamSink

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.datastream.DataStreamSink<T>``。
本工程用法（VehicleTrackFlinkJob 步骤 6）：
    resultStream.addSink(new TrailResultSink());   // 返回值被丢弃

【Java→Python】关键差异
1) Java 的 ``DataStreamSink`` 只是 DAG 上的一个**终点节点**，构造时即把
   SinkFunction 写进 Transformation 树；替身构造函数里**主动登记到 env**
   （``env._sink_streams.append(self)``），使 ``env.execute()`` 能找到它。
2) Java 侧 ``addSink`` 还有 ``name`` / ``setParallelism`` / ``disableChaining``
   等链式方法（本工程未使用），替身只保留 ``name`` / ``setParallelism``
   以保持调用形状一致。
3) Java 的 ``DataStreamSink`` **不是** DataStream 的子类；替身同样不继承。
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["DataStreamSink"]


class DataStreamSink(object):
    """``DataStreamSink<T>`` 的替身（DAG 终点 + 本地执行入口）。"""

    def __init__(self, env: Any, upstream: Any, sink: Any) -> None:
        self._env = env
        self._upstream = upstream
        self._sink = sink
        self._name: Optional[str] = None
        self._parallelism: Optional[int] = None
        # 【Java→Python】登记到 env，供 execute() 遍历（Java 靠 Transformation 树）
        if env is not None:
            env._sink_streams.append(self)

    # ------------------------------------------------------------------ 链式 API
    def name(self, name: str) -> "DataStreamSink":
        self._name = name
        return self

    def setParallelism(self, parallelism: int) -> "DataStreamSink":
        self._parallelism = int(parallelism)
        return self

    # ------------------------------------------------------------------ 执行
    def emit(self) -> list:
        """Java 没有此方法；替身把上游元素逐条交给 SinkFunction.invoke。"""
        from org.apache.flink.streaming.api.functions.sink.SinkFunction import (
            SinkFunction,
        )

        emitted = []
        for value in self._upstream._values():
            self._sink.invoke(value, SinkFunction.Context())
            emitted.append(value)
        return emitted

    def getSinkFunction(self) -> Any:
        """Java 无公开 getter；替身用于断言。"""
        return self._sink

    def __repr__(self) -> str:
        return "DataStreamSink(name=%r, sink=%r)" % (self._name, self._sink)
