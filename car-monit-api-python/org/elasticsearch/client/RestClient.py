# -*- coding: utf-8 -*-
"""org.elasticsearch.client.RestClient

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch-rest-client jar：
``org.elasticsearch.client.RestClient`` / ``RestClientBuilder``。
本工程用法（ElasticsearchConfig）：
    new RestHighLevelClient(
            RestClient.builder(new HttpHost(host, port, scheme))
                    .setRequestConfigCallback(b -> b.setConnectTimeout(...)
                                                    .setSocketTimeout(...)));

【Java→Python】关键差异
1) Java 的 ``RestClient.builder(HttpHost... hosts)`` 是**静态工厂 + 可变参数**；
   Python 写成 ``@staticmethod def builder(*hosts)``，调用写法一致。
2) Java 的 Builder 是**独立类** ``RestClientBuilder``（同包），链式方法返回 ``this``；
   替身保持同样结构，``build()`` 才真正创建 ``RestClient``。
   注意：Java 里 ``RestClient.builder()`` 返回的是 ``RestClientBuilder`` 而不是 RestClient。
3) 真实 RestClient 持有 Apache HttpClient 连接池并做负载均衡；替身不建连接，
   只保存 ``hosts`` 与 ``requestConfig``，供 ``RestHighLevelClient`` 读取/断言。
4) ``close()`` 在 Java 里是 ``Closeable`` 语义（幂等）；替身只置标志位。

【optimization 包补充】``EsIndexManageService`` 的 ILM 管理走**低层 REST**：
    Response response = esClient.getLowLevelClient().performRequest(request);
它们需要真实的 HTTP 层，而替身没有网络，因此本替身把 ILM 策略与
``_settings`` 快照存在**类属性**里（模拟集群状态，跟 RestClient 无关）：
    - ``PUT  /_ilm/policy/{name}``  → 写入 ``_ILM_POLICIES[name]``，返回 201
    - ``GET  /_ilm/policy/{name}``  → 存在返回 200 + JSON，否则 404
    - ``PUT  /{index}/_settings``   → 记录到 ``_INDEX_SETTINGS``，返回 200
其余路径统一返回 200 与空 JSON，保证不因“未知端点”中断业务。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from org.apache.http.HttpHost import HttpHost
from org.apache.http.client.config.RequestConfig import RequestConfig
from org.elasticsearch.client.Request import Request
from org.elasticsearch.client.Response import Response, StatusLine, HttpEntity

__all__ = ["RestClient", "RestClientBuilder"]

#: ``GET/PUT /_ilm/policy/{name}`` 的路径匹配
_ILM_POLICY_PATH = re.compile(r"^/_ilm/policy/([^/?]+)")
#: ``PUT /{index}/_settings`` 的路径匹配
_INDEX_SETTINGS_PATH = re.compile(r"^/([^/?]+)/_settings")


class RestClient(object):
    """``RestClient`` 的替身：保存目标节点与请求配置。"""

    #: 模拟集群的 ILM 策略：policy_name -> policy JSON 原文
    _ILM_POLICIES: Dict[str, str] = {}
    #: 模拟已写入的索引 settings：index -> settings JSON 原文
    _INDEX_SETTINGS: Dict[str, str] = {}

    def __init__(self, hosts: List[HttpHost],
                 request_config: Optional[RequestConfig] = None) -> None:
        self.hosts = list(hosts)
        self.requestConfig = request_config or RequestConfig.DEFAULT
        self.closed = False

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def builder(*hosts: HttpHost) -> "RestClientBuilder":
        """对应 ``RestClient.builder(HttpHost... hosts)``。"""
        return RestClientBuilder(*hosts)

    # ------------------------------------------------------------------ 低层 REST 请求
    def performRequest(self, request: Request) -> Response:
        """对应 ``Response performRequest(Request request)``。

        【Java→Python】真实实现会发 HTTP；替身只处理 EsIndexManageService
        用到的三个 ILM 相关端点（见模块注释），其余端点返回 200 空 JSON。
        """
        method = (request.getMethod() or "GET").upper()
        endpoint = request.getEndpoint() or ""
        body = request.getJsonEntity()

        matched = _ILM_POLICY_PATH.match(endpoint)
        if matched:
            policy_name = matched.group(1)
            if method == "GET":
                if policy_name in RestClient._ILM_POLICIES:
                    # 真实 ES 的响应体形如 {"<policy>": {"version":..,"policy":{..}}}
                    payload = {policy_name: json.loads(RestClient._ILM_POLICIES[policy_name])}
                    return Response(StatusLine(200),
                                    HttpEntity(json.dumps(payload, ensure_ascii=False)))
                # 404 对应“策略不存在”，让 ilmPolicyExists 返回 False
                return Response(StatusLine(404),
                                HttpEntity('{"error":"resource_not_found_exception"}'))
            if method in ("PUT", "POST"):
                RestClient._ILM_POLICIES[policy_name] = body or "{}"
                return Response(StatusLine(201), HttpEntity('{"acknowledged":true}'))

        matched = _INDEX_SETTINGS_PATH.match(endpoint)
        if matched and method in ("PUT", "POST"):
            RestClient._INDEX_SETTINGS[matched.group(1)] = body or "{}"
            return Response(StatusLine(200), HttpEntity('{"acknowledged":true}'))

        return Response(StatusLine(200), HttpEntity("{}"))

    # ------------------------------------------------------------------ 测试辅助
    @classmethod
    def resetIlmPolicies(cls) -> None:
        """清空模拟的 ILM 策略与 settings（Java 无此方法，仅供测试隔离）。"""
        cls._ILM_POLICIES.clear()
        cls._INDEX_SETTINGS.clear()

    # ------------------------------------------------------------------ 生命周期
    def close(self) -> None:
        """对应 ``close()``（幂等）。"""
        self.closed = True

    # ------------------------------------------------------------------ 测试辅助
    def getHosts(self) -> List[HttpHost]:
        """Java 没有公开此方法；替身用于断言“配置被正确传递”。"""
        return list(self.hosts)

    def __repr__(self) -> str:
        return "RestClient(hosts=%r, requestConfig=%r)" % (self.hosts,
                                                           self.requestConfig)


class RestClientBuilder(object):
    """``RestClientBuilder`` 的替身（链式配置，``build()`` 产出 RestClient）。"""

    def __init__(self, *hosts: HttpHost) -> None:
        self._hosts = list(hosts)
        self._request_config_callback: Optional[Any] = None
        self._max_retry_timeout_millis = 30000

    # ------------------------------------------------------------------ 配置
    def setRequestConfigCallback(self, callback: Any) -> "RestClientBuilder":
        """对应 ``setRequestConfigCallback(RequestConfigCallback)``。

        Java 的函数式接口签名是::

            RequestConfig.Builder customizeRequestConfig(RequestConfig.Builder b)

        因此回调**必须有返回值**；Python lambda 若不写 return 会得到 None，
        这里对 None 做兜底（回退到传入的 builder），两种写法都能工作。
        """
        self._request_config_callback = callback
        return self

    def setMaxRetryTimeoutMillis(self, millis: int) -> "RestClientBuilder":
        self._max_retry_timeout_millis = millis
        return self

    # ------------------------------------------------------------------ 构建
    def build(self) -> RestClient:
        config = None
        if self._request_config_callback is not None:
            builder = RequestConfig.Builder()
            customized = self._request_config_callback(builder)
            # Java 强制返回 Builder；Python 若漏写 return，则使用原 builder
            builder = customized if customized is not None else builder
            config = builder.build()
        return RestClient(self._hosts, config)

    def __repr__(self) -> str:
        return "RestClientBuilder(hosts=%r)" % (self._hosts,)
