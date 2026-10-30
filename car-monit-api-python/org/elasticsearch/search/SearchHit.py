# -*- coding: utf-8 -*-
"""org.elasticsearch.search.SearchHit

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：``org.elasticsearch.search.SearchHit``。
本工程用法（EsQueryService.parseEsResponse）：
    JSON.parseObject(hit.getSourceAsString(), OdsRtSzdnSnapshotFlowAddcode.class)

【Java→Python】关键差异
1) Java 的 ``getSourceAsString()`` 返回 ``_source`` 的 JSON 文本；
   替身在索引时保存的就是 ``JSON.toJSONString(data)`` 的原文，原样返回，
   保证 ``JSON.parseObject`` 解析路径与 Java 完全一致。
2) ``getSourceAsMap()`` 在 Java 里返回 ``Map<String,Object>``；
   Python 直接返回 ``dict``（3.7+ 保序）。
3) ``getScore()`` 在 Java 里是命中得分（未指定排序时为 float）；
   替身不做相关性打分，统一返回 ``1.0``。
"""

from __future__ import annotations

import json
from typing import Any, Dict

__all__ = ["SearchHit"]


class SearchHit(object):
    """``SearchHit`` 的替身（id + 原始 JSON 文本）。"""

    def __init__(self, index: str, doc_id: str, source: str,
                 score: float = 1.0) -> None:
        self._index = index
        self._id = doc_id
        self._source = source
        self._score = score

    # ------------------------------------------------------------------ getter
    def getIndex(self) -> str:
        return self._index

    def getId(self) -> str:
        return self._id

    def getSourceAsString(self) -> str:
        return self._source

    def getSourceAsMap(self) -> Dict[str, Any]:
        return json.loads(self._source) if self._source else {}

    def getScore(self) -> float:
        return self._score

    def __repr__(self) -> str:
        return "SearchHit(index=%r, id=%r)" % (self._index, self._id)
