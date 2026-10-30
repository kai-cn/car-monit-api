# -*- coding: utf-8 -*-
"""com.ruoyi.common.exception.base.BaseException

源文件：pro-base-common/src/main/java/com/ruoyi/common/exception/base/BaseException.java
"""
from __future__ import annotations

from typing import Any, Optional, Sequence


class BaseException(RuntimeError):
    """基础异常。

    【Java→Python】
    1) extends RuntimeException → RuntimeError；注意本类名与 Python 内置 BaseException 同名，
       因此 ``from ...BaseException import BaseException`` 会遮蔽内置名，使用时需留意
       （模块内统一用本类，捕获时写 ``except BaseException as e`` 需确认指向）。
    2) Java 五个重载构造器 → 一个构造器 + 默认参数，参数顺序与原类一致。
    3) getMessage()：Java 重写了 Throwable.getMessage()，Python 对应实现是覆盖 __str__；
       同时保留 getMessage() 方法以便逐行对照调用点。
    4) Java 的 message 可能返回 null；Python __str__ 必须返回 str，故 None 时返回空串
       （调用方若依赖 null 判断，请改用 getMessage_or_none()）。
    """

    def __init__(
        self,
        module: Optional[str] = None,
        code: Optional[str] = None,
        args: Optional[Sequence[Any]] = None,
        default_message: Optional[str] = None,
    ) -> None:
        self.module = module
        self.code = code
        self.args = list(args) if args is not None else None
        self.default_message = default_message
        super().__init__(default_message)

    def get_message_or_none(self) -> Optional[str]:
        """Java: public String getMessage()（可能返回 null）。"""
        message: Optional[str] = None
        if self.code is not None and self.code != "":
            # Java: MessageUtils.message(code, args) —— 延迟导入避免循环依赖
            from com.ruoyi.common.utils.MessageUtils import MessageUtils

            message = MessageUtils.message(self.code, self.args)
        if message is None:
            message = self.default_message
        return message

    def getMessage(self) -> str:
        """Java 方法名保持一致；Java 可能返回 null，这里用空串兜底。"""
        return self.get_message_or_none() or ""

    def __str__(self) -> str:
        return self.get_message_or_none() or ""

    def getModule(self) -> Optional[str]:
        return self.module

    def getCode(self) -> Optional[str]:
        return self.code

    def getArgs(self) -> Optional[list[Any]]:
        return self.args

    def getDefaultMessage(self) -> Optional[str]:
        return self.default_message
