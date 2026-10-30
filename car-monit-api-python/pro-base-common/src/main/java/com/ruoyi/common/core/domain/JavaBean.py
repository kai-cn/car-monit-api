# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.JavaBean

源文件：（无 Java 对应文件 —— Python 专用基础设施）

【Java→Python】为什么需要这个文件
Java 的实体用 Lombok ``@Data`` 在编译期生成 ``getXxx()/setXxx()/isXxx()``，
源码里看不到这些方法。Python 的 ``@dataclass`` 只生成字段，没有 getter/setter。
如果为 30 个实体逐个手写 getter/setter，会产生数千行样板代码，且极易漏写。

本模块用 ``__getattr__`` 动态生成 Bean 访问器，使 Java 风格的调用**无需改动即可运行**：

    entity.setCarNo("赣A1")         # 等价于 entity.car_no = "赣A1"，且返回 self 支持链式
    entity.getCarNo()               # 等价于 entity.car_no
    entity.setId(1).setEpsId(2)     # @Accessors(chain = true) 的链式写法

命名映射规则（与 MyBatis-Plus 的 map-underscore-to-camel-case 一致）：
- 字段 ``car_no`` ⇔ Java 属性 ``carNo``（getCarNo/setCarNo）
- 字段 ``id`` ⇔ getId/setId
- 全大写缩写 ``URL`` → 字段 ``url``

注意：
1) ``__getattr__`` 只在正常属性查找失败时触发，因此不会影响 dataclass 字段本身；
2) ``getClass()`` 对应 Java 的 ``Object.getClass()``，返回类型对象；
3) ``toString()`` 按 Lombok 的格式输出 ``类名(field=value, ...)``；
4) 若字段名与 Java 属性名完全一致（如 ``crosstime``），映射同样成立。
"""
from __future__ import annotations

import dataclasses
import re
from typing import Any, Callable

# 类 → {Java 属性名或字段名: 实际字段名}
_FIELD_MAP_CACHE: dict[type, dict[str, str]] = {}

_ACRONYM_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    """Java 属性名 → Python 字段名（carNo → car_no，URL → url）。"""
    intermediate = _ACRONYM_RE.sub(r"\1_\2", name)
    return _CAMEL_RE.sub(r"\1_\2", intermediate).lower()


def snake_to_camel(name: str) -> str:
    """Python 字段名 → Java 属性名（car_no → carNo）。"""
    parts = name.split("_")
    if len(parts) == 1:
        return name
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _field_map(clazz: type) -> dict[str, str]:
    """构建并缓存 Java 属性名 → 字段名 的映射。"""
    cached = _FIELD_MAP_CACHE.get(clazz)
    if cached is not None:
        return cached

    mapping: dict[str, str] = {}
    if dataclasses.is_dataclass(clazz):
        for field_info in dataclasses.fields(clazz):
            mapping[field_info.name] = field_info.name
            # getCarNo/setCarNo → car_no
            mapping[snake_to_camel(field_info.name)] = field_info.name
            # 若字段本身就是 camelCase，再补一个 camel_to_snake 的键
            mapping[camel_to_snake(field_info.name)] = field_info.name
    else:
        # 非 dataclass（如普通类）时退化为 __annotations__ 中已有的属性名
        for name in getattr(clazz, "__annotations__", {}):
            mapping[name] = name
            mapping[snake_to_camel(name)] = name
            mapping[camel_to_snake(name)] = name

    _FIELD_MAP_CACHE[clazz] = mapping
    return mapping


def _decapitalize(name: str) -> str:
    """``getCarNo`` → ``CarNo`` → ``carNo``。

    【Java→Python】JavaBeans 规范：若前两个字符都是大写则保持不变（如 ``getURL`` → ``URL``），
    这里按同一规则处理后交给 camel_to_snake。
    """
    if len(name) >= 2 and name[0].isupper() and name[1].isupper():
        return name
    if len(name) == 1:
        return name.lower()
    return name[0].lower() + name[1:]


def _resolve_field(clazz: type, java_name: str) -> str | None:
    """把 Java 属性名解析成实际字段名。

    【Java→Python】首字母之外的缩写无法从 snake_case 反推：字段 ``gantry_capture_bo``
    对应 Java 属性 ``gantryCaptureBO``（getter ``getGantryCaptureBO``），而
    ``snake_to_camel`` 只能得到 ``gantryCaptureBo``。因此先精确匹配，
    再退化为“忽略大小写”匹配（缩写、URL 等命名差异都能命中）。
    """
    mapping = _field_map(clazz)
    target = mapping.get(java_name)
    if target is not None:
        return target
    lowered = java_name.lower()
    for key, value in mapping.items():
        if key.lower() == lowered:
            return value
    return None


class JavaBean:
    """Java Bean 访问器兼容层（供所有 Lombok @Data 实体继承）。"""

    def __getattr__(self, item: str) -> Any:
        # getXxx() / isXxx()
        if item.startswith("get") and len(item) > 3:
            target = _resolve_field(type(self), _decapitalize(item[3:]))
            if target is not None:
                return _make_getter(self, target)
        if item.startswith("is") and len(item) > 2:
            target = _resolve_field(type(self), _decapitalize(item[2:]))
            if target is not None:
                return _make_getter(self, target)
        # setXxx(value) → 支持链式（返回 self）
        if item.startswith("set") and len(item) > 3:
            target = _resolve_field(type(self), _decapitalize(item[3:]))
            if target is not None:
                return _make_setter(self, target)

        if item == "getClass":
            return lambda: type(self)
        if item == "toString":
            return lambda: _to_string(self)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")


def _make_getter(instance: JavaBean, field_name: str) -> Callable[[], Any]:
    def getter() -> Any:
        return getattr(instance, field_name)
    return getter


def _make_setter(instance: JavaBean, field_name: str) -> Callable[[Any], JavaBean]:
    def setter(value: Any) -> JavaBean:
        setattr(instance, field_name, value)
        # @Accessors(chain = true) 的语义：return this
        return instance
    return setter


def _to_string(instance: Any) -> str:
    """等价于 Lombok @Data 生成的 toString()：类名(field=value, ...)。"""
    if dataclasses.is_dataclass(instance):
        parts = [f"{field_info.name}={getattr(instance, field_info.name)!r}"
                 for field_info in dataclasses.fields(instance)]
        return f"{type(instance).__name__}({', '.join(parts)})"
    return repr(instance)
