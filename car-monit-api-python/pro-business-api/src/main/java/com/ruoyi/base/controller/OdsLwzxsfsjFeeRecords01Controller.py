# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsLwzxsfsjFeeRecords01Controller

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java

基础-收费流水Controller

【Java→Python】关键差异
1) 路由前缀 ``/base/feerecords`` → 类常量 ``BASE_PATH``。
2) 三个 ``@Autowired``（收费流水 service + 门架 service + ``RedisCache``）→ 构造器注入，
   缺省分别 ``OdsLwzxsfsjFeeRecords01ServiceImpl()`` / ``OdsSzdnGantryServiceImpl()`` /
   ``RedisCache()``。
3) ``vehicleplate.indexOf("_") > -1`` → ``"_" in vehicleplate``。
4) ``vehicleplate.split("_")`` + ``[0]`` → ``_java_split("_", vehicleplate)[0]``：
   **Java 的 split 是正则且丢弃尾部空串**（``"A12345_1".split("_")`` → ``["A12345","1"]``，
   ``"A12345_".split("_")`` → ``["A12345"]``）。若车牌只有 ``"_"``，Java 抛
   ``ArrayIndexOutOfBoundsException``，Python 的 ``[0]`` 抛 ``IndexError``（等价失败）。
5) ``new HashMap<>()`` → ``dict``；``containsKey`` → ``in``；``get`` → ``[]``。
6) ``Arrays.stream(x.split(",")).collect(Collectors.toList())`` → ``_java_split(",", x)``。
   注意本类**不像** SnapshotFlowAddcode 那样把 sectioncode/code 清空，
   Java 原样保留（仅设置 List），此处同样保留。
7) ``System.out.println("查询范围参数："+dataQuery)`` → ``print(...)``，仅 ``list`` 里有；
   ``listToExport`` 没有（Java 原样如此）。
8) HashMap 变量名原拼写 ``gantryMao``（源码笔误，不是 Map）→ 保留原名。
9) **getInfo 返回裸实体**（Java 未包 AjaxResult）→ Python 同样直接返回实体。
10) 局部变量 ``list`` → ``list_``；``null != list && list.size() > 0`` → ``list_`` 真值判断。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service import \
    IOdsLwzxsfsjFeeRecords01Service
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl import \
    OdsLwzxsfsjFeeRecords01ServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils import CommonUtil
from com.ruoyi.common.utils.DateUtils import DateUtils
from com.ruoyi.common.utils.StringUtils import _java_split

__all__ = ["OdsLwzxsfsjFeeRecords01Controller"]


class OdsLwzxsfsjFeeRecords01Controller(BaseController):
    """基础-收费流水Controller。"""

    # Java: @RequestMapping("/base/feerecords")
    BASE_PATH = "/base/feerecords"

    def __init__(self,
                 odsLwzxsfsjFeeRecords01Service:
                 Optional[IOdsLwzxsfsjFeeRecords01Service] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsLwzxsfsjFeeRecords01Service odsLwzxsfsjFeeRecords01Service;
        self.odsLwzxsfsjFeeRecords01Service = (
            odsLwzxsfsjFeeRecords01Service or OdsLwzxsfsjFeeRecords01ServiceImpl())
        # Java: @Autowired private IOdsSzdnGantryService odsSzdnGantryService;
        self.odsSzdnGantryService = odsSzdnGantryService or OdsSzdnGantryServiceImpl()
        # Java: @Autowired private RedisCache redisCache;
        self.redisCache = redisCache or RedisCache()

    def list(self, odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01) -> TableDataInfo:
        """查询基础-收费流水列表（GET /base/feerecords/list）。"""
        self.startPage()

        queryQx = "noall"
        # 查询范围
        dataQuery = CommonUtil.isNull(self.redisCache.getCacheObject("sys_config:data_query"))
        print("查询范围参数：" + dataQuery)
        if CommonUtil.isNotBlank(dataQuery):
            queryQx = dataQuery

        if queryQx != "queryall":
            # 权限只能查询吉安东
            vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate()
            if CommonUtil.isBlank(vehicleplateQuery):
                odsLwzxsfsjFeeRecords01.setFlag("JiAnDong")

        # 路段
        sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr()
        if CommonUtil.isNotBlank(sectionCodeStr):
            # Java: Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList())
            odsLwzxsfsjFeeRecords01.setSectionList(_java_split(",", sectionCodeStr))

        # 门架
        code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode())
        if CommonUtil.isNotBlank(code):
            # 服务区 收费站
            odsLwzxsfsjFeeRecords01.setCodeList(_java_split(",", code))
            odsLwzxsfsjFeeRecords01.setCode("")  # 查询范围

        list_ = self.odsLwzxsfsjFeeRecords01Service \
            .selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01)

        if list_ is not None and len(list_) > 0:

            gantryList: List[OdsSzdnGantry] = self.odsSzdnGantryService.getGantryRedis()
            # Java 源码变量名就是 gantryMao（Map 的笔误），保留原名
            gantryMao: Dict[str, OdsSzdnGantry] = {}
            for rtnOdsSzdnGantry in gantryList:
                gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())] = rtnOdsSzdnGantry

            for feeRecords in list_:
                vehicleplate = CommonUtil.isNull(feeRecords.getVehicleplate())
                if "_" in vehicleplate:
                    vehicleplateStr = _java_split("_", vehicleplate)
                    # Java: vehicleplateStr[0]（越界即抛 ArrayIndexOutOfBoundsException）
                    feeRecords.setVehicleplate(vehicleplateStr[0])
                    # Java 原文此处被块注释：
                    #   if (vehicleplateStr.length > 1) {
                    #       feeRecords.setPlateColor(vehicleplateStr[1]);
                    #   }

                # 计费交易时间
                if feeRecords.getTranstime() is not None:
                    feeRecords.setTranstimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getTranstime()))

                # 计费交易时间
                if feeRecords.getLastgantrytime() is not None:
                    feeRecords.setLastgantrytimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getLastgantrytime()))

                gantryid = CommonUtil.isNull(feeRecords.getGantryid())
                if gantryid in gantryMao:
                    gantry = gantryMao[gantryid]
                    feeRecords.setGantryName(gantry.getGantryName())  # 门架名称
                    feeRecords.setSectionCodeStr(gantry.getSectionCode())  # 路线编号

        return self.getDataTable(list_)

    def listToExport(self,
                     odsLwzxsfsjFeeRecords01: OdsLwzxsfsjFeeRecords01
                     ) -> List[OdsLwzxsfsjFeeRecords01]:
        """导出基础-收费流水列表（GET /base/feerecords/listToExport）。

        【Java→Python】返回**裸 List**（Java 不包 TableDataInfo）。前置处理与 list()
        在 Java 中是整段复制的（只少一行 println），此处同样保留重复代码。
        """
        self.startPage()

        queryQx = "noall"
        dataQuery = CommonUtil.isNull(self.redisCache.getCacheObject("sys_config:data_query"))
        if CommonUtil.isNotBlank(dataQuery):
            queryQx = dataQuery

        if queryQx != "queryall":
            # 权限只能查询吉安东
            vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate()
            if CommonUtil.isBlank(vehicleplateQuery):
                odsLwzxsfsjFeeRecords01.setFlag("JiAnDong")

        # 路段
        sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr()
        if CommonUtil.isNotBlank(sectionCodeStr):
            odsLwzxsfsjFeeRecords01.setSectionList(_java_split(",", sectionCodeStr))

        # 门架
        code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode())
        if CommonUtil.isNotBlank(code):
            # 服务区 收费站
            odsLwzxsfsjFeeRecords01.setCodeList(_java_split(",", code))
            odsLwzxsfsjFeeRecords01.setCode("")  # 查询范围

        list_ = self.odsLwzxsfsjFeeRecords01Service \
            .selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01)

        if list_ is not None and len(list_) > 0:

            gantryList: List[OdsSzdnGantry] = self.odsSzdnGantryService.getGantryRedis()
            gantryMao: Dict[str, OdsSzdnGantry] = {}
            for rtnOdsSzdnGantry in gantryList:
                gantryMao[CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode())] = rtnOdsSzdnGantry

            for feeRecords in list_:
                vehicleplate = CommonUtil.isNull(feeRecords.getVehicleplate())
                if "_" in vehicleplate:
                    vehicleplateStr = _java_split("_", vehicleplate)
                    feeRecords.setVehicleplate(vehicleplateStr[0])
                    # Java 原文此处被块注释：
                    #   if (vehicleplateStr.length > 1) {
                    #       feeRecords.setPlateColor(vehicleplateStr[1]);
                    #   }

                # 计费交易时间
                if feeRecords.getTranstime() is not None:
                    feeRecords.setTranstimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getTranstime()))

                # 计费交易时间
                if feeRecords.getLastgantrytime() is not None:
                    feeRecords.setLastgantrytimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getLastgantrytime()))

                gantryid = CommonUtil.isNull(feeRecords.getGantryid())
                if gantryid in gantryMao:
                    gantry = gantryMao[gantryid]
                    feeRecords.setGantryName(gantry.getGantryName())  # 门架名称
                    feeRecords.setSectionCodeStr(gantry.getSectionCode())  # 路线编号

        return list_

    def getInfo(self, bigId: str) -> OdsLwzxsfsjFeeRecords01:
        """获取基础-收费流水详细信息（GET /base/feerecords/{bigId}）。

        【Java→Python】Java 返回**裸实体**（不经 AjaxResult 包装），Python 保持一致。
        """
        return self.odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01ById(bigId)
