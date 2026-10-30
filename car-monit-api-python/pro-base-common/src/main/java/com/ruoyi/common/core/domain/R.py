# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.R

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/R.java
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from com.ruoyi.common.constant.HttpStatus import HttpStatus

T = TypeVar("T")


@dataclass
class R(Generic[T]):
    """响应信息主体。

    【Java→Python】
    1) 静态方法 ok()/ok(T)/ok(T,String) 三个重载 → 合并为带默认参数的 ok(data=None, msg="操作成功")；
       Java 在传 null 时都会落到不同重载，Python 用默认值表达同一结果。
    2) fail() 系列中 fail(int code, String msg) 与 fail(T data, String msg) 参数个数相同，
       只能用“第一个参数是否为 int”分派——这与 Java 重载解析规则一致
       （传入 int 时命中 fail(int,String)，传入其它对象时命中 fail(T,String)）。
    3) `R.SUCCESS == ret.getCode()`：Java 的 == 比较 int 值；Python 用 ==，但要注意
       True == 1，因此显式排除 bool（与本类 isSuccess 的写法保持一致）。
    """

    SUCCESS = HttpStatus.SUCCESS  # 成功
    FAIL = HttpStatus.ERROR       # 失败

    code: int = 0
    msg: Optional[str] = None
    data: Optional[T] = None

    # ---- ok 系列 ----------------------------------------------------------
    @staticmethod
    def ok(data: Any = None, msg: str = "操作成功") -> "R[T]":
        return R.restResult(data, R.SUCCESS, msg)

    # ---- fail 系列 --------------------------------------------------------
    @staticmethod
    def fail(*args: Any) -> "R[T]":
        """对应 fail() / fail(String) / fail(T) / fail(T,String) / fail(int,String)。"""
        if len(args) == 0:
            return R.restResult(None, R.FAIL, "操作失败")
        if len(args) == 1:
            only = args[0]
            if isinstance(only, str):
                return R.restResult(None, R.FAIL, only)
            return R.restResult(only, R.FAIL, "操作失败")
        first, second = args[0], args[1]
        if isinstance(first, int) and not isinstance(first, bool):
            return R.restResult(None, first, second)
        return R.restResult(first, R.FAIL, second)

    @staticmethod
    def restResult(data: Any, code: int, msg: str) -> "R[T]":
        api_result: "R[T]" = R()
        api_result.code = code
        api_result.data = data
        api_result.msg = msg
        return api_result

    # ---- getter/setter（Java 手写实现） ----------------------------------
    def getCode(self) -> int:
        return self.code

    def setCode(self, code: int) -> None:
        self.code = code

    def getMsg(self) -> Optional[str]:
        return self.msg

    def setMsg(self, msg: str) -> None:
        self.msg = msg

    def getData(self) -> Optional[T]:
        return self.data

    def setData(self, data: T) -> None:
        self.data = data

    # ---- 判定 -------------------------------------------------------------
    @staticmethod
    def isError(ret: "R[T]") -> bool:
        return not R.isSuccess(ret)

    @staticmethod
    def isSuccess(ret: "R[T]") -> bool:
        code = ret.getCode()
        return not isinstance(code, bool) and code == R.SUCCESS
