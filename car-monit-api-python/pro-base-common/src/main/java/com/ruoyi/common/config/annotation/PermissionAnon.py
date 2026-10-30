# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.annotation.PermissionAnon

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/annotation/PermissionAnon.java
"""
from __future__ import annotations

from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def PermissionAnon(target: F) -> F:
    """自定义权限拦截注解：标注在类或方法上，表示该接口允许匿名访问。

    【Java→Python】Java 的 @interface 无成员，仅作为标记元数据由 SecurityInterceptor 反射读取；
    Python 没有运行期注解，这里退化为“原样返回被装饰对象的标记装饰器”，
    并在对象上打 ``__permission_anon__ = True`` 便于拦截器判断，
    语义等价于 Java 侧 ``clazz.isAnnotationPresent(PermissionAnon.class)``。
    """
    setattr(target, "__permission_anon__", True)
    return target


def is_permission_anon(target: object) -> bool:
    """等价于 Java 的 isAnnotationPresent(PermissionAnon.class)。"""
    return bool(getattr(target, "__permission_anon__", False))
