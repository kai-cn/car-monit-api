# -*- coding: utf-8 -*-
"""com.github.pagehelper.PageInfo

【无 Java 源文件：框架类替身】（PageHelper 5.x 的 ``com.github.pagehelper.PageInfo``）

【Java→Python】为什么需要它
Java 侧的 ``BaseController.getDataTable(list)`` 与个别 Controller 会写
``new PageInfo(list).getTotal()``，PageInfo 由 PageHelper 在**查询执行时**把
“分页后的 List”包装成 Page 对象，``getTotal()`` 返回数据库的总记录数。

Python 侧没有 MyBatis 拦截器，分页参数由 ``PageUtils.startPage()`` 写进线程上下文；
本替身的 ``getTotal()`` 因此：
1) 优先读取 ``PageUtils.get_page_total()``（由手写分页 SQL 的 count 结果写入）；
2) 上下文里没有 total 时退化为 ``len(list)`` —— 与 PageInfo 在“未分页/未命中
   PageHelper 拦截”时的表现一致。

只实现本工程实际用到的方法（getTotal / getList），其余 PageInfo API 未翻译。
"""
from __future__ import annotations

from typing import Any, Optional

from com.ruoyi.common.utils.PageUtils import PageUtils

__all__ = ["PageInfo"]


class PageInfo:
    """``PageInfo<T>`` 的最小等价实现。"""

    def __init__(self, data_list: Optional[list[Any]] = None) -> None:
        # Java: new PageInfo(List<T> list) —— 无分页上下文时 pageNum/pageSize 均为 0
        self._list: list[Any] = data_list if data_list is not None else []

    def getList(self) -> list[Any]:
        """分页后的数据列表。"""
        return self._list

    def getTotal(self) -> int:
        """总记录数：优先取分页上下文，取不到则等于列表长度。"""
        total = PageUtils.get_page_total()
        if total is not None:
            return total
        return len(self._list)
