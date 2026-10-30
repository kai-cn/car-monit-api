# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnGantryIpController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnGantryIpController.java

省界设备ipController

【Java→Python】关键差异
1) 路由前缀 ``/base/gantryIp`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsSzdnGantryIpServiceImpl()``）。
3) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留。
4) ``@PathVariable("id") Long id`` → Python ``int``（该表主键是数字 id）。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl import OdsSzdnGantryIpServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnGantryIpController"]


class OdsSzdnGantryIpController(BaseController):
    """省界设备ipController。"""

    # Java: @RequestMapping("/base/gantryIp")
    BASE_PATH = "/base/gantryIp"

    def __init__(self, odsSzdnGantryIpService: Optional[IOdsSzdnGantryIpService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnGantryIpService odsSzdnGantryIpService;
        self.odsSzdnGantryIpService = odsSzdnGantryIpService or OdsSzdnGantryIpServiceImpl()

    def list(self, odsSzdnGantryIp: OdsSzdnGantryIp) -> TableDataInfo:
        """查询省界设备ip列表（GET /base/gantryIp/list）。"""
        self.startPage()
        # odsSzdnGantryIp.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsSzdnGantryIpService.selectOdsSzdnGantryIpList(odsSzdnGantryIp)
        return self.getDataTable(list_)

    def getInfo(self, id: int) -> AjaxResult:
        """获取省界设备ip详细信息（GET /base/gantryIp/{id}）。"""
        return AjaxResult.success(self.odsSzdnGantryIpService.selectOdsSzdnGantryIpById(id))
