# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsLwzxsfsjFeeStationExit01Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeStationExit01Controller.java

收费站出口流水Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/feestationexit``（全小写，注意与 Enter 的驼峰写法不一致）→ ``BASE_PATH``。
2) ``@Autowired`` → 构造器注入（缺省 ``OdsLwzxsfsjFeeStationExit01ServiceImpl()``）。
3) ``@PathVariable("bigId") String bigId`` → Python ``str``（注意这里是 String，
   而同类 Enter 接口是 Long，原工程两种主键类型混用）。
4) 局部变量 ``list`` → ``list_``。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01
from com.ruoyi.base.service.IOdsLwzxsfsjFeeStationExit01Service import \
    IOdsLwzxsfsjFeeStationExit01Service
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeStationExit01ServiceImpl import \
    OdsLwzxsfsjFeeStationExit01ServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["OdsLwzxsfsjFeeStationExit01Controller"]


class OdsLwzxsfsjFeeStationExit01Controller(BaseController):
    """收费站出口流水Controller。"""

    # Java: @RequestMapping("/base/feestationexit")
    BASE_PATH = "/base/feestationexit"

    def __init__(self,
                 odsLwzxsfsjFeeStationExit01Service:
                 Optional[IOdsLwzxsfsjFeeStationExit01Service] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsLwzxsfsjFeeStationExit01Service ...;
        self.odsLwzxsfsjFeeStationExit01Service = (
            odsLwzxsfsjFeeStationExit01Service or OdsLwzxsfsjFeeStationExit01ServiceImpl())

    def list(self, odsLwzxsfsjFeeStationExit01: OdsLwzxsfsjFeeStationExit01) -> TableDataInfo:
        """查询收费站出口流水列表（GET /base/feestationexit/list）。"""
        self.startPage()
        list_ = self.odsLwzxsfsjFeeStationExit01Service \
            .selectOdsLwzxsfsjFeeStationExit01List(odsLwzxsfsjFeeStationExit01)
        return self.getDataTable(list_)

    def getInfo(self, bigId: str) -> AjaxResult:
        """获取收费站出口流水详细信息（GET /base/feestationexit/{bigId}）。"""
        return AjaxResult.success(
            self.odsLwzxsfsjFeeStationExit01Service
            .selectOdsLwzxsfsjFeeStationExit01ById(bigId))
