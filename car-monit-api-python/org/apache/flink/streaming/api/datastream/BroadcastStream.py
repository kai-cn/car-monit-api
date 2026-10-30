# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.datastream.BroadcastStream

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.datastream.BroadcastStream<T>``。
本工程用法（VehicleTrackFlinkJob.createDictBroadcastStream）：
    return dictStream.broadcast(dictStateDesc);   // → BroadcastStream<Map<String,Object>>

【Java→Python】关键差异
1) Java 的 BroadcastStream 只能由 ``DataStream.broadcast(MapStateDescriptor)``
   创建（构造器是包级私有），替身保持同一入口，但构造器可见。
2) **描述符绑定**：Flink 要求广播流与后续 ``ctx.getBroadcastState(desc)``
   使用**同名**描述符，否则运行时拿不到状态。替身把描述符原样保存在
   ``_descriptor``，由 BroadcastConnectedStream 在执行时传给算子做校验提示。
3) 广播流本身不是 DataStream 的子类（Java 里也不是），不能直接 map/keyBy；
   替身同样不继承 DataStream。
"""
from __future__ import annotations

from typing import Any

__all__ = ["BroadcastStream"]


class BroadcastStream(object):
    """``BroadcastStream<T>`` 的替身。"""

    def __init__(self, upstream: Any, descriptor: Any) -> None:
        self._upstream = upstream
        self._descriptor = descriptor

    def getUpstream(self) -> Any:
        """Java 无公开 getter；替身用于执行器回溯上游。"""
        return self._upstream

    def getStateDescriptor(self) -> Any:
        """对应 ``getStateDescriptor()``（Flink 内部有同名方法）。"""
        return self._descriptor

    def __repr__(self) -> str:
        return "BroadcastStream(descriptor=%r)" % (self._descriptor,)
