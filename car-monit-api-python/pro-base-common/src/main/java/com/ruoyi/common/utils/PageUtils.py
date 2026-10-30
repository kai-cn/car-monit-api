# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.PageUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/PageUtils.java
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from com.ruoyi.common.core.page.PageDomain import PageDomain
from com.ruoyi.common.core.page.TableSupport import TableSupport
from com.ruoyi.common.utils.sql.SqlUtil import SqlUtil


@dataclass
class PageContext:
    """PageHelper 分页上下文的等价物。"""

    page_num: Optional[int] = None
    page_size: Optional[int] = None
    order_by: str = ""
    reasonable: bool = True
    total: Optional[int] = None


class PageUtils:
    """分页工具类（Java 侧 extends PageHelper）。

    【Java→Python】
    1) PageHelper 使用 ThreadLocal 保存分页参数（PageHelper.startPage 后紧跟的第一次查询
       自动分页）。Python 侧用 threading.local 还原“线程内有效”的语义；
       若运行在 asyncio 单线程多协程环境，应改用 contextvars.ContextVar。
    2) `PageHelper.startPage(pageNum, pageSize, orderBy).setReasonable(reasonable)`
       的链式调用 → 本类拆成“构造上下文 + setReasonable”两步，语义一致。
    3) 手写分页 SQL 的场景需要读取 total，这里额外提供 get_page_total() 供 BaseController 使用。
    """

    _local = threading.local()

    @staticmethod
    def _context() -> Optional[PageContext]:
        return getattr(PageUtils._local, "context", None)

    @staticmethod
    def startPage() -> None:
        """设置请求分页数据。"""
        page_domain: PageDomain = TableSupport.buildPageRequest()
        page_num = page_domain.getPageNum()
        page_size = page_domain.getPageSize()
        order_by = SqlUtil.escapeOrderBySql(page_domain.getOrderBy())
        reasonable = page_domain.getReasonable()
        context = PageContext(page_num, page_size, order_by, reasonable)
        PageUtils._local.context = context

    @staticmethod
    def orderBy(order_by: str) -> None:
        """等价于 PageHelper.orderBy(orderBy)。"""
        context = PageUtils._context()
        if context is None:
            context = PageContext()
            PageUtils._local.context = context
        context.order_by = order_by

    @staticmethod
    def setReasonable(reasonable: bool) -> None:
        """等价于 startPage(...).setReasonable(...) 的链式设置。"""
        context = PageUtils._context()
        if context is None:
            context = PageContext()
            PageUtils._local.context = context
        context.reasonable = reasonable

    @staticmethod
    def clearPage() -> None:
        """清理分页的线程变量。"""
        PageUtils._local.context = None

    @staticmethod
    def get_page_total() -> Optional[int]:
        """读取当前分页上下文中的总记录数（供 PageInfo 替身使用）。"""
        context = PageUtils._context()
        return None if context is None else context.total

    @staticmethod
    def set_page_total(total: int) -> None:
        context = PageUtils._context()
        if context is not None:
            context.total = total
