# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.GaussEsConsistencyService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/GaussEsConsistencyService.java

GaussDB ↔ Elasticsearch 一致性对账与修复服务
GaussDB ↔ Elasticsearch consistency reconciliation & repair service.

=================================================================================
背景 / Background:
  异步线程消费 Kafka 写 ES 与 GaussDB 之间天然存在时序漂移（写 DB 成功但写 ES 失败、
  写入延迟、消息重复/丢失）。本服务是「四层一致性保障」的最后一层（兜底中的兜底）。

四层保障 / 4-layer guarantee:
  1) 应用双写 (Async Dual-Write)      —— 主路径，_id=业务主键 保证幂等
  2) Redis 水位增量同步                —— 日常补偿，at-least-once + 幂等 = exactly-once
  3) Debezium CDC 兜底                 —— 捕获型补偿，覆盖双写缺失窗口
  4) 本服务：定时对账 + 修复            —— 低频全量校验，以 GaussDB 为准回灌 ES

对账思路 / Reconciliation approach:
  按「月分区」对 GaussDB 与 ES 在相同时间窗内做 COUNT 比对；条数不一致即视为漂移，
  触发 repairSync 以 GaussDB 为准重跑该时间窗，回灌 ES（_id 幂等覆盖）。

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；3 个 `@Value` → 构造器里 `Environment().value(...)`；
   6 个 `@Autowired` → 构造器可选参数（缺省 `or new Xxx()`，esClient 复用
   `indexManageService.esClient`，与 UnifiedQueryService / UnifiedExportService 一致）。
2) **`@Scheduled(cron = "${consistency.reconcile.cron:0 30 2 * * ?}")` → 装饰器**：
   Python 用 `org.springframework.scheduling.annotation.Scheduled` 还原（元数据挂
   `__scheduled__`，占位符在**启动时**才解析），由 `app/scheduler` 扫描后交给
   `ThreadPoolTaskScheduler` 按 cron 排期。
   方法体内的 `if not reconcileEnabled: return` 守卫**原样保留**——
   即使被调度器无条件调用，行为也与 Java 完全一致（默认关闭）。
3) `public static class ConsistencyReport` → 模块级类 + 类属性挂回。
   字段全 public（Java 是 public 字段，非 getter），`toString()` 是**自定义格式**，
   必须显式实现（不能退回 JavaBean 的 Lombok 格式）。
4) `private static final SimpleDateFormat SDF` → 模块级 `SDF`。
   注意 Java 的 SimpleDateFormat **非线程安全**（多线程共用一个 static 实例是隐患），
   替身用无状态的 strftime/strptime，天然线程安全 —— 结果相同，隐患消失。
5) `new QueryWrapper<Xxx>().between("field", start, end)` → 同名替身（泛型参数不参与运行期）。
   `parse()` 把时间串转成 `datetime` 后作为 between 的边界值传入。
6) `Math.abs(long)` → 内置 `abs()`；三元嵌套的 `ratio` → 条件表达式（保留原判断顺序）。
7) `"DRIFT".equals(report.status)` → `report.status == "DRIFT"`（Java 常量在左侧防 NPE，
   Python 的 `==` 对 None 天然安全）。
8) `new Thread(() -> triggerRepair(fds, start, end), "consistency-repair-" + ds).start()`
   → `threading.Thread(target=..., name=...)` + `start()`。
   Java 的 `final DataSource fds = ds;`（lambda 捕获要求）在 Python 不需要
   （闭包直接捕获 `ds`，且每轮循环都是新绑定），这里直接用 `ds`。
   线程名里的 `"consistency-repair-" + ds` 用的是 `ds.toString()` → `ds.name`。
9) `log.error(fmt, ds, start, end, e)`（最后一个参数是 Throwable）→ `exc_info=True`；
   日志里的 `ds` 是 `ds.toString()`，故改传 `_java_str(ds)`（见该函数说明）。
10) `throws Exception` 在 `countInEs` 上 → Python 不声明受检异常，照常向上抛，
    由 `reconcile` 的 `except Exception` 兜住并置 status="ERROR"。
11) `throw new RuntimeException("时间解析失败: " + s, e)` → `raise RuntimeError(...) from error`
    （`from` 即 Java 的 cause 链）；`e.getMessage()` → `str(e)`。
12) `Date` → Python 的 `datetime`（Calendar 替身的 `getTime()` 返回 `datetime`）。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from com.baomidou.mybatisplus.core.conditions.query.QueryWrapper import QueryWrapper
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import OdsLwzxsfsjFeeRecords01Mapper
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from com.ruoyi.base.service.optimization.EsIndexManageService import EsIndexManageService
from com.ruoyi.base.service.optimization.LargeScaleDataSyncService import (
    LargeScaleDataSyncService,
)
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from java.text.SimpleDateFormat import SimpleDateFormat
from java.util.Calendar import Calendar
from java.util.concurrent.atomic.AtomicLong import AtomicLong
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchResponse import SearchResponse
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.index.query.RangeQueryBuilder import RangeQueryBuilder
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder
from org.springframework.core.env.Environment import Environment
from org.springframework.scheduling.annotation.Scheduled import Scheduled

__all__ = ["ConsistencyReport", "GaussEsConsistencyService", "SDF"]

log = logging.getLogger(__name__)

#: `private static final SimpleDateFormat SDF`（线程安全隐患见文件头第 4 条）
SDF = SimpleDateFormat("yyyy-MM-dd HH:mm:ss")


def _java_str(value: Any) -> str:
    """复刻 Java 字符串拼接语义：`null` → `"null"`，枚举 → 常量名。

    【Java→Python】日志/`toString` 里的 `ds` 在 Java 走 `Enum.toString()`（= name）；
    Python 的 `str(DataSource.SNAPSHOT)` 会输出 `"DataSource.SNAPSHOT"`，需要还原。
    本工程的枚举有两种 `name` 形态：属性式（DataSource）与方法式（DataScaleLevel），
    这里两种都兼容。
    """
    if value is None:
        return "null"
    if isinstance(value, Enum):
        name = value.name
        return name() if callable(name) else name
    return str(value)


class ConsistencyReport(object):
    """一致性对账报告（Java 侧为 GaussEsConsistencyService.ConsistencyReport）。

    【Java→Python】字段在 Java 里是 public（非 getter），这里同样是公开属性。
    `long` 字段 → int（Python 整数无上限）。
    """

    def __init__(self) -> None:
        #: 数据源 / data source
        self.dataSource: Any = None
        self.startTime: Optional[str] = None
        self.endTime: Optional[str] = None
        #: GaussDB 侧条数
        self.gaussDbCount: int = 0
        #: ES 侧条数
        self.esCount: int = 0
        #: 差异条数
        self.diff: int = 0
        #: CONSISTENT / DRIFT / ERROR
        self.status: Optional[str] = None
        #: 处理建议
        self.suggestion: Optional[str] = None

    def __str__(self) -> str:
        """自定义 toString（Java 侧手写拼接，**不是** Lombok 格式）。"""
        return ("ConsistencyReport{ds=" + _java_str(self.dataSource)
                + ", range=[" + _java_str(self.startTime) + ","
                + _java_str(self.endTime) + ")"
                + ", gaussDb=" + _java_str(self.gaussDbCount)
                + ", es=" + _java_str(self.esCount)
                + ", diff=" + _java_str(self.diff)
                + ", status=" + _java_str(self.status)
                + ", suggestion=" + _java_str(self.suggestion) + "}")

    def __repr__(self) -> str:
        return self.__str__()


class GaussEsConsistencyService(object):
    """GaussDB ↔ ES 一致性对账与修复服务（`@Service`）。"""

    #: `public static class ConsistencyReport` 的类级访问路径
    ConsistencyReport = ConsistencyReport

    def __init__(self,
                 esClient: Optional[RestHighLevelClient] = None,
                 indexManageService: Optional[EsIndexManageService] = None,
                 dataSyncService: Optional[LargeScaleDataSyncService] = None,
                 snapshotMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 feeMapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 trailMapper: Optional[ZdataTrailFittingMapper] = None) -> None:
        # 【Java→Python】`@Autowired` 字段注入 → 构造器可选参数
        self.indexManageService: EsIndexManageService = (
            indexManageService if indexManageService is not None
            else EsIndexManageService())
        # esClient 复用 indexManageService 内部的同一个客户端（单例 Bean 语义）
        self.esClient: RestHighLevelClient = (
            esClient if esClient is not None else self.indexManageService.esClient)
        self.dataSyncService: LargeScaleDataSyncService = (
            dataSyncService if dataSyncService is not None
            else LargeScaleDataSyncService())
        self.snapshotMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotMapper if snapshotMapper is not None
            else OdsRtSzdnSnapshotFlowAddcodeMapper())
        self.feeMapper: OdsLwzxsfsjFeeRecords01Mapper = (
            feeMapper if feeMapper is not None
            else OdsLwzxsfsjFeeRecords01Mapper())
        self.trailMapper: ZdataTrailFittingMapper = (
            trailMapper if trailMapper is not None
            else ZdataTrailFittingMapper())

        #: 是否开启定时对账任务（默认 false）
        self.reconcileEnabled: bool = Environment().value(
            "${consistency.reconcile.enabled:false}", bool)
        #: 对账回看月份数（仅校验最近 N 个月，控制成本）
        self.lookbackMonths: int = Environment().value(
            "${consistency.reconcile.lookback-months:3}", int)
        #: 漂移告警阈值：ES 与 GaussDB 条数差异超过该比例视为漂移
        self.driftRatio: float = Environment().value(
            "${consistency.reconcile.drift-ratio:0.01}", float)

        #: 累计修复次数（监控用）
        self.repairCounter = AtomicLong(0)

    # ==================================================================
    # 对账
    # ==================================================================
    def reconcile(self, ds: Any, startTime: str, endTime: str) -> ConsistencyReport:
        """对指定数据源在指定时间窗内做一致性对账。

        :param ds: 数据源 / data source
        :param startTime: 起始时间 yyyy-MM-dd HH:mm:ss
        :param endTime: 结束时间 / end time
        :return: 对账报告 / reconciliation report
        """
        report = ConsistencyReport()
        report.dataSource = ds
        report.startTime = startTime
        report.endTime = endTime

        try:
            # 1) GaussDB 侧条数（依赖分区裁剪，按月分区下很快）
            report.gaussDbCount = self.countInGaussDb(ds, startTime, endTime)
            # 2) ES 侧条数（Count API，倒排索引聚合）
            report.esCount = self.countInEs(ds, startTime, endTime)
            # 3) 计算差异与状态
            report.diff = abs(report.gaussDbCount - report.esCount)
            # Java: gaussDbCount == 0 ? (esCount == 0 ? 0 : 1)
            #                       : (double) diff / gaussDbCount
            ratio: float
            if report.gaussDbCount == 0:
                ratio = 0 if report.esCount == 0 else 1
            else:
                ratio = report.diff / report.gaussDbCount
            if report.diff == 0 or ratio <= self.driftRatio:
                report.status = "CONSISTENT"
                report.suggestion = "OK"
            else:
                report.status = "DRIFT"
                report.suggestion = "建议触发 repairSync 以 GaussDB 为准回灌 ES"
            log.info("[一致性对账] %s", report)
        except Exception as error:  # noqa: BLE001 - catch (Exception e)
            log.error("[一致性对账] 对账失败 ds=%s, range=[%s,%s]",
                      _java_str(ds), startTime, endTime, exc_info=True)
            report.status = "ERROR"
            report.suggestion = str(error)
        return report

    def triggerRepair(self, ds: Any, startTime: str, endTime: str) -> None:
        """依据对账差异触发指定时间窗的补同步（以 GaussDB 为准回灌 ES）。"""
        log.info("[一致性修复] 触发补同步 ds=%s, range=[%s,%s]",
                 _java_str(ds), startTime, endTime)
        try:
            self.dataSyncService.repairSync(ds, startTime, endTime)
            self.repairCounter.incrementAndGet()
        except Exception:  # noqa: BLE001 - catch (Exception e)
            log.error("[一致性修复] 补同步失败 ds=%s, range=[%s,%s]",
                      _java_str(ds), startTime, endTime, exc_info=True)

    # ------------------------------------------------------------------
    # @Scheduled(cron = "${consistency.reconcile.cron:0 30 2 * * ?}")
    # ------------------------------------------------------------------
    @Scheduled(cron="${consistency.reconcile.cron:0 30 2 * * ?}")
    def scheduledReconcile(self) -> None:
        """定时对账任务（cron ``0 30 2 * * ?``，默认关闭）。

        设计思路 / Design:
          - 每天凌晨 02:30 执行一次（cron 可在 application.yml 覆盖）
          - 遍历三张表、最近 lookbackMonths 个月，逐月对账
          - 仅当漂移超过阈值时异步触发 repairSync，避免风暴
          - 逐月而非整年一次性，控制单次 COUNT/Count 的资源占用

        【Java→Python】`@Scheduled` 由 `app/scheduler` 在启动时注册并按期调用；
        `if not reconcileEnabled: return` 守卫保持不变（默认关闭，与 Java 一致）。
        """
        if not self.reconcileEnabled:
            return
        log.info("[一致性对账] 定时任务启动, lookback-months=%s", self.lookbackMonths)
        all_sources: List[Any] = UnifiedQueryService.DataSource.values()
        cal: Calendar = Calendar.getInstance()
        # 归零到「本月 1 日 00:00:00.000」——月分区的右边界
        cal.set(Calendar.DAY_OF_MONTH, 1)
        cal.set(Calendar.HOUR_OF_DAY, 0)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)

        for _ in range(self.lookbackMonths):
            monthEnd: datetime = cal.getTime()
            # 回到月初（上个月 1 日 00:00:00）
            cal.add(Calendar.MONTH, -1)
            monthStart: datetime = cal.getTime()
            start: str = SDF.format(monthStart)
            end: str = SDF.format(monthEnd)
            for ds in all_sources:
                try:
                    report: ConsistencyReport = self.reconcile(ds, start, end)
                    if report.status == "DRIFT":
                        # 异步触发修复，避免阻塞对账主流程
                        threading.Thread(target=self.triggerRepair,
                                         args=(ds, start, end),
                                         name="consistency-repair-" + _java_str(ds)).start()
                except Exception:  # noqa: BLE001 - catch (Exception e)
                    log.error("[一致性对账] 月度对账异常 ds=%s, range=[%s,%s]",
                              _java_str(ds), start, end, exc_info=True)
        log.info("[一致性对账] 定时任务完成, 累计修复次数=%s", self.repairCounter.get())

    # ==================================================================
    # 内部实现（Java 侧均为 private）
    # ==================================================================
    def countInGaussDb(self, ds: Any, startTime: str, endTime: str) -> int:
        """GaussDB 侧条数统计。

        【Java→Python】`new QueryWrapper<Xxx>().between("field", start, end)` →
        同名替身（泛型参数不参与运行期）；`Date` → `datetime`。
        """
        start: datetime = self.parse(startTime)
        end: datetime = self.parse(endTime)
        # 注意：Java 原文写的是 `new QueryWrapper<OdsRtSzdnSnapshotFlowAddcode>()`，
        # 显式指定泛型是因为链式 `.between()` 会破坏菱形推断；Python 的类型参数
        # 不参与运行期，故按本工程约定直接 `QueryWrapper()`（见该替身的文件头说明）。
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return self.snapshotMapper.selectCount(
                QueryWrapper().between("snapshottime", start, end))
        if ds is UnifiedQueryService.DataSource.FEE:
            return self.feeMapper.selectCount(
                QueryWrapper().between("transtime", start, end))
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return self.trailMapper.selectCount(
                QueryWrapper().between("extime", start, end))
        # default: return 0L;
        return 0

    def countInEs(self, ds: Any, startTime: str, endTime: str) -> int:
        """ES 侧条数统计（`size(0)` + `track_total_hits` 取精确总数）。

        使用 SearchRequest(size=0 + track_total_hits) 获取精确文档数，
        避免依赖可能不存在的 Count API 类（ES 版本差异）。
        """
        indexName: str = self.resolveIndexName(ds)
        timeField: str = self.resolveTimeField(ds)

        range_query: RangeQueryBuilder = (QueryBuilders.rangeQuery(timeField)
                                          .format("yyyy-MM-dd HH:mm:ss")
                                          .gte(startTime).lte(endTime))
        ssb: SearchSourceBuilder = (SearchSourceBuilder().query(range_query)
                                    .size(0).trackTotalHits(True))
        searchRequest: SearchRequest = SearchRequest(indexName)
        searchRequest.source(ssb)

        response: SearchResponse = self.esClient.search(searchRequest,
                                                       RequestOptions.DEFAULT)
        return int(response.getHits().getTotalHits().value)

    def resolveIndexName(self, ds: Any) -> str:
        """按数据源解析索引名（Java 侧为 private）。"""
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return self.indexManageService.getSnapshotIndex()
        if ds is UnifiedQueryService.DataSource.FEE:
            return self.indexManageService.getFeeIndex()
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return self.indexManageService.getTrailIndex()
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + _java_str(ds))

    def resolveTimeField(self, ds: Any) -> str:
        """按数据源解析时间字段（Java 侧为 private）。"""
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return "snapshottime"
        if ds is UnifiedQueryService.DataSource.FEE:
            return "transtime"
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return "extime"
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + _java_str(ds))

    def parse(self, s: str) -> datetime:
        """时间串 → datetime；解析失败抛 RuntimeException（Java 侧为 private）。"""
        try:
            return SDF.parse(s)
        except Exception as error:  # noqa: BLE001 - catch (Exception e)
            # 【Java→Python】RuntimeException(msg, e) → RuntimeError + `from error`（cause 链）
            raise RuntimeError("时间解析失败: " + s) from error
