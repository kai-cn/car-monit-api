# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.LargeScaleQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleQueryService.java

超大规模数据查询服务（导出 / 统计，三表统一）
Large-scale query service (export / aggregation, unified for 3 tables).

====================================================================
核心设计思路（针对 8 亿条数据）/ Core design for 800M-row scale:
  1. 倒排索引分层：hot(0-30d)/warm(30-90d)/cold/frozen，由 ILM 管理
  2. 全字段模糊查询：ngram 倒排索引（match on .ngram，term/wildcard on .keyword）
  3. 统计：ES aggregation 分布式并行，不拉原始数据到应用层
  4. 导出：PIT + search_after / Scroll 游标深翻页，流式写文件，避免 OOM
  5. 查询保障：search_after 替代 from+size 深翻页；terminate_after + timeout 双保险

本服务支持三表（通过 type 参数区分）：snapshot / fee / trail

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；3 个 `@Value` → 构造器里 `Environment().value(...)`。
2) `@PostConstruct init()` → **构造器末尾显式调用**（与 EsIndexManageService 同款处理）；
   `@PreDestroy destroy()` → 公开方法，由容器/测试负责调用。
3) `private static class Target` → 模块级 `Target`；`public static class ExportTaskStatus`
   → 模块级 `ExportTaskStatus`，**文件末尾挂回类属性**，保证
   `LargeScaleQueryService.ExportTaskStatus` 的访问路径与 Java 一致（控制器在用）。
4) `private static class NamedThreadFactory` → 模块级 `_NamedThreadFactory(ThreadFactory)`；
   Java 的 `new Thread(r, name)` + `setDaemon(true)` → `threading.Thread` + `daemon=True`
   （与 HighPerformanceSyncService 的既有替身写法一致）。
5) `ThreadPoolExecutor(4, 8, 60L, SECONDS, new LinkedBlockingQueue<>(500), factory,
   CallerRunsPolicy)` → 同名 JDK 替身。注意替身**以 maximumPoolSize 作为实际并发上限**
   且不会真正触发 CallerRunsPolicy（详见 java/util/concurrent/ThreadPoolExecutor.py）。
6) `ConcurrentHashMap<String, ExportTaskStatus>` → 同名替身（线程安全 dict）；
   `volatile` 字段 → 普通实例属性（Python 属性赋值本身是原子的）。
7) **方法重载**：Java 有两个 `fuzzyQuery`（5 参=默认 snapshot / 6 参=带 type）。
   Python 不能按「首参类型」区分（两者首参都是 String），因此按**实参个数**分派，
   见 `fuzzyQuery` 的注释。
8) `switch (type.toLowerCase()) { case "fee": ... }` → `if/elif`，**保留 `lower()` 语义**
   （Java 先小写再与小写常量比较）；`type == null` 先归一为 "snapshot"。
9) `for (Map.Entry<String,String> e : map.entrySet())` → `for key, value in map.items()`；
   `value.isEmpty()` → `len(value) == 0`（保留“null/空串都不参与过滤”两处边界判断）。
10) `throws Exception` → **Python 不声明受检异常**，`executeExportScroll` 照常抛。
11) 文件导出：`Paths.get` / `Files.exists` / `Files.createDirectories` /
    `Files.newBufferedWriter` → `pathlib.Path` + `open(..., encoding="utf-8", newline="")`。
    `Files.newBufferedWriter` 默认 UTF-8、`newline=""` 对应 BufferedWriter 不做行尾转换。
12) `JSON.toJSONString(doc)` → fastjson2 替身同名方法（紧凑 JSON、不转义中文）。
13) **顺序语义损失**：`sourceBuilder.sort(timeField, DESC)` 在 ES 替身里只记录不排序
    （见 SearchSourceBuilder.sort 说明），因此查询/导出结果的**顺序**与真实 ES 不同，
    但**集合内容**一致。
14) `log.error(fmt, a, b, e)`（最后一个参数是 Throwable）→ `exc_info=True`。
15) `throw new RuntimeException(msg, e)` → `raise RuntimeError(msg) from error`
    （`from` 即 Java 的 cause 链）；`e.getMessage()` → `str(e)`。
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.service.optimization.EsIndexManageService import EsIndexManageService
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from java.lang.System import System
from java.util.UUID import UUID
from java.util.concurrent.ConcurrentHashMap import ConcurrentHashMap
from java.util.concurrent.Executors import ThreadFactory
from java.util.concurrent.LinkedBlockingQueue import LinkedBlockingQueue
from java.util.concurrent.ThreadPoolExecutor import ThreadPoolExecutor
from java.util.concurrent.TimeUnit import TimeUnit
from java.util.concurrent.atomic.AtomicInteger import AtomicInteger
from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.action.search.ClearScrollRequest import ClearScrollRequest
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchScrollRequest import SearchScrollRequest
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.QueryBuilder import QueryBuilder
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.search.Scroll import Scroll
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.aggregations.AggregationBuilders import AggregationBuilders
from org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms import (
    ParsedStringTerms,
)
from org.elasticsearch.search.aggregations.bucket.terms.Terms import Terms
from org.elasticsearch.search.aggregations.metrics.ValueCount import ValueCount
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder
from org.elasticsearch.search.sort.SortOrder import SortOrder
from org.springframework.core.env.Environment import Environment

__all__ = ["ExportTaskStatus", "LargeScaleQueryService", "Target"]

log = logging.getLogger(__name__)


class Target(object):
    """每类查询的目标（索引名、时间字段、导出列）

    【Java→Python】`private static class Target`（字段均为 final）→ 模块级普通类；
    字段名保持 Java 的 camelCase，代码里 `target.timeField` 与 Java 逐字对应。
    """

    def __init__(self, indexName: str, timeField: str,
                 idField: str, plateField: str) -> None:
        self.indexName = indexName
        self.timeField = timeField
        #: 文档 _id / 业务主键
        self.idField = idField
        #: 车牌/车辆编号字段
        self.plateField = plateField

    def __repr__(self) -> str:
        return "Target(%s, %s, %s, %s)" % (self.indexName, self.timeField,
                                           self.idField, self.plateField)


class ExportTaskStatus(object):
    """导出任务状态 / Export task status

    【Java→Python】Java 用的是 `public volatile` **字段**（控制器直接读
    `status.totalExported` 等），因此这里也用公开实例属性，不提供 getter。
    """

    def __init__(self) -> None:
        self.taskId: Optional[str] = None
        #: PENDING / RUNNING / COMPLETED / FAILED
        self.status: Optional[str] = None
        self.submitTime: int = 0
        self.endTime: int = 0
        self.totalExported: int = 0
        self.filePartCount: int = 0
        self.errorMessage: Optional[str] = None

    def __repr__(self) -> str:
        return "ExportTaskStatus(taskId=%r, status=%r, totalExported=%d)" % (
            self.taskId, self.status, self.totalExported)


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


def _java_str(value: Any) -> str:
    """Java 字符串拼接语义：`null` 拼成 `"null"`（`String.valueOf(null)`）。

    【Java→Python】只用于**文件名**里的 `type`（`export_<type>_<taskId>_p<n>.csv`）。
    CSV 单元格仍按 Java 的三元表达式把 null 写成空串，不走这里。
    """
    return "null" if value is None else str(value)


class LargeScaleQueryService(object):
    """超大规模数据查询服务（导出 / 统计，三表统一）。"""

    #: 单次 ES 查询超时（秒）
    QUERY_TIMEOUT_SECONDS = 30
    #: 单次 scroll 最大文档数
    SCROLL_BATCH_SIZE = 2000
    #: 导出文件每 N 条切一个文件
    EXPORT_BATCH_SIZE = 100000

    #: `public static class ExportTaskStatus` 的访问路径（末尾赋值）
    ExportTaskStatus = ExportTaskStatus

    def __init__(self,
                 indexManageService: Optional[EsIndexManageService] = None) -> None:
        # 单次 ES 查询超时（秒）/ 字段类型在 Java 里是 `static final int`
        self.esHost: str = Environment().value("${elasticsearch.host:127.0.0.1}", str)
        self.esPort: int = Environment().value("${elasticsearch.port:9200}", int)
        #: 导出文件根目录
        self.exportDir: str = Environment().value(
            "${optimization.export.dir:/data/export}", str)

        # 【Java→Python】字段初始化顺序与 Java 一致：线程池先建，再注入依赖，最后 init()
        self.queryExecutor = ThreadPoolExecutor(
            4, 8, 60, TimeUnit.SECONDS,
            LinkedBlockingQueue(500),
            _NamedThreadFactory("lq-worker"),
            ThreadPoolExecutor.CallerRunsPolicy())
        #: 导出任务追踪 Map (taskId -> status)
        self.exportTaskMap = ConcurrentHashMap()
        # `@Autowired` 字段注入 → 构造器可选参数
        self.indexManageService: EsIndexManageService = (
            indexManageService if indexManageService is not None
            else EsIndexManageService())

        self.client: Optional[RestHighLevelClient] = None
        # 【Java→Python】`@PostConstruct init()`：容器回调 → 构造器末尾显式调用
        self.init()

    # ==================================================================
    # 生命周期
    # ==================================================================
    def init(self) -> None:
        """`@PostConstruct init()`：初始化 ES 客户端（连接/读取超时与 Java 一致）。"""
        log.info("[大规模查询服务] 初始化 ES 客户端 host=%s, port=%s",
                 self.esHost, self.esPort)
        self.client = RestHighLevelClient(
            RestClient.builder(HttpHost(self.esHost, self.esPort, "http"))
            .setRequestConfigCallback(
                lambda builder: builder
                .setConnectTimeout(10000)
                .setSocketTimeout(60000)
                .setConnectionRequestTimeout(10000)))

    def destroy(self) -> None:
        """`@PreDestroy destroy()`：关闭客户端并停掉线程池。"""
        try:
            if self.client is not None:
                self.client.close()
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (IOException e) 一致
            log.error("[大规模查询服务] 关闭客户端异常", exc_info=True)
        self.queryExecutor.shutdown()

    # ==================================================================
    # 目标索引解析（三表）
    # ==================================================================
    def resolve(self, type: Optional[str]) -> Target:
        """按 type 解析目标索引与字段 / Resolve target by type.

        【Java→Python】`type` 参数名与内置函数同名，但为保持与 Java 逐字对应故不改名
        （作用域仅限本方法，方法体内不使用内置 `type`）。
        """
        if type is None:
            type = "snapshot"
        if type.lower() == "fee":
            ds = UnifiedQueryService.DataSource.FEE
            timeField, idField, plateField = "transtime", "big_id", "vehicleplate"
        elif type.lower() == "trail":
            ds = UnifiedQueryService.DataSource.TRAIL
            timeField, idField, plateField = "extime", "cid", "envehicleid"
        else:
            # case "snapshot": default:
            ds = UnifiedQueryService.DataSource.SNAPSHOT
            timeField, idField, plateField = ("snapshottime", "datauuid",
                                              "platenumber")
        # 索引名统一由 EsIndexManageService 解析，保证与同步/对账一致
        indexName = self.indexManageService.resolveIndexName(ds)
        return Target(indexName, timeField, idField, plateField)

    # ==================================================================
    # 模块1：全字段模糊查询
    # ==================================================================
    def fuzzyQuery(self, *args: Any) -> List[Dict[str, Any]]:
        """全字段模糊查询（两个 Java 重载合并）/ Fuzzy query.

        【Java→Python】Java 有两个重载::

            fuzzyQuery(String startTime, String endTime, Map fuzzyFields,
                       int pageNum, int pageSize)                      // 默认 snapshot
            fuzzyQuery(String type, String startTime, String endTime, Map fuzzyFields,
                       int pageNum, int pageSize)

        两个重载的**首参都是 String**（时间串 vs "snapshot"/"fee"/"trail"），
        Python 无法用类型区分，因此按**实参个数**分派：5 个走旧接口（补 "snapshot"），
        6 个走带 type 的接口。

        性能关键点 / Key points:
          1) 时间范围过滤到最近一年索引，分区裁剪思想同样适用于 ES 时间过滤
          2) 模糊字段走 ngram 倒排索引（match on .ngram）
          3) from+size 仅用于窗口内浅分页；深翻页请用导出接口
        """
        if len(args) == 5:
            startTime, endTime, fuzzyFields, pageNum, pageSize = args
            return self.fuzzyQuery("snapshot", startTime, endTime, fuzzyFields,
                                   pageNum, pageSize)
        if len(args) != 6:
            raise TypeError("fuzzyQuery 需要 5 或 6 个参数，实际 %d 个" % len(args))

        type, startTime, endTime, fuzzyFields, pageNum, pageSize = args
        target = self.resolve(type)
        start = System.currentTimeMillis()
        try:
            boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()
            boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                             .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime))

            if fuzzyFields is not None and len(fuzzyFields) > 0:
                for key, value in fuzzyFields.items():
                    if value is None or len(value) == 0:
                        continue
                    boolQuery.must(self.buildFuzzyQuery(key, value))

            sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
            sourceBuilder.query(boolQuery)
            sourceBuilder.from_((pageNum - 1) * pageSize)
            sourceBuilder.size(pageSize)
            sourceBuilder.sort(target.timeField, SortOrder.DESC)
            # 单次最多扫描 100 万，防慢查询
            sourceBuilder.terminateAfter(1000000)
            sourceBuilder.timeout(TimeValue(self.QUERY_TIMEOUT_SECONDS, TimeUnit.SECONDS))

            searchRequest: SearchRequest = SearchRequest(target.indexName)
            searchRequest.source(sourceBuilder)
            response = self.client.search(searchRequest, RequestOptions.DEFAULT)

            results: List[Dict[str, Any]] = []
            for hit in response.getHits().getHits():
                results.append(hit.getSourceAsMap())
            totalHits: int = int(response.getHits().getTotalHits().value)
            log.info("[全字段模糊查询] type=%s, 命中=%s, 返回=%s, 耗时=%sms",
                     type, totalHits, len(results),
                     System.currentTimeMillis() - start)
            return results
        except Exception as error:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[全字段模糊查询] ES 查询失败 type=%s", type, exc_info=True)
            raise RuntimeError("大规模数据查询服务异常：" + str(error)) from error

    def buildFuzzyQuery(self, fieldName: str, value: str) -> QueryBuilder:
        """根据字段内容智能构建模糊查询条件（与 UnifiedQueryService 一致）。

        【Java→Python】`value.length() >= 7` → `len(value) >= 7`；
        `"platenumber".equals(fieldName)` → `fieldName == "platenumber"`
        （Java 把常量写在左边避免 NPE；Python 的 `==` 对 None 天然安全，无需倒置）。
        """
        if len(value) >= 7 and (fieldName == "platenumber"
                                or fieldName == "vehicleplate"
                                or fieldName == "gantrycode"
                                or fieldName == "sectioncode"
                                or fieldName == "envehicleid"):
            return QueryBuilders.termQuery(fieldName + ".keyword", value)
        if len(value) >= 3:
            return QueryBuilders.matchQuery(fieldName + ".ngram", value)
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*")

    # ==================================================================
    # 模块2：统计查询（ES aggregation，三表）
    # ==================================================================
    def aggregationStats(self, type: Optional[str], startTime: str, endTime: str,
                         groupBy: str, countField: Optional[str],
                         fuzzyFields: Optional[Dict[str, str]],
                         topN: int) -> Dict[str, int]:
        """统计查询 - 按维度分组计数（指定 type）。

        原理：ES 在分片并行聚合，不将 8 亿条数据拉到应用层。
        【Java→Python】`LinkedHashMap` → 普通 dict（3.7+ 保序）；
        返回类型 `Map<String, Long>` → `Dict[str, int]`。
        """
        target = self.resolve(type)
        start = System.currentTimeMillis()
        try:
            boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()
            boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                             .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime))
            if fuzzyFields is not None:
                for key, value in fuzzyFields.items():
                    if value is not None and len(value) > 0:
                        boolQuery.must(self.buildFuzzyQuery(key, value))

            sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
            sourceBuilder.query(boolQuery)
            sourceBuilder.size(0)
            sourceBuilder.timeout(TimeValue(60, TimeUnit.SECONDS))
            sourceBuilder.aggregation(
                AggregationBuilders.terms("group_by_" + groupBy)
                .field(groupBy + ".keyword")
                .size(topN)
                .subAggregation(AggregationBuilders.count("total_count")
                                .field("_id" if countField is None else countField)))

            request: SearchRequest = SearchRequest(target.indexName)
            request.source(sourceBuilder)
            response = self.client.search(request, RequestOptions.DEFAULT)

            resultMap: Dict[str, int] = {}
            # 【Java→Python】`ParsedStringTerms terms = response.getAggregations().get(...)`
            # 的泛型强转在 Python 里不存在，取值直接是聚合对象（类型由替身保证）
            terms: Optional[ParsedStringTerms] = (
                response.getAggregations().get("group_by_" + groupBy))
            for bucket in terms.getBuckets():
                count: ValueCount = bucket.getAggregations().get("total_count")
                resultMap[bucket.getKeyAsString()] = count.getValue()
            log.info("[统计查询] type=%s, groupBy=%s, 桶数=%s, 耗时=%sms",
                     type, groupBy, len(resultMap),
                     System.currentTimeMillis() - start)
            return resultMap
        except Exception as error:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[统计查询] 聚合失败 type=%s", type, exc_info=True)
            raise RuntimeError("统计查询异常：" + str(error)) from error

    # ==================================================================
    # 模块3：大数据量导出（三表，PIT + search_after / Scroll）
    # ==================================================================
    def submitExportTask(self, type: Optional[str], startTime: str, endTime: str,
                         fuzzyFields: Optional[Dict[str, str]]) -> str:
        """异步提交导出任务（指定 type）/ Submit async export task."""
        taskId: str = UUID.randomUUID().toString()
        status = ExportTaskStatus()
        status.taskId = taskId
        status.status = "PENDING"
        status.submitTime = System.currentTimeMillis()
        self.exportTaskMap.put(taskId, status)

        def _runExport() -> None:
            # 【Java→Python】lambda 实现 Runnable；异常处理与原代码一致（catch 后置 FAILED）
            try:
                self.executeExportScroll(type, taskId, startTime, endTime, fuzzyFields)
            except Exception as error:  # noqa: BLE001 - catch (Exception e)
                log.error("[导出任务] task=%s 执行异常", taskId, exc_info=True)
                status.status = "FAILED"
                status.errorMessage = str(error)

        self.queryExecutor.submit(_runExport)
        return taskId

    def getExportStatus(self, taskId: str) -> Optional[ExportTaskStatus]:
        """查询导出任务状态 / Get export task status（不存在返回 None，Java 返回 null）。"""
        return self.exportTaskMap.get(taskId)

    def executeExportScroll(self, type: Optional[str], taskId: str,
                            startTime: str, endTime: str,
                            fuzzyFields: Optional[Dict[str, str]]) -> None:
        """核心：使用 Scroll API 深度分页导出大量数据。

        为什么不用 from+size：from=1,000,000 需先扫描百万再丢弃，O(n) 且内存爆。
        """
        target = self.resolve(type)
        status: ExportTaskStatus = self.exportTaskMap.get(taskId)
        status.status = "RUNNING"
        log.info("[导出任务] taskId=%s, type=%s 开始执行", taskId, type)

        boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()
        boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                         .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime))
        if fuzzyFields is not None:
            for key, value in fuzzyFields.items():
                if value is not None and len(value) > 0:
                    boolQuery.must(self.buildFuzzyQuery(key, value))

        sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
        sourceBuilder.query(boolQuery)
        sourceBuilder.size(self.SCROLL_BATCH_SIZE)
        sourceBuilder.sort(target.timeField, SortOrder.DESC)
        sourceBuilder.timeout(TimeValue(120, TimeUnit.SECONDS))

        searchRequest: SearchRequest = SearchRequest(target.indexName)
        searchRequest.source(sourceBuilder)
        searchRequest.scroll(Scroll(TimeValue(5, TimeUnit.MINUTES)))
        scrollResp = self.client.search(searchRequest, RequestOptions.DEFAULT)

        scrollId: Optional[str] = scrollResp.getScrollId()
        totalCount = 0
        filePartIndex = 0
        currentWriter: Any = None
        dirPath: Path = Path(self.exportDir)
        if not dirPath.exists():
            # 对应 `Files.createDirectories`：父目录不存在时一并创建
            dirPath.mkdir(parents=True)

        # 【Java→Python】注意 try 的位置：Java 在 `client.search` **之后**才进 try，
        # 因此“首页查询失败”不会走到 finally 的 clearScroll（此处保持一致）。
        try:
            while len(scrollResp.getHits().getHits()) > 0:
                if currentWriter is None or totalCount % self.EXPORT_BATCH_SIZE == 0:
                    if currentWriter is not None:
                        currentWriter.close()
                    filePartIndex += 1
                    fileName = (self.exportDir + "/export_" + _java_str(type) + "_"
                                + taskId + "_p" + str(filePartIndex) + ".csv")
                    # 【Java→Python】Files.newBufferedWriter 默认 UTF-8；
                    # newline="" 对应 BufferedWriter 不做行尾转换
                    currentWriter = open(Path(fileName), "w",
                                         encoding="utf-8", newline="")
                    # CSV 表头：业务主键 + 车牌/车辆编号 + 时间 + 完整 JSON 明细
                    currentWriter.write(target.idField + "," + target.plateField
                                        + "," + target.timeField + ",detail\n")

                for hit in scrollResp.getHits().getHits():
                    doc: Dict[str, Any] = hit.getSourceAsMap()
                    idValue = ("" if doc.get(target.idField) is None
                               else str(doc.get(target.idField)))
                    plate = ("" if doc.get(target.plateField) is None
                             else str(doc.get(target.plateField)))
                    timeValue = ("" if doc.get(target.timeField) is None
                                 else str(doc.get(target.timeField)))
                    # detail 列包含完整文档 JSON（CSV 内换行用空格替换，避免破坏行结构）
                    detail = (JSON.toJSONString(doc)
                              .replace("\n", " ").replace("\r", ""))
                    currentWriter.write(idValue + "," + plate + "," + timeValue
                                        + ",\"" + detail + "\"\n")
                    totalCount += 1
                status.totalExported = totalCount

                scrollRequest: SearchScrollRequest = SearchScrollRequest(scrollId)
                scrollRequest.scroll(Scroll(TimeValue(5, TimeUnit.MINUTES)))
                scrollResp = self.client.scroll(scrollRequest, RequestOptions.DEFAULT)
                scrollId = scrollResp.getScrollId()

                if totalCount % (self.SCROLL_BATCH_SIZE * 10) == 0:
                    log.info("[导出任务] taskId=%s, type=%s 已导出%s条...",
                             taskId, type, totalCount)
            status.status = "COMPLETED"
            status.filePartCount = filePartIndex
            status.endTime = System.currentTimeMillis()
            log.info("[导出任务] taskId=%s, type=%s 完成, 共导出 %s 条, 切分 %s 个文件",
                     taskId, type, totalCount, filePartIndex)
        finally:
            if currentWriter is not None:
                currentWriter.close()
            clearScrollRequest: ClearScrollRequest = ClearScrollRequest()
            clearScrollRequest.addScrollId(scrollId)
            self.client.clearScroll(clearScrollRequest, RequestOptions.DEFAULT)
