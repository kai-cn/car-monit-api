# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.typeinfo.TypeHint

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.typeinfo.TypeHint<T>``。
本工程用法（VehicleTrackFlinkJob，[修复2] 的产物）：
    TypeInformation.of(new TypeHint<Map<String, Object>>() {})
    TypeInformation.of(new TypeHint<TrailState>() {})

【Java→Python】关键差异（**泛型擦除的典型坑**）
1) Java 的 ``new TypeHint<X>() {}`` 是**匿名子类**：泛型参数 X 被写进
   class 文件的 Signature 属性，Flink 通过反射 ``getGenericSuperclass()``
   把它读出来 —— 也就是说“类型信息”是**运行时真实存在**的。
   Python 在运行时**完全擦除**泛型（``TypeHint[X]`` 与 ``TypeHint[Y]`` 的
   类型相同），因此必须显式把 X 作为值传进来：
       ``TypeHint[X]`` → 返回 ``TypeHint`` 实例，``instance.type`` 为 X。
   下面用 ``__class_getitem__`` 实现，使调用写法与 Java 极为接近
   （只少了 ``new ...() {}`` 那对花括号）。
2) Java 的 TypeHint 是无状态标记类；替身只保存 ``type`` 字段。
"""
from __future__ import annotations

from typing import Any

__all__ = ["TypeHint"]


class TypeHint(object):
    """``TypeHint<T>`` 的替身：显式携带被擦除的泛型参数。"""

    def __init__(self, type_: Any = None) -> None:
        #: 被 Java 泛型参数表达的类型（Python 必须显式保存）
        self.type = type_

    def __class_getitem__(cls, item: Any) -> "TypeHint":
        """支持 ``TypeHint[TrailState]`` 写法（对应 Java 的 ``new TypeHint<T>(){}``）。"""
        return cls(item)

    def getType(self) -> Any:
        return self.type

    def __repr__(self) -> str:
        name = getattr(self.type, "__name__", repr(self.type))
        return "TypeHint[%s]" % name
