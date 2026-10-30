# -*- coding: utf-8 -*-
"""com.fasterxml.jackson.databind.JsonNode

【无 Java 源文件：框架类替身】
Java 侧来自 jackson-databind jar：``com.fasterxml.jackson.databind.JsonNode``。

【Java→Python 为什么单独建一个文件】
Java 的 ``JsonNode`` 与 ``ObjectMapper`` 同属 ``com.fasterxml.jackson.databind``
包但分属两个源文件，业务代码 `import com.fasterxml.jackson.databind.JsonNode;`
单独引用类型。Python 模块与文件一一对应，因此这里提供独立模块路径，
实现体复用 ``ObjectMapper.py`` 中的同一个 ``JsonNode`` 类。

    Java : import com.fasterxml.jackson.databind.JsonNode;
    Py   : from com.fasterxml.jackson.databind.JsonNode import JsonNode
"""

from __future__ import annotations

from com.fasterxml.jackson.databind.ObjectMapper import JsonNode

__all__ = ["JsonNode"]
