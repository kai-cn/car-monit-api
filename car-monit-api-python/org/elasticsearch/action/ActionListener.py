# -*- coding: utf-8 -*-
"""org.elasticsearch.action.ActionListener

【无 Java 源文件：框架类替身】
Java 侧来自 elasticsearch jar：`org.elasticsearch.action.ActionListener<Response>`。

本工程用法（LargeScaleDataSyncService.buildBulkProcessor）：
    BiConsumer<BulkRequest, ActionListener<BulkResponse>> bulkConsumer =
        (request, bulkListener) -> client.bulkAsync(request, RequestOptions.DEFAULT, bulkListener);

【Java→Python 关键差异】
1) Java 的 `ActionListener<T>` 是**函数式接口**（两个方法 onResponse/onFailure，
   但通过默认实现组合成“双方法 SAM”）；Python 没有函数式接口概念，
   这里保留为**普通基类**，由 BulkProcessor 内部匿名子类实现（与 Java 匿名类一一对应）。
2) Java 的异步回调在独立 IO 线程执行；替身是**同步回调**（bulkAsync 内部立即回调），
   因此不要在回调里假设“当前线程不是调用线程”。
"""
from __future__ import annotations

from typing import Any

__all__ = ["ActionListener"]


class ActionListener(object):
    """`ActionListener<T>` 的替身基类。"""

    def onResponse(self, response: Any) -> None:  # pragma: no cover - 由子类实现
        raise NotImplementedError("ActionListener.onResponse 需由子类实现")

    def onFailure(self, error: BaseException) -> None:  # pragma: no cover - 由子类实现
        raise NotImplementedError("ActionListener.onFailure 需由子类实现")
