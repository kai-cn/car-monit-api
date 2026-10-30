# -*- coding: utf-8 -*-
"""org.elasticsearch.xcontent.XContentType

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.xcontent.XContentType``。
本工程用法：
    new IndexRequest(ES_INDEX).id(...).source(JSON.toJSONString(data), XContentType.JSON)

【Java→Python】关键差异
1) Java 的 ``XContentType`` 是枚举；这里用**普通类 + 字符串常量**表达
   （枚举的 ``name()`` 在 Java 里返回大写名，替身让 ``XContentType.JSON``
   直接可比较/可打印为 ``"JSON"``，与 ``name()`` 的语义一致）。
2) 该值只用于告诉 HTTP 层“请求体是 JSON”，替身不做编码转换。
"""

__all__ = ["XContentType"]


class XContentType(object):
    """ES 内容类型常量（``JSON`` / ``SMILE`` / ``CBOR`` ...）。

    【Java→Python】Java 的 ``XContentType.JSON`` 是枚举实例，其 ``name()`` 为 ``"JSON"``；
    替身直接把它定义为字符串常量 ``"JSON"``，因此 ````XContentType.JSON.name()`` 的写法
    需要改写成 ``XContentType.JSON``（本工程只把它传给 ``IndexRequest.source``，不取 name）。
    """

    JSON = "JSON"
    SMILE = "SMILE"
    CBOR = "CBOR"
    YAML = "YAML"

    #: ``XContentType.JSON.mediaTypeWithoutParameters()`` 的返回值
    MEDIA_TYPE_JSON = "application/json"
