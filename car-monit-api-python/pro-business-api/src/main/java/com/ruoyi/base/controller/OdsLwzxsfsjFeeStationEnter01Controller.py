# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsLwzxsfsjFeeStationEnter01Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeStationEnter01Controller.java

收费站入口数据Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/feeStationEnter`` → 类常量 ``BASE_PATH``（无 Web 容器，不自动注册）。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsLwzxsfsjFeeStationEnter01ServiceImpl()``）。
3) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留为注释。
4) ``@PathVariable("bigId") Long bigId`` → Python ``int``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationEnter01Service import \
    IOdsLwzxsfsjFeeStationEnter01Service
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationEnter01ServiceImpl import \
    OdsLwzxsfsjFeeStationEnter01ServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsLwzxsfsjFeeStationEnter01Controller"]


class OdsLwzxsfsjFeeStationEnter01Controller(BaseController):
    """收费站入口数据Controller。"""

    # Java: @RequestMapping("/base/feeStationEnter")
    BASE_PATH = "/base/feeStationEnter"

    def __init__(self,
                 odsLwzxsfsjFeeStationEnter01Service:
                 Optional[IOdsLwzxsfsjFeeStationEnter01Service] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsLwzxsfsjFeeStationEnter01Service ...;
        self.odsLwzxsfsjFeeStationEnter01Service = (
            odsLwzxsfsjFeeStationEnter01Service or OdsLwzxsfsjFeeStationEnter01ServiceImpl())

    def list(self, odsLwzxsfsjFeeStationEnter01: OdsLwzxsfsjFeeStationEnter01) -> TableDataInfo:
        """查询收费站入口数据列表（GET /base/feeStationEnter/list）。"""
        self.startPage()
        # odsLwzxsfsjFeeStationEnter01.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsLwzxsfsjFeeStationEnter01Service \
            .selectOdsLwzxsfsjFeeStationEnter01List(odsLwzxsfsjFeeStationEnter01)
        return self.getDataTable(list_)

    def getInfo(self, bigId: int) -> AjaxResult:
        """获取收费站入口数据详细信息（GET /base/feeStationEnter/{bigId}）。"""
        return AjaxResult.success(
            self.odsLwzxsfsjFeeStationEnter01Service
            .selectOdsLwzxsfsjFeeStationEnter01ById(bigId))
