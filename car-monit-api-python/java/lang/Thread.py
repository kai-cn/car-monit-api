# -*- coding: utf-8 -*-
"""java.lang.Thread

【无 Java 源文件：框架类替身】
Java 侧来自 JDK：`java.lang.Thread`。业务代码用到：
    Thread.sleep(ms)
    Thread.currentThread().interrupt()
    Thread.currentThread().isInterrupted()
    Thread.currentThread().getName()
    new Thread(runnable).start()        // 另起后台线程（Controller / Service 里常见）
    new Thread(runnable, name)          // 带线程名

【Java→Python 关键差异】
1) Python 的 `time.sleep` 不会因为“被中断”抛异常，也没有线程中断标志位；
   这里用 `threading.local` 给每个线程挂一个 `_interrupted` 标记来还原。
2) Java 的 `Thread.sleep()` 声明 `throws InterruptedException`，被中断时立即抛出
   并**清除**中断标志；本替身同样：标志位为 True 时抛 InterruptedException 并复位，
   这样 `catch (InterruptedException e) { Thread.currentThread().interrupt(); break; }`
   的写法可以原样保留。
3) Java 的线程对象本身带名字/优先级/守护标记；Python 里对应 `threading.Thread`，
   本替身只做“当前线程视图”，真正的池化线程由 java.util.concurrent 的替身创建。
4) `new Thread(runnable).start()` → `Thread(runnable).start()`：本替身内部包一层
   `threading.Thread`，兼容 Runnable 的两种形态（可调用对象 / 实现 `run()` 的对象）。
   Java 默认线程是**非守护**线程，Python 的 `threading.Thread` 默认同样是非守护，
   因此 `daemon` 缺省值为 False，与 Java 一致。
5) Java 重复调用 `start()` 抛 `IllegalThreadStateException`（RuntimeException），
   Python 用 `RuntimeError` 表达。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

__all__ = ["Thread", "InterruptedException"]


class InterruptedException(Exception):
    """java.lang.InterruptedException 的替身。"""


class _JavaThreadState(threading.local):
    """线程本地状态：中断标志 + 线程名。"""

    def __init__(self) -> None:
        self.interrupted = False
        self.name: Optional[str] = None


_STATE = _JavaThreadState()


class _ThreadView(object):
    """`Thread.currentThread()` 返回的“当前线程视图”。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def getName(self) -> str:
        return self.name

    def interrupt(self) -> None:
        """置位中断标志（Java 的 interrupt() 只“建议”停止，不强制杀线程）。"""
        _STATE.interrupted = True

    def isInterrupted(self) -> bool:
        """查询并**保留**中断标志（对应 Java 的 isInterrupted()）。"""
        return bool(_STATE.interrupted)

    def interrupted(self) -> bool:
        """静态方法 `Thread.interrupted()` 的实例化写法：查询并**清除**标志。"""
        current = bool(_STATE.interrupted)
        _STATE.interrupted = False
        return current


class Thread(object):
    """`java.lang.Thread` 的替身：静态方法 + 可 new 的线程对象。"""

    def __init__(self, target: Optional[object] = None, name: Optional[str] = None) -> None:
        # Java: new Thread(Runnable target) / new Thread(Runnable target, String name)
        self._target = target
        self._name = name
        self._daemon = False  # Java 默认非守护线程
        self._thread: Optional[threading.Thread] = None

    # ---------------- 实例 API：new Thread(...).start() ----------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("java.lang.IllegalThreadStateException: thread already started")
        self._thread = threading.Thread(
            target=self._run,
            name=self._name or ("Thread-%d" % (id(self) & 0xFFFF)),
            daemon=self._daemon)
        self._thread.start()

    def run(self) -> None:
        """执行 Runnable；Java 的 `Thread.run()` 在未设置 target 时什么都不做。"""
        if self._target is None:
            return
        # Runnable 形态 1：实现了 run() 的对象；形态 2：Python lambda / 函数
        run_method = getattr(self._target, "run", None)
        if callable(run_method):
            run_method()
        elif callable(self._target):
            self._target()
        else:
            raise TypeError("Runnable 必须是可调用对象或实现 run() 的实例")

    def _run(self) -> None:
        # 单独包一层，避免与“静态方法区”里的名字冲突；子线程内的异常不会回传到主线程
        self.run()

    def join(self, millis: Optional[int] = None) -> None:
        if self._thread is None:
            return
        self._thread.join(None if millis is None else millis / 1000.0)

    def isAlive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def setDaemon(self, on: bool) -> None:
        self._daemon = bool(on)

    def isDaemon(self) -> bool:
        return self._daemon

    def getName(self) -> str:
        if self._name:
            return self._name
        return self._thread.name if self._thread is not None else ""

    def setName(self, name: str) -> None:
        self._name = name
        if self._thread is not None:
            self._thread.name = name

    # ------------- 静态 API：Thread.sleep / currentThread -------------

    # 让 `Thread.currentThread().getName()` 拿到真实线程名
    @staticmethod
    def currentThread() -> _ThreadView:
        name = _STATE.name or threading.current_thread().name
        _STATE.name = name
        return _ThreadView(name)

    @staticmethod
    def sleep(millis: int) -> None:
        """睡眠指定毫秒；中断标志已置位时抛 InterruptedException（并清除标志）。"""
        if _STATE.interrupted:
            _STATE.interrupted = False
            raise InterruptedException("sleep interrupted")
        time.sleep(millis / 1000.0)
