# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.UnifiedExportService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedExportService.java

统一异步导出服务（3 大表通用）/ Unified async export service.

====================================================================
设计目标：
  面向"单次导出 >100 万条"场景，避免 OOM 与 HTTP 超时。

实现要点：
  1. 异步任务：调用方立即返回 taskId，后台线程池执行
  2. ES Scroll API：每次拉取 scrollBatchSize 条，避免 from+size 深分页性能问题
  3. 流式写盘：每 exportBatchSize 条切一个 CSV 文件，避免堆内存堆积
  4. 进度上报：内存 Map 实时记录状态，前端轮询获取

与 LargeScaleQueryService.submitExportTask 的区别：
  - 通用化：3 表共用同一导出路径，按数据源抽象出 time field / index / 列定义
  - 独立线程池：避免与查询服务竞争线程
  - 可观测：导出完成后保留可下载的文件路径

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；4 个 `@Value` 字段 → 构造器里
   `Environment().value(...)`（字段名保持 Java 的 camelCase，便于逐字对照）；
   2 个 `@Autowired` → 构造器可选参数。
2) **`esClient` 复用 indexManageService 的同一个客户端**（与 UnifiedQueryService 同款处理）：
   Java 里 `RestHighLevelClient` 是单例 Bean，两个 `@Autowired` 注入的是同一个对象，
   不能在这里新建第二个连接池。
3) `private static final Map<...> COLUMNS`（静态初始化块）→ 模块级 dict，并在类体里
   `COLUMNS = COLUMNS` 挂回类属性（Java 语义是"类级常量"）。dict 的插入顺序无关紧要：
   只按 `DataSource` 键取值，不迭代。
4) `public static class ExportTaskStatus` → 模块级类 + 类属性挂回。
   Java 用的是 `public volatile` **字段**（控制器直接读 `status.totalExported`、
   `status.filePaths` 等），因此这里同样用公开实例属性、**不提供 getter**。
   `volatile` 在 Python 无对应关键字：属性赋值本身是原子的，且 CPython 有 GIL。
5) `Collections.synchronizedList(new ArrayList<>())` → 普通 `list`：
   单个 `append` 在 GIL 下是原子操作，导出线程与轮询线程并发读写的语义一致。
6) `private static class NamedThreadFactory` → 模块级 `_NamedThreadFactory(ThreadFactory)`；
   `new Thread(r, name)` + `setDaemon(true)` → `threading.Thread` + `daemon=True`
   （与 LargeScaleQueryService / HighPerformanceSyncService 的既有替身写法一致）。
7) `taskStatusMap.entrySet().removeIf(predicate)` → 先取 key 快照再逐个 `del`。
   Java 的 removeIf 在 `ConcurrentHashMap` 上是逐项原子删除；Python 这里对 dict 的
   `del` 同样由 GIL 保护，差别仅在于"遍历期间新插入的任务"可能不在快照里
   （这些任务本来就早于阈值，不影响正确性）。
8) **枚举名**：`ds.name()`（Java 枚举方法）→ `ds.name`（Python Enum 的属性）。
   `UnifiedQueryService.DataSource` 沿用了“属性式”写法（见其文件头及
   LargeScaleQueryController），因此这里不加括号；日志里的 `{}` 传 `ds` 会输出
   `DataSource.FEE`，故同样改传 `ds.name` 以对齐 Java 的 `ds.toString()`。
9) `switch (ds) { case SNAPSHOT: ... default: throw new IllegalArgumentException(...) }`
   → `if/elif` + 末尾 `raise ValueError`（Python 的 ValueError 对应 IllegalArgumentException）。
   注意本类**没有**复用 `EsIndexManageService.resolveIndexName`：Java 原文是直接调用
   `getSnapshotIndex/getFeeIndex/getTrailIndex`，这里保持原样（两者的异常文案不同）。
10) 文件导出：`Paths.get` / `Files.createDirectories` / `Files.newBufferedWriter` →
    `pathlib.Path` + `mkdir(parents=True, exist_ok=True)` +
    `open(..., encoding="utf-8", newline="")`（`newline=""` 对应 BufferedWriter
    不做行尾转换，与 LargeScaleQueryService 一致）。
11) **CSV 转义只判断 `,` / `\\n` / `"`**（原文如此，**没有**判断 `\\r`），
    因此含 `\\r` 的值不整体加引号 —— 与 LargeScaleQueryService 的 detail 列处理不同，
    这里逐字保留原行为。
12) `throws Exception` → Python 不声明受检异常，`executeExportScroll` 照常向上抛。
13) `log.error(fmt, taskId, e)` / `log.warn(fmt, taskId, e)`（最后一个参数是 Throwable）
    → `exc_info=True`。
14) `Thread.currentThread().interrupt()` → `java.lang.Thread` 替身的同名方法
    （Python 线程无中断标志位，替身用 threading.local 模拟，详见 java/lang/Thread.py）。
15) `sourceBuilder.fetchSource(String[], String[])` 已由 ES 替身支持（只记录不裁剪）。
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from com.ruoyi.base.service.optimization.EsIndexManageService import EsIndexManageService
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from java.lang.System import System
from java.lang.Thread import InterruptedException, Thread
from java.util.UUID import UUID
from java.util.concurrent.ConcurrentHashMap import ConcurrentHashMap
from java.util.concurrent.Executors import ThreadFactory
from java.util.concurrent.LinkedBlockingQueue import LinkedBlockingQueue
from java.util.concurrent.ThreadPoolExecutor import ThreadPoolExecutor
from java.util.concurrent.TimeUnit import TimeUnit
from java.util.concurrent.atomic.AtomicInteger import AtomicInteger
from org.elasticsearch.action.search.ClearScrollRequest import ClearScrollRequest
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchScrollRequest import SearchScrollRequest
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.QueryBuilder import QueryBuilder
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.index.query.RangeQueryBuilder import RangeQueryBuilder
from org.elasticsearch.search.Scroll import Scroll
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder
from org.elasticsearch.search.sort.SortOrder import SortOrder
from org.springframework.core.env.Environment import Environment

__all__ = ["COLUMNS", "ExportTaskStatus", "UnifiedExportService"]

log = logging.getLogger(__name__)

#: 三种数据源的列定义（导出 CSV 表头）
#: Java: `private static final Map<UnifiedQueryService.DataSource, List<String>> COLUMNS`
COLUMNS: Dict[Any, List[str]] = {
    UnifiedQueryService.DataSource.SNAPSHOT: [
        "datauuid", "platenumber", "gantrycode", "gantryname",
        "sectioncode", "sectionname", "roadcode", "roadname",
        "orgcode", "orgname", "snapshottime", "platecolor",
    ],
    UnifiedQueryService.DataSource.FEE: [
        "big_id", "vehicleplate", "gantryid", "gantryname",
        "sectioncode", "sectionname", "roadname", "tollname",
        "orgname", "transtime", "fee", "axlecount", "passstate",
    ],
    UnifiedQueryService.DataSource.TRAIL: [
        "cid", "envehicleid", "exvehicleid",
        "entollstationname", "extollstationname",
        "entime", "extime", "envehicleclass", "exvehicleclass",
    ],
}


class ExportTaskStatus(object):
    """导出任务状态（Java 侧为 UnifiedExportService.ExportTaskStatus）。

    【Java→Python】字段与 Java 逐一对应，全部公开、无 getter：
    控制器（UnifiedQueryController.getExportStatus）直接读
    `status.status` / `status.totalExported` / `status.filePaths` 等。
    """

    def __init__(self) -> None:
        self.taskId: Optional[str] = None
        self.dataSource: Optional[str] = None
        self.startTime: Optional[str] = None
        self.endTime: Optional[str] = None
        #: PENDING / RUNNING / COMPLETED / FAILED
        self.status: Optional[str] = None
        self.submitTime: int = 0
        self.finishTime: int = 0
        self.totalExported: int = 0
        self.filePartCount: int = 0
        self.errorMessage: Optional[str] = None
        #: 已生成的 CSV 文件列表（Java 为 synchronizedList）
        self.filePaths: List[str] = []

    def __repr__(self) -> str:
        return ("ExportTaskStatus(taskId=%r, dataSource=%r, status=%r, "
                "totalExported=%d, filePartCount=%d)" %
                (self.taskId, self.dataSource, self.status,
                 self.totalExported, self.filePartCount))


class _NamedThreadFactory(ThreadFactory):
    """`private static class NamedThreadFactory implements ThreadFactory` 的替身。

    线程命名规则与原实现一致：`<prefix>-<自增序号>`，且为 daemon 线程。
    """

    def __init__(self, prefix: str) -> None:
        self.counter = AtomicInteger(0)
        self.namePrefix = prefix

    def newThread(self, target: Any) -> Any:
        # 【Java→Python】Java 用 `new Thread(r, name).setDaemon(true)`；
        # Python 只能返回 threading.Thread，daemon 显式置位。
        thread = threading.Thread(
            target=target,
            name=self.namePrefix + "-" + str(self.counter.incrementAndGet()))
        thread.daemon = True
        return thread


class UnifiedExportService(object):
    """统一异步导出服务（`@Service`）。"""

    #: `private static final Map<...> COLUMNS` 的类级访问路径
    COLUMNS = COLUMNS

    def __init__(self,
                 esClient: Optional[Any] = None,
                 indexManageService: Optional[EsIndexManageService] = None) -> None:
        # 【Java→Python】`@Autowired` 字段注入 → 构造器可选参数。
        # esClient 必须复用 indexManageService 内部的同一个客户端（单例 Bean 语义）。
        self.indexManageService: EsIndexManageService = (
            indexManageService if indexManageService is not None
            else EsIndexManageService())
        self.esClient: Any = (
            esClient if esClient is not None else self.indexManageService.esClient)

        # 单次 scroll 拉取的文档数（过大内存压力大，过小IO频繁）
        self.scrollBatchSize: int = Environment().value(
            "${optimization.export.scroll-batch:2000}", int)
        # 每 exportBatchSize 条切一个文件
        self.exportBatchSize: int = Environment().value(
            "${optimization.export.file-batch:100000}", int)
        # 导出文件根目录
        self.exportDir: str = Environment().value(
            "${optimization.export.dir:/data/export}", str)
        # Scroll 上下文保留时长（分钟）
        self.scrollKeepaliveMin: int = Environment().value(
            "${optimization.export.scroll-keepalive-min:5}", int)

        # 导出任务线程池（独立于查询服务，避免互相挤占）
        self.exportExecutor = ThreadPoolExecutor(
            2, 4, 60, TimeUnit.SECONDS,
            LinkedBlockingQueue(200),
            _NamedThreadFactory("export-worker"),
            ThreadPoolExecutor.CallerRunsPolicy())
        # 任务状态追踪 Map（taskId -> ExportTaskStatus）
        self.taskStatusMap = ConcurrentHashMap()

    # ============================================================
    # 公共入口
    # ============================================================
    def submitExportTask(self, ds: Any, startTime: str, endTime: str,
                         fuzzyFields: Optional[Dict[str, str]]) -> str:
        """提交异步导出任务。

        :param ds: 数据源类型 / data source
        :param startTime: 起始时间 yyyy-MM-dd HH:mm:ss
        :param endTime: 结束时间 / end time
        :param fuzzyFields: 模糊字段（key=字段名，value=模糊内容）；可为空
        :return: taskId 调用方凭此轮询状态/下载
        """
        taskId: str = UUID.randomUUID().toString()
        status = ExportTaskStatus()
        status.taskId = taskId
        # 【Java→Python】Java 的 `ds.name()` → Python Enum 的 `ds.name` 属性
        status.dataSource = ds.name
        status.startTime = startTime
        status.endTime = endTime
        status.status = "PENDING"
        status.submitTime = System.currentTimeMillis()
        self.taskStatusMap.put(taskId, status)

        def _runExport() -> None:
            # 【Java→Python】lambda 实现 Runnable；catch 后置 FAILED 与原代码一致
            try:
                self.executeExportScroll(taskId, ds, startTime, endTime, fuzzyFields)
            except Exception as error:  # noqa: BLE001 - catch (Exception e)
                log.error("[统一导出] task=%s 执行失败", taskId, exc_info=True)
                status.status = "FAILED"
                status.errorMessage = str(error)
                status.finishTime = System.currentTimeMillis()

        self.exportExecutor.submit(_runExport)

        log.info("[统一导出] 已提交任务 taskId=%s, ds=%s, time=%s~%s, fuzzyFields=%s",
                 taskId, ds.name, startTime, endTime,
                 0 if fuzzyFields is None else len(fuzzyFields))
        return taskId

    def getExportStatus(self, taskId: str) -> Optional[ExportTaskStatus]:
        """查询导出任务状态（不存在返回 None，Java 返回 null）。"""
        return self.taskStatusMap.get(taskId)

    def cleanExpiredTasks(self, maxAgeMs: int) -> None:
        """清理过期的任务状态（避免内存泄漏）。

        建议由定时任务每天调用一次，清理超过 7 天的已完成任务。

        【Java→Python】`entrySet().removeIf(...)` → 先取 key 快照再逐个删除
        （详见文件头第 7 条）。
        """
        threshold: int = System.currentTimeMillis() - maxAgeMs
        for taskId in list(self.taskStatusMap.keys()):
            status: ExportTaskStatus = self.taskStatusMap.get(taskId)
            if (status.status == "COMPLETED" or status.status == "FAILED") \
                    and status.finishTime > 0 and status.finishTime < threshold:
                del self.taskStatusMap[taskId]

    def destroy(self) -> None:
        """`@PreDestroy destroy()`：停掉导出线程池。"""
        self.exportExecutor.shutdown()
        try:
            self.exportExecutor.awaitTermination(5, TimeUnit.SECONDS)
        except InterruptedException:
            Thread.currentThread().interrupt()

    # ============================================================
    # 核心导出实现：ES Scroll + 流式 CSV
    # ============================================================
    def executeExportScroll(self, taskId: str, ds: Any, startTime: str,
                            endTime: str,
                            fuzzyFields: Optional[Dict[str, str]]) -> None:
        """核心：ES Scroll + 流式写 CSV（Java 侧为 private）。"""
        status: ExportTaskStatus = self.taskStatusMap.get(taskId)
        status.status = "RUNNING"
        log.info("[统一导出] task=%s 开始执行", taskId)

        # 1. 构建查询
        boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()
        boolQuery.filter(self.buildTimeRange(ds, startTime, endTime))

        if fuzzyFields is not None:
            for key, value in fuzzyFields.items():
                if value is None or len(value) == 0:
                    continue
                # 智能模糊策略（与 UnifiedQueryService 统一）
                boolQuery.must(self.buildFuzzyQuery(key, value))

        sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
        sourceBuilder.query(boolQuery)
        sourceBuilder.size(self.scrollBatchSize)
        sourceBuilder.sort(self.resolveTimeField(ds), SortOrder.DESC)
        sourceBuilder.timeout(TimeValue(120, TimeUnit.SECONDS))
        # 导出时不做 terminate_after 限制，按条件完整导出
        sourceBuilder.fetchSource(list(COLUMNS[ds]), None)

        # 2. 初始化 scroll
        searchRequest: SearchRequest = SearchRequest(self.resolveIndexName(ds))
        searchRequest.source(sourceBuilder)
        searchRequest.scroll(Scroll(TimeValue(self.scrollKeepaliveMin, TimeUnit.MINUTES)))

        scrollResp = self.esClient.search(searchRequest, RequestOptions.DEFAULT)
        scrollId: Optional[str] = scrollResp.getScrollId()

        totalCount = 0
        filePartIndex = 0
        currentWriter: Any = None

        # 【Java→Python】try 的位置与原文一致：`esClient.search` 在 try **之前**，
        # 因此“首页查询失败”不会进入 finally 的 clearScroll。
        try:
            # 3. 循环 scroll 直到无更多数据
            while len(scrollResp.getHits().getHits()) > 0:
                # 3.1 切分文件：每 exportBatchSize 条开一个新 CSV
                if currentWriter is None or totalCount % self.exportBatchSize == 0:
                    if currentWriter is not None:
                        currentWriter.close()
                    filePartIndex += 1
                    filePath: Path = Path(self.exportDir, "export_" + taskId
                                          + "_p" + str(filePartIndex) + ".csv")
                    # 确保目录存在（对应 Files.createDirectories）
                    filePath.parent.mkdir(parents=True, exist_ok=True)
                    # 【Java→Python】Files.newBufferedWriter 默认 UTF-8；
                    # newline="" 对应 BufferedWriter 不做行尾转换
                    currentWriter = open(filePath, "w", encoding="utf-8", newline="")
                    # 文件头
                    currentWriter.write(",".join(COLUMNS[ds]) + "\n")
                    status.filePaths.append(str(filePath))
                    log.info("[统一导出] task=%s 切分新文件 part=%s", taskId, filePartIndex)

                # 3.2 写入当前批次
                for hit in scrollResp.getHits().getHits():
                    doc: Dict[str, Any] = hit.getSourceAsMap()
                    line: List[str] = []
                    for index, column in enumerate(COLUMNS[ds]):
                        if index > 0:
                            line.append(",")
                        value = doc.get(column)
                        if value is not None:
                            # CSV 转义：包含逗号/换行/引号时加引号并转义引号
                            text = str(value)
                            if "," in text or "\n" in text or '"' in text:
                                line.append('"' + text.replace('"', '""') + '"')
                            else:
                                line.append(text)
                    currentWriter.write("".join(line) + "\n")
                    totalCount += 1
                status.totalExported = totalCount

                # 3.3 进度日志（每 scrollBatchSize*50 条打一次）
                if totalCount % (self.scrollBatchSize * 50) == 0:
                    log.info("[统一导出] task=%s 已导出 %s 条, filePart=%s",
                             taskId, totalCount, filePartIndex)

                # 3.4 下一批 scroll
                scrollRequest: SearchScrollRequest = SearchScrollRequest(scrollId)
                scrollRequest.scroll(
                    Scroll(TimeValue(self.scrollKeepaliveMin, TimeUnit.MINUTES)))
                scrollResp = self.esClient.scroll(scrollRequest, RequestOptions.DEFAULT)
                scrollId = scrollResp.getScrollId()

            # 4. 完成
            if currentWriter is not None:
                currentWriter.close()
            status.status = "COMPLETED"
            status.filePartCount = filePartIndex
            status.finishTime = System.currentTimeMillis()
            log.info("[统一导出] task=%s 完成, 共导出 %s 条, 切分为 %s 个 CSV 文件",
                     taskId, totalCount, filePartIndex)
        finally:
            # 关键：清空 scroll 上下文，释放 ES 服务端游标资源
            if currentWriter is not None:
                try:
                    currentWriter.close()
                except Exception:  # noqa: BLE001 - 与 catch (IOException ignored) 一致
                    pass
            try:
                clearReq: ClearScrollRequest = ClearScrollRequest()
                clearReq.addScrollId(scrollId)
                self.esClient.clearScroll(clearReq, RequestOptions.DEFAULT)
            except Exception:  # noqa: BLE001 - catch (Exception e)
                log.warning("[统一导出] task=%s 清空 scroll 上下文失败", taskId,
                            exc_info=True)

    def buildTimeRange(self, ds: Any, startTime: str,
                       endTime: str) -> RangeQueryBuilder:
        """时间范围过滤（Java 侧为 private）。"""
        return (QueryBuilders.rangeQuery(self.resolveTimeField(ds))
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime))

    def buildFuzzyQuery(self, fieldName: str, value: str) -> QueryBuilder:
        """智能模糊查询（与 UnifiedQueryService.buildFuzzyQuery 保持一致）。

        【Java→Python】`"platenumber".equals(fieldName)` → `fieldName == "platenumber"`
        （Java 把常量写在左边避免 NPE；Python 的 `==` 对 None 天然安全）。
        注意本方法判断的字段集合比 LargeScaleQueryService 的版本**少**：
        原文只有 platenumber / gantrycode / sectioncode 三个，逐字保留。
        """
        if len(value) >= 7 and (fieldName == "platenumber"
                                or fieldName == "gantrycode"
                                or fieldName == "sectioncode"):
            return QueryBuilders.termQuery(fieldName + ".keyword", value)
        if len(value) >= 3:
            return QueryBuilders.matchQuery(fieldName + ".ngram", value)
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*")

    def resolveIndexName(self, ds: Any) -> str:
        """按数据源解析索引名（Java 侧为 private）。"""
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return self.indexManageService.getSnapshotIndex()
        if ds is UnifiedQueryService.DataSource.FEE:
            return self.indexManageService.getFeeIndex()
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return self.indexManageService.getTrailIndex()
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + str(ds))

    def resolveTimeField(self, ds: Any) -> str:
        """按数据源解析时间字段（Java 侧为 private）。"""
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return "snapshottime"
        if ds is UnifiedQueryService.DataSource.FEE:
            return "transtime"
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return "extime"
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + str(ds))
