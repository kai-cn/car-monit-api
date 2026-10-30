# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.MessageUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/MessageUtils.java
"""
from __future__ import annotations

from typing import Any, Optional

from com.ruoyi.common.utils.spring.SpringUtils import SpringUtils


class MessageUtils:
    """获取 i18n 资源文件。

    【Java→Python】
    1) Spring 的 MessageSource + LocaleContextHolder → Python 标准库 gettext 的语义模型。
       这里通过 SpringUtils 取得注册的 messageSource（任何实现了
       ``getMessage(code, args, locale)`` 的对象均可），保持调用链与 Java 一致。
    2) Java 的 Object... args 变长参数 → Python 的 *args（BaseException.getArgs() 传来的 list
       需要解包，调用点写 ``MessageUtils.message(code, *args)``）。
    """

    @staticmethod
    def message(code: str, args: Optional[Any] = None) -> str:
        message_source = SpringUtils.getBean("messageSource")
        if message_source is None:
            # 没有配置 i18n 时退化为原样返回 code
            return code
        # Java: messageSource.getMessage(code, args, LocaleContextHolder.getLocale())
        return message_source.getMessage(code, args, SpringUtils.getLocale())
