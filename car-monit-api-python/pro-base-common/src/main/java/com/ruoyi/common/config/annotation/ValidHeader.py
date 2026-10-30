# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.annotation.ValidHeader

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/annotation/ValidHeader.java
"""
from __future__ import annotations

from typing import Callable, Sequence


def ValidHeader(value: Sequence[str], message: str = "Header parameter is empty") -> Callable:
    """校验请求头注解：声明必须存在的请求头名称。

    【Java→Python】Java 注解的成员 value()/message() 由拦截器反射读取；
    Python 侧改为“注解工厂 + 属性挂载”，用法：
        @ValidHeader(["token", "userId"])
        def handler(...): ...
    拦截器通过 getattr(fn, "__valid_header__", None) 读取 (headers, message)。
    """

    def decorator(target: Callable) -> Callable:
        setattr(target, "__valid_header__", (list(value), message))
        return target

    return decorator
