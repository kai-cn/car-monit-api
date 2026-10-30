# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.OdsRtSzdnSnapshotFlowAddcodeController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java

门架抓拍流水Controller

【Java→Python】关键差异（本类逻辑较重，按 Java 行号顺序列出）
1) 路由前缀 ``/base/snapshotflow`` → 类常量 ``BASE_PATH``。
2) 两个 ``@Autowired``（service + ``RedisCache``）→ 构造器注入，
   缺省分别 ``OdsRtSzdnSnapshotFlowAddcodeServiceImpl()`` / ``RedisCache()``
   （本工程的 RedisCache 替身自带内存存储，无需真实 Redis 即可运行）。
3) ``CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"))``：
   取 Redis 中的“查询范围”配置；Python 调用签名完全一致（CommonUtil 是**模块级函数**）。
4) ``"queryall".equals(queryQx)`` → ``queryQx == "queryall"``：Java 的 ``equals`` 判值，
   Python 的 ``==`` 同样是值比较（不要写成 ``is``）。
5) ``Arrays.stream(x.split(",")).collect(Collectors.toList())`` →
   ``_java_split(",", x)``：**Java 的 split 参数是正则且丢弃尾部空串**
   （``"a,".split(",")`` → ``["a"]``），Python 的 ``str.split`` 会保留尾部空串，
   因此用 StringUtils 里的 ``_java_split`` 保持逐位一致。
6) ``System.out.println("查询范围参数："+dataQuery)`` → ``print(...)``（保留原调试输出）。
   注意：``listToExport`` 里**没有**这行打印，Java 原样如此。
7) ``StringUtils.getUUID()`` 保留原工具类调用（Java: UUID 去横线 32 位）。
8) ``DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, time)`` 签名一致。
9) **getInfo 返回裸实体**（Java 未包 AjaxResult）→ Python 同样直接返回实体。
10) ``list`` 与 ``listToExport`` 的前置处理在 Java 里是**整段复制**的，
    这里同样复制（唯一差别：export 少一行 println、不做图片路径替换）。
"""
from __future__ import annotations

from typing import List, Optional

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import \
    IOdsRtSzdnSnapshotFlowAddcodeService
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import \
    OdsRtSzdnSnapshotFlowAddcodeServiceImpl
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils import CommonUtil
from com.ruoyi.common.utils.DateUtils import DateUtils
from com.ruoyi.common.utils.StringUtils import StringUtils, _java_split

__all__ = ["OdsRtSzdnSnapshotFlowAddcodeController"]


class OdsRtSzdnSnapshotFlowAddcodeController(BaseController):
    """门架抓拍流水Controller。"""

    # Java: @RequestMapping("/base/snapshotflow")
    BASE_PATH = "/base/snapshotflow"

    def __init__(self,
                 odsRtSzdnSnapshotFlowAddcodeService:
                 Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        super().__init__()
        # Java: @Autowired private IOdsRtSzdnSnapshotFlowAddcodeService ...;
        self.odsRtSzdnSnapshotFlowAddcodeService = (
            odsRtSzdnSnapshotFlowAddcodeService or OdsRtSzdnSnapshotFlowAddcodeServiceImpl())
        # Java: @Autowired private RedisCache redisCache;
        self.redisCache = redisCache or RedisCache()

    def list(self, odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode) -> TableDataInfo:
        """查询门架抓拍流水列表（GET /base/snapshotflow/list）。"""
        self.startPage()

        queryQx = "noall"
        # 查询范围（Java: CommonUtil.isNull(...) 把 null 转成 ""）
        dataQuery = CommonUtil.isNull(self.redisCache.getCacheObject("sys_config:data_query"))
        print("查询范围参数：" + dataQuery)
        if CommonUtil.isNotBlank(dataQuery):
            queryQx = dataQuery

        if queryQx != "queryall":
            platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber()
            if CommonUtil.isBlank(platenumber):
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong")

        # 路段
        sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr()
        if CommonUtil.isNotBlank(sectionCodeStr):
            # Java: Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList())
            odsRtSzdnSnapshotFlowAddcode.setSectionList(_java_split(",", sectionCodeStr))
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("")

        # 门架
        code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode())
        if CommonUtil.isNotBlank(code):
            # 服务区 收费站
            odsRtSzdnSnapshotFlowAddcode.setCodeList(_java_split(",", code))
            odsRtSzdnSnapshotFlowAddcode.setCode("")  # 查询范围

        list_ = self.odsRtSzdnSnapshotFlowAddcodeService \
            .selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode)
        if list_ is not None and len(list_) > 0:
            for rtn in list_:
                rtn.setId(StringUtils.getUUID())
                # 抓拍时间格式化
                if rtn.getSnapshottime() is not None:
                    rtn.setSnapshottimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()))
                # 图片路径替换
                imagesArry = CommonUtil.deleteEnd(rtn.getSnappicturepath())
                rtn.setSnappicturepath(CommonUtil.repalacePicUrl(imagesArry))
        return self.getDataTable(list_)

    def listToExport(self,
                     odsRtSzdnSnapshotFlowAddcode: OdsRtSzdnSnapshotFlowAddcode
                     ) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """导出门架抓拍流水列表（GET /base/snapshotflow/listToExport）。

        【Java→Python】返回**裸 List**（Java 不包 TableDataInfo）。前置处理与 list()
        在 Java 中是整段复制的，此处同样保留重复代码，便于与源码逐行对照。
        """
        self.startPage()

        queryQx = "noall"
        dataQuery = CommonUtil.isNull(self.redisCache.getCacheObject("sys_config:data_query"))
        if CommonUtil.isNotBlank(dataQuery):
            queryQx = dataQuery

        if queryQx != "queryall":
            platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber()
            if CommonUtil.isBlank(platenumber):
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong")

        # 路段
        sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr()
        if CommonUtil.isNotBlank(sectionCodeStr):
            odsRtSzdnSnapshotFlowAddcode.setSectionList(_java_split(",", sectionCodeStr))
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("")

        # 门架
        code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode())
        if CommonUtil.isNotBlank(code):
            # 服务区 收费站
            odsRtSzdnSnapshotFlowAddcode.setCodeList(_java_split(",", code))
            odsRtSzdnSnapshotFlowAddcode.setCode("")  # 查询范围

        list_ = self.odsRtSzdnSnapshotFlowAddcodeService \
            .selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode)
        if list_ is not None and len(list_) > 0:
            for rtn in list_:
                rtn.setId(StringUtils.getUUID())
                # 抓拍时间格式化
                if rtn.getSnapshottime() is not None:
                    rtn.setSnapshottimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()))
        return list_

    def getInfo(self, bigId: str) -> OdsRtSzdnSnapshotFlowAddcode:
        """获取门架抓拍流水详细信息（GET /base/snapshotflow/{bigId}）。

        【Java→Python】Java 返回**裸实体**（不经 AjaxResult 包装），Python 保持一致。
        """
        return self.odsRtSzdnSnapshotFlowAddcodeService \
            .selectOdsRtSzdnSnapshotFlowAddcodeById(bigId)
