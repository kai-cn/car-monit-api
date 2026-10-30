# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnSectionController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnSectionController.java

路段信息Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/section`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsSzdnSectionServiceImpl()``）。
3) ``/listAll`` 返回**裸 List**（Java 不包 TableDataInfo）→ Python 直接返回列表。
4) ``@PathVariable("id") String id`` → Python ``str``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnSectionController"]


class OdsSzdnSectionController(BaseController):
    """路段信息Controller。"""

    # Java: @RequestMapping("/base/section")
    BASE_PATH = "/base/section"

    def __init__(self, odsSzdnSectionService: Optional[IOdsSzdnSectionService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnSectionService odsSzdnSectionService;
        self.odsSzdnSectionService = odsSzdnSectionService or OdsSzdnSectionServiceImpl()

    def list(self, odsSzdnSection: OdsSzdnSection) -> TableDataInfo:
        """查询路段信息列表（GET /base/section/list）。"""
        self.startPage()
        list_ = self.odsSzdnSectionService.selectOdsSzdnSectionList(odsSzdnSection)
        return self.getDataTable(list_)

    def getInfo(self, id: str) -> AjaxResult:
        """获取路段信息详细信息（GET /base/section/{id}）。"""
        return AjaxResult.success(self.odsSzdnSectionService.selectOdsSzdnSectionById(id))

    def getListAll(self) -> List[OdsSzdnSection]:
        """获取路段信息列表（GET /base/section/listAll）。"""
        return self.odsSzdnSectionService.selectOdsSzdnSectionList(OdsSzdnSection())
