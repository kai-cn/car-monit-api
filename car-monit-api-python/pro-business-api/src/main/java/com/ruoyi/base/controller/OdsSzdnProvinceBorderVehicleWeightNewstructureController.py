# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsSzdnProvinceBorderVehicleWeightNewstructureController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsSzdnProvinceBorderVehicleWeightNewstructureController.java

省界称重Controller

【Java→Python】关键差异（本文件有一个“假路径变量”的坑）
1) 路由前缀 ``/base/vehicleweight`` → 类常量 ``BASE_PATH``。
2) **``@PathVariable("dataSource") String dataSource`` 并不是主键**：
   Java 把它当作 ``selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(dataSource)``
   的入参 —— 即“路径段传 dataSource 值去做 byId 查询”（原工程的字段/主键命名不一致，
   忠实保留，不做纠正）。
3) ``@GetMapping("/map")`` 是**无参**接口，内部硬编码两个 uuid 逗号串调用
   ``selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(...)``（原样保留）。
4) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import \
    OdsSzdnProvinceBorderVehicleWeightNewstructure
from com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService import \
    IOdsSzdnProvinceBorderVehicleWeightNewstructureService
from com.ruoyi.base.service.impl.OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl import \
    OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsSzdnProvinceBorderVehicleWeightNewstructureController"]

# /map 接口里硬编码的两个 uuid（原工程写死在 Controller 中）
_MAP_QUERY_UUIDS = "18f8e2af-6ebe-4b33-8f37-a688f441de37,7379e7aa-e325-449b-9728-b8f6940c77f1"


class OdsSzdnProvinceBorderVehicleWeightNewstructureController(BaseController):
    """省界称重Controller。"""

    # Java: @RequestMapping("/base/vehicleweight")
    BASE_PATH = "/base/vehicleweight"

    def __init__(self,
                 odsSzdnProvinceBorderVehicleWeightNewstructureService:
                 Optional[IOdsSzdnProvinceBorderVehicleWeightNewstructureService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsSzdnProvinceBorderVehicleWeightNewstructureService ...;
        self.odsSzdnProvinceBorderVehicleWeightNewstructureService = (
            odsSzdnProvinceBorderVehicleWeightNewstructureService
            or OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl())

    def list(self,
             odsSzdnProvinceBorderVehicleWeightNewstructure:
             OdsSzdnProvinceBorderVehicleWeightNewstructure) -> TableDataInfo:
        """查询省界称重列表（GET /base/vehicleweight/list）。"""
        self.startPage()
        # odsSzdnProvinceBorderVehicleWeightNewstructure.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsSzdnProvinceBorderVehicleWeightNewstructureService \
            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(
                odsSzdnProvinceBorderVehicleWeightNewstructure)
        return self.getDataTable(list_)

    def getInfo(self, dataSource: str) -> AjaxResult:
        """获取省界称重详细信息（GET /base/vehicleweight/{dataSource}）。

        【Java→Python】路径变量名是 dataSource，但被当作 byId 的查询值使用 —— 原工程如此。
        """
        return AjaxResult.success(
            self.odsSzdnProvinceBorderVehicleWeightNewstructureService
            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(dataSource))

    def map(self) -> AjaxResult:
        """按固定 uuid 列表查询（GET /base/vehicleweight/map）。

        【Java→Python】Java 里 uuid 串直接写死在方法体中；Python 提到模块常量，
        值完全一致。注意 ``ByQueryUuids`` 接收的是**逗号分隔字符串**，不是列表。
        """
        return AjaxResult.success(
            self.odsSzdnProvinceBorderVehicleWeightNewstructureService
            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(_MAP_QUERY_UUIDS))
