# -*- coding: utf-8 -*-
"""org.apache.http.client.config.RequestConfig

【无 Java 源文件：框架类替身】
Java 侧来自 Apache HttpComponents：``org.apache.http.client.config.RequestConfig``。
本工程不直接 import 它，只在 ``ElasticsearchConfig`` 的 lambda 中出现：
    .setRequestConfigCallback(requestConfigBuilder ->
            requestConfigBuilder.setConnectTimeout(connectionTimeout)
                                .setSocketTimeout(socketTimeout))

【Java→Python】关键差异
1) Java 的 ``setRequestConfigCallback`` 接收 ``RestClientBuilder.RequestConfigCallback``
   （函数式接口：``RequestConfig.Builder customizeRequestConfig(RequestConfig.Builder b)``）。
   Python 的 lambda 没有类型约束，替身只是把 ``RequestConfig.Builder`` 实例交给回调，
   **并使用回调的返回值**（Java 强制要求返回；Python 若不写 return 则拿到 None，
   此时回退到传入的那个 builder，两种写法都能工作）。
2) Java 的 ``Builder`` 是 ``RequestConfig`` 的静态内部类；Python 用嵌套类
   ``RequestConfig.Builder`` 保持 ``.Builder()`` 的写法不变。
3) ``-1`` 表示“未设置”，与 Java 的默认值一致（HttpClient 会回落到底层默认值）。
"""

from __future__ import annotations

__all__ = ["RequestConfig"]


class RequestConfig(object):
    """``RequestConfig`` 的替身；只保留三个超时配置项。"""

    class Builder(object):
        """对应 ``RequestConfig.Builder``（链式 setter）。"""

        def __init__(self) -> None:
            self.connectTimeout = -1
            self.socketTimeout = -1
            self.connectionRequestTimeout = -1

        def setConnectTimeout(self, connect_timeout: int) -> "RequestConfig.Builder":
            self.connectTimeout = connect_timeout
            return self

        def setSocketTimeout(self, socket_timeout: int) -> "RequestConfig.Builder":
            self.socketTimeout = socket_timeout
            return self

        def setConnectionRequestTimeout(self,
                                        timeout: int) -> "RequestConfig.Builder":
            self.connectionRequestTimeout = timeout
            return self

        def build(self) -> "RequestConfig":
            return RequestConfig(self.connectTimeout, self.socketTimeout,
                                 self.connectionRequestTimeout)

    DEFAULT = None  # 在类定义结束后赋值为单例，见文件末尾

    def __init__(self, connect_timeout: int = -1, socket_timeout: int = -1,
                 connection_request_timeout: int = -1) -> None:
        self.connectTimeout = connect_timeout
        self.socketTimeout = socket_timeout
        self.connectionRequestTimeout = connection_request_timeout

    # ------------------------------------------------------------------ getter
    def getConnectTimeout(self) -> int:
        return self.connectTimeout

    def getSocketTimeout(self) -> int:
        return self.socketTimeout

    def getConnectionRequestTimeout(self) -> int:
        return self.connectionRequestTimeout

    def __repr__(self) -> str:
        return ("RequestConfig(connectTimeout=%d, socketTimeout=%d, "
                "connectionRequestTimeout=%d)" %
                (self.connectTimeout, self.socketTimeout,
                 self.connectionRequestTimeout))


# Java: RequestConfig.DEFAULT 是一个全默认值的静态常量
RequestConfig.DEFAULT = RequestConfig()
