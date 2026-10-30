# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/ProgressiveQueryArchitectureService.java

渐进式查询架构服务 - Progressive Query Architecture Service

架构思路 / Architecture Design:

阶段一：千万级（单表 < 5000万行）- Phase 1: Ten Million Level
  - 策略：GaussDB 原生 B-tree 索引 + pg_trgm GIN 索引 + 游标分页
  - 适用：LIKE '%xxx%' 模糊查询通过 trigram GIN 索引加速
  - 查询路径：Controller → GaussDB（B-tree + GIN 索引扫描）

阶段二：亿级（单表 5000万 ~ 5亿行）- Phase 2: Hundred Million Level
  - 策略：按月范围分区（Range Partition）+ 分区裁剪 + 覆盖索引 + 物化视图
  - 查询路径：Controller → GaussDB 分区表（分区裁剪 + 索引扫描）
  - 统计查询走物化视图，明细查询走分区表

阶段三：十亿级（单表 > 5亿行）- Phase 3: Billion Level
  - 策略：冷热分离 + Elasticsearch 全文检索 + GaussDB 只处理热数据
  - 查询路径：Controller → 路由判断 → ES（全模糊/统计/导出）/ GaussDB（精确查询/热数据）
  - ES 负责全字段模糊查询、聚合统计、大规模导出
  - GaussDB 负责近期热数据的精确查询和事务操作

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；`@Value` → 构造器里 `Environment().value(...)`；
   4 个 `@Autowired` → 构造器可选参数（缺省时 `or new XxxImpl()`）；
   `@Autowired(required = false) ElasticsearchQueryService` → 默认 `None`，
   代码里 `if self.elasticsearchQueryService is not None` 的降级分支因此可被真实触发。
2) **内部枚举 `DataScaleLevel`** → 模块级 `Enum`，并补齐 Java 枚举自带的
   `name()` / `valueOf(String)` / `values()`（Python 的 Enum 只有 `.name` 属性），
   文件末尾挂回 `ProgressiveQueryArchitectureService.DataScaleLevel`，
   保证控制器里 `ProgressiveQueryArchitectureService.DataScaleLevel` 的访问路径不变。
3) **内部静态类 `QueryRequest` / `QueryResult`** → 模块级类 + 末尾挂回类属性。
   - `QueryRequest` 是手写 POJO（10 组 getter/setter）→ `@dataclass(JavaBean)`，
     `getStartTime()/setStartTime()` 等由 JavaBean 动态提供，方法体可逐字保留；
     但 `toString()` 是**自定义格式**，必须显式实现（不能退回 Lombok 格式）。
   - `QueryResult` 只有 getter + 两个静态工厂 → 普通类 + `@staticmethod of/esPlaceholder`。
4) `switch (level) { case LEVEL_10M: ... }` → `if/elif`（枚举无 fallthrough）。
5) `Long.parseLong(cached.toString())` → `int(str(cached))`（非数字抛 ValueError，
   对应 NumberFormatException，且与原代码一样**不被 catch**）。
6) `DataScaleLevel.valueOf(config)` 在 `try/catch(Exception)` 内 → Python 的 `valueOf`
   非法名抛 ValueError，同样被捕获并降级为 LEVEL_10M。
7) `java.sql.Timestamp.valueOf(String)` → Timestamp 替身同名静态方法（返回 datetime）。
8) `List<?>` → `List[Any]`；`Collections.emptyList()` → `[]`（空 list）。
9) `log.info("...{}...", level, request)` → `%s` 传 `level`（枚举重写了 `__str__`）
   与 `request.toString()`（Java 记录的是 `toString()` 的结果）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import OdsLwzxsfsjFeeRecords01Mapper
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
    ElasticsearchQueryService,
)
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from java.sql.Timestamp import Timestamp
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import (
    RedisTemplate,
    defaultRedisTemplate,
)

__all__ = ["DataScaleLevel", "ProgressiveQueryArchitectureService", "QueryRequest",
           "QueryResult"]

log = logging.getLogger(__name__)


class DataScaleLevel(Enum):
    """数据量级别枚举（Java 侧为 ProgressiveQueryArchitectureService.DataScaleLevel）。

    【Java→Python】Java 枚举自带 `name()` / `valueOf(String)` / `values()`；
    Python 的 Enum 只有 `.name` 属性与 `Enum['NAME']` 索引，这里补齐三个 Java API，
    使 `detectScaleLevel(...).name()` 与 `DataScaleLevel.valueOf(...)` 原样可用。
    枚举成员用 `is` 比较（Java 的 `==` 也是引用比较，语义一致）。
    """

    #: 千万级：单表 < 5000万
    LEVEL_10M = "LEVEL_10M"
    #: 亿级：5000万 ~ 5亿
    LEVEL_100M = "LEVEL_100M"
    #: 十亿级：> 5亿
    LEVEL_1B = "LEVEL_1B"

    def name(self) -> str:  # type: ignore[override]
        """等价 Java 的 `Enum.name()`（返回枚举常量名）。"""
        return self._name_

    def __str__(self) -> str:
        # 等价 Java `Enum.toString()` → name()；否则日志里会出现 "DataScaleLevel.LEVEL_10M"
        return self._name_

    @staticmethod
    def valueOf(name: str) -> "DataScaleLevel":
        """等价 `DataScaleLevel.valueOf(String)`：名称非法时抛 IllegalArgumentException。

        【Java→Python】Java 抛 IllegalArgumentException，Python 对应 ValueError。
        """
        try:
            return DataScaleLevel[name]
        except KeyError:
            raise ValueError(
                "No enum constant ProgressiveQueryArchitectureService.DataScaleLevel."
                + str(name))

    @staticmethod
    def values() -> List["DataScaleLevel"]:
        """等价 `DataScaleLevel.values()`。"""
        return list(DataScaleLevel)


@dataclass
class QueryRequest(JavaBean):
    """统一查询请求对象 / Unified query request object.

    【Java→Python】手写 POJO → `@dataclass` + `JavaBean`：字段用 snake_case，
    但 `getStartTime()` / `setPageSize()` 等 Java 写法由 JavaBean 动态提供。
    `pageSize` 在 Java 里带初值 20（`private int pageSize = 20;`），这里同样默认 20。
    """

    #: 开始时间（yyyy-MM-dd HH:mm:ss）
    start_time: Optional[str] = None
    #: 结束时间（yyyy-MM-dd HH:mm:ss）
    end_time: Optional[str] = None
    #: 车牌号
    platenumber: Optional[str] = None
    #: 管理中心名称
    orgname: Optional[str] = None
    #: 路段名称
    sectionname: Optional[str] = None
    #: 道路名称
    roadname: Optional[str] = None
    #: 门架名称
    gantryname: Optional[str] = None
    #: 收费站名称
    tollname: Optional[str] = None
    #: 游标（游标分页用，上一页最后一条记录的时间戳）
    cursor: Optional[str] = None
    #: 每页大小
    page_size: int = 20

    def toString(self) -> str:
        """自定义 toString（**不是** Lombok 格式，必须显式实现）。

        【Java→Python】`String.format` → `%` 格式化；`%d` 对应 pageSize(int)。
        """
        return ("QueryRequest{start=%s, end=%s, plate=%s, gantry=%s, pageSize=%d}"
                % (self.start_time, self.end_time, self.platenumber,
                   self.gantryname, self.page_size))


class QueryResult(object):
    """统一查询结果对象 / Unified query result object.

    【Java→Python】字段在 Java 里是 private + 只读 getter，
    赋值只发生在下面两个静态工厂里，因此这里用普通类而非 dataclass。
    """

    def __init__(self) -> None:
        #: 结果数据列表（Java 里 `new QueryResult()` 后为 null，只有工厂会赋值）
        self.data: Optional[List[Any]] = None
        #: 总记录数
        self.total: int = 0
        #: 实际采用的查询策略标识
        self.strategy: Optional[str] = None

    # ------------------------------------------------------------------ 工厂
    @staticmethod
    def of(data: List[Any], total: int, strategy: str) -> "QueryResult":
        """构造普通查询结果（对应 `static QueryResult of(List<?>, long, String)`）。"""
        result = QueryResult()
        result.data = data
        result.total = total
        result.strategy = strategy
        return result

    @staticmethod
    def esPlaceholder(strategy: str) -> "QueryResult":
        """构造 ES 占位结果（空列表 + total=0）。"""
        result = QueryResult()
        result.data = []
        result.total = 0
        result.strategy = strategy
        return result

    # ------------------------------------------------------------------ getter
    def getData(self) -> Optional[List[Any]]:
        return self.data

    def getTotal(self) -> int:
        return self.total

    def getStrategy(self) -> Optional[str]:
        return self.strategy

    def __repr__(self) -> str:
        return "QueryResult(total=%d, strategy=%r)" % (self.total, self.strategy)


class ProgressiveQueryArchitectureService(object):
    """渐进式查询架构服务（`@Service`）。"""

    #: 表行数缓存前缀
    TABLE_COUNT_CACHE = "table:count:"
    #: 表行数缓存过期时间（秒，1 小时）
    TABLE_COUNT_TTL = 3600

    #: 内部枚举 / 内部静态类的 Java 访问路径（与 UnifiedQueryService.DataSource 同款做法）
    DataScaleLevel = DataScaleLevel
    QueryRequest = QueryRequest
    QueryResult = QueryResult

    def __init__(self,
                 snapshotFlowMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 feeRecordsMapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 trailFittingMapper: Optional[ZdataTrailFittingMapper] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 elasticsearchQueryService: Optional[ElasticsearchQueryService] = None) -> None:
        # `@Value("${optimization.scale-level:LEVEL_10M}")`
        self.configuredScaleLevel: str = Environment().value(
            "${optimization.scale-level:LEVEL_10M}", str)
        # 【Java→Python】4 个 @Autowired + 1 个 required=false → 构造器可选参数
        self.snapshotFlowMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotFlowMapper if snapshotFlowMapper is not None
            else OdsRtSzdnSnapshotFlowAddcodeMapper())
        self.feeRecordsMapper: OdsLwzxsfsjFeeRecords01Mapper = (
            feeRecordsMapper if feeRecordsMapper is not None
            else OdsLwzxsfsjFeeRecords01Mapper())
        self.trailFittingMapper: ZdataTrailFittingMapper = (
            trailFittingMapper if trailFittingMapper is not None
            else ZdataTrailFittingMapper())
        self.redisTemplate: RedisTemplate = redisTemplate or defaultRedisTemplate()
        #: 阶段三启用的可选依赖（容器里可能没有该 Bean）
        self.elasticsearchQueryService: Optional[ElasticsearchQueryService] = (
            elasticsearchQueryService)

    # ==================================================================
    # 数据量级别判定
    # ==================================================================
    def detectScaleLevel(self, tableName: str) -> DataScaleLevel:
        """自动检测数据量级别（按表行数）。

        :param tableName: 表名
        :return: 数据量级别
        """
        # 1. 先从 Redis 缓存读取
        cacheKey: str = self.TABLE_COUNT_CACHE + tableName
        cached = self.redisTemplate.opsForValue().get(cacheKey)
        if cached is not None:
            count: int = int(str(cached))
            return self.judgeScaleLevel(count)
        # 2. 缓存未命中，使用配置的级别
        try:
            return DataScaleLevel.valueOf(self.configuredScaleLevel)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 配置非法时降级为千万级
            return DataScaleLevel.LEVEL_10M

    def judgeScaleLevel(self, count: int) -> DataScaleLevel:
        """根据行数判定数据量级别。

        【Java→Python】`50_000_000L` 的下划线写法 Python 同样支持，直接保留。
        """
        if count < 50000000:
            return DataScaleLevel.LEVEL_10M
        if count < 500000000:
            return DataScaleLevel.LEVEL_100M
        return DataScaleLevel.LEVEL_1B

    # ==================================================================
    # 统一查询入口：门架抓拍流水
    # ==================================================================
    def querySnapshotFlow(self, request: QueryRequest) -> QueryResult:
        """统一查询入口 - 门架抓拍流水（按数据量级别选策略）。"""
        level: DataScaleLevel = self.detectScaleLevel("ods_rt_szdn_snapshot_flow_addcode")
        log.info("[渐进式查询] 门架抓拍流水，数据量级别=%s, 请求=%s",
                 level, request.toString())

        if level is DataScaleLevel.LEVEL_10M:
            return self.querySnapshotFlowPhase1(request)
        if level is DataScaleLevel.LEVEL_100M:
            return self.querySnapshotFlowPhase2(request)
        if level is DataScaleLevel.LEVEL_1B:
            return self.querySnapshotFlowPhase3(request)
        # default:
        return self.querySnapshotFlowPhase1(request)

    # ==================== 阶段一：千万级 ====================
    def querySnapshotFlowPhase1(self, request: QueryRequest) -> QueryResult:
        """阶段一查询：门架抓拍流水（千万级）。

        策略：B-tree 索引 + GIN trigram 索引 + 游标分页。
        """
        # 构建查询条件对象
        query: OdsRtSzdnSnapshotFlowAddcode = OdsRtSzdnSnapshotFlowAddcode()
        query.setApplyTime1(request.getStartTime())
        query.setApplyTime2(request.getEndTime())
        if request.getPlatenumber() is not None:
            query.setPlatenumber(request.getPlatenumber())
        if request.getGantryname() is not None:
            query.setGantryname(request.getGantryname())
        if request.getRoadname() is not None:
            query.setRoadname(request.getRoadname())
        if request.getSectionname() is not None:
            query.setSectionname(request.getSectionname())
        if request.getOrgname() is not None:
            query.setOrgname(request.getOrgname())
        if request.getTollname() is not None:
            query.setTollname(request.getTollname())

        # 走 GaussDB 原生索引扫描
        rows: List[OdsRtSzdnSnapshotFlowAddcode] = (
            self.snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query))
        return QueryResult.of(rows, len(rows), "phase1-gaussdb-gin")

    # ==================== 阶段二：亿级 ====================
    def querySnapshotFlowPhase2(self, request: QueryRequest) -> QueryResult:
        """阶段二查询：门架抓拍流水（亿级）。

        策略：分区裁剪 + 覆盖索引 + 游标分页。
        """
        # 使用游标分页避免深翻页
        if request.getCursor() is not None and len(request.getCursor()) > 0:
            maxTime: Optional[str] = request.getEndTime()
            rows: List[OdsRtSzdnSnapshotFlowAddcode] = (
                self.snapshotFlowMapper.selectByCursorShard(
                    request.getStartTime(), maxTime, request.getCursor(), None,
                    request.getPageSize()))
            return QueryResult.of(rows, len(rows), "phase2-partition-cursor")
        # 无游标时走分区裁剪查询
        query: OdsRtSzdnSnapshotFlowAddcode = OdsRtSzdnSnapshotFlowAddcode()
        query.setApplyTime1(request.getStartTime())
        query.setApplyTime2(request.getEndTime())
        if request.getPlatenumber() is not None:
            query.setPlatenumber(request.getPlatenumber())
        if request.getGantryname() is not None:
            query.setGantryname(request.getGantryname())
        if request.getRoadname() is not None:
            query.setRoadname(request.getRoadname())
        if request.getSectionname() is not None:
            query.setSectionname(request.getSectionname())
        if request.getOrgname() is not None:
            query.setOrgname(request.getOrgname())
        if request.getTollname() is not None:
            query.setTollname(request.getTollname())
        rows = self.snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query)
        return QueryResult.of(rows, len(rows), "phase2-partition-prune")

    # ==================== 阶段三：十亿级 ====================
    def querySnapshotFlowPhase3(self, request: QueryRequest) -> QueryResult:
        """阶段三查询：门架抓拍流水（十亿级）。

        策略：ES 全文检索 + 冷热分离。
        """
        if self.elasticsearchQueryService is not None:
            # 有任何模糊查询条件时走 ES
            hasFuzzy: bool = (request.getPlatenumber() is not None
                              or request.getGantryname() is not None
                              or request.getRoadname() is not None
                              or request.getSectionname() is not None
                              or request.getOrgname() is not None
                              or request.getTollname() is not None)
            if hasFuzzy or request.getPageSize() > 100:
                # 走 ES 查询（实际数据由调用方进一步处理）
                return QueryResult.esPlaceholder("phase3-elasticsearch")
        # 精确查询走 GaussDB 热数据
        return self.querySnapshotFlowPhase2(request)

    # ==================================================================
    # 统一查询入口：收费流水
    # ==================================================================
    def queryFeeRecords(self, request: QueryRequest) -> QueryResult:
        """统一查询入口 - 收费流水（按数据量级别选策略）。"""
        level: DataScaleLevel = self.detectScaleLevel("ods_lwzxsfsj_fee_records_01")
        log.info("[渐进式查询] 收费流水，数据量级别=%s, 请求=%s",
                 level, request.toString())
        if level is DataScaleLevel.LEVEL_10M:
            return self.queryFeeRecordsPhase1(request)
        if level is DataScaleLevel.LEVEL_100M:
            return self.queryFeeRecordsPhase2(request)
        if level is DataScaleLevel.LEVEL_1B:
            return self.queryFeeRecordsPhase3(request)
        # default:
        return self.queryFeeRecordsPhase1(request)

    def queryFeeRecordsPhase1(self, request: QueryRequest) -> QueryResult:
        """阶段一查询：收费流水（千万级）。"""
        query: OdsLwzxsfsjFeeRecords01 = OdsLwzxsfsjFeeRecords01()
        query.setInApplyTime1(request.getStartTime())
        query.setInApplyTime2(request.getEndTime())
        if request.getPlatenumber() is not None:
            query.setVehicleplate(request.getPlatenumber())
        rows: List[OdsLwzxsfsjFeeRecords01] = (
            self.feeRecordsMapper.selectOdsLwzxsfsjFeeRecords01List(query))
        return QueryResult.of(rows, len(rows), "phase1-gaussdb-gin")

    def queryFeeRecordsPhase2(self, request: QueryRequest) -> QueryResult:
        """阶段二查询：收费流水（亿级）。

        分区表对应用透明，复用阶段一查询逻辑。
        """
        return self.queryFeeRecordsPhase1(request)

    def queryFeeRecordsPhase3(self, request: QueryRequest) -> QueryResult:
        """阶段三查询：收费流水（十亿级）。"""
        if self.elasticsearchQueryService is not None:
            hasFuzzy: bool = request.getPlatenumber() is not None
            if hasFuzzy or request.getPageSize() > 100:
                return QueryResult.esPlaceholder("phase3-elasticsearch")
        return self.queryFeeRecordsPhase2(request)

    # ==================================================================
    # 统一查询入口：车辆轨迹拟合
    # ==================================================================
    def queryTrailFitting(self, request: QueryRequest) -> QueryResult:
        """统一查询入口 - 车辆轨迹拟合（按数据量级别选策略）。"""
        level: DataScaleLevel = self.detectScaleLevel("zdata_trail_fitting")
        log.info("[渐进式查询] 轨迹拟合，数据量级别=%s, 请求=%s",
                 level, request.toString())
        if level is DataScaleLevel.LEVEL_10M:
            return self.queryTrailFittingPhase1(request)
        if level is DataScaleLevel.LEVEL_100M:
            return self.queryTrailFittingPhase2(request)
        if level is DataScaleLevel.LEVEL_1B:
            return self.queryTrailFittingPhase3(request)
        # default:
        return self.queryTrailFittingPhase1(request)

    def queryTrailFittingPhase1(self, request: QueryRequest) -> QueryResult:
        """阶段一查询：车辆轨迹拟合（千万级）。"""
        query: ZdataTrailFitting = ZdataTrailFitting()
        # 入口时间作为查询上界
        if request.getStartTime() is not None:
            query.setEntime(Timestamp.valueOf(request.getStartTime()))
        # 出口时间作为查询下界
        if request.getEndTime() is not None:
            query.setExtime(Timestamp.valueOf(request.getEndTime()))
        rows: List[ZdataTrailFitting] = (
            self.trailFittingMapper.selectZdataTrailFittingList(query))
        return QueryResult.of(rows, len(rows), "phase1-gaussdb-gin")

    def queryTrailFittingPhase2(self, request: QueryRequest) -> QueryResult:
        """阶段二查询：车辆轨迹拟合（亿级）：分区表透明，复用阶段一逻辑。"""
        return self.queryTrailFittingPhase1(request)

    def queryTrailFittingPhase3(self, request: QueryRequest) -> QueryResult:
        """阶段三查询：车辆轨迹拟合（十亿级）。"""
        if self.elasticsearchQueryService is not None:
            return QueryResult.esPlaceholder("phase3-elasticsearch")
        return self.queryTrailFittingPhase2(request)
