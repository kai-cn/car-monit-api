# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.Custom

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/Custom.java
"""


class Custom:
    """标识自定义类接口（空标记接口）。

    【Java→Python】Java 的空标记接口 → Python 的空基类。
    没有抽象方法，仅用于类型判断；Python 中可用 isinstance(obj, Custom) 等价于
    Java 的 obj instanceof Custom。
    """
