# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.functions.RuntimeContext

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.functions.RuntimeContext``。
本工程用法（VehicleTrackFlinkJob.TrailAggregatorProcessFunction.open）：
    trailState = getRuntimeContext().getState(trailStateDesc);
    pendingQueue = getRuntimeContext().getListState(pendingQueueDesc);

【Java→Python】关键差异
1) Java 的 RuntimeContext 由 Flink 运行时注入（``AbstractRichFunction`` 内部持有），
   提供**当前 subtask / key 的状态分区**；Python 侧没有运行时，
   本替身自己维护状态字典，并由本地执行器在调用 processElement 前
   通过 ``setCurrentKey(key)`` 切换分桶 —— 这就是“键控状态按 key 隔离”
   在替身里的实现方式。
2) Java 的 ``getState(ValueStateDescriptor)`` 返回 ``ValueState<T>``；
   ``getListState`` / ``getMapState`` 同理。替身返回绑定当前 key 的句柄，
   句柄本身可复用（每次调用不必新建）。
3) ``getTaskName()`` / ``getNumberOfParallelSubtasks()`` 等本工程未使用，不实现。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from org.apache.flink.api.common.state.ListState import ListState
from org.apache.flink.api.common.state.MapState import MapState
from org.apache.flink.api.common.state.ValueState import ValueState

__all__ = ["RuntimeContext"]


class RuntimeContext(object):
    """``RuntimeContext`` 的替身（状态工厂 + 当前 key）。"""

    def __init__(self) -> None:
        #: 键控状态存储：{(状态名, key): value} / {(状态名, key): list} / {(状态名, key): dict}
        # 【Java→Python】三张表分开存，避免同一 name 在不同类型状态间串味
        self._value_store: Dict[tuple, Any] = {}
        self._list_store: Dict[tuple, Any] = {}
        self._map_store: Dict[tuple, Any] = {}
        #: 当前处理的 key（对应 Flink 的 keyed 上下文）
        self._current_key: Optional[Any] = None

    # ------------------------------------------------------------------ key
    def setCurrentKey(self, key: Any) -> None:
        """Java 无此方法；替身用于模拟 Flink 的「按 key 分区」上下文切换。"""
        self._current_key = key

    def currentKey(self) -> Any:
        """Java 的 ``getCurrentKey()`` 语义（仅在键控上下文中可用）。"""
        return self._current_key

    # ------------------------------------------------------------------ 状态工厂
    def getState(self, descriptor: Any) -> ValueState:
        """对应 ``getState(ValueStateDescriptor<T>)``。"""
        return ValueState(self._value_store, descriptor.getName(), self)

    def getListState(self, descriptor: Any) -> ListState:
        """对应 ``getListState(ListStateDescriptor<T>)``。"""
        return ListState(self._list_store, descriptor.getName(), self)

    def getMapState(self, descriptor: Any) -> MapState:
        """对应 ``getMapState(MapStateDescriptor<K,V>)``。"""
        return MapState(self._map_store, descriptor.getName(), self)

    def __repr__(self) -> str:
        return ("RuntimeContext(currentKey=%r, valueStates=%d, listStates=%d)" %
                (self._current_key, len(self._value_store),
                 len(self._list_store)))
