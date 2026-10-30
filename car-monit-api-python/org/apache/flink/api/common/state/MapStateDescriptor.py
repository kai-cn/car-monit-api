# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.state.MapStateDescriptor

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.state.MapStateDescriptor<UK, UV>``。
本工程用法（VehicleTrackFlinkJob，两处）：
    // 1) 广播流描述符（main 里 createDictBroadcastStream）
    MapStateDescriptor<String, Map<String, Object>> dictStateDesc =
            new MapStateDescriptor<>("dict-broadcast-state", Types.STRING,
                    TypeInformation.of(new TypeHint<Map<String, Object>>() {}));
    return dictStream.broadcast(dictStateDesc);

    // 2) 处理函数内**用同一个 name 重建**描述符以拿到广播状态
    dictStateDesc = new MapStateDescriptor<>("dict-broadcast-state", ...);

【Java→Python】关键差异
1) **广播状态的描述符必须“同名同类型”重建**：Flink 的 ``broadcast(desc)`` 与
   ``ctx.getBroadcastState(desc)`` 通过 ``desc.getName()`` 匹配。Java 里靠两个
   独立构造但 name 相同来对齐；Python 完全照搬这一约定（见 DataStream.broadcast
   与 ReadOnlyContext.getBroadcastState）。
2) Java 构造器是 3 参 ``(name, keyTypeInfo, valueTypeInfo)``；替身保持一致，
   不做重载合并。
3) 泛型 <String, Map<String,Object>> 在 Python 运行时擦除，两个 TypeInformation
   仅作记录。
"""
from __future__ import annotations

from typing import Any

from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation

__all__ = ["MapStateDescriptor"]


class MapStateDescriptor(object):
    """``MapStateDescriptor<UK, UV>`` 的替身。"""

    def __init__(self, name: str, key_type_info: Any, value_type_info: Any) -> None:
        self._name = name
        self._key_type_info = (key_type_info
                               if isinstance(key_type_info, TypeInformation)
                               else TypeInformation.of(key_type_info))
        self._value_type_info = (value_type_info
                                 if isinstance(value_type_info, TypeInformation)
                                 else TypeInformation.of(value_type_info))

    def getName(self) -> str:
        return self._name

    def getKeyTypeInfo(self) -> TypeInformation:
        return self._key_type_info

    def getValueTypeInfo(self) -> TypeInformation:
        return self._value_type_info

    def __repr__(self) -> str:
        return "MapStateDescriptor(name=%r)" % (self._name,)
