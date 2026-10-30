# -*- coding: utf-8 -*-
"""org.apache.flink.streaming.api.functions.sink.SinkFunction

【无 Java 源文件：框架类替身】
Java 侧来自 flink-streaming-java：
``org.apache.flink.streaming.api.functions.sink.SinkFunction<T>``。
本工程用法（VehicleTrackFlinkJob.TrailResultSink）：
    private static class TrailResultSink implements SinkFunction<TrailResult> {
        @Override
        public void invoke(TrailResult value, Context context) throws Exception { ... }
    }

【Java→Python】关键差异
1) Java 的 ``SinkFunction`` 有嵌套接口 ``Context``（Flink 1.13 起用于
   获取当前时间戳等），``invoke(T value, Context context)`` 是**默认方法**
   （Java 8 interface default）。替身用嵌套类 ``Context`` 表达，并在
   本地执行器里每次调用前 new 一个。
2) Java 接口里还有一个已废弃的 ``invoke(T value)`` 重载；本工程只用两参版本，
   替身不实现单参重载（若子类写成单参，调用时会 TypeError，
   正好暴露“签名与 Java 不一致”）。
3) ``invoke`` 的异常在 Java 侧会触发作业失败；Python 侧直接向上抛。
"""
from __future__ import annotations

from typing import Any

__all__ = ["SinkFunction"]


class SinkContext(object):
    """``SinkFunction.Context`` 的替身。"""

    def __init__(self, current_processing_time: int = None) -> None:
        self._current_processing_time = current_processing_time

    def currentProcessingTime(self) -> Any:
        """对应 ``currentProcessingTime()``（本工程未使用）。"""
        return self._current_processing_time

    def currentWatermark(self) -> Any:
        """对应 ``currentWatermark()``（本工程未使用）。"""
        return None

    def timestamp(self) -> Any:
        """对应 ``timestamp()``（本工程未使用）。"""
        return None

    def __repr__(self) -> str:
        return "SinkFunction.Context()"


class SinkFunction(object):
    """``SinkFunction<T>`` 的替身：子类实现 ``invoke``。"""

    # 【Java→Python】Java 的 Context 是**嵌套接口**，用类属性暴露同名引用
    Context = SinkContext

    def invoke(self, value: Any, context: SinkContext) -> None:
        """对应 ``void invoke(T value, Context context)``。"""
        raise NotImplementedError("SinkFunction.invoke 必须由子类实现")

    def __repr__(self) -> str:
        return "%s()" % type(self).__name__
