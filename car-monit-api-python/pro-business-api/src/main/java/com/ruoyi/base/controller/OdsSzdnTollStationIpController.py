# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnTollStationIpController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnTollStationIpController.java

收费站ipController

【Java→Python】关键差异
1) 路由前缀 ``/base/tollStationIp`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsSzdnTollStationIpServiceImpl()``）。
3) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留。
4) ``@PathVariable("id") Long id`` → Python ``int``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl import \
    OdsSzdnTollStationIpServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnTollStationIpController"]


class OdsSzdnTollStationIpController(BaseController):
    """收费站ipController。"""

    # Java: @RequestMapping("/base/tollStationIp")
    BASE_PATH = "/base/tollStationIp"

    def __init__(self,
                 odsSzdnTollStationIpService: Optional[IOdsSzdnTollStationIpService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnTollStationIpService odsSzdnTollStationIpService;
        self.odsSzdnTollStationIpService = (
            odsSzdnTollStationIpService or OdsSzdnTollStationIpServiceImpl())

    def list(self, odsSzdnTollStationIp: OdsSzdnTollStationIp) -> TableDataInfo:
        """查询收费站ip列表（GET /base/tollStationIp/list）。"""
        self.startPage()
        # odsSzdnTollStationIp.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsSzdnTollStationIpService.selectOdsSzdnTollStationIpList(odsSzdnTollStationIp)
        return self.getDataTable(list_)

    def getInfo(self, id: int) -> AjaxResult:
        """获取收费站ip详细信息（GET /base/tollStationIp/{id}）。"""
        return AjaxResult.success(self.odsSzdnTollStationIpService.selectOdsSzdnTollStationIpById(id))
