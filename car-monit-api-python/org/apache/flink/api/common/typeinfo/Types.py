# -*- coding: utf-8 -*-
"""org.apache.flink.api.common.typeinfo.Types

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.api.common.typeinfo.Types``。
本工程用法（VehicleTrackFlinkJob）：
    new MapStateDescriptor<>("dict-broadcast-state", Types.STRING, TypeInformation.of(...))

【Java→Python】关键差异（**本工程 [修复2] 关注的正是这里**）
1) Java 的 ``Types.STRING`` 等是**静态字段**（``public static final TypeInformation<String>``），
   替身用类属性一一对应。
2) 原代码曾写 ``Types.OBJECT`` —— Flink 的 ``Types`` **没有 OBJECT 这个字段**
   （只有 ``Types.GENERIC`` / ``Types.POJO`` 等），这就是源码注释里
   “[修复2] Types.OBJECT -> TypeInformation.of(new TypeHint<...>(){})” 的由来。
   替身同样**不定义 OBJECT**，保留这个约束（若有人改回 ``Types.OBJECT``，
   Python 会立刻 AttributeError，与 Java 编译失败等价）。
3) 泛型参数（<String>）在 Python 运行时被擦除，``Types.STRING`` 只携带 str 类型对象。
"""
from __future__ import annotations

from org.apache.flink.api.common.typeinfo.TypeInformation import TypeInformation

__all__ = ["Types"]


class Types(object):
    """``Types`` 的静态字段子集（只实现本工程用到的类型）。"""

    STRING = TypeInformation(str)
    LONG = TypeInformation(int)
    INT = TypeInformation(int)
    DOUBLE = TypeInformation(float)
    BOOLEAN = TypeInformation(bool)

    # 【Java→Python】有意不提供 OBJECT：Flink 的 Types 里没有该常量（见模块注释第 2 条）
