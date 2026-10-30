# -*- coding: utf-8 -*-
"""com.ruoyi.base.controller.ProgressiveQueryController

源文件：pro-business-api/src/main/java/com/ruoyi/base/controller/ProgressiveQueryController.java

渐进式查询架构 Controller —— 为 3 张核心大表按数据量级别自动选择最优查询策略。

接口说明 / API Description:
  1. GET /progressive/snapshotflow/list  - 门架抓拍流水渐进式查询
  2. GET /progressive/feerecords/list    - 收费流水渐进式查询
  3. GET /progressive/trailfitting/list  - 车辆轨迹渐进式查询
  4. GET /progressive/scale-level        - 查看当前数据量级别

【Java→Python】关键差异
1) 路由前缀 ``/progressive`` → 类常量 ``BASE_PATH``（类**不继承** BaseController，与 Java 一致）。
2) ``@Slf4j`` → 模块级 ``log``（本类实际未打日志，保留以对齐结构）。
3) ``@Autowired ProgressiveQueryArchitectureService`` → 构造器注入，缺省同包实现实例。
4) Java 的**静态内部类** ``QueryRequest`` / ``QueryResult`` / ``DataScaleLevel``
   定义在 ``ProgressiveQueryArchitectureService`` 内，Python 侧同样是该模块的类
   （``from ... import QueryRequest, QueryResult``）。
5) ``@RequestParam(defaultValue = "20") int pageSize`` → 方法参数默认值 ``pageSize: int = 20``。
6) ``getDataTable((List<?>) result.getData())`` → 直接 ``self.getDataTable(result.getData())``
   （Python 无泛型强转；getData() 已返回 list）。
7) ``new java.util.LinkedHashMap<>()`` → ``dict``（Python 3.7+ 字典保持插入顺序，
   与 LinkedHashMap 一致）。
8) ``.name()``（枚举名）→ ``DataScaleLevel.name()``：服务类里的 ``name()`` 是
   普通方法（覆盖了 Enum 的 ``name`` 属性），必须**带括号**调用。
   注意 ``UnifiedQueryService.DataSource`` 没有定义 ``name()``，那里才是
   不加括号的 ``ds.name`` 属性，两个枚举约定不同，按各自实现照抄。
9) 三个查询方法的前 10 个参数构建逻辑在 Java 中是重复的，Python 同样保留重复。
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService import (
    DataScaleLevel,
    ProgressiveQueryArchitectureService,
    QueryRequest,
    QueryResult,
)
from com.ruoyi.common.core.controller.BaseController import BaseController
from com.ruoyi.common.core.domain.AjaxResult import AjaxResult
from com.ruoyi.common.core.page.TableDataInfo import TableDataInfo

__all__ = ["ProgressiveQueryController"]


class ProgressiveQueryController(BaseController):
    """渐进式查询Controller。"""

    # Java: @RequestMapping("/progressive")
    BASE_PATH = "/progressive"

    def __init__(self,
                 progressiveQueryService: Optional[ProgressiveQueryArchitectureService] = None
                 ) -> None:
        super().__init__()
        # Java: @Autowired private ProgressiveQueryArchitectureService progressiveQueryService;
        self.progressiveQueryService = (
            progressiveQueryService or ProgressiveQueryArchitectureService())

    def snapshotFlowList(self,
                         startTime: Optional[str] = None,
                         endTime: Optional[str] = None,
                         platenumber: Optional[str] = None,
                         gantryname: Optional[str] = None,
                         roadname: Optional[str] = None,
                         sectionname: Optional[str] = None,
                         orgname: Optional[str] = None,
                         tollname: Optional[str] = None,
                         cursor: Optional[str] = None,
                         pageSize: int = 20) -> TableDataInfo:
        """门架抓拍流水渐进式查询（GET /progressive/snapshotflow/list）。"""
        # 构建统一查询请求 / Build unified query request
        request = QueryRequest()
        request.setStartTime(startTime)
        request.setEndTime(endTime)
        request.setPlatenumber(platenumber)
        request.setGantryname(gantryname)
        request.setRoadname(roadname)
        request.setSectionname(sectionname)
        request.setOrgname(orgname)
        request.setTollname(tollname)
        request.setCursor(cursor)
        request.setPageSize(pageSize)

        # 执行渐进式查询 / Execute progressive query
        result: QueryResult = self.progressiveQueryService.querySnapshotFlow(request)

        # 封装分页结果 / Wrap paginated result
        tableData = self.getDataTable(result.getData())
        tableData.setMsg("策略: " + result.getStrategy())
        return tableData

    def feeRecordsList(self,
                       startTime: Optional[str] = None,
                       endTime: Optional[str] = None,
                       platenumber: Optional[str] = None,
                       gantryname: Optional[str] = None,
                       roadname: Optional[str] = None,
                       sectionname: Optional[str] = None,
                       orgname: Optional[str] = None,
                       tollname: Optional[str] = None,
                       cursor: Optional[str] = None,
                       pageSize: int = 20) -> TableDataInfo:
        """收费流水渐进式查询（GET /progressive/feerecords/list）。"""
        request = QueryRequest()
        request.setStartTime(startTime)
        request.setEndTime(endTime)
        request.setPlatenumber(platenumber)
        request.setGantryname(gantryname)
        request.setRoadname(roadname)
        request.setSectionname(sectionname)
        request.setOrgname(orgname)
        request.setTollname(tollname)
        request.setCursor(cursor)
        request.setPageSize(pageSize)

        result: QueryResult = self.progressiveQueryService.queryFeeRecords(request)

        tableData = self.getDataTable(result.getData())
        tableData.setMsg("策略: " + result.getStrategy())
        return tableData

    def trailFittingList(self,
                         startTime: Optional[str] = None,
                         endTime: Optional[str] = None,
                         platenumber: Optional[str] = None,
                         gantryname: Optional[str] = None,
                         roadname: Optional[str] = None,
                         sectionname: Optional[str] = None,
                         orgname: Optional[str] = None,
                         tollname: Optional[str] = None,
                         cursor: Optional[str] = None,
                         pageSize: int = 20) -> TableDataInfo:
        """车辆轨迹渐进式查询（GET /progressive/trailfitting/list）。"""
        request = QueryRequest()
        request.setStartTime(startTime)
        request.setEndTime(endTime)
        request.setPlatenumber(platenumber)
        request.setGantryname(gantryname)
        request.setRoadname(roadname)
        request.setSectionname(sectionname)
        request.setOrgname(orgname)
        request.setTollname(tollname)
        request.setCursor(cursor)
        request.setPageSize(pageSize)

        result: QueryResult = self.progressiveQueryService.queryTrailFitting(request)

        tableData = self.getDataTable(result.getData())
        tableData.setMsg("策略: " + result.getStrategy())
        return tableData

    def scaleLevel(self) -> AjaxResult:
        """查看当前数据量级别（GET /progressive/scale-level）。"""
        # Java: Map<String, String> levels = new java.util.LinkedHashMap<>();
        levels: dict[str, str] = {}
        levels["ods_rt_szdn_snapshot_flow_addcode"] = self.progressiveQueryService \
            .detectScaleLevel("ods_rt_szdn_snapshot_flow_addcode").name()
        levels["ods_lwzxsfsj_fee_records_01"] = self.progressiveQueryService \
            .detectScaleLevel("ods_lwzxsfsj_fee_records_01").name()
        levels["zdata_trail_fitting"] = self.progressiveQueryService \
            .detectScaleLevel("zdata_trail_fitting").name()
        return AjaxResult.success(levels)
