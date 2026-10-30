# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.AjaxResult

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/AjaxResult.java
"""
from __future__ import annotations

from typing import Any, Optional

from com.ruoyi.common.constant.HttpStatus import HttpStatus
from com.ruoyi.common.utils.StringUtils import StringUtils


class AjaxResult(dict):
    """操作消息提醒（Java 侧 extends HashMap<String, Object>）。

    【Java→Python】
    1) extends HashMap<String,Object> → 继承内置 dict，因此 put/get/containsKey 等方法
       与 Java 的 HashMap 语义一致（Python 叫 [] / get / in）。
    2) Java 的 4 个 success(...) 重载在 Python 中合并为一个，并按“唯一参数是否为 str”
       分派：Java 重载解析同样优先选择 success(String) 而不是 success(Object)，
       因此 `AjaxResult.success("msg")` 仍是 msg、`AjaxResult.success(data)` 仍是 data，
       与 Java 行为完全一致。
    3) Java 的 put 返回 this 支持链式调用 → Python 覆盖 __setitem__ 无法返回值，
       故保留 put() 方法并返回 self。
    """

    CODE_TAG = "code"     # 状态码
    MSG_TAG = "msg"       # 返回内容
    DATA_TAG = "data"     # 数据对象

    def __init__(self, code: Optional[int] = None, msg: Optional[str] = None, data: Any = None) -> None:
        super().__init__()
        # 对应 Java 的 AjaxResult() 无参构造：表示一个空消息
        if code is None and msg is None:
            return
        dict.__setitem__(self, AjaxResult.CODE_TAG, code)
        dict.__setitem__(self, AjaxResult.MSG_TAG, msg)
        # Java: if (StringUtils.isNotNull(data))
        if StringUtils.isNotNull(data):
            dict.__setitem__(self, AjaxResult.DATA_TAG, data)

    # ---- success ----------------------------------------------------------
    @staticmethod
    def success(*args: Any) -> "AjaxResult":
        """对应 Java 的 4 个重载 success() / success(Object) / success(String) / success(String, Object)。"""
        if len(args) == 0:
            return AjaxResult.success("操作成功")
        if len(args) == 1:
            only = args[0]
            if isinstance(only, str):
                # Java 优先命中 success(String) 重载
                return AjaxResult.success(only, None)
            return AjaxResult.success("操作成功", only)
        return AjaxResult(HttpStatus.SUCCESS, args[0], args[1])

    # ---- warn -------------------------------------------------------------
    @staticmethod
    def warn(msg: str, data: Any = None) -> "AjaxResult":
        """对应 Java 的 warn(String) / warn(String, Object) 两个重载。"""
        return AjaxResult(HttpStatus.WARN, msg, data)

    # ---- error ------------------------------------------------------------
    @staticmethod
    def error(*args: Any) -> "AjaxResult":
        """对应 Java 的 error() / error(String) / error(String, Object) / error(int, String)。"""
        if len(args) == 0:
            return AjaxResult.error("操作失败")
        if len(args) == 1:
            return AjaxResult.error(args[0], None)
        if len(args) == 2 and isinstance(args[0], int):
            # Java: error(int code, String msg)
            return AjaxResult(args[0], args[1], None)
        return AjaxResult(HttpStatus.ERROR, args[0], args[1])

    # ---- 判定 -------------------------------------------------------------
    def isSuccess(self) -> bool:
        # Java: Objects.equals(HttpStatus.SUCCESS, get(CODE_TAG))
        # 【Java→Python】HttpStatus.SUCCESS 是 int，而 HashMap 里可能存 Integer；
        # Python 中 True == 1，若 code 存了 bool 会误判，故显式排除 bool。
        code = self.get(AjaxResult.CODE_TAG)
        return not isinstance(code, bool) and code == HttpStatus.SUCCESS

    def isWarn(self) -> bool:
        code = self.get(AjaxResult.CODE_TAG)
        return not isinstance(code, bool) and code == HttpStatus.WARN

    def isError(self) -> bool:
        code = self.get(AjaxResult.CODE_TAG)
        return not isinstance(code, bool) and code == HttpStatus.ERROR

    # ---- 链式 put ---------------------------------------------------------
    def put(self, key: str, value: Any) -> "AjaxResult":
        dict.__setitem__(self, key, value)
        return self
