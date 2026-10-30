# -*- coding: utf-8 -*-
"""org.apache.http.HttpHost

【无 Java 源文件：框架类替身】
Java 侧来自 Apache HttpComponents：``org.apache.http.HttpHost``。
本工程只在 ``ElasticsearchConfig`` 中构造一次：
    new HttpHost(host, port, scheme)

【Java→Python】关键差异
1) Java 的可变参数 ``RestClient.builder(HttpHost... hosts)`` → Python 用 ``*hosts``。
2) Java 的字段名是 ``hostname``（全小写），getter 是 ``getHostName()``；
   替身同时提供 ``hostName`` / ``hostname`` 两个属性，避免调用方写法差异。
3) ``port`` 缺省为 ``-1``（Java 表示“按 scheme 取默认端口”），
   本工程总是显式传入，缺省值仅为对齐 Java 构造器签名。
"""

from __future__ import annotations

from typing import Any

__all__ = ["HttpHost"]


class HttpHost(object):
    """``HttpHost`` 的等价实现（仅保存 host/port/scheme 三元组）。"""

    DEFAULT_SCHEME_NAME = "http"

    def __init__(self, hostname: str, port: int = -1,
                 scheme: str = DEFAULT_SCHEME_NAME) -> None:
        self.hostname = hostname
        self.hostName = hostname  # Java 的 getHostName() 对应的字段拼写
        self.port = port
        self.schemeName = scheme

    # ------------------------------------------------------------------ getter
    def getHostName(self) -> str:
        return self.hostname

    def getPort(self) -> int:
        return self.port

    def getSchemeName(self) -> str:
        return self.schemeName

    # ------------------------------------------------------------------ 输出
    def toURI(self) -> str:
        """对应 ``toURI()``：``http://localhost:9200``（-1 端口时省略端口）。"""
        if self.port > 0:
            return "%s://%s:%d" % (self.schemeName, self.hostname, self.port)
        return "%s://%s" % (self.schemeName, self.hostname)

    def __str__(self) -> str:
        # Java 的 toString() 输出就是 scheme://host:port
        return self.toURI()

    def __repr__(self) -> str:
        return "HttpHost(%r, %r, %r)" % (self.hostname, self.port, self.schemeName)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, HttpHost):
            return NotImplemented
        return (self.hostname, self.port, self.schemeName) == \
               (other.hostname, other.port, other.schemeName)

    def __hash__(self) -> int:
        return hash((self.hostname, self.port, self.schemeName))
