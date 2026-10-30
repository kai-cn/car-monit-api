# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.BillionLevelQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/BillionLevelQueryService.java

十亿级数据量查询优化服务 / Billion level query optimization service.

适用场景 / Applicable Scenario:
  单表数据量 > 5亿行，未来3年达到8亿级

核心策略 / Core Strategies:
  1. 冷热分离：热数据（近6个月）留在 GaussDB，冷数据归档 + 同步到 ES
  2. Elasticsearch 全文检索：所有模糊查询、多条件组合查询走 ES
  3. GaussDB 精确查询：有精确等值条件的查询走 GaussDB 分区表
  4. 异步导出：大规模数据导出使用 ES Scroll API 异步拉取
  5. 查询路由：根据查询条件自动路由到 ES 或 GaussDB

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；4 个 `@Value` → 构造器里 `Environment().value(...)`。
2) 3 个 `@Autowired` → 构造器可选参数。**注意 `@Autowired(required = false)`**：
   `ElasticsearchQueryService` 与 `JdbcTemplate` 在容器里可能不存在，因此默认 `None`，
   而不是 `or new Xxx()`；这样 `if self.elasticsearchQueryService is None: return emptyResult()`
   与 `if self.jdbcTemplate is None: return` 两个降级分支都**能被真实触发**。
   `RedisTemplate` 是 `required = true`，默认取共享实例（`defaultRedisTemplate()`）。
3) `public static class QueryRouteRequest`（手写 POJO）→ 模块级
   `@dataclass(JavaBean)`，类属性挂回，保证 `BillionLevelQueryService.QueryRouteRequest`
   的访问路径不变。`getXxx()/setXxx()/isXxx()` 由 JavaBean 动态提供，因此
   `getPlatenumber()` / `isExport()` 等方法无需手写；而
   `hasFuzzyCondition()` / `getTimeRangeDays()` 是**自定义方法**，必须显式实现。
4) **反射**：`getClass().getMethod("queryByConditions", String.class, Map.class, int.class,
   int.class)` + `method.invoke(...)` → Python 没有 Class/Method 反射对象，改用
   `getattr(obj, name, None)` + `callable()` 判定（等价 `NoSuchMethodException` 分支），
   之后直接调用。签名不参与匹配（Python 无方法重载）。
   ⚠ 真实行为：`ElasticsearchQueryService` 里**并没有** `queryByConditions` 与
   `scrollExport` 这两个方法，所以这两处反射在 Java 运行时**必然**走
   `NoSuchMethodException` 分支（打 warn 日志 + 返回空结果/0）。本移植同样如此，
   属于**保留原有缺陷**（不臆造新方法）。
5) `SimpleDateFormat.parse(...).getTime()` → Python 的 `parse` 返回 `datetime`
   （见 java/text/SimpleDateFormat.py），因此改写成 `int(dt.timestamp() * 1000)`，
   与 UnifiedQueryService 的既有写法一致。
6) `(int) (diff / (1000 * 60 * 60 * 24))`：Java 的整数除法**向零截断**，
   Python 的 `//` 是**向下取整**（负数结果不同）。因此用 `int(diff / (...))`
   保留"向零截断"语义。
7) `s.trim().isEmpty()` → `len(s.strip()) == 0`（Python 的 `strip()` 等价 `trim()`）。
8) `CompletableFuture.supplyAsync(supplier, Executors.newFixedThreadPool(2))` → 同名替身；
   注意 Java 原文**每次调用都新建一个 2 线程池且不关闭**，这里逐字保留（属原有缺陷）。
9) `@SuppressWarnings("unchecked")` 的泛型强转 `(Map<String, Object>)` → Python 无泛型强转，去掉。
10) `catch (Exception e)` + `log.error(msg, e)` → `except Exception` + `exc_info=True`。
11) `Collections.emptyList()` → `[]`；`new HashMap<>()` → `{}`。
12) `throws` 不存在于原文；`asyncExport` 里的异常在 supplier 内部被 catch，
    因此 `CompletableFuture.join()` 不会抛（与 Java 一致）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
    ElasticsearchQueryService,
)
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from java.text.SimpleDateFormat import SimpleDateFormat
from java.util.concurrent.CompletableFuture import CompletableFuture
from java.util.concurrent.Executors import Executors
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import (
    RedisTemplate,
    defaultRedisTemplate,
)
from org.springframework.jdbc.core.JdbcTemplate import JdbcTemplate

__all__ = ["BillionLevelQueryService", "QueryRouteRequest"]

log = logging.getLogger(__name__)


@dataclass
class QueryRouteRequest(JavaBean):
    """查询路由请求 - 用于判断走 ES 还是 GaussDB。

    【Java→Python】手写 POJO → `@dataclass` + `JavaBean`：
    - 13 个字段 snake_case（`platenumber` / `gantryname` 等本来就与 Java 同名）；
    - `getStartTime()/setExportCount()/isAggregation()` 等 22 个 getter/setter
      由 JavaBean 动态提供，无需手写；
    - `boolean aggregation` / `boolean export` / `int exportCount` 是**基本类型**，
      Java 默认值 false/false/0 → Python 默认值同样为 False/False/0
      （不能写 None，否则 `isAggregation()` 的返回值与 Java 不同）。
    """

    start_time: Optional[str] = None
    end_time: Optional[str] = None
    platenumber: Optional[str] = None
    gantryname: Optional[str] = None
    roadname: Optional[str] = None
    sectionname: Optional[str] = None
    orgname: Optional[str] = None
    tollname: Optional[str] = None
    #: 是否聚合统计
    aggregation: bool = False
    #: 是否导出
    export: bool = False
    #: 导出条数
    export_count: int = 0

    # ------------------------------------------------------------ 业务方法
    def hasFuzzyCondition(self) -> bool:
        """是否存在模糊条件（Java 侧为 public 方法）。

        【Java→Python】`||` 短路求值 → `or`，语义一致。
        """
        return (self.isNotEmpty(self.platenumber)
                or self.isNotEmpty(self.gantryname)
                or self.isNotEmpty(self.roadname)
                or self.isNotEmpty(self.sectionname)
                or self.isNotEmpty(self.orgname)
                or self.isNotEmpty(self.tollname))

    def getTimeRangeDays(self) -> int:
        """查询时间跨度（天）。

        【Java→Python】`parse(...).getTime()` → `int(dt.timestamp() * 1000)`；
        `(int)(diff / (1000*60*60*24))` → `int(diff / (...))`（向零截断，见文件头第 6 条）。
        时间缺失或格式非法时返回 365（与原代码的 catch 分支一致）。
        """
        try:
            if self.start_time is None or self.end_time is None:
                return 365
            sdf: SimpleDateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
            diff: int = (int(sdf.parse(self.end_time).timestamp() * 1000)
                         - int(sdf.parse(self.start_time).timestamp() * 1000))
            return int(diff / (1000 * 60 * 60 * 24))
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            return 365

    def isNotEmpty(self, s: Optional[str]) -> bool:
        """`s != null && !s.trim().isEmpty()`（Java 侧为 private）。"""
        return s is not None and len(s.strip()) > 0

    def __repr__(self) -> str:
        return ("QueryRouteRequest(start=%r, end=%r, plate=%r, aggregation=%r, "
                "export=%r, exportCount=%d)" %
                (self.start_time, self.end_time, self.platenumber,
                 self.aggregation, self.export, self.export_count))


class BillionLevelQueryService(object):
    """十亿级数据量查询优化服务（`@Service`）。"""

    #: `public static class QueryRouteRequest` 的类级访问路径
    QueryRouteRequest = QueryRouteRequest

    def __init__(self,
                 elasticsearchQueryService: Optional[ElasticsearchQueryService] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 jdbcTemplate: Optional[JdbcTemplate] = None) -> None:
        # 【Java→Python】`@Autowired(required = false)` → 默认 None，
        # 使"依赖缺失"的降级分支可被真实触发（详见文件头第 2 条）
        self.elasticsearchQueryService: Optional[ElasticsearchQueryService] = (
            elasticsearchQueryService)
        # `@Autowired`（required = true）→ 共享的 RedisTemplate
        self.redisTemplate: RedisTemplate = redisTemplate or defaultRedisTemplate()
        # `@Autowired(required = false)`
        self.jdbcTemplate: Optional[JdbcTemplate] = jdbcTemplate

        # 时间范围超过 N 天强制走 ES
        self.esForceDays: int = Environment().value(
            "${optimization.query.es-force-days:30}", int)
        # ES 查询超时（毫秒；`long` 在 Python 就是 int）
        self.esQueryTimeout: int = Environment().value(
            "${optimization.query.timeout-ms:30000}", int)
        # 单次 scroll 拉取的文档数
        self.scrollBatchSize: int = Environment().value(
            "${optimization.export.scroll-batch:2000}", int)
        # 热数据保留天数
        self.hotDataDays: int = Environment().value(
            "${optimization.cold-hot.hot-days:180}", int)

    # ==================================================================
    # 查询路由
    # ==================================================================
    def routeQuery(self, request: QueryRouteRequest) -> str:
        """查询路由判断 - 决定走 ES 还是 GaussDB。

        :return: "es" 或 "gaussdb"
        """
        if request.hasFuzzyCondition():
            log.debug("[十亿级路由] 命中规则1: 有模糊条件 → ES")
            return "es"
        if request.getTimeRangeDays() > self.esForceDays:
            log.debug("[十亿级路由] 命中规则2: 时间范围%s天 > %s天 → ES",
                      request.getTimeRangeDays(), self.esForceDays)
            return "es"
        if request.isAggregation():
            log.debug("[十亿级路由] 命中规则3: 聚合统计 → ES")
            return "es"
        if request.isExport() and request.getExportCount() > 1000:
            log.debug("[十亿级路由] 命中规则4: 导出%s条 → ES", request.getExportCount())
            return "es"
        log.debug("[十亿级路由] 默认: 精确查询 → GaussDB")
        return "gaussdb"

    # ==================================================================
    # ES 全字段模糊查询（3 表）
    # ==================================================================
    def querySnapshotFlowFromES(self, startTime: Optional[str],
                                endTime: Optional[str],
                                plateNumber: Optional[str],
                                gantryName: Optional[str],
                                roadName: Optional[str],
                                sectionName: Optional[str],
                                orgName: Optional[str],
                                tollName: Optional[str],
                                pageNum: int, pageSize: int) -> Dict[str, Any]:
        """ES 全字段模糊查询 - 门架抓拍流水。"""
        log.info("[十亿级查询] ES门架抓拍流水: start=%s, end=%s, plate=%s, "
                 "pageNum=%s, pageSize=%s",
                 startTime, endTime, plateNumber, pageNum, pageSize)
        if self.elasticsearchQueryService is None:
            log.warning("[十亿级查询] ElasticsearchQueryService 未注入，返回空结果")
            return self.emptyResult()
        try:
            conditions: Dict[str, Any] = {}
            if startTime is not None:
                conditions["snapshottime_gte"] = startTime
            if endTime is not None:
                conditions["snapshottime_lte"] = endTime
            if plateNumber is not None:
                conditions["platenumber"] = plateNumber
            if gantryName is not None:
                conditions["gantryname"] = gantryName
            if roadName is not None:
                conditions["roadname"] = roadName
            if sectionName is not None:
                conditions["sectionname"] = sectionName
            if orgName is not None:
                conditions["orgname"] = orgName
            if tollName is not None:
                conditions["tollname"] = tollName
            return self.invokeQueryByConditions("snapshot_flow", conditions,
                                                pageNum, pageSize)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级查询] ES查询失败，降级到 GaussDB", exc_info=True)
            return self.emptyResult()

    def queryFeeRecordsFromES(self, startTime: Optional[str],
                             endTime: Optional[str],
                             plateNumber: Optional[str],
                             gantryName: Optional[str],
                             pageNum: int, pageSize: int) -> Dict[str, Any]:
        """ES 全字段模糊查询 - 收费流水。"""
        log.info("[十亿级查询] ES收费流水: start=%s, end=%s, plate=%s",
                 startTime, endTime, plateNumber)
        if self.elasticsearchQueryService is None:
            return self.emptyResult()
        try:
            conditions: Dict[str, Any] = {}
            if startTime is not None:
                conditions["transtime_gte"] = startTime
            if endTime is not None:
                conditions["transtime_lte"] = endTime
            if plateNumber is not None:
                conditions["vehicleplate"] = plateNumber
            return self.invokeQueryByConditions("fee_records", conditions,
                                                pageNum, pageSize)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级查询] ES查询失败", exc_info=True)
            return self.emptyResult()

    def queryTrailFittingFromES(self, startTime: Optional[str],
                               endTime: Optional[str],
                               plateNumber: Optional[str],
                               stationName: Optional[str],
                               pageNum: int, pageSize: int) -> Dict[str, Any]:
        """ES 全字段模糊查询 - 轨迹拟合。

        【Java→Python】`plateNumber` 在轨迹表里落到 `envehicleid`，
        `stationName` 落到 `extollstationname`（原文如此，字段映射是硬编码的）。
        """
        log.info("[十亿级查询] ES轨迹拟合: start=%s, end=%s", startTime, endTime)
        if self.elasticsearchQueryService is None:
            return self.emptyResult()
        try:
            conditions: Dict[str, Any] = {}
            if startTime is not None:
                conditions["extime_gte"] = startTime
            if endTime is not None:
                conditions["extime_lte"] = endTime
            if plateNumber is not None:
                conditions["envehicleid"] = plateNumber
            if stationName is not None:
                conditions["extollstationname"] = stationName
            return self.invokeQueryByConditions("trail_fitting", conditions,
                                                pageNum, pageSize)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级查询] ES查询失败", exc_info=True)
            return self.emptyResult()

    # ==================================================================
    # 异步导出
    # ==================================================================
    def asyncExport(self, indexName: str,
                    conditions: Dict[str, Any]) -> CompletableFuture:
        """异步导出 - 使用 ES Scroll API 分批拉取。

        【Java→Python】原文每次调用都 `Executors.newFixedThreadPool(2)` 且**从不关闭**
        该线程池（原有缺陷，逐字保留）。
        """

        def _supplier() -> int:
            totalExported = 0
            try:
                log.info("[十亿级导出] 开始异步导出: index=%s, conditions=%s",
                         indexName, conditions)
                if self.elasticsearchQueryService is not None:
                    totalExported = self.invokeScrollExport(
                        indexName, conditions, self.scrollBatchSize)
                log.info("[十亿级导出] 导出完成，共 %s 条", totalExported)
            except Exception:  # noqa: BLE001 - catch (Exception e)
                log.error("[十亿级导出] 导出失败", exc_info=True)
            return totalExported

        return CompletableFuture.supplyAsync(_supplier,
                                            Executors.newFixedThreadPool(2))

    # ==================================================================
    # 冷热分离：归档
    # ==================================================================
    def archiveColdData(self) -> None:
        """归档冷数据 - 将超过热数据保留期的数据迁移到归档表。"""
        if self.jdbcTemplate is None:
            return
        try:
            log.info("[十亿级冷热分离] 开始归档冷数据，热数据保留 %s 天", self.hotDataDays)
            archiveSql = ("INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_archive "
                          "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode "
                          "WHERE snapshottime < NOW() - INTERVAL '"
                          + str(self.hotDataDays) + " days'")
            deleteSql = ("DELETE FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode "
                         "WHERE snapshottime < NOW() - INTERVAL '"
                         + str(self.hotDataDays) + " days'")
            self.executeArchive(archiveSql, deleteSql,
                                "ods_rt_szdn_snapshot_flow_addcode")

            archiveSql = ("INSERT INTO jl_data01.ods_lwzxsfsj_fee_records_archive "
                          "SELECT * FROM jl_data01.ods_lwzxsfsj_fee_records_01 "
                          "WHERE transtime < NOW() - INTERVAL '"
                          + str(self.hotDataDays) + " days'")
            deleteSql = ("DELETE FROM jl_data01.ods_lwzxsfsj_fee_records_01 "
                         "WHERE transtime < NOW() - INTERVAL '"
                         + str(self.hotDataDays) + " days'")
            self.executeArchive(archiveSql, deleteSql, "ods_lwzxsfsj_fee_records_01")

            archiveSql = ("INSERT INTO jl_data01.zdata_trail_fitting_archive "
                          "SELECT * FROM jl_data01.zdata_trail_fitting "
                          "WHERE extime < NOW() - INTERVAL '"
                          + str(self.hotDataDays) + " days'")
            deleteSql = ("DELETE FROM jl_data01.zdata_trail_fitting "
                         "WHERE extime < NOW() - INTERVAL '"
                         + str(self.hotDataDays) + " days'")
            self.executeArchive(archiveSql, deleteSql, "zdata_trail_fitting")

            log.info("[十亿级冷热分离] 冷数据归档完成")
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级冷热分离] 归档失败", exc_info=True)

    def executeArchive(self, archiveSql: str, deleteSql: str,
                       tableName: str) -> None:
        """执行单表归档 + 删除（Java 侧为 private）。"""
        try:
            archived: int = self.jdbcTemplate.update(archiveSql)
            log.info("[十亿级冷热分离] %s 归档 %s 条", tableName, archived)
            deleted: int = self.jdbcTemplate.update(deleteSql)
            log.info("[十亿级冷热分离] %s 删除冷数据 %s 条", tableName, deleted)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级冷热分离] %s 归档失败", tableName, exc_info=True)

    # ==================================================================
    # 反射调用（Java 侧为 private）
    # ==================================================================
    def invokeQueryByConditions(self, indexName: str,
                                conditions: Dict[str, Any],
                                pageNum: int, pageSize: int) -> Dict[str, Any]:
        """反射调用 `ElasticsearchQueryService.queryByConditions`。

        Java 原文：找不到方法 → 打 warn + 返回空结果。
        【Java→Python】`getClass().getMethod(name, ...)` → `getattr(obj, name, None)`
        + `callable()`；签名不参与匹配（Python 无方法重载）。

        ⚠ 保留原有缺陷：`ElasticsearchQueryService` 里没有 `queryByConditions`，
        因此这里**必然**走"方法不存在"分支（见文件头第 4 条）。
        """
        try:
            method = getattr(self.elasticsearchQueryService, "queryByConditions", None)
            if method is None or not callable(method):
                # 对应 catch (NoSuchMethodException e)
                log.warning("[十亿级查询] ElasticsearchQueryService.queryByConditions "
                            "方法不存在，返回空结果")
                return self.emptyResult()
            return method(indexName, conditions, pageNum, pageSize)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级查询] 反射调用 queryByConditions 失败", exc_info=True)
            return self.emptyResult()

    def invokeScrollExport(self, indexName: str, conditions: Dict[str, Any],
                          batchSize: int) -> int:
        """反射调用 `ElasticsearchQueryService.scrollExport`。

        Java 原文：找不到方法 → 打 warn + 返回 0。
        ⚠ 同样保留原有缺陷：该方法在 `ElasticsearchQueryService` 里不存在。
        """
        try:
            method = getattr(self.elasticsearchQueryService, "scrollExport", None)
            if method is None or not callable(method):
                # 对应 catch (NoSuchMethodException e)
                log.warning("[十亿级导出] ElasticsearchQueryService.scrollExport "
                            "方法不存在，返回 0")
                return 0
            return method(indexName, conditions, batchSize)
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[十亿级导出] 反射调用 scrollExport 失败", exc_info=True)
            return 0

    def emptyResult(self) -> Dict[str, Any]:
        """空结果 `{total: 0, data: []}`（Java 侧为 private）。"""
        return {"total": 0, "data": []}
