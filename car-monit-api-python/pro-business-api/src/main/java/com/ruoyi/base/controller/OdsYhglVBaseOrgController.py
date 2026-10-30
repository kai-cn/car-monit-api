# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsYhglVBaseOrgController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsYhglVBaseOrgController.java

机构信息Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/org`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsYhglVBaseOrgServiceImpl()``）。
3) ``/listAll`` 返回**裸 List**（Java 不包 TableDataInfo）→ Python 直接返回列表。
4) ``@PathVariable("bigId") String bigId`` → Python ``str``。
5) 局部变量 ``list`` → ``list_``。
6) Java 第 53 行 ``return  odsYhglVBaseOrgService...``（return 后两个空格）为源码原样
   排版瑕疵，Python 语法上无意义，此处忠实保留行为、注释标注。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.OdsYhglVBaseOrg import OdsYhglVBaseOrg
from com.ruoyi.base.service.IOdsYhglVBaseOrgService import IOdsYhglVBaseOrgService
from com.ruoyi.base.service.impl.OdsYhglVBaseOrgServiceImpl import OdsYhglVBaseOrgServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsYhglVBaseOrgController"]


class OdsYhglVBaseOrgController(BaseController):
    """机构信息Controller。"""

    # Java: @RequestMapping("/base/org")
    BASE_PATH = "/base/org"

    def __init__(self, odsYhglVBaseOrgService: Optional[IOdsYhglVBaseOrgService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsYhglVBaseOrgService odsYhglVBaseOrgService;
        self.odsYhglVBaseOrgService = odsYhglVBaseOrgService or OdsYhglVBaseOrgServiceImpl()

    def list(self, odsYhglVBaseOrg: OdsYhglVBaseOrg) -> TableDataInfo:
        """查询机构信息列表（GET /base/org/list）。"""
        self.startPage()
        list_ = self.odsYhglVBaseOrgService.selectOdsYhglVBaseOrgList(odsYhglVBaseOrg)
        return self.getDataTable(list_)

    def getInfo(self, bigId: str) -> AjaxResult:
        """获取机构信息详细信息（GET /base/org/{bigId}）。"""
        return AjaxResult.success(self.odsYhglVBaseOrgService.selectOdsYhglVBaseOrgById(bigId))

    def getListAll(self) -> List[OdsYhglVBaseOrg]:
        """获取机构信息列表（GET /base/org/listAll）。"""
        # Java 原文：return  odsYhglVBaseOrgService.selectOdsYhglVBaseOrgList(new OdsYhglVBaseOrg());
        return self.odsYhglVBaseOrgService.selectOdsYhglVBaseOrgList(OdsYhglVBaseOrg())
