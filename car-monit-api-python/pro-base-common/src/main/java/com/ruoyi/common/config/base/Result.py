# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.base.Result

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/base/Result.java
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """接口返回数据格式（Lombok @Data → @dataclass）。

    【Java→Python】
    1) Java 泛型仅编译期存在（类型擦除），Python 的 Generic[T] 也只在类型检查时有意义，
       运行时同样不做校验，两者行为一致。
    2) Java 的 ``private long timestamp = System.currentTimeMillis();`` 是“字段初始化时”
       取当前时间；dataclass 用 default_factory 在实例化时求值，语义一致。
    3) 无参构造 + setter：Python 用 dataclass 默认值 + 直接属性赋值模拟。
    4) Java 的 ``success(String)`` 实例方法与静态工厂 OK(...) 同名不同义，Python 保留原名。
    """

    success: bool = True                                  # 成功标志
    message: str = "操作成功！"                            # 返回处理消息
    code: Optional[int] = 0                               # 返回代码
    result: Optional[T] = None                            # 返回数据对象 data
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))  # 时间戳

    def success_(self, message: str) -> "Result[T]":
        """Java: public Result<T> success(String message)（实例方法，与字段 success 同名冲突）。

        【Java→Python】Java 允许字段与方法同名（Lombok 生成 isSuccess()/setSuccess()），
        Python 的实例属性会遮蔽同名方法，因此方法名加下划线区分。
        """
        self.message = message
        self.code = 200
        self.success = True
        return self

    # ---- 静态工厂：OK() 系列
    @staticmethod
    def OK() -> "Result[T]":
        r = Result()
        r.success = True
        r.code = 200
        r.message = "成功"
        return r

    @staticmethod
    def OK_msg(msg: str) -> "Result[T]":
        """Java: static <T> Result<T> OK(String msg)。

        【Java→Python】Java 靠重载区分 OK() / OK(String) / OK(T) / OK(String, T)，
        Python 无重载，这里按“参数类型/个数”拆分方法名，并保留 OK 作为主入口。
        """
        r = Result()
        r.success = True
        r.code = 200
        r.message = msg
        return r

    @staticmethod
    def OK_data(data: T) -> "Result[T]":
        r = Result()
        r.success = True
        r.code = 200
        r.result = data
        return r

    @staticmethod
    def OK_msg_data(msg: str, data: T) -> "Result[T]":
        r = Result()
        r.success = True
        r.code = 200
        r.message = msg
        r.result = data
        return r

    # ---- 静态工厂：error() 系列
    @staticmethod
    def error(msg: str) -> "Result[object]":
        return Result.error_code_msg(500, msg)

    @staticmethod
    def error_code_msg(code: int, msg: str) -> "Result[object]":
        r = Result()
        r.code = code
        r.message = msg
        r.success = False
        return r

    @staticmethod
    def error_msg_data(msg: str, data: T) -> "Result[T]":
        r = Result()
        r.success = False
        r.code = 500
        r.message = msg
        r.result = data
        return r

    @staticmethod
    def error_code_msg_data(code: int, msg: str, data: object) -> "Result[object]":
        r = Result()
        r.code = code
        r.message = msg
        r.result = data
        r.success = False
        return r

    @staticmethod
    def error500(message: str) -> "Result[T]":
        r = Result()
        r.success = False
        r.code = 500
        r.message = message
        return r

    @staticmethod
    def error500_data(data: object) -> "Result[object]":
        r = Result()
        r.success = False
        r.code = 500
        r.result = data
        return r
