# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.ListStateDescriptor

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.ListStateDescriptor<T>``。
本工程用法（VehicleTrackFlinkJob.TrailAggregatorProcessFunction.open）：
    ListStateDescriptor<PendingEvent> pendingQueueDesc =
            new ListStateDescriptor<>("pending-queue",
                    TypeInformation.of(new TypeHint<PendingEvent>() {}));
    pendingQueue = getRuntimeContext().getListState(pendingQueueDesc);

【Java→Python】关键差异
1) 同 ValueStateDescriptor：Java 的 ``(name, TypeInformation)`` 与 ``(name, Class)``
   两个重载合并为一个构造器。
2) 本工程**没有**给 pendingQueue 设置 TTL（只有 trailState 设置了 30 天），
   因此替身也不提供 ``enableTimeToLive``（Flink 的 ListStateDescriptor 其实有，
   但本工程未使用 —— 按“只实现用到的 API”原则不补）。
"""
from __future__ import annotations

from typing import Any

from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation

__all__ = ["ListStateDescriptor"]


class ListStateDescriptor(object):
    """``ListStateDescriptor<T>`` 的替身。"""

    def __init__(self, name: str, type_info: Any) -> None:
        self._name = name
        self._type_info = (type_info if isinstance(type_info, TypeInformation)
                           else TypeInformation.of(type_info))

    def getName(self) -> str:
        return self._name

    def getTypeInfo(self) -> TypeInformation:
        return self._type_info

    def __repr__(self) -> str:
        return "ListStateDescriptor(name=%r, type=%r)" % (self._name,
                                                          self._type_info)
