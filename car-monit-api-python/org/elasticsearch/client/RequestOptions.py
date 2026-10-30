# -*- coding: utf-8 -*-
"""org.elasticsearch.client.RequestOptions

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.client.RequestOptions``。
本工程用法：
    esClient.index(request, RequestOptions.DEFAULT);
    esClient.search(searchRequest, RequestOptions.DEFAULT);
    client.ping(RequestOptions.DEFAULT);

【Java→Python】关键差异
1) Java 的 ``RequestOptions`` 是**不可变值对象**，``DEFAULT`` 是静态单例常量；
   Python 用模块级单例 + 类属性 ``DEFAULT`` 表达，调用写法完全一致。
2) 真实对象还携带请求头、超时、WarningsHandler 等；本工程只用默认值，
   替身仅保留 ``DEFAULT`` 与几个常见选项的 getter，不参与任何网络行为。
"""

from __future__ import annotations

from typing import List, Optional

__all__ = ["RequestOptions"]


class RequestOptions(object):
    """``RequestOptions`` 的替身（只承载“默认选项”语义）。"""

    def __init__(self, headers: Optional[List[str]] = None) -> None:
        self._headers = list(headers or [])

    # Java 的 DEFAULT 是 public static final RequestOptions DEFAULT
    DEFAULT: "RequestOptions" = None  # 在文件末尾赋值，见下

    def getHeaders(self) -> List[str]:
        return list(self._headers)

    def __repr__(self) -> str:
        return "RequestOptions.DEFAULT" if self is RequestOptions.DEFAULT \
            else "RequestOptions(headers=%r)" % self._headers


# 模块加载完成后创建单例（避免在类体内引用自身构造器）
RequestOptions.DEFAULT = RequestOptions()
