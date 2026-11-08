# -*- coding: utf-8 -*-
"""三个真实中间件适配器共享的熔断状态机（高危 H2）。

语义
----
* **闭合**：调用直连真实服务；
* **打开**（``degraded``）：调用全部回落进程内替身；
* **半开**：距**最后一次失败**满 ``retry_seconds`` 后，只放行**一个**探测请求；
  其余并发请求继续走替身。

修复点（2026-11-08 审阅 H2）
------------------------------
此前 ``_down_since`` 只在**首次**故障时写入，60 秒后每次调用都会直连故障
服务（半开窗口退化成"每请求探测"）。现在失败分支**无条件**刷新
``_down_since``，并且用 ``_probing`` 保证半开窗口内最多一个在途探测。

线程安全：所有状态迁移都在锁内完成；``degraded`` 只读布尔值（Python 的
属性读取天然原子，竞争最坏结果是日志多打一行）。
"""
from __future__ import annotations

import threading
import time
from typing import Tuple

__all__ = ["CircuitBreaker"]


class CircuitBreaker:
    """轻量熔断器：``acquire`` → 成功/失败上报。"""

    def __init__(self, retry_seconds: float = 60.0) -> None:
        self._retry_seconds = float(retry_seconds)
        self._lock = threading.Lock()
        self._down = False
        self._down_since = 0.0
        self._probing = False

    @property
    def degraded(self) -> bool:
        """当前是否处于熔断降级。"""
        return self._down

    def acquire(self) -> Tuple[bool, bool]:
        """申请一次真实调用。

        :return: ``(allowed, is_probe)``——``allowed=False`` 表示应直接走替身；
                 ``is_probe=True`` 表示这是半开窗口内唯一放行的探测，
                 调用方必须在异常路径调用 :meth:`release_probe`。
        """
        with self._lock:
            if not self._down:
                return True, False
            if time.monotonic() - self._down_since < self._retry_seconds:
                return False, False
            if self._probing:
                return False, False
            self._probing = True
            return True, True

    def success(self) -> bool:
        """真实调用成功：闭合熔断。返回此前是否处于降级（供调用方打恢复日志）。"""
        with self._lock:
            was_down = self._down
            self._down = False
            self._probing = False
            return was_down

    def failure(self) -> bool:
        """真实调用失败：打开熔断并**无条件刷新**计时。

        :return: 是否首次故障（供调用方打首跳日志）。
        """
        with self._lock:
            first = not self._down
            self._down = True
            self._down_since = time.monotonic()
            self._probing = False
            return first

    def release_probe(self) -> None:
        """探测因确定性错误结束（既非成功也非故障）：仅释放探测名额。"""
        with self._lock:
            self._probing = False
