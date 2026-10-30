# -*- coding: utf-8 -*-
"""org.elasticsearch.search.aggregations.bucket.terms.Terms

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：
``org.elasticsearch.search.aggregations.bucket.terms.Terms``（接口）。
本工程用法（LargeScaleQueryService.aggregationStats）：
    for (Terms.Bucket bucket : terms.getBuckets()) {
        ValueCount count = bucket.getAggregations().get("total_count");
        resultMap.put(bucket.getKeyAsString(), count.getValue());
    }

【Java→Python】关键差异
1) ``Terms.Bucket`` 在 Java 里是 ``Terms`` 的**嵌套接口**；Python 用嵌套类表达，
   访问路径 ``Terms.Bucket`` 保持不变。
2) ``getKey()`` 在 Java 返回 ``Object``（StringTerms 为 String、LongTerms 为 Long）；
   Python 直接返回原始值（str / int / float）。
   ``getKeyAsString()`` 在 Java 里由 ``formatKey`` 决定（字符串原样、数字用
   ``convertToString``、布尔为 ``"true"/"false"``）；替身按同样规则实现，
   见 :func:`_key_as_string`。
3) ``getDocCount()`` 返回 long → Python int（桶内文档数，**与 subAggregation 无关**）。
4) ``getBuckets()`` 在 Java 返回 ``List<? extends Bucket>``（不可变）；替身返回 list 副本。
5) ``getDocCountError()`` / ``getSumOtherDocCount()``（后者在 ``ParsedStringTerms``）
   本工程未使用；``getBucketByKey()`` 为方便对拍一并提供。
"""

from __future__ import annotations

from typing import Any, List, Optional

from org.elasticsearch.search.aggregations.Aggregation import Aggregation
from org.elasticsearch.search.aggregations.Aggregations import Aggregations

__all__ = ["Terms"]


def _key_as_string(key: Any) -> Optional[str]:
    """复刻 ES 的 ``formatKey``：字符串原样、布尔小写、其余 ``toString()``。"""
    if key is None:
        return None
    if isinstance(key, bool):
        return "true" if key else "false"
    return str(key)


class Terms(Aggregation):
    """``Terms`` 接口的替身（桶列表）。"""

    class Bucket(object):
        """``Terms.Bucket`` 嵌套接口的替身。"""

        def __init__(self, key: Any, doc_count: int,
                     aggregations: Optional[Aggregations] = None) -> None:
            self._key = key
            self._doc_count = int(doc_count)
            self._aggregations = aggregations if aggregations is not None else Aggregations()

        # -------------------------------------------------------------- getter
        def getKey(self) -> Any:
            """对应 ``Object getKey()``。"""
            return self._key

        def getKeyAsString(self) -> Optional[str]:
            """对应 ``String getKeyAsString()``（布尔小写，其余 str）。"""
            return _key_as_string(self._key)

        def getDocCount(self) -> int:
            """对应 ``long getDocCount()``：桶内文档数。"""
            return self._doc_count

        def getAggregations(self) -> Aggregations:
            """对应 ``Aggregations getAggregations()``。"""
            return self._aggregations

        def __repr__(self) -> str:
            return "Terms.Bucket(key=%r, docCount=%d)" % (self._key, self._doc_count)

    def __init__(self, name: str, buckets: Optional[List["Terms.Bucket"]] = None) -> None:
        super().__init__(name)
        self._buckets: List[Terms.Bucket] = list(buckets or [])

    # ------------------------------------------------------------------ getter
    def getBuckets(self) -> List["Terms.Bucket"]:
        """对应 ``List<? extends Bucket> getBuckets()``：Python 返回 list。"""
        return list(self._buckets)

    def getBucketByKey(self, key: Any) -> Optional["Terms.Bucket"]:
        """对应 ``Bucket getBucketByKey(String key)``：不存在返回 None（Java 返回 null）。"""
        key_string = _key_as_string(key)
        for bucket in self._buckets:
            if bucket.getKeyAsString() == key_string:
                return bucket
        return None

    def __len__(self) -> int:
        # Python 独有：桶数量（Java 用 getBuckets().size()）
        return len(self._buckets)
