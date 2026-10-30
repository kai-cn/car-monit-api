# -*- coding: utf-8 -*-
"""org.apache.flink.configuration.Configuration

【无 Java 源文件：框架类替身】
Java 侧来自 flink-core：``org.apache.flink.configuration.Configuration``。
本工程用法（VehicleTrackFlinkJob）：只作为 ``open(Configuration parameters)`` 的入参，
方法体内**从未读取**任何配置项。

【Java→Python】关键差异
1) Java 的 ``Configuration`` 是 Flink 的全局配置容器（内部是
   ``Map<String, String>`` + 类型化 setter/getter）；替身只保留
   ``setString`` / ``getString`` 与一个 ``toMap()``，够 ``open()`` 的形参使用。
2) Flink 在调用 ``open()`` 时传入的是**作业级配置的副本**；本项目不使用，
   替身由运行时传一个空实例即可。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["Configuration"]


class Configuration(object):
    """``Configuration`` 的替身（字符串 key/value 容器）。"""

    def __init__(self, entries: Optional[Dict[str, Any]] = None) -> None:
        self._entries: Dict[str, Any] = dict(entries or {})

    def setString(self, key: str, value: str) -> None:
        self._entries[key] = value

    def getString(self, key: str, default_value: Optional[str] = None) -> Optional[str]:
        value = self._entries.get(key)
        return default_value if value is None else value

    def setInteger(self, key: str, value: int) -> None:
        self._entries[key] = int(value)

    def getInteger(self, key: str, default_value: Optional[int] = None) -> Optional[int]:
        value = self._entries.get(key)
        if value is None:
            return default_value
        return int(value)

    def toMap(self) -> Dict[str, Any]:
        return dict(self._entries)

    def __repr__(self) -> str:
        return "Configuration(%r)" % (self._entries,)
