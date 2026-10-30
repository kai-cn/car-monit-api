# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.page.TableSupport

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/page/TableSupport.java
"""
from __future__ import annotations

from com.ruoyi.common.core.page.PageDomain import PageDomain
from com.ruoyi.common.core.text.Convert import Convert
from com.ruoyi.common.utils.ServletUtils import ServletUtils


class TableSupport:
    """表格数据处理。

    【Java→Python】参数来源是 ServletRequest（ThreadLocal 中的当前请求）。
    Python 侧由 ServletUtils 模拟“当前请求上下文”（contextvar），方法名保持一致；
    其余逻辑逐行照搬：toInt(参数, 1) / toInt(参数, 10) 的默认值不可省略。
    """

    PAGE_NUM = "pageNum"                # 当前记录起始索引
    PAGE_SIZE = "pageSize"              # 每页显示记录数
    ORDER_BY_COLUMN = "orderByColumn"   # 排序列
    IS_ASC = "isAsc"                    # 排序的方向 "desc" 或者 "asc"
    REASONABLE = "reasonable"           # 分页参数合理化

    @staticmethod
    def getPageDomain() -> PageDomain:
        page_domain = PageDomain()
        page_domain.setPageNum(Convert.toInt(ServletUtils.getParameter(TableSupport.PAGE_NUM), 1))
        page_domain.setPageSize(Convert.toInt(ServletUtils.getParameter(TableSupport.PAGE_SIZE), 10))
        page_domain.setOrderByColumn(ServletUtils.getParameter(TableSupport.ORDER_BY_COLUMN))
        page_domain.setIsAsc(ServletUtils.getParameter(TableSupport.IS_ASC))
        page_domain.setReasonable(ServletUtils.getParameterToBool(TableSupport.REASONABLE))
        return page_domain

    @staticmethod
    def buildPageRequest() -> PageDomain:
        return TableSupport.getPageDomain()
