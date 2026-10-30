# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.CompositeQueryOptimizationService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/CompositeQueryOptimizationService.java

====================================================================
方案三：组合优化查询 - 智能路由服务
====================================================================

核心思路：
  根据查询条件，智能选择最优的查询策略，实现降级和并行查询

查询策略选择逻辑：
  | 条件                    | 首选方案       | 降级方案             |
  | 完整车牌号               | ES termQuery   | GaussDB B-tree索引    |
  | 车牌号前缀(3-6位)        | ES prefixQuery | GaussDB GIN 索引       |
  | 全模糊查询 like '%赣%'   | ES wildcard    | GaussDB pg_trgm GIN   |
  | 时间范围小（1-7天）      | GaussDB 分区表  | ES                     |
  | 时间范围大（1-6个月）    | ES             | 多分区并行查询         |
  | 多字段组合查询（推荐）    | ES boolQuery   | GIN+组合索引           |

性能目标：
  - 90%的查询响应时间 < 500ms
  - 99%的查询响应时间 < 3秒
  - 最大查询响应时间 < 30秒（否则超时降级）

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；3 个 `@Value` → `Environment().value(...)`。
2) `public enum QueryStrategy`（内部枚举）→ **模块级 Enum** + 末尾挂回
   `CompositeQueryOptimizationService.QueryStrategy`，保持
   `CompositeQueryOptimizationService.QueryStrategy.ES_ONLY` 的访问路径不变。
   同时重写 `__str__`，使日志输出 `ES_ONLY`（而不是 `QueryStrategy.ES_ONLY`），
   与 Java 枚举的 `toString()` 一致。
3) `switch (strategy)` → `if/elif` 链：Java 的 `case ES_ONLY: case ES_FIRST_THEN_DB:`
   贯穿（fall-through）改写为 `or` 条件；`default` 改写为最后的 `return`。
4) `Future<List<X>> esFuture = executorService.submit(() -> {...})` →
   `Future` + 嵌套函数；**lambda 里的 try/catch 必须展开成 def**，因为
   Python lambda 只能包含表达式，不能写 `try/except`。
5) `esFuture.get(queryTimeoutMs, TimeUnit.MILLISECONDS)` → `Future.get(timeout, unit)`；
   `catch (TimeoutException e)` → `except TimeoutError`（Java 的受检异常在
   Python 里没有对应类，替身的 Future 用内置 `TimeoutError` 表达）。
6) `Integer.MAX_VALUE` → `_INT_MAX_VALUE`（2147483647，与 JDK 常量值一致；
   **不能**用 `sys.maxsize`，那是 2^63-1）。
7) `Collections.emptyList()` → `[]`；`List.isEmpty()` → `not list`。
8) `java.time.Duration.between(start, end).toDays()` → `Duration` 替身；
   `(int)` 强转 → `int(...)`（Python 的 int() 对正负都是向零截断）。
9) `log.warn("[...] 失败", e)` → `log.warning("[...] 失败", exc_info=True)`
   （Python 的日志没有“最后参数是异常”的约定）。
10) `Map<String, Object> healthCheck()` → `dict`；Java 的 `HashMap` 无序，
    Python 3.7+ 的 dict 保序 —— 对本方法无影响。
11) `FULL_PLATE_PATTERN` 在 Java 里**定义了但从未被引用**（死代码），
    这里原样保留并标注，不删不改。
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, List, Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
    ElasticsearchQueryService,
)
from com.ruoyi.base.service.optimization.LargeTableQueryOptimizationService import (
    LargeTableQueryOptimizationService,
)
from com.ruoyi.base.service.optimization.QueryValidationService import QueryValidationService
from java.time.Duration import Duration
from java.time.LocalDateTime import LocalDateTime
from java.time.format.DateTimeFormatter import DateTimeFormatter
from java.util.concurrent.ExecutorService import Future
from java.util.concurrent.LinkedBlockingQueue import LinkedBlockingQueue
from java.util.concurrent.ThreadPoolExecutor import ThreadPoolExecutor
from java.util.concurrent.TimeUnit import TimeUnit
from org.springframework.core.env.Environment import Environment

__all__ = ["CompositeQueryOptimizationService", "QueryStrategy"]

log = logging.getLogger(__name__)

#: Java `Integer.MAX_VALUE`（2147483647）
#: 【Java→Python】不能用 `sys.maxsize`（那是 64 位平台的 2^63-1）
_INT_MAX_VALUE = 2147483647

#: 时间格式（与前端/ES mapping 约定一致）
#: 【Java→Python】Java 在原方法内联创建 DateTimeFormatter，这里提为模块常量
#: （DateTimeFormatter 不可变、线程安全，提出来不影响语义）。
_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")


# ====================================================================
# 查询策略枚举（Java 内部 `public enum QueryStrategy`）
# ====================================================================
class QueryStrategy(Enum):
    """查询策略枚举。"""

    #: 仅ES查询 - 性能最高
    ES_ONLY = "ES_ONLY"
    #: 仅数据库查询 - 精确匹配小范围
    DB_ONLY = "DB_ONLY"
    #: ES优先，失败降级到数据库
    ES_FIRST_THEN_DB = "ES_FIRST_THEN_DB"
    #: ES和数据库并行查询，取最快结果
    PARALLEL_QUERY = "PARALLEL_QUERY"

    def __str__(self) -> str:
        # 【Java→Python】Java 枚举的 toString() 返回常量名；Python Enum 默认
        # 返回 "QueryStrategy.ES_ONLY"，会让日志多出类名前缀，这里对齐 Java。
        return self.name

    def toString(self) -> str:
        return self.name


class CompositeQueryOptimizationService(object):
    """组合优化查询 - 智能路由服务（`@Service`）。"""

    #: 线程池大小（根据查询策略调整）
    POOL_SIZE = 8

    #: 车牌号正则（完整车牌）
    #: 【Java→Python】`private static final Pattern` → 类属性 `re.Pattern`；
    #: 原工程**定义了但从未使用**（死代码），此处忠实保留。
    FULL_PLATE_PATTERN = re.compile(
        "^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]"
        "[A-Z][A-Z0-9]{5,6}$")

    def __init__(
        self,
        esQueryService: Optional[ElasticsearchQueryService] = None,
        dbQueryService: Optional[LargeTableQueryOptimizationService] = None,
        queryValidationService: Optional[QueryValidationService] = None,
    ) -> None:
        # 【Java→Python】`@Value("${k:d}")` → 构造器里显式取值
        self.esRouteEnabled: bool = Environment().value(
            "${optimization.query.route.es:true}", bool)
        self.parallelEnabled: bool = Environment().value(
            "${optimization.query.route.parallel:true}", bool)
        self.queryTimeoutMs: int = Environment().value(
            "${optimization.query.timeout-ms:30000}", int)

        # 【Java→Python】`@Autowired` 字段注入 → 构造器可选参数（缺省 new 一个）
        self.esQueryService: ElasticsearchQueryService = (
            esQueryService if esQueryService is not None else ElasticsearchQueryService())
        self.dbQueryService: LargeTableQueryOptimizationService = (
            dbQueryService if dbQueryService is not None
            else LargeTableQueryOptimizationService())
        self.queryValidationService: QueryValidationService = (
            queryValidationService if queryValidationService is not None
            else QueryValidationService())

        # 【Java→Python】`private final ExecutorService executorService = new ThreadPoolExecutor(...)`
        # → 构造器内创建。Java 的 4 个 static final 常量
        # （POOL_SIZE/60L/SECONDS/1000）逐个透传，便于断言构造参数是否一致。
        # 【注意】Java 的 6 参构造是 (core, max, keepAlive, unit, workQueue, handler)；
        # ThreadPoolExecutor 替身按 Java 7 参顺序在 threadFactory 之后才是 handler，
        # 因此 handler 必须用关键字传参（见 ThreadPoolExecutor.py 构造器说明）。
        self.executorService = ThreadPoolExecutor(
            CompositeQueryOptimizationService.POOL_SIZE,
            CompositeQueryOptimizationService.POOL_SIZE,
            60,
            TimeUnit.SECONDS,
            LinkedBlockingQueue(1000),
            handler=ThreadPoolExecutor.CallerRunsPolicy(),
        )

    # ====================================================================
    # 门架抓拍流水 - 组合查询入口
    # ====================================================================
    def querySnapshotFlow(
        self,
        startTime: str,
        endTime: str,
        plateNumber: str,
        gantryCode: str,
        sectionCode: str,
        orgCode: str,
        pageNum: int,
        pageSize: int,
    ) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """门架抓拍流水 - 组合查询入口

        根据查询条件智能选择：
          1. 参数校验：强制时间范围、限制深分页
          2. 模糊查询检测：LIKE '%xxx%' 走 ES
          3. 完整车牌+短时间范围 -> DB (B-tree 精确匹配)
          4. 完整车牌+长时间范围 -> ES
          5. 模糊/部分车牌 -> 全走 ES
          6. 降级策略：ES失败 -> 数据库
        """
        # ============== 1. 参数校验 ==============
        validation: QueryValidationService.ValidationResult = (
            self.queryValidationService.validatePageQuery(
                startTime, endTime, pageNum, pageSize))
        if not validation.isValid():
            log.warning("[组合查询] 参数校验失败: %s", validation.getErrorMessage())
            # 【Java→Python】`throw new RuntimeException(msg)` → 内置 RuntimeError
            raise RuntimeError(validation.getErrorMessage())

        # ============== 2. 智能路由决策 ==============
        strategy: QueryStrategy = self.decideStrategy(
            startTime, endTime, plateNumber, gantryCode, sectionCode)
        log.info("[组合查询] 智能路由策略 strategy=%s, plate=%s, timeRange=%s天, validation=%s",
                 strategy, plateNumber, validation.getTimeRangeDays(), validation)

        # ============== 3. 执行查询 ==============
        # 【Java→Python】`switch (strategy)` → if/elif；Java 的枚举 switch 编译成
        # "跳转表 + 枚举序号"，Python 用 `is` 比较枚举成员（单例，等价于 ==）
        if strategy is QueryStrategy.ES_ONLY:
            return self.esQueryService.querySnapshotFlowByEs(
                startTime, endTime, plateNumber, gantryCode, sectionCode,
                orgCode, pageNum, pageSize)
        if strategy is QueryStrategy.DB_ONLY:
            return self.dbQueryService.querySnapshotFlowOptimized(
                startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode)
        # case ES_FIRST_THEN_DB: default:
        return self.parallelOrFallbackQuery(
            startTime, endTime, plateNumber, gantryCode, sectionCode,
            orgCode, pageNum, pageSize)

    # ====================================================================
    # 决策
    # ====================================================================
    def decideStrategy(self, startTime: str, endTime: str, plateNumber: str,
                       gantryCode: str, sectionCode: str) -> QueryStrategy:
        """决策：根据查询条件选择最优策略

        规则：
          1. 完整车牌号(7-8位) - 优先级高的等值查询：ES_FIRST_THEN_DB
          2. 全模糊查询（如 "赣", "A1"）且时间范围大 - 用ES
          3. 有明确的 gantrycode/sectioncode/orgcode 且时间范围 <=7天 - 用DB
          4. 默认 - ES_FIRST_THEN_DB
        """
        # 条件1：完整车牌 - ES优先
        # 【Java→Python】`plateNumber != null && plateNumber.length() >= 7`
        # → `is not None and len(...) >= 7`（原代码用长度判断，未走正则，缺陷保留）
        isFullPlate: bool = plateNumber is not None and len(plateNumber) >= 7
        # 条件2：精确字段是否有值
        hasExactField: bool = ((gantryCode is not None and len(gantryCode) != 0)
                               or (sectionCode is not None and len(sectionCode) != 0))
        # 条件3：估算时间范围天数
        timeRangeDays: int = self.estimateDayRange(startTime, endTime)

        if not self.esRouteEnabled:
            return QueryStrategy.DB_ONLY

        # 完整车牌 - ES
        if isFullPlate:
            return QueryStrategy.ES_FIRST_THEN_DB

        # 有精确字段且时间范围<=7天 - DB
        if hasExactField and timeRangeDays <= 7 and timeRangeDays > 0:
            return QueryStrategy.DB_ONLY

        # 时间范围大 - ES优先
        if timeRangeDays > 30:
            return QueryStrategy.ES_FIRST_THEN_DB

        # 全模糊查询 - ES_FIRST_THEN_DB
        return QueryStrategy.ES_FIRST_THEN_DB

    # ====================================================================
    # 并行或降级查询
    # ====================================================================
    def parallelOrFallbackQuery(
        self,
        startTime: str,
        endTime: str,
        plateNumber: str,
        gantryCode: str,
        sectionCode: str,
        orgCode: str,
        pageNum: int,
        pageSize: int,
    ) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """并行或降级查询：先查 ES，失败则查询数据库"""
        esFuture: Optional[Future] = None
        dbFuture: Optional[Future] = None

        try:
            # 并行查询策略：ES和数据库并行查询，先返回的优先
            if self.parallelEnabled:
                # 【Java→Python】Java 的 lambda 内含 try/catch，Python 的 lambda
                # 只能是表达式，因此改写为嵌套函数 + submit。
                def _esTask() -> List[OdsRtSzdnSnapshotFlowAddcode]:
                    try:
                        return self.esQueryService.querySnapshotFlowByEs(
                            startTime, endTime, plateNumber, gantryCode,
                            sectionCode, orgCode, pageNum, pageSize)
                    except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                        # 【Java→Python】`log.warn(msg, e)` → `log.warning(msg, exc_info=True)`
                        log.warning("[组合查询] ES 并行查询失败", exc_info=True)
                        return []

                def _dbTask() -> List[OdsRtSzdnSnapshotFlowAddcode]:
                    try:
                        return self.dbQueryService.querySnapshotFlowOptimized(
                            startTime, endTime, plateNumber, gantryCode,
                            sectionCode, orgCode)
                    except Exception:  # noqa: BLE001
                        log.warning("[组合查询] DB 并行查询失败", exc_info=True)
                        return []

                esFuture = self.executorService.submit(_esTask)
                dbFuture = self.executorService.submit(_dbTask)

                # ES优先，成功直接返回
                esResult: List[OdsRtSzdnSnapshotFlowAddcode] = esFuture.get(
                    self.queryTimeoutMs, TimeUnit.MILLISECONDS)
                if esResult is not None and len(esResult) != 0:
                    log.info("[组合查询] ES查询成功，返回结果 size=%s", len(esResult))
                    return esResult

                # ES查询为空，返回DB
                dbResult: List[OdsRtSzdnSnapshotFlowAddcode] = dbFuture.get(
                    self.queryTimeoutMs, TimeUnit.MILLISECONDS)
                log.info("[组合查询] ES为空，返回DB查询结果 size=%s", len(dbResult))
                return dbResult

            # 串行：先ES后降级
            esResult = self.esQueryService.querySnapshotFlowByEs(
                startTime, endTime, plateNumber, gantryCode, sectionCode,
                orgCode, pageNum, pageSize)
            if esResult is not None and len(esResult) != 0:
                return esResult
            return self.dbQueryService.querySnapshotFlowOptimized(
                startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode)

        except TimeoutError:
            # 【Java→Python】`catch (TimeoutException e)` → `except TimeoutError`
            # （替身的 Future.get 超时抛内置 TimeoutError）
            log.error("[组合查询] 查询超时 timeOut=%sms", self.queryTimeoutMs,
                      exc_info=True)
            return []
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[组合查询] 查询异常", exc_info=True)
            return []

    # ====================================================================
    # 时间范围估算
    # ====================================================================
    def estimateDayRange(self, startTime: str, endTime: str) -> int:
        """估算时间范围的天数 - 用于路由决策"""
        try:
            if startTime is None or endTime is None:
                return _INT_MAX_VALUE
            # 简化：解析时间字符串并计算天数差
            # 【Java→Python】`java.time.Duration.between(...).toDays()` → Duration 替身；
            # `(int)` 强转 → `int()`（向零截断，Java 语义）
            start: LocalDateTime = LocalDateTime.parse(startTime, _TIME_FORMATTER)
            end: LocalDateTime = LocalDateTime.parse(endTime, _TIME_FORMATTER)
            return int(Duration.between(start, end).toDays()) + 1
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            return _INT_MAX_VALUE

    # ====================================================================
    # 交易流水 - 组合查询入口
    # ====================================================================
    def queryFeeRecords(self, startTime: str, endTime: str, vehiclePlate: str,
                        gantryId: str, sectionCode: str,
                        pageNum: int, pageSize: int) -> List[OdsLwzxsfsjFeeRecords01]:
        """交易流水 - 组合查询入口"""
        strategy: QueryStrategy = self.decideStrategy(
            startTime, endTime, vehiclePlate, gantryId, sectionCode)
        log.info("[组合查询-交易] 策略 strategy=%s", strategy)

        # 【Java→Python】`case ES_ONLY: case ES_FIRST_THEN_DB:` 的贯穿语义 → `or`
        if (strategy is QueryStrategy.ES_ONLY
                or strategy is QueryStrategy.ES_FIRST_THEN_DB):
            esResult: List[OdsLwzxsfsjFeeRecords01] = (
                self.esQueryService.queryFeeRecordsByEs(
                    startTime, endTime, vehiclePlate, gantryId, sectionCode,
                    pageNum, pageSize))
            if esResult is not None and len(esResult) != 0:
                return esResult
            # 降级
            return self.dbQueryService.queryFeeRecordsOptimized(
                startTime, endTime, vehiclePlate, gantryId)

        # case DB_ONLY: default:
        return self.dbQueryService.queryFeeRecordsOptimized(
            startTime, endTime, vehiclePlate, gantryId)

    # ====================================================================
    # 轨迹数据 - 组合查询入口
    # ====================================================================
    def queryTrailFitting(self, startTime: str, endTime: str, envehicleid: str,
                          stationName: str,
                          pageNum: int, pageSize: int) -> List[ZdataTrailFitting]:
        """轨迹数据 - 组合查询入口"""
        strategy: QueryStrategy = self.decideStrategy(
            startTime, endTime, envehicleid, None, None)
        log.info("[组合查询-轨迹] 策略 strategy=%s", strategy)

        if (strategy is QueryStrategy.ES_ONLY
                or strategy is QueryStrategy.ES_FIRST_THEN_DB):
            esResult: List[ZdataTrailFitting] = (
                self.esQueryService.queryTrailFittingByEs(
                    startTime, endTime, envehicleid, stationName, pageNum, pageSize))
            if esResult is not None and len(esResult) != 0:
                return esResult
            return self.dbQueryService.queryTrailFittingOptimized(
                startTime, endTime, envehicleid, stationName)

        # case DB_ONLY: default:
        return self.dbQueryService.queryTrailFittingOptimized(
            startTime, endTime, envehicleid, stationName)

    # ====================================================================
    # 健康检查
    # ====================================================================
    def healthCheck(self) -> dict:
        """查询状态健康检查"""
        # 【Java→Python】`Map<String, Object> health = new HashMap<>()` → dict
        health: dict = {}
        health["esAvailable"] = self.esQueryService.checkHealth()
        health["dbRouteEnabled"] = self.esRouteEnabled
        health["parallelEnabled"] = self.parallelEnabled
        health["queryTimeoutMs"] = self.queryTimeoutMs
        return health

    def __repr__(self) -> str:
        return ("CompositeQueryOptimizationService(esRouteEnabled=%s, "
                "parallelEnabled=%s, queryTimeoutMs=%d)" %
                (self.esRouteEnabled, self.parallelEnabled, self.queryTimeoutMs))


# 【Java→Python】Java 的内部枚举通过 `CompositeQueryOptimizationService.QueryStrategy`
# 访问；挂到类属性上保持同一访问路径（与 QueryValidationService.ValidationResult 一致）。
CompositeQueryOptimizationService.QueryStrategy = QueryStrategy
