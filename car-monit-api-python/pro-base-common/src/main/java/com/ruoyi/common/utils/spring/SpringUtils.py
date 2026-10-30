# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.spring.SpringUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/spring/SpringUtils.java
"""
from __future__ import annotations

from typing import Any, Optional


class _Environment:
    """Spring Environment 的最小替身：保存 activeProfiles 与属性表。"""

    def __init__(self, active_profiles: Optional[list[str]] = None,
                 properties: Optional[dict[str, str]] = None) -> None:
        self._active_profiles = active_profiles or []
        self._properties = properties or {}

    def getActiveProfiles(self) -> list[str]:
        return self._active_profiles

    def getRequiredProperty(self, key: str) -> str:
        if key not in self._properties:
            # Java 抛 IllegalStateException
            raise RuntimeError(f"Property '{key}' not found")
        return self._properties[key]


class _Locale:
    def __str__(self) -> str:
        return "zh_CN"


class SpringUtils:
    """spring 工具类：方便在非 spring 管理环境中获取 bean。

    【Java→Python】
    1) Java 通过 BeanFactoryPostProcessor / ApplicationContextAware 回填静态字段；
       Python 没有容器，改用模块级注册表：由启动代码调用 ``register_bean(name, obj)``
       与 ``set_application_context(env)`` 完成“注入”。
    2) getBean(String) 与 getBean(Class<T>) 两个重载 → Python 用单方法 + 类型分派
       （传入 str 按名字取；传入 type 按类型匹配）。
    3) getAopProxy 依赖 Spring AOP 的当前代理对象；Python 无 AOP 容器，
       直接返回入参（等价于“没有代理时的自我调用”）。
    4) getActiveProfile() 返回 null 的语义 → Python 返回 None。
    """

    _beans: dict[str, Any] = {}
    _environment: Optional[_Environment] = _Environment()
    _locale: Any = _Locale()

    @staticmethod
    def register_bean(name: str, bean: Any) -> None:
        SpringUtils._beans[name] = bean

    @staticmethod
    def set_application_context(environment: Optional[_Environment]) -> None:
        SpringUtils._environment = environment

    @staticmethod
    def getLocale() -> Any:
        """等价于 LocaleContextHolder.getLocale()。"""
        return SpringUtils._locale

    @staticmethod
    def getBean(name_or_type: Any) -> Any:
        """对应 getBean(String) 与 getBean(Class<T>)。"""
        if isinstance(name_or_type, str):
            # Java: beanFactory.getBean(name) —— 不存在时抛 NoSuchBeanDefinitionException
            if name_or_type not in SpringUtils._beans:
                return None
            return SpringUtils._beans[name_or_type]
        for bean in SpringUtils._beans.values():
            if isinstance(bean, name_or_type):
                return bean
        return None

    @staticmethod
    def containsBean(name: str) -> bool:
        return name in SpringUtils._beans

    @staticmethod
    def isSingleton(name: str) -> bool:
        # Python 注册表里的对象天然都是单例
        return name in SpringUtils._beans

    @staticmethod
    def getType(name: str) -> Optional[type]:
        bean = SpringUtils._beans.get(name)
        return type(bean) if bean is not None else None

    @staticmethod
    def getAliases(name: str) -> list[str]:
        # Python 注册表没有别名机制
        return []

    @staticmethod
    def getAopProxy(invoker: Any) -> Any:
        return invoker

    @staticmethod
    def getActiveProfiles() -> list[str]:
        return SpringUtils._environment.getActiveProfiles() if SpringUtils._environment else []

    @staticmethod
    def getActiveProfile() -> Optional[str]:
        active_profiles = SpringUtils.getActiveProfiles()
        return active_profiles[0] if len(active_profiles) > 0 else None

    @staticmethod
    def getRequiredProperty(key: str) -> str:
        if SpringUtils._environment is None:
            raise RuntimeError("applicationContext is not initialized")
        return SpringUtils._environment.getRequiredProperty(key)

    @staticmethod
    def getBeanOfType(clazz: type) -> dict[str, Any]:
        return {name: bean for name, bean in SpringUtils._beans.items() if isinstance(bean, clazz)}
