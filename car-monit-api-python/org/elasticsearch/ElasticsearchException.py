# -*- coding: utf-8 -*-
"""org.elasticsearch.ElasticsearchException / ElasticsearchStatusException

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.ElasticsearchException``（运行时异常）与其子类
``org.elasticsearch.ElasticsearchStatusException``（REST 层对非 2xx 响应的封装）。

【Java→Python】为什么需要这个替身
``RestHighLevelClient.search()`` 在索引不存在时**不会**返回空结果，而是抛异常——
Java 侧上游代码正是靠这个异常做降级/报错：

    UnifiedQueryService.query()      → catch (Exception e) → 降级查 MySQL
    LargeScaleQueryService.aggregationStats() → catch → throw new RuntimeException("统计查询异常：" + e.getMessage())

如果替身悄悄返回空结果，降级分支永远不会触发，接口输出就和 Java 不一致
（实测：``/api/v1/large/snapshot`` Python 返回 0 条而 Java 返回 10 条）。

``getMessage()`` 的格式与真实 ES 客户端完全一致（实测自 ES 7.15.2 与 Java 进程）：

    Elasticsearch exception [type=index_not_found_exception, reason=no such index [snapshot_flow]]

真实 ES 对缺失索引的响应体（``POST /snapshot_flow/_search``）为 HTTP 404：
    {"error":{"type":"index_not_found_exception",
              "reason":"no such index [snapshot_flow]", ...}, "status":404}
"""
from __future__ import annotations

__all__ = [
    "ElasticsearchException",
    "ElasticsearchStatusException",
    "index_not_found_exception",
]


class ElasticsearchException(RuntimeError):
    """``org.elasticsearch.ElasticsearchException`` 的替身。

    Java 的 ``getMessage()`` 不是简单的 reason，而是
    ``Elasticsearch exception [type=<type>, reason=<reason>]``；
    业务代码把 ``e.getMessage()`` 直接拼进响应体，所以这里必须逐字对齐。
    """

    def __init__(self, message: str = "", type_: str = "", reason: str = "") -> None:
        self.type_ = type_
        self.reason = reason
        super().__init__(message)

    def getMessage(self) -> str:
        """Java: ``getMessage()``。"""
        return str(self)

    def getExceptionName(self) -> str:
        """Java: ``getExceptionName()``（序列化用的短名）。"""
        return type(self).__name__


class ElasticsearchStatusException(ElasticsearchException):
    """``org.elasticsearch.ElasticsearchStatusException`` 的替身（带 HTTP 状态码）。"""

    def __init__(self, message: str, status: int, type_: str = "", reason: str = "") -> None:
        self.status = status
        super().__init__(message, type_=type_, reason=reason)


def index_not_found_exception(index: str) -> ElasticsearchStatusException:
    """构造与真实 ES 客户端逐字一致的“索引不存在”异常。

    :param index: 请求里写到的不存在的索引名
    """
    reason = "no such index [%s]" % index
    message = "Elasticsearch exception [type=index_not_found_exception, reason=%s]" % reason
    return ElasticsearchStatusException(
        message, 404, type_="index_not_found_exception", reason=reason)
