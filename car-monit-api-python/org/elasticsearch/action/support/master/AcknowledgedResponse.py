# -*- coding: utf-8 -*-
"""org.elasticsearch.action.support.master.AcknowledgedResponse

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.action.support.master.AcknowledgedResponse``。
本工程用法（EsIndexManageService.dropIndex / addAlias）：
    AcknowledgedResponse resp = esClient.indices().delete(deleteReq, RequestOptions.DEFAULT);
    return resp.isAcknowledged();

【Java→Python 关键差异】
1) Java 的 ``AcknowledgedResponse`` 是**抽象基类**，``CreateIndexResponse`` /
   ``DeleteIndexResponse`` / ``PutMappingResponse`` 都继承它；
   Python 替身同样作为基类，保存 ``_acknowledged`` 标志。
2) Java 的 ``isAcknowledged()`` 由字段 ``acknowledged`` 派生；
   替身用同名方法暴露，语义一致。
"""

from __future__ import annotations

__all__ = ["AcknowledgedResponse"]


class AcknowledgedResponse(object):
    """``AcknowledgedResponse`` 的替身（只承载 acknowledged 标志）。"""

    def __init__(self, acknowledged: bool = True) -> None:
        self._acknowledged = bool(acknowledged)

    def isAcknowledged(self) -> bool:
        """对应 ``isAcknowledged()``。"""
        return self._acknowledged

    def isFragment(self) -> bool:
        """对应 ``isFragment()``：响应是否为分片级片段（恒 False）。"""
        return False

    def __repr__(self) -> str:
        return "AcknowledgedResponse(acknowledged=%s)" % self._acknowledged
