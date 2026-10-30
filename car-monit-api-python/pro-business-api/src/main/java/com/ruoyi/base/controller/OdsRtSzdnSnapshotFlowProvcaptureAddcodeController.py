# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsRtSzdnSnapshotFlowProvcaptureAddcodeController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowProvcaptureAddcodeController.java

省界抓拍Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/provcapture`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl()``）。
3) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留。
4) ``@PathVariable("bigId") Long bigId`` → Python ``int``。
5) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode import \
    OdsRtSzdnSnapshotFlowProvcaptureAddcode
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService import \
    IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl import \
    OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsRtSzdnSnapshotFlowProvcaptureAddcodeController"]


class OdsRtSzdnSnapshotFlowProvcaptureAddcodeController(BaseController):
    """省界抓拍Controller。"""

    # Java: @RequestMapping("/base/provcapture")
    BASE_PATH = "/base/provcapture"

    def __init__(self,
                 odsRtSzdnSnapshotFlowProvcaptureAddcodeService:
                 Optional[IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService ...;
        self.odsRtSzdnSnapshotFlowProvcaptureAddcodeService = (
            odsRtSzdnSnapshotFlowProvcaptureAddcodeService
            or OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl())

    def list(self,
             odsRtSzdnSnapshotFlowProvcaptureAddcode: OdsRtSzdnSnapshotFlowProvcaptureAddcode
             ) -> TableDataInfo:
        """查询省界抓拍列表（GET /base/provcapture/list）。"""
        self.startPage()
        # odsRtSzdnSnapshotFlowProvcaptureAddcode.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.odsRtSzdnSnapshotFlowProvcaptureAddcodeService \
            .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(
                odsRtSzdnSnapshotFlowProvcaptureAddcode)
        return self.getDataTable(list_)

    def getInfo(self, bigId: int) -> AjaxResult:
        """获取省界抓拍详细信息（GET /base/provcapture/{bigId}）。"""
        return AjaxResult.success(
            self.odsRtSzdnSnapshotFlowProvcaptureAddcodeService
            .selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(bigId))
