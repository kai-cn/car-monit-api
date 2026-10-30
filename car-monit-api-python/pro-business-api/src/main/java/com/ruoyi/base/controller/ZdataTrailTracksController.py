# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.ZdataTrailTracksController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/ZdataTrailTracksController.java

轨迹数据Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/trailtracks`` → 类常量 ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``ZdataTrailTracksServiceImpl()``）。
3) 本类**没有** ``/listAll`` 端点（与同批其它 CRUD Controller 不同）。
4) ``@PathVariable("uuid") String uuid`` → Python ``str``（主键名为 uuid，不是 id）。
5) 被注释的 ``setTenantId(SecurityUtils.getTenantId())`` 忠实保留为注释。
6) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService
from com.ruoyi.base.service.impl.ZdataTrailTracksServiceImpl import ZdataTrailTracksServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["ZdataTrailTracksController"]


class ZdataTrailTracksController(BaseController):
    """轨迹数据Controller。"""

    # Java: @RequestMapping("/base/trailtracks")
    BASE_PATH = "/base/trailtracks"

    def __init__(self, zdataTrailTracksService: Optional[IZdataTrailTracksService] = None) -> None:
        super().__init__()
        # Java: @Autowired private IZdataTrailTracksService zdataTrailTracksService;
        self.zdataTrailTracksService = zdataTrailTracksService or ZdataTrailTracksServiceImpl()

    def list(self, zdataTrailTracks: ZdataTrailTracks) -> TableDataInfo:
        """查询轨迹数据列表（GET /base/trailtracks/list）。"""
        self.startPage()
        # zdataTrailTracks.setTenantId(SecurityUtils.getTenantId())  # 查询我自己单位的租户
        list_ = self.zdataTrailTracksService.selectZdataTrailTracksList(zdataTrailTracks)
        return self.getDataTable(list_)

    def getInfo(self, uuid: str) -> AjaxResult:
        """获取轨迹数据详细信息（GET /base/trailtracks/{uuid}）。"""
        return AjaxResult.success(self.zdataTrailTracksService.selectZdataTrailTracksById(uuid))
