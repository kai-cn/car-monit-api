# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.ValueStateDescriptor

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.ValueStateDescriptor<T>``。
本工程用法（VehicleTrackFlinkJob.TrailAggregatorProcessFunction.open）：
    ValueStateDescriptor<TrailState> trailStateDesc =
            new ValueStateDescriptor<>("trail-state",
                    TypeInformation.of(new TypeHint<TrailState>() {}));
    trailStateDesc.enableTimeToLive(ttlConfig);
    trailState = getRuntimeContext().getState(trailStateDesc);

【Java→Python】关键差异
1) Java 构造器有两个重载（``(String name, TypeInformation<T>)`` 与
   ``(String name, Class<T>)``）；Python 单构造器接收 ``type_info``，
   传 Class 也兼容（内部包一层 TypeInformation）。
2) Java 的 ``enableTimeToLive(StateTtlConfig)`` 返回 ``ValueStateDescriptor<T>``；
   替身同样返回 self 以支持链式调用。
3) 状态句柄（ValueState）由运行时根据**描述符**创建；替身把描述符当作
   “状态存储的键”（name + 类型），见 ``RuntimeContext.getState``。
"""
from __future__ import annotations

from typing import Any, Optional

from org.apache.flink.api.common.state.StateTtlConfig import StateTtlConfig
from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation

__all__ = ["ValueStateDescriptor"]


class ValueStateDescriptor(object):
    """``ValueStateDescriptor<T>`` 的替身。"""

    def __init__(self, name: str, type_info: Any) -> None:
        self._name = name
        # Java: 传 Class<T> 的重载内部同样会走 TypeInformation.of(Class)
        self._type_info = (type_info if isinstance(type_info, TypeInformation)
                           else TypeInformation.of(type_info))
        self._ttl_config: Optional[StateTtlConfig] = None

    # ------------------------------------------------------------------ 配置
    def enableTimeToLive(self, ttl_config: StateTtlConfig) -> "ValueStateDescriptor":
        """对应 ``enableTimeToLive(StateTtlConfig)``（返回 this）。"""
        self._ttl_config = ttl_config
        return self

    # ------------------------------------------------------------------ getter
    def getName(self) -> str:
        return self._name

    def getTypeInfo(self) -> TypeInformation:
        return self._type_info

    def getTtlConfig(self) -> Optional[StateTtlConfig]:
        """Java 侧没有公开 getter；替身用于测试断言 TTL 是否生效。"""
        return self._ttl_config

    def __repr__(self) -> str:
        return "ValueStateDescriptor(name=%r, type=%r)" % (self._name,
                                                           self._type_info)
