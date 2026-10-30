# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.controller.BaseController

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from com.github.pagehelper.PageInfo import PageInfo
from com.ruoyi.common.constant.HttpStatus import HttpStatus
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.PageDomain import PageDomain
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo
from com.ruoyi.common.core.page.TableSupport import TableSupport
from com.ruoyi.common.utils.DateUtils import DateUtils
from com.ruoyi.common.utils.PageUtils import PageUtils
from com.ruoyi.common.utils.StringUtils import StringUtils
from com.ruoyi.common.utils.sql.SqlUtil import SqlUtil

log = logging.getLogger(__name__)


class BaseController:
    """web 层通用数据处理。

    【Java→Python】
    1) `protected final Logger logger = LoggerFactory.getLogger(this.getClass())` →
       模块级 logger（Python 无“按实例类名”取 logger 的必要）。
    2) @InitBinder 的日期自动转换依赖 Spring MVC 参数绑定，Python Web 框架（FastAPI/Flask）
       没有等价机制；initBinder 保留为“把文本按 DateUtils.parseDate 解析”的工具方法。
    3) toAjax 的 int / boolean 两个重载 → 单方法内先判 bool（Python 中 bool 是 int 子类，
       若不先判 bool，True 会被当成 int 1）。
    4) success()/success(String)/success(Object) 三个重载 → *args 分派，交给 AjaxResult 处理。
    5) `StringUtils.format("redirect:{}", url)` 即 StrFormatter.format。
    6) `new PageInfo(list).getTotal()` → 框架替身 `com.github.pagehelper.PageInfo`
       （原先的私有 `_PageInfo` 已替换为该替身，与 Java 的 import 逐字对应）。
    """

    def __init__(self) -> None:
        self.logger = log

    def initBinder(self, text: Optional[str]) -> Optional[Any]:
        """将前台传递过来的日期格式的字符串，自动转化为 Date 类型。"""
        return DateUtils.parseDate(text)

    def startPage(self) -> None:
        """设置请求分页数据。"""
        PageUtils.startPage()

    def startOrderBy(self) -> None:
        """设置请求排序数据。"""
        page_domain: PageDomain = TableSupport.buildPageRequest()
        if StringUtils.isNotEmpty(page_domain.getOrderBy()):
            order_by = SqlUtil.escapeOrderBySql(page_domain.getOrderBy())
            PageUtils.orderBy(order_by)

    def clearPage(self) -> None:
        """清理分页的线程变量。"""
        PageUtils.clearPage()

    def getDataTable(self, data_list: list[Any]) -> TableDataInfo:
        """响应请求分页数据。"""
        rsp_data = TableDataInfo()
        rsp_data.setCode(HttpStatus.SUCCESS)
        rsp_data.setMsg("查询成功")
        rsp_data.setRows(data_list)
        rsp_data.setTotal(PageInfo(data_list).getTotal())
        return rsp_data

    # ---- 响应封装（Java 重载 → Python 类型分派） --------------------------
    def success(self, *args: Any) -> AjaxResult:
        return AjaxResult.success(*args) if args else AjaxResult.success()

    def error(self, *args: Any) -> AjaxResult:
        return AjaxResult.error(*args) if args else AjaxResult.error()

    def warn(self, message: str) -> AjaxResult:
        return AjaxResult.warn(message)

    def toAjax(self, rows_or_result: Any) -> AjaxResult:
        """对应 toAjax(int rows) 与 toAjax(boolean result) 两个重载。"""
        # 【Java→Python】必须先判 bool：Python 的 True/False 是 int 的子类，
        # 若先按 int 处理，toAjax(true) 会被当作 rows=1 走 success 分支（结果虽同，
        # 但 toAjax(false) 会变成 rows=0 的 error 分支——需显式区分以保持可读性）。
        if isinstance(rows_or_result, bool):
            return self.success() if rows_or_result else self.error()
        return self.success() if int(rows_or_result) > 0 else self.error()

    def redirect(self, url: str) -> str:
        """页面跳转。"""
        return StringUtils.format("redirect:{}", url)
