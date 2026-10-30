# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsRtSzdnSnapshotFlowStationcaptureAddcodeController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowStationcaptureAddcodeController.java

收费站抓拍Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/stationcapture`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl()``）。
3) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留。
4) ``@PathVariable("bigId") Long bigId`` → Python ``int``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import \
    OdsRtSzdnSnapshotFlowStationcaptureAddcode
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService import \
    IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl import \
    OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsRtSzdnSnapshotFlowStationcaptureAddcodeController"]


class OdsRtSzdnSnapshotFlowStationcaptureAddcodeController(BaseController):
    """收费站抓拍Controller。"""

    # Java: @RequestMapping("/base/stationcapture")
    BASE_PATH = "/base/stationcapture"

    def __init__(self,
                 odsRtSzdnSnapshotFlowStationcaptureAddcodeService:
                 Optional[IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService ...;
        self.odsRtSzdnSnapshotFlowStationcaptureAddcodeService = (
            odsRtSzdnSnapshotFlowStationcaptureAddcodeService
            or OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl())

    def list(self,
             odsRtSzdnSnapshotFlowStationcaptureAddcode:
             OdsRtSzdnSnapshotFlowStationcaptureAddcode) -> TableDataInfo:
        """查询收费站抓拍列表（GET /base/stationcapture/list）。"""
        self.startPage()
        # odsRtSzdnSnapshotFlowStationcaptureAddcode.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsRtSzdnSnapshotFlowStationcaptureAddcodeService \
            .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(
                odsRtSzdnSnapshotFlowStationcaptureAddcode)
        return self.getDataTable(list_)

    def getInfo(self, bigId: int) -> AjaxResult:
        """获取收费站抓拍详细信息（GET /base/stationcapture/{bigId}）。"""
        return AjaxResult.success(
            self.odsRtSzdnSnapshotFlowStationcaptureAddcodeService
            .selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(bigId))
