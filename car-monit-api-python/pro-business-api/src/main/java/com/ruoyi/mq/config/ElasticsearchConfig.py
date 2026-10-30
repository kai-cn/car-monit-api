# -*- coding: utf-8 -*-
"""com.ruoyi.mq.config.ElasticsearchConfig

源文件：pro-business-api/src/main/java/com/ruoyi/mq/config/ElasticsearchConfig.java

【Java→Python】关键差异
1) Lombok 的 ``@Data``（getter/setter/toString/equals）→ ``@dataclass`` +
   手写 Java 风格 getter/setter（本工程用 ``@Data`` 只为生成 getter，
   真正被读取的是字段本身，这里仍保留 getXxx 以对齐原 API）。
2) 类上同时有 ``@Configuration`` 与 ``@ConfigurationProperties(prefix="elasticsearch")``：
   - ``@ConfigurationProperties``：Spring Boot 把 ``elasticsearch.host`` 等外部配置
     绑定到字段；Python 无容器，用 ``from_properties(props)`` 模拟松散绑定
     （支持 kebab-case / camelCase 两种 key）。
   - ``@Configuration`` + ``@Bean``：``restHighLevelClient()`` 是工厂方法，
     Spring 保证**单例**；Python 侧不注册容器，由调用方自行缓存实例。
3) ``@Value`` / 配置文件默认值：Java 字段自带默认值（host=localhost、port=9200 …），
   ``from_properties`` 缺省时保留这些默认值，语义与 Spring 一致。
4) ``log.info("[ES配置] 初始化ES客户端, host={}, port={}, scheme={}", ...)``
   → Python ``%s`` 占位符；SLF4J 的 ``{}`` 与 ``%s`` 一一对应。
5) ``RestClient.builder(...).setRequestConfigCallback(b -> b.setConnectTimeout(...)
   .setSocketTimeout(...))`` 是一段**返回 Builder 的 lambda**；Python lambda
   同样返回链式结果（若不 return，替身会回退到原 builder，见 RestClient.py）。
6) ``e.getMessage()`` → ``str(e)``（Python 异常没有 getMessage()）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient

log = logging.getLogger(__name__)


@dataclass
class ElasticsearchConfig:
    """ES 连接配置 + RestHighLevelClient 工厂（@Data @Configuration @ConfigurationProperties）。"""

    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None
    connection_timeout: int = 30000
    socket_timeout: int = 30000

    # ------------------------------------------------------------------ getter/setter
    # 【Java→Python】@Data 生成的 getter 名是 getHost()/getPort()/...；
    # 字段本身在 Python 里可直接访问（config.host），两种写法都可用。
    def getHost(self) -> str:
        return self.host

    def setHost(self, value: str) -> None:
        self.host = value

    def getPort(self) -> int:
        return self.port

    def setPort(self, value: int) -> None:
        self.port = int(value)

    def getScheme(self) -> str:
        return self.scheme

    def setScheme(self, value: str) -> None:
        self.scheme = value

    def getUsername(self) -> Optional[str]:
        return self.username

    def setUsername(self, value: Optional[str]) -> None:
        self.username = value

    def getPassword(self) -> Optional[str]:
        return self.password

    def setPassword(self, value: Optional[str]) -> None:
        self.password = value

    def getConnectionTimeout(self) -> int:
        return self.connection_timeout

    def setConnectionTimeout(self, value: int) -> None:
        self.connection_timeout = int(value)

    def getSocketTimeout(self) -> int:
        return self.socket_timeout

    def setSocketTimeout(self, value: int) -> None:
        self.socket_timeout = int(value)

    # ------------------------------------------------------------------ @Bean
    def restHighLevelClient(self) -> RestHighLevelClient:
        """对应 ``@Bean public RestHighLevelClient restHighLevelClient()``。"""
        log.info("[ES配置] 初始化ES客户端, host=%s, port=%s, scheme=%s",
                 self.host, self.port, self.scheme)

        client = RestHighLevelClient(
            RestClient.builder(HttpHost(self.host, self.port, self.scheme))
            .setRequestConfigCallback(
                lambda requestConfigBuilder: requestConfigBuilder
                .setConnectTimeout(self.connection_timeout)
                .setSocketTimeout(self.socket_timeout))
        )

        # 测试连接：ping 失败只 warn，不影响 Bean 创建（与 Java 完全一致）
        try:
            client.ping(RequestOptions.DEFAULT)
            log.info("[ES配置] ES客户端连接成功")
        except Exception as e:  # noqa: BLE001 - Java 捕获 Exception
            log.warning("[ES配置] ES连接测试失败, error=%s", str(e))

        return client

    # ------------------------------------------------------------------ 配置绑定
    @staticmethod
    def from_properties(props: Any,
                        prefix: str = "elasticsearch") -> "ElasticsearchConfig":
        """模拟 Spring Boot 的松散绑定（kebab-case / camelCase 均可）。

        【Java→Python】Spring 的 Binder 会忽略大小写、把 ``-`` 与驼峰视为等价；
        这里显式列举候选 key，取第一个命中的值。缺失时使用字段默认值。
        """
        def lookup(*names: str) -> Any:
            for name in names:
                full = "%s.%s" % (prefix, name)
                if full in props:
                    return props[full]
            return None

        config = ElasticsearchConfig()
        value = lookup("host")
        if value is not None:
            config.host = str(value)
        value = lookup("port")
        if value is not None:
            config.port = int(value)
        value = lookup("scheme")
        if value is not None:
            config.scheme = str(value)
        value = lookup("username")
        if value is not None:
            config.username = str(value)
        value = lookup("password")
        if value is not None:
            config.password = str(value)
        value = lookup("connection-timeout", "connectionTimeout", "CONNECTION_TIMEOUT")
        if value is not None:
            config.connection_timeout = int(value)
        value = lookup("socket-timeout", "socketTimeout", "SOCKET_TIMEOUT")
        if value is not None:
            config.socket_timeout = int(value)
        return config
