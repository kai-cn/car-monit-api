# -*- coding: utf-8 -*-
"""org.elasticsearch.client.indices.CreateIndexResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.client.indices.CreateIndexResponse``。
本工程用法（EsIndexManageService）：
    CreateIndexResponse resp = esClient.indices().create(createReq, RequestOptions.DEFAULT);
    log.info("... acknowledged={}", resp.isAcknowledged());

【Java→Python 关键差异】
1) Java 的 ``CreateIndexResponse`` 继承 ``AcknowledgedResponse``，只有
   ``isAcknowledged()`` 与 ``index()`` 两个有效方法；替身同样继承。
2) Java 的 ``isAcknowledged()`` 返回 boolean；Python 保持同名方法。
"""

from __future__ import annotations

from org.elasticsearch.action.support.master.AcknowledgedResponse import (
    AcknowledgedResponse,
)

__all__ = ["CreateIndexResponse"]


class CreateIndexResponse(AcknowledgedResponse):
    """``CreateIndexResponse`` 的替身（acknowledged + index）。"""

    def __init__(self, index: str, acknowledged: bool = True) -> None:
        super().__init__(acknowledged)
        self._index = index

    def index(self) -> str:
        """对应 ``index()``：新建的索引名。"""
        return self._index

    def __repr__(self) -> str:
        return "CreateIndexResponse(index=%r, acknowledged=%s)" % (
            self._index, self.isAcknowledged())
