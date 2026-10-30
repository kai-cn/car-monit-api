# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnGantryController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryController.java

门架信息Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/gantry`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsSzdnGantryServiceImpl()``）。
3) ``@GetMapping(value = "/listAll")`` 返回**裸 List**（不包 TableDataInfo）：
   Python 同样直接返回列表对象，由 Web 框架序列化。
4) ``@PathVariable("id") String id`` → Python ``str``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnGantryController"]


class OdsSzdnGantryController(BaseController):
    """门架信息Controller。"""

    # Java: @RequestMapping("/base/gantry")
    BASE_PATH = "/base/gantry"

    def __init__(self, odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnGantryService odsSzdnGantryService;
        self.odsSzdnGantryService = odsSzdnGantryService or OdsSzdnGantryServiceImpl()

    def list(self, odsSzdnGantry: OdsSzdnGantry) -> TableDataInfo:
        """查询门架信息列表（GET /base/gantry/list）。"""
        self.startPage()
        list_ = self.odsSzdnGantryService.selectOdsSzdnGantryList(odsSzdnGantry)
        return self.getDataTable(list_)

    def getInfo(self, id: str) -> AjaxResult:
        """获取门架信息详细信息（GET /base/gantry/{id}）。"""
        return AjaxResult.success(self.odsSzdnGantryService.selectOdsSzdnGantryById(id))

    def getListAll(self) -> List[OdsSzdnGantry]:
        """获取门架信息列表（GET /base/gantry/listAll）。"""
        return self.odsSzdnGantryService.selectOdsSzdnGantryList(OdsSzdnGantry())
