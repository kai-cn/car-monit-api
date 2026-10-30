# -*- coding: utf-8 -*-
"""org.elasticsearch.action.bulk.BackoffPolicy

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.bulk.BackoffPolicy`。

本工程用法（LargeScaleDataSyncService.buildBulkProcessor）：
    .setBackoffPolicy(BackoffPolicy.exponentialBackoff(TimeValue.timeValueMillis(1000), 5))

【Java→Python 关键差异】
1) Java 的 `BackoffPolicy` 是接口，`exponentialBackoff` 是静态工厂，返回一个
   能按 `iterator()` 产出等待时长的策略对象；本工程只“设置”不读取，
   替身仅保存（初始延时, 最大重试次数）供断言，不做真正的退避计算。
2) 若将来需要在替身里模拟重试，应按 Java 语义实现：
   delay(n) = initialDelay * 2^n（n 从 0 开始），最多 maxNumberOfRetries 次。
"""
from __future__ import annotations

from typing import Any

__all__ = ["BackoffPolicy"]


class BackoffPolicy(object):
    """`BackoffPolicy` 的替身（仅记录退避参数）。"""

    def __init__(self, initial_delay: Any = None, max_number_of_retries: int = 0) -> None:
        self._initial_delay = initial_delay
        self._max_number_of_retries = max_number_of_retries

    @staticmethod
    def exponentialBackoff(initial_delay: Any, max_number_of_retries: int) -> "BackoffPolicy":
        """对应 `static BackoffPolicy exponentialBackoff(TimeValue, int)`。"""
        return BackoffPolicy(initial_delay, max_number_of_retries)

    def getInitialDelay(self) -> Any:
        return self._initial_delay

    def getMaxNumberOfRetries(self) -> int:
        return self._max_number_of_retries

    def __repr__(self) -> str:
        return "BackoffPolicy.exponential(initial=%r, retries=%d)" % (
            self._initial_delay, self._max_number_of_retries)
