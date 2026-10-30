# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.OrikaMapperConfig

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/OrikaMapperConfig.java

【Java→Python】整体说明
1) Orika 是 Java 的 Bean 拷贝/映射框架，通过 ``Mappers.getMapper()`` 或注入
   ``MapperFacade`` 做 Entity ↔ DTO 转换。Python 无对应三方库，
   这里用**最小反射映射器**（按同名字段逐个 copy）替代，并保留
   ``classMap(a, b).byDefault().customize(mapper).register()`` 的链式 API，
   使原 Java 的注册代码可以逐行照搬。
2) ``@Component`` + ``@Autowired(required=false) List<Mapper>``：Spring 会把容器里
   所有 Mapper/Converter 实现注入进来。Python 无自动注入，
   改为构造参数 ``mappers`` / ``converters``（默认空列表），
   并在 ``register_bean`` 时由启动代码显式传入。
3) ``ConfigurableMapper.configure(MapperFactory)`` 是模板方法，
   由父类构造函数触发一次；Python 在 ``__init__`` 末尾调用 ``configure`` 以保持触发时机一致。
4) ``super.configure(factory)`` 在 Orika 里注册内置映射；Python 侧父类无内置映射，空实现。
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


class Mapper:
    """``ma.glasnost.orika.Mapper<A, B>`` 的替身。

    子类只需提供 ``map_a_to_b`` / ``map_b_to_a``（Java 是 ``mapAtoB/mapBtoA``）。
    """

    def getAType(self) -> Any:
        raise NotImplementedError

    def getBType(self) -> Any:
        raise NotImplementedError

    def mapAtoB(self, a: Any, b: Any, context: Optional[Any] = None) -> None:
        # Python 无“输出参数”惯用法，Java 的 mapAtoB(a, b, ctx) 语义按属性拷贝实现
        _copy_attributes(a, b)

    def mapBtoA(self, b: Any, a: Any, context: Optional[Any] = None) -> None:
        _copy_attributes(b, a)


class Converter:
    """``ma.glasnost.orika.Converter<S, D>`` 的替身。"""

    def getSourceType(self) -> Any:
        raise NotImplementedError

    def getDestinationType(self) -> Any:
        raise NotImplementedError

    def convert(self, source: Any, destination_type: Optional[type] = None) -> Any:
        raise NotImplementedError


def _attributes_of(obj: Any) -> dict[str, Any]:
    """取对象的可拷贝属性：dataclass 用 fields，普通对象用 __dict__。"""
    if obj is None:
        return {}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {}


def _copy_attributes(source: Any, target: Any) -> None:
    """等价于 Orika ``byDefault()``：按同名字段逐个赋值，类型不同则跳过。"""
    source_attrs = _attributes_of(source)
    for name, value in source_attrs.items():
        if hasattr(target, name):
            try:
                setattr(target, name, value)
            except AttributeError:
                # 只读属性（如 property 无 setter）→ 跳过，对应 Orika 的不可映射字段告警
                log.debug("skip read-only property %s", name)


class _ClassMapBuilder:
    """``factory.classMap(a, b).byDefault().customize(mapper).register()`` 的链式替身。"""

    def __init__(self, factory: "MapperFactory", a_type: Any, b_type: Any) -> None:
        self.factory = factory
        self.a_type = a_type
        self.b_type = b_type
        self._by_default = False
        self._custom_mapper: Optional[Mapper] = None

    def byDefault(self) -> "_ClassMapBuilder":
        self._by_default = True
        return self

    def customize(self, mapper: Mapper) -> "_ClassMapBuilder":
        self._custom_mapper = mapper
        return self

    def register(self) -> "_ClassMapBuilder":
        self.factory.register(self.a_type, self.b_type, self._by_default, self._custom_mapper)
        return self


class _ConverterFactory:
    """``factory.getConverterFactory()`` 的替身。"""

    def __init__(self) -> None:
        self.converters: list[Converter] = []

    def registerConverter(self, converter: Converter) -> None:
        self.converters.append(converter)


class MapperFactory:
    """``ma.glasnost.orika.MapperFactory`` 的替身：保存映射表并提供 map 能力。"""

    def __init__(self) -> None:
        # 键为 (a_type, b_type)，值为 (by_default, custom_mapper)
        self.class_maps: dict[tuple[Any, Any], tuple[bool, Optional[Mapper]]] = {}
        self._converter_factory = _ConverterFactory()

    def classMap(self, a_type: Any, b_type: Any) -> _ClassMapBuilder:
        return _ClassMapBuilder(self, a_type, b_type)

    def getConverterFactory(self) -> _ConverterFactory:
        return self._converter_factory

    def register(self, a_type: Any, b_type: Any, by_default: bool,
                 custom_mapper: Optional[Mapper]) -> None:
        self.class_maps[(a_type, b_type)] = (by_default, custom_mapper)

    def getMapper(self, a_type: Any, b_type: Any) -> Optional[Mapper]:
        entry = self.class_maps.get((a_type, b_type))
        return entry[1] if entry else None

    def map(self, source: Any, destination_type: type, source_type: Optional[type] = None) -> Any:
        """对应 ``MapperFacade.map(source, destinationClass)``。"""
        destination = _new_instance(destination_type)
        mapper = self.getMapper(type(source) if source_type is None else source_type,
                                destination_type)
        if mapper is not None:
            mapper.mapAtoB(source, destination, None)
        else:
            _copy_attributes(source, destination)
        return destination

    def map_list(self, sources: list[Any], destination_type: type) -> list[Any]:
        """对应 ``MapperFacade.mapAsList(Iterable, Class)``。"""
        return [self.map(item, destination_type) for item in sources]


def _new_instance(clazz: type) -> Any:
    """等价于 ``clazz.newInstance()``：优先无参构造，dataclass 用全默认构造。"""
    try:
        return clazz()
    except TypeError:
        if dataclasses.is_dataclass(clazz):
            kwargs = {}
            for field in dataclasses.fields(clazz):
                # 无默认值字段给 None（Java 反射 newInstance 也不会填值）
                if field.default is dataclasses.MISSING and \
                        field.default_factory is dataclasses.MISSING:  # type: ignore[misc]
                    kwargs[field.name] = None
            return clazz(**kwargs)
        raise


class ConfigurableMapper:
    """``ma.glasnost.orika.impl.ConfigurableMapper`` 的替身（模板方法模式）。"""

    def __init__(self) -> None:
        self.factory = MapperFactory()
        # Java 父类构造 → 调用 configure(factory)，时机保持一致
        self.configure(self.factory)

    def configure(self, factory: MapperFactory) -> None:
        """父类默认实现（Orika 注册内置转换器），Python 侧空实现。"""
        return None

    # 对外便捷方法，等价于 ConfigurableMapper 暴露的 MapperFacade
    def map(self, source: Any, destination_type: type) -> Any:
        return self.factory.map(source, destination_type)

    def mapAsList(self, sources: list[Any], destination_type: type) -> list[Any]:
        return self.factory.map_list(sources, destination_type)


class OrikaMapperConfig(ConfigurableMapper):
    """实体类与 dto 转换的映射。

    【Java→Python】``@Autowired(required = false)`` 表示“容器里没有该类型的 Bean 时留 null”；
    Python 用默认空列表表达，``if mappers is not None`` 的判断原样保留。
    """

    def __init__(self, mappers: Optional[list[Mapper]] = None,
                 converters: Optional[list[Converter]] = None) -> None:
        self.mappers = mappers
        self.converters = converters
        super().__init__()

    def configure(self, factory: MapperFactory) -> None:
        super().configure(factory)
        if self.mappers is not None:
            for mapper in self.mappers:
                # 对应 Java lambda：
                # factory.classMap(mapper.getAType(), mapper.getBType()).byDefault()
                #        .customize(mapper).register()
                factory.classMap(mapper.getAType(), mapper.getBType()) \
                    .byDefault() \
                    .customize(mapper) \
                    .register()
        if self.converters is not None:
            for converter in self.converters:
                factory.getConverterFactory().registerConverter(converter)
