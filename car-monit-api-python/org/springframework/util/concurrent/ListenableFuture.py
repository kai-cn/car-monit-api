# -*- coding: utf-8 -*-
"""org.springframework.util.concurrent.ListenableFuture

【无 Java 源文件：框架类替身】
Java 侧来自 spring-core：`org.springframework.util.concurrent.ListenableFuture<T>`
（继承 `java.util.concurrent.Future<T>`，额外提供 `addCallback(...)`）。
Kafka 的 `KafkaTemplate.send(...)` 返回的就是它。

【Java→Python 关键差异】
1) Spring 的 ListenableFuture 支持“**先完成、后注册回调**”：若 future 已完成，
   `addCallback` 会立即用结果回调（SettableListenableFuture 的语义）。
   本替身完全照此实现，否则 `send()` 同步模拟成功时回调永远不触发。
2) Java 有两个 `addCallback` 重载：
       addCallback(ListenableFutureCallback<? super T> callback)
       addCallback(SuccessCallback<? super T>, FailureCallback)
   Python 用一个方法 + `failure_callback=None` 表达。
3) 回调抛出的异常在 Spring 里会被 `AsyncUncaughtExceptionHandler` 记录；
   这里直接让异常冒泡（测试里更容易发现回调写错）。
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from java.util.concurrent.ExecutorService import Future

__all__ = ["ListenableFuture"]


class ListenableFuture(Future):
    """`ListenableFuture<T>` 的替身：Future + 回调。"""

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: List[Callable[[Any, Optional[BaseException]], None]] = []

    # ------------------------------------------------------------------ 注册
    def addCallback(self, callback: Any, failure_callback: Any = None) -> None:
        """注册成功/失败回调（兼容 Java 的两个重载）。"""
        if failure_callback is not None:
            # 重载二：两个函数式接口
            def adapter(value: Any, error: Optional[BaseException]) -> None:
                if error is not None:
                    failure_callback(error)
                else:
                    callback(value)
        else:
            # 重载一：单个 ListenableFutureCallback
            def adapter(value: Any, error: Optional[BaseException]) -> None:
                if error is not None:
                    callback.onFailure(error)
                else:
                    callback.onSuccess(value)

        if self.isDone():
            # Spring 语义：已完成则立即回调（不再等待）
            if self._error is not None:
                adapter(None, self._error)
            else:
                adapter(self._result, None)
            return
        self._callbacks.append(adapter)

    def addListener(self, listener: Callable[[], None]) -> None:
        """`addListener(Runnable)`：完成时执行，不关心结果。"""
        self.addCallback(lambda _value: listener())

    # ------------------------------------------------------------------ 完成
    def _setResult(self, value: Any) -> None:
        super()._setResult(value)
        self._fire()

    def _setException(self, error: BaseException) -> None:
        super()._setException(error)
        self._fire()

    def _fire(self) -> None:
        callbacks = self._callbacks
        self._callbacks = []
        for callback in callbacks:
            # 【Java→Python】失败时 value 仍为 None，错误通过第二个参数传给 onFailure，
            # 不能直接 raise，否则 onFailure 永远没机会执行。
            callback(self._result, self._error)
