# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnTollController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnTollController.java

收费站基础信息Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/toll`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsSzdnTollServiceImpl()``）。
3) ``/listAll`` 返回**裸 List** → Python 直接返回列表对象。
4) ``@PathVariable("id") String id`` → Python ``str``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnTollController"]


class OdsSzdnTollController(BaseController):
    """收费站基础信息Controller。"""

    # Java: @RequestMapping("/base/toll")
    BASE_PATH = "/base/toll"

    def __init__(self, odsSzdnTollService: Optional[IOdsSzdnTollService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnTollService odsSzdnTollService;
        self.odsSzdnTollService = odsSzdnTollService or OdsSzdnTollServiceImpl()

    def list(self, odsSzdnToll: OdsSzdnToll) -> TableDataInfo:
        """查询收费站基础信息列表（GET /base/toll/list）。"""
        self.startPage()
        list_ = self.odsSzdnTollService.selectOdsSzdnTollList(odsSzdnToll)
        return self.getDataTable(list_)

    def getInfo(self, id: str) -> AjaxResult:
        """获取收费站基础信息详细信息（GET /base/toll/{id}）。"""
        return AjaxResult.success(self.odsSzdnTollService.selectOdsSzdnTollById(id))

    def getListAll(self) -> List[OdsSzdnToll]:
        """获取收费站基础信息列表（GET /base/toll/listAll）。"""
        return self.odsSzdnTollService.selectOdsSzdnTollList(OdsSzdnToll())
