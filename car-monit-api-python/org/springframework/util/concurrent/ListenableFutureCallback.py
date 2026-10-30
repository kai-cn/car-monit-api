# -*- coding: utf-8 -*-
"""org.springframework.util.concurrent.ListenableFutureCallback

【无 Java 源文件：框架类替身】
Java 侧来自 spring-core：`org.springframework.util.concurrent.ListenableFutureCallback<T>`。
业务代码用**匿名内部类**实现它：
    future.addCallback(new ListenableFutureCallback<SendResult<String, Object>>() {
        @Override public void onSuccess(SendResult<String, Object> result) { ... }
        @Override public void onFailure(Throwable ex) { ... }
    });

【Java→Python 关键差异】
1) Python 没有匿名内部类，转写为**继承本类的具名/嵌套类**，并实现 onSuccess/onFailure
   （见 KafkaProducerService 中的用法）。
2) Java 的 `Throwable` → Python 的 `BaseException`；两者都表示“异常对象”。
"""
from __future__ import annotations

from typing import Any

__all__ = ["ListenableFutureCallback"]


class ListenableFutureCallback(object):
    """`ListenableFutureCallback<T>` 的替身基类。"""

    def onSuccess(self, result: Any) -> None:  # pragma: no cover - 由子类实现
        raise NotImplementedError("ListenableFutureCallback.onSuccess 需由子类实现")

    def onFailure(self, ex: BaseException) -> None:  # pragma: no cover - 由子类实现
        raise NotImplementedError("ListenableFutureCallback.onFailure 需由子类实现")
