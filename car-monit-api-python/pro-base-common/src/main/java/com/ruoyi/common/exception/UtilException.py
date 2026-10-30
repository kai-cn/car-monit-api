# -*- coding: utf-8 -*-
"""com.ruoyi.common.exception.UtilException

源文件：pro-base-common/src/main/java/com/ruoyi/common/exception/UtilException.java
"""
from __future__ import annotations


class UtilException(RuntimeError):
    """工具类异常。

    【Java→Python】
    1) extends RuntimeException → 继承 RuntimeError（Python 中与“非受检异常”对应的基类）。
    2) Java 的三个重载构造器在 Python 中合并为一个（Python 无重载）；
       通过 cause 参数区分 ``new UtilException(Throwable)`` 与 ``new UtilException(String)``。
    3) Java 的 cause 链 → Python 的 ``raise ... from ...`` / ``__cause__`` 语义。
    """

    def __init__(self, message_or_cause=None, throwable: BaseException | None = None) -> None:
        if isinstance(message_or_cause, BaseException) and throwable is None:
            # 对应 UtilException(Throwable e)：super(e.getMessage(), e)
            super().__init__(str(message_or_cause))
            self.__cause__ = message_or_cause
        else:
            # 对应 UtilException(String)、UtilException(String, Throwable)
            super().__init__(message_or_cause)
            if throwable is not None:
                self.__cause__ = throwable
