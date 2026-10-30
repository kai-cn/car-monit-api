# -*- coding: utf-8 -*-
"""org.elasticsearch.action.bulk.BulkProcessor

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.bulk.BulkProcessor`。

本工程用法（LargeScaleDataSyncService.buildBulkProcessor → add → flush → awaitClose）：
    BulkProcessor.builder(bulkConsumer, new BulkProcessor.Listener() {...})
            .setBulkActions(1000)
            .setBulkSize(new ByteSizeValue(10L, ByteSizeUnit.MB))
            .setFlushInterval(TimeValue.timeValueSeconds(5))
            .setConcurrentRequests(4)
            .setBackoffPolicy(BackoffPolicy.exponentialBackoff(...))
            .build();
    ...
    bulkProcessor.add(request);
    bulkProcessor.flush();
    bulkProcessor.awaitClose(30, TimeUnit.SECONDS);

【Java→Python 重点差异】
1) **异步批量 → 同步批量**：真实 BulkProcessor 由后台定时线程按 1000 条/10MB/5s
   先到先触发，通过 `client.bulkAsync(...)` 异步发送；替身没有网络与定时线程，
   改为**同步发送**：`add()` 累计到 bulkActions 条立即 `flush()`，
   `flush()` 把当前批次交给 `bulkConsumer` 并同步等待回调完成。
   因此本替身里“5 秒定时刷新”不会自动发生 —— 业务侧显式 `flush()`/`awaitClose()`
   仍是唯一保证末批数据落库的方式（与原工程调用顺序一致）。
2) **Listener 的 afterBulk 重载**：Java 有两个重载
     afterBulk(long, BulkRequest, BulkResponse)
     afterBulk(long, BulkRequest, Throwable)
   Python 无重载，合并为 `afterBulk(executionId, request, response_or_failure)`，
   由传入对象的类型区分成功/失败（`BaseException` 代表失败）。
3) **Builder 内部类**：Java 的 `BulkProcessor.Builder` 是静态内部类，
   Python 保留嵌套类 `BulkProcessor.Builder`，访问路径不变。
4) `awaitClose(timeout, unit)` 返回 boolean：替身先 flush 再返回 True（超时永不发生）。
"""
from __future__ import annotations

import threading
from typing import Any, List, Optional

from org.elasticsearch.action.ActionListener import ActionListener
from org.elasticsearch.action.bulk.BulkRequest import BulkRequest

__all__ = ["BulkProcessor"]


class BulkProcessor(object):
    """`BulkProcessor` 的替身（同步批量写入）。"""

    class Listener(object):
        """`BulkProcessor.Listener` 的替身接口。"""

        def beforeBulk(self, execution_id: int, request: BulkRequest) -> None:
            """批次发送前回调。"""

        def afterBulk(self, execution_id: int, request: BulkRequest,
                      response_or_failure: Any) -> None:
            """批次结束后回调（Java 两个重载合并，见文件头第 2 条）。"""

    class Builder(object):
        """`BulkProcessor.Builder` 的替身（链式构建）。"""

        def __init__(self, bulk_consumer: Any, listener: Optional["BulkProcessor.Listener"]) -> None:
            self._bulk_consumer = bulk_consumer
            self._listener = listener
            self._bulk_actions = 1000
            self._bulk_size: Any = None
            self._flush_interval: Any = None
            self._concurrent_requests = 1
            self._backoff_policy: Any = None

        def setBulkActions(self, bulk_actions: int) -> "BulkProcessor.Builder":
            self._bulk_actions = int(bulk_actions)
            return self

        def setBulkSize(self, bulk_size: Any) -> "BulkProcessor.Builder":
            self._bulk_size = bulk_size
            return self

        def setFlushInterval(self, flush_interval: Any) -> "BulkProcessor.Builder":
            self._flush_interval = flush_interval
            return self

        def setConcurrentRequests(self, concurrent_requests: int) -> "BulkProcessor.Builder":
            self._concurrent_requests = int(concurrent_requests)
            return self

        def setBackoffPolicy(self, backoff_policy: Any) -> "BulkProcessor.Builder":
            self._backoff_policy = backoff_policy
            return self

        def build(self) -> "BulkProcessor":
            return BulkProcessor(self._bulk_consumer, self._listener,
                                 self._bulk_actions, self._bulk_size,
                                 self._flush_interval, self._concurrent_requests,
                                 self._backoff_policy)

    # ------------------------------------------------------------------ 构造
    def __init__(self, bulk_consumer: Any, listener: Optional[Listener],
                 bulk_actions: int = 1000, bulk_size: Any = None,
                 flush_interval: Any = None, concurrent_requests: int = 1,
                 backoff_policy: Any = None) -> None:
        self._bulk_consumer = bulk_consumer
        self._listener = listener
        self._bulk_actions = max(1, int(bulk_actions))
        self._bulk_size = bulk_size
        self._flush_interval = flush_interval
        self._concurrent_requests = int(concurrent_requests)
        self._backoff_policy = backoff_policy
        # 【Java→Python】用锁保护待发批次（真实 BulkProcessor 内部同样有并发控制）
        self._lock = threading.RLock()
        self._pending: List[Any] = []
        self._execution_seq = 0
        self._closed = False

    @staticmethod
    def builder(bulk_consumer: Any,
                listener: Optional["BulkProcessor.Listener"]) -> "BulkProcessor.Builder":
        """对应 `static Builder builder(BiConsumer, Listener)`。"""
        return BulkProcessor.Builder(bulk_consumer, listener)

    # ------------------------------------------------------------------ 写入
    def add(self, request: Any) -> None:
        """对应 `add(IndexRequest)`：累计到阈值立即同步 flush。"""
        with self._lock:
            self._pending.append(request)
            should_flush = len(self._pending) >= self._bulk_actions
        if should_flush:
            self.flush()

    def flush(self) -> None:
        """对应 `flush()`：同步发送当前批次（见文件头第 1 条）。"""
        with self._lock:
            if not self._pending:
                return
            actions = self._pending
            self._pending = []
            execution_id = self._execution_seq
            self._execution_seq += 1

        request = BulkRequest()
        for action in actions:
            request.add(action)

        if self._listener is not None:
            self._listener.beforeBulk(execution_id, request)

        # Java: new ActionListener<BulkResponse>() {...}（匿名内部类）
        listener_self = self

        class _BulkListener(ActionListener):
            def onResponse(self, response: Any) -> None:
                if listener_self._listener is not None:
                    listener_self._listener.afterBulk(execution_id, request, response)

            def onFailure(self, error: BaseException) -> None:
                if listener_self._listener is not None:
                    listener_self._listener.afterBulk(execution_id, request, error)

        self._bulk_consumer(request, _BulkListener())

    def awaitClose(self, timeout: int, unit: Any) -> bool:
        """对应 `awaitClose(long, TimeUnit)`：冲刷后关闭（替身不会超时）。"""
        self.flush()
        self._closed = True
        return True

    def close(self) -> None:
        """对应 `close()`（Closeable 语义）：冲刷后关闭。"""
        self.flush()
        self._closed = True

    # ------------------------------------------------------------------ 测试辅助
    def isClosed(self) -> bool:
        return self._closed

    def pendingActions(self) -> int:
        """Java 无此方法：查看尚未发送的条数（仅供测试断言）。"""
        return len(self._pending)

    def __repr__(self) -> str:
        return ("BulkProcessor(actions=%d, size=%r, flushInterval=%r, "
                "concurrentRequests=%d)" % (self._bulk_actions, self._bulk_size,
                                            self._flush_interval,
                                            self._concurrent_requests))
