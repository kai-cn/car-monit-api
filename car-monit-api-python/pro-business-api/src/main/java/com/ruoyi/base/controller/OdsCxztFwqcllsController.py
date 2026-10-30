# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsCxztFwqcllsController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsCxztFwqcllsController.java

服务区车辆流水Controller

【Java→Python】关键差异
1) 路由前缀是 ``/manager/fwqclls``（**不是** /base），保留为类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsCxztFwqcllsServiceImpl()``）。
3) ``@GetMapping("/list")`` 里被注释的
   ``odsCxztFwqclls.setTenantId(SecurityUtils.getTenantId())`` 是原工程遗留：
   **忠实保留为注释**（未启用，多租户过滤实际未生效）。
4) ``@PathVariable("bigId") Long bigId`` → Python ``int``（Java 的 Long）。
5) 局部变量 ``list`` → ``list_``（避免遮蔽内置 ``list``）。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsCxztFwqclls import OdsCxztFwqclls
from com.ruoyi.base.service.IOdsCxztFwqcllsService import IOdsCxztFwqcllsService
from com.ruoyi.base.service.impl.OdsCxztFwqcllsServiceImpl import OdsCxztFwqcllsServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsCxztFwqcllsController"]


class OdsCxztFwqcllsController(BaseController):
    """服务区车辆流水Controller。"""

    # Java: @RequestMapping("/manager/fwqclls")
    BASE_PATH = "/manager/fwqclls"

    def __init__(self, odsCxztFwqcllsService: Optional[IOdsCxztFwqcllsService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsCxztFwqcllsService odsCxztFwqcllsService;
        self.odsCxztFwqcllsService = odsCxztFwqcllsService or OdsCxztFwqcllsServiceImpl()

    def list(self, odsCxztFwqclls: OdsCxztFwqclls) -> TableDataInfo:
        """查询服务区车辆流水列表（GET /manager/fwqclls/list）。"""
        self.startPage()
        # odsCxztFwqclls.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsCxztFwqcllsService.selectOdsCxztFwqcllsList(odsCxztFwqclls)
        return self.getDataTable(list_)

    def getInfo(self, bigId: int) -> AjaxResult:
        """获取服务区车辆流水详细信息（GET /manager/fwqclls/{bigId}）。"""
        return AjaxResult.success(self.odsCxztFwqcllsService.selectOdsCxztFwqcllsById(bigId))
