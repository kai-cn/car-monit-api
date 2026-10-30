# -*- coding: utf-8 -*-
"""org.apache.flink.util.Collector

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.util.Collector<T>``。
本工程用法（VehicleTrackFlinkJob）：
    void processElement(StandardEvent event, ReadOnlyContext ctx,
                        Collector<TrailResult> out) { out.collect(new TrailResult(...)); }

【Java→Python】关键差异
1) Java 的 ``Collector`` 是**接口**，由运行时实现并向下游传递；
   Python 用具体类表达，内部就是 ``list.append``。
2) Java 的 ``collect(T record)`` 返回值 void；替身同样返回 None。
3) ``close()`` 在 Collector 接口里存在（默认空实现），替身保留。
"""
from __future__ import annotations

from typing import Any, List

__all__ = ["Collector"]


class Collector(object):
    """``Collector<T>`` 的替身（把输出收集到列表）。"""

    def __init__(self, sink: List[Any] = None) -> None:
        #: 输出缓冲；默认每次新建，也可传入外部列表以复用
        self._output: List[Any] = sink if sink is not None else []

    def collect(self, record: Any) -> None:
        """对应 ``collect(T record)``。"""
        self._output.append(record)

    def close(self) -> None:
        return None

    # ------------------------------------------------------------------ 测试辅助
    def getOutput(self) -> List[Any]:
        """Java 没有此方法；替身用于断言算子输出。"""
        return self._output

    def __repr__(self) -> str:
        return "Collector(size=%d)" % len(self._output)
