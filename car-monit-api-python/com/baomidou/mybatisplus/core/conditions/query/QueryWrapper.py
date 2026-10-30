# -*- coding: utf-8 -*-
"""com.baomidou.mybatisplus.core.conditions.query.QueryWrapper

【无 Java 源文件：框架类替身】
Java 侧来自 MyBatis-Plus jar：
    com.baomidou.mybatisplus.core.conditions.query.QueryWrapper<T>

【Java→Python 为什么单独建一个文件】
Java 的 ``QueryWrapper`` 与 ``LambdaQueryWrapper`` 是**同包的两个独立类**，
业务代码按类名分别 import。Python 的模块与文件一一对应，因此这里为
``QueryWrapper`` 单独提供模块路径，实现体复用 ``LambdaQueryWrapper.py`` 中的
同一个 ``QueryWrapper`` 类（两者条件构造逻辑完全相同，见该文件说明）：

    Java : import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
    Py   : from com.baomidou.mybatisplus.core.conditions.query.QueryWrapper import QueryWrapper

【Java→Python】使用差异
1) 本工程对该类只用**列名字符串**写法（``.between("snapshottime", a, b)``、
   ``.ge/.le/.like/.last``），无需方法引用，可直接逐字迁移。
2) ``QueryWrapper<T>`` 的泛型参数在 Python 侧由 ``Generic[T]`` 承载，
   原代码里的 ``new QueryWrapper<OdsRtSzdnSnapshotFlowAddcode>()`` →
   ``QueryWrapper()``（Python 的类型参数不参与运行期）。
3) Java 的**裸类型**警告（``QueryWrapper qw = new QueryWrapper();``）在 Python
   不存在；为保持“三张表共用一个 wrapper”的原意，这里同样允许不带类型参数。
"""

from __future__ import annotations

from com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper import (
    AbstractWrapper,
    QueryWrapper as _QueryWrapper,
)

__all__ = ["QueryWrapper"]


class QueryWrapper(_QueryWrapper):
    """列名形式的条件构造器（实现见 LambdaQueryWrapper.py，此处仅为独立模块路径）。"""
