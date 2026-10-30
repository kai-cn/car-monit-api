# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.page.TableDataInfo

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/page/TableDataInfo.java
"""
from __future__ import annotations

from typing import Any, Optional


class TableDataInfo:
    """表格分页数据对象。

    【Java→Python】
    1) Java 的 long total → Python int（无溢出）。
    2) 两个构造器 TableDataInfo() / TableDataInfo(List, int) → 一个 __init__ + 默认参数。
    3) `int total` 形参赋给 `long` 字段是 Java 的隐式拓宽转换，Python 无此区别。
    """

    def __init__(self, rows: Optional[list[Any]] = None, total: int = 0) -> None:
        self.total = total        # 总记录数（Java long）
        self.rows = rows          # 列表数据
        self.code = 0             # 消息状态码（Java int，默认 0）
        self.msg: Optional[str] = None  # 消息内容

    def getTotal(self) -> int:
        return self.total

    def setTotal(self, total: int) -> None:
        self.total = total

    def getRows(self) -> Optional[list[Any]]:
        return self.rows

    def setRows(self, rows: Optional[list[Any]]) -> None:
        self.rows = rows

    def getCode(self) -> int:
        return self.code

    def setCode(self, code: int) -> None:
        self.code = code

    def getMsg(self) -> Optional[str]:
        return self.msg

    def setMsg(self, msg: str) -> None:
        self.msg = msg
