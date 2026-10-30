# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.typeinfo.TypeInformation

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.typeinfo.TypeInformation<T>``。
本工程用法（VehicleTrackFlinkJob）：
    TypeInformation.of(new TypeHint<Map<String, Object>>() {})
    ValueStateDescriptor<TrailState>(name, TypeInformation.of(...))

【Java→Python】关键差异
1) Java 的 ``TypeInformation`` 是类型系统的核心（决定序列化器、状态后端编码方式）；
   Python 侧没有 Flink 运行时，也就没有序列化器，本替身只保存**被描述的类型对象**，
   供 ``ValueStateDescriptor`` / ``MapStateDescriptor`` 记录并在断言中使用。
2) ``TypeInformation.of(TypeHint)`` 与 ``TypeInformation.of(Class)`` 是重载；
   Python 单方法按参数类型分派（传 TypeHint 取其 ``type``，传类则原样保存）。
3) Java 的 ``createSerializer`` / ``getTypeClass`` 等本工程未使用，不实现。
"""
from __future__ import annotations

from typing import Any

from org.apache.flink.api.common.typeinfo.TypeHint import TypeHint

__all__ = ["TypeInformation"]


class TypeInformation(object):
    """``TypeInformation<T>`` 的替身（只记录类型）。"""

    def __init__(self, type_: Any = None) -> None:
        self.type = type_

    @staticmethod
    def of(source: Any) -> "TypeInformation":
        """对应 ``of(Class<T>)`` / ``of(TypeHint<T>)`` 两个重载。"""
        if isinstance(source, TypeHint):
            return TypeInformation(source.getType())
        return TypeInformation(source)

    def getTypeClass(self) -> Any:
        return self.type

    def __repr__(self) -> str:
        name = getattr(self.type, "__name__", repr(self.type))
        return "TypeInformation(%s)" % name
