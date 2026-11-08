# -*- coding: utf-8 -*-
"""三个真实中间件适配器共享的熔断状态机（高危 H2 / 复核中危）。

语义
----
* **闭合**：调用直连真实服务；
* **打开**（``degraded``）：调用全部回落进程内替身（``fallback=error`` 时不回落，
  但仍记录降级状态供 readiness 使用）；
* **半开**：距**最后一次失败**满 ``retry_seconds`` 后，只放行**一个**探测请求；
  其余并发请求继续走替身。

复核修正
--------
1. 失败分支**无条件**刷新 ``_down_since``（修复"60 秒后每次调用都直连"）；
2. ``_probing`` 保证半开窗口内最多一个在途探测；
3. **epoch（代际）校验**：每次失败递增代际，成功回调必须携带获取时的代际，
   只有代际仍匹配才允许闭合熔断。这样并发场景下"旧请求的成功"不会误清新
   近一次失败打开的窗口。
"""
from __future__ import annotations

import threading
import time
from typing import Tuple

__all__ = ["CircuitBreaker"]


class CircuitBreaker:
    """轻量熔断器：``acquire`` → 成功/失败上报（带代际）。"""

    def __init__(self, retry_seconds: float = 60.0) -> None:
        self._retry_seconds = float(retry_seconds)
        self._lock = threading.Lock()
        self._down = False
        self._down_since = 0.0
        self._probing = False
        self._epoch = 0

    @property
    def degraded(self) -> bool:
        """当前是否处于熔断降级。"""
        return self._down

    def acquire(self) -> Tuple[bool, bool, int]:
        """申请一次真实调用。

        :return: ``(allowed, is_probe, epoch)``——``allowed=False`` 表示应直接
                 走替身；``is_probe=True`` 表示这是半开窗口内唯一放行的探测，
                 调用方必须在异常路径调用 :meth:`release_probe`。
        """
        with self._lock:
            if not self._down:
                return True, False, self._epoch
            if time.monotonic() - self._down_since < self._retry_seconds:
                return False, False, self._epoch
            if self._probing:
                return False, False, self._epoch
            self._probing = True
            return True, True, self._epoch

    def success(self, epoch: int | None = None) -> bool:
        """真实调用成功：代际匹配时闭合熔断。

        :param epoch: ``acquire()`` 返回的代际；不传等价于"无条件成功"
                      （仅用于不经过 ``acquire`` 的显式健康检查）。
        :return: 是否发生了"从降级到恢复"的状态变化（供日志使用）。
        """
        with self._lock:
            if epoch is not None and epoch != self._epoch:
                # 本次成功属于旧代际：期间已发生新失败，不能清掉新窗口
                return False
            was_down = self._down
            self._down = False
            self._probing = False
            return was_down

    def failure(self) -> bool:
        """真实调用失败：打开熔断、**无条件刷新**计时并递增代际。

        :return: 是否首次故障（供调用方打首跳日志）。
        """
        with self._lock:
            first = not self._down
            self._down = True
            self._down_since = time.monotonic()
            self._probing = False
            self._epoch += 1
            return first

    def release_probe(self, epoch: int | None = None) -> None:
        """探测因确定性错误结束（既非成功也非故障）：仅释放探测名额。

        带代际时，旧代际的探测不得释放新代际的探测名额。
        """
        with self._lock:
            if epoch is not None and epoch != self._epoch:
                return
            self._probing = False
