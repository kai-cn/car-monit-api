# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.LargeScaleDataSyncService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleDataSyncService.java

=====================================================================
超大规模数据同步服务 - GaussDB -> Elasticsearch（三表统一）
Large-scale data sync service: GaussDB -> Elasticsearch (unified for 3 tables).

背景：
  3 张表，每张表未来 3 年预计 8 亿条数据，日增约 70 万条。
  需将最近 12 个月数据实时同步到 ES，支撑全字段模糊查询、统计与导出。
  本服务是「GaussDB↔ES 一致性保障」的主路径（应用双写 / 增量补偿）。

同步策略：
  1. 全量同步（首次上线）：按时间分片并行 + 游标分页(keyset) + BulkProcessor
  2. 增量同步（日常）：Redis 水位标记，拉取 > watermark 且 < now-10s 的新数据
  3. 补同步（修复）：按指定时间窗重放，以 GaussDB 为准回灌 ES

性能保障：
  A. BulkProcessor: 1000 条 / 10MB / 5s 先到先触发，并发 4，指数退避重试
  B. 游标分页(keyset): 复杂度 O(total)，避免 limit/offset 的 O(offset) 深翻页
  C. 背压队列(BlockingQueue, 10000): ES 写入过载时阻塞读取端，防 OOM
  D. Redis 水位: 真实读写，增量不重复、不漏读（留 10s 缓冲规避写入延迟）

【Java→Python 本文件重点差异】
1) **构造器注入**：Java 的 5 参构造器（Spring 4.3+ 单构造器自动注入）→ Python 构造器
   可选参数；`RedisTemplate` 缺省用 `defaultRedisTemplate()`（进程级单例，对应 Spring
   容器里唯一的 RedisTemplate Bean）。
2) **@PostConstruct/@PreDestroy** → 恒等装饰器 + 构造器末尾显式调用 `init()`；
   `destroy()` 需由使用方显式调用（Python 无容器销毁钩子）。
3) **@Value 与初始化时机**：Java 注释强调“@Value 字段在构造器执行时尚未注入，
   所以 ES 客户端初始化必须放进 @PostConstruct”；Python 的 Environment 在构造器里
   即可读到配置，但为了与 Java 生命周期完全一致，仍在构造器末尾调用 `init()`。
4) **匿名 ThreadFactory（两个）**：Java 的 `r -> { Thread t = new Thread(r, "es-shard-reader");
   t.setDaemon(true); return t; }` 是 lambda 实现 ThreadFactory 接口；Python 无匿名类，
   改为模块级 `_ShardReaderThreadFactory` / `_BulkSchedulerThreadFactory`（见各自注释）。
5) **匿名 BulkProcessor.Listener**：Java 匿名内部类 → 嵌套类 `_SyncBulkListener`。
   其中 `afterBulk` 有**两个重载**（成功/失败），Python 合并为一个方法 + 类型判断。
6) **@FunctionalInterface CursorReader** → 模块级**包装类**（见类注释）：Java 的调用点
   是 `task.reader.read(...)`，若直接用 callable 就要改成 `task.reader(...)`；
   为保持调用点逐字一致，包装类保留 `read(...)` 方法。
   同理 `Function<Object,String> idExtractor` → `java.util.function.Function` 替身，
   调用点 `task.idExtractor.apply(...)` 不变。
7) **`r -> ((OdsRtSzdnSnapshotFlowAddcode) r).getDatauuid()`**：Java 的强制类型转换
   在 Python 不存在；实体是 dataclass，getter 就是属性，写作 `r.datauuid`。
8) **`List<Future<Long>>` + `f.get(6, TimeUnit.HOURS)`** → 替身 Future.get(timeout, unit)
   语义一致；`catch (Exception e)` 同时覆盖 ExecutionException/TimeoutException。
9) **`Stream.filter().findFirst().orElseThrow()`** → for 循环 + 判空 + `raise ValueError`
   （`IllegalArgumentException` → `ValueError`）。
10) **方法重载**：Java 有两个 `repairSync`（前者 ds+窗口，后者仅窗口=默认 SNAPSHOT）。
    Python 无重载，合并为一个方法并按第一个参数类型分派（见 repairSync 注释）。
11) **`while (++emptyCount >= 3)`**：Python 无 `++`，拆成 `emptyCount += 1` 再比较。
12) **`Thread.sleep(1000)`**：Java 抛受检 `InterruptedException`，Python 的
    `time.sleep` 抛 `KeyboardInterrupt`（不算受检异常），无需 try/catch。
13) **`(System.currentTimeMillis() - startMs) / 1000`**：Java 的整数除法向零截断，
    Python 用 `//`（正数时结果一致）。
14) **private static class SyncTask / TimeShard** → 模块级类，文件末尾挂回
    `LargeScaleDataSyncService.SyncTask` / `.TimeShard`，保持访问路径一致。
15) **`java.util.function.BiConsumer` / `Function`**：只出现在类型声明里，Python 无需
    import（lambda/callable 直接代替），故不建替身文件。
16) **`java.util.concurrent.ScheduledExecutorService`**：`Executors.newScheduledThreadPool`
    在替身里返回 `ExecutorService`（本工程只用到 `shutdown()`）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
    OdsRtSzdnSnapshotFlowAddcode,
)
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import (
    OdsLwzxsfsjFeeRecords01Mapper,
)
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from com.ruoyi.base.service.optimization.EsIndexManageService import (
    EsIndexManageService,
)
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from java.lang.System import System
from java.text.SimpleDateFormat import SimpleDateFormat
from java.util.Calendar import Calendar
from java.util.concurrent.atomic.AtomicLong import AtomicLong
from java.util.concurrent.Executors import Executors, ThreadFactory
from java.util.concurrent.LinkedBlockingQueue import LinkedBlockingQueue
from java.util.concurrent.ThreadPoolExecutor import ThreadPoolExecutor
from java.util.concurrent.TimeUnit import TimeUnit
from java.util.function.Function import Function
from javax.annotation.PostConstruct import PostConstruct
from javax.annotation.PreDestroy import PreDestroy
from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.action.bulk.BackoffPolicy import BackoffPolicy
from org.elasticsearch.action.bulk.BulkProcessor import BulkProcessor
from org.elasticsearch.action.index.IndexRequest import IndexRequest
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.common.unit.ByteSizeUnit import ByteSizeUnit
from org.elasticsearch.common.unit.ByteSizeValue import ByteSizeValue
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.xcontent.XContentType import XContentType
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import (
    RedisTemplate,
    defaultRedisTemplate,
)

__all__ = ["LargeScaleDataSyncService", "SyncTask", "TimeShard", "CursorReader"]

log = logging.getLogger(__name__)

# 【Java→Python】`@FunctionalInterface private interface CursorReader`
# → 包装类（保留 `.read(...)` 调用形式，见类注释）
class CursorReader(object):
    """`@FunctionalInterface private interface CursorReader` 的替身。

    原接口：
        List<?> read(Date start, Date end, String cursorTime, String cursorUuid, int limit);

    【Java→Python】Python 的函数式接口就是 callable，本可省略本类；但 Java 的调用点
    写的是 `task.reader.read(...)`（依赖方法名），故保留包装类，让调用点逐字一致。
    """

    def __init__(self, fn: Callable[[Any, Any, Optional[str], Optional[str], int], List[Any]]) -> None:
        self._fn = fn

    def read(self, start: Any, end: Any, cursorTime: Optional[str],
             cursorUuid: Optional[str], limit: int) -> List[Any]:
        """对应 `List<?> read(Date, Date, String, String, int)`。"""
        return self._fn(start, end, cursorTime, cursorUuid, limit)

    def __call__(self, start: Any, end: Any, cursorTime: Optional[str],
                 cursorUuid: Optional[str], limit: int) -> List[Any]:
        """【Java→Python】兼容直接调用（等价 read）。"""
        return self._fn(start, end, cursorTime, cursorUuid, limit)

    def __repr__(self) -> str:
        return "CursorReader(%r)" % (self._fn,)


class _ShardReaderThreadFactory(ThreadFactory):
    """分片读取线程工厂。

    【Java→Python】对应 buildBulkProcessor 所在类字段处的匿名 lambda：
        r -> { Thread t = new Thread(r, "es-shard-reader"); t.setDaemon(true); return t; }
    Python 没有匿名类，改为具名类；线程名与 Java 完全一致。
    """

    def newThread(self, target: Any) -> threading.Thread:
        return threading.Thread(target=target, name="es-shard-reader", daemon=True)


class _BulkSchedulerThreadFactory(ThreadFactory):
    """Bulk 调度线程工厂（对应 `Executors.newScheduledThreadPool(1, r -> {...})` 的 lambda）。"""

    def newThread(self, target: Any) -> threading.Thread:
        return threading.Thread(target=target, name="es-bulk-scheduler", daemon=True)


class _SyncBulkListener(BulkProcessor.Listener):
    """`new BulkProcessor.Listener() {...}` 匿名内部类。

    【Java→Python】Java 的两个 `afterBulk` 重载：
        afterBulk(long executionId, BulkRequest request, BulkResponse response)
        afterBulk(long executionId, BulkRequest request, Throwable failure)
    Python 无重载 → 合并为 `afterBulk(executionId, request, responseOrFailure)`，
    用 `isinstance(..., BaseException)` 区分失败分支。
    """

    def __init__(self, owner: "LargeScaleDataSyncService") -> None:
        # 对应匿名内部类隐式持有外部类引用（访问 totalWriteXxxCount）
        self._owner = owner

    def beforeBulk(self, executionId: int, request: Any) -> None:
        log.debug("[Bulk] 执行批次 %s, size=%s条", executionId,
                  request.numberOfActions())

    def afterBulk(self, executionId: int, request: Any,
                  responseOrFailure: Any) -> None:
        owner: LargeScaleDataSyncService = self._owner
        # ---------------- 失败重载：afterBulk(long, BulkRequest, Throwable)
        if isinstance(responseOrFailure, BaseException):
            failure = responseOrFailure
            # 【Java→Python】`log.error(fmt, a, b, failure)` 的最后一个参数是 Throwable，
            # slf4j 会把它当异常栈；Python 必须用 exc_info=failure（否则会被当成 %s 参数）。
            log.error("[Bulk] 批次 %s 异常, size=%s", executionId,
                      request.numberOfActions(), exc_info=failure)
            owner.totalWriteFailedCount.addAndGet(request.numberOfActions())
            return

        # ---------------- 成功重载：afterBulk(long, BulkRequest, BulkResponse)
        response = responseOrFailure
        if response.hasFailures():
            # 【Java→Python】Java 的
            #   Arrays.stream(items).filter(BulkItemResponse::isFailed)
            #         .peek(item -> log.warn(...)).count()
            # → Python for 循环 + 计数器（Stream 的 peek 在 count 终止时会执行）
            failed: int = 0
            for item in response.getItems():
                if item.isFailed():
                    log.warning("[Bulk] 写入失败: id=%s, reason=%s",
                                item.getId(), item.getFailureMessage())
                    failed += 1
            owner.totalWriteFailedCount.addAndGet(failed)
            owner.totalWriteSuccessCount.addAndGet(
                request.numberOfActions() - failed)
        else:
            owner.totalWriteSuccessCount.addAndGet(request.numberOfActions())

        total: int = owner.totalWriteSuccessCount.get()
        if total > 0 and total % 10000 == 0:
            log.info("[Bulk] 进度: 已写入 %s 条, 失败 %s 条", total,
                     owner.totalWriteFailedCount.get())


class SyncTask(object):
    """单表同步任务描述符。

    将「表名、Redis 水位 key、时间字段、游标读取器、主键提取器」封装为一个任务，
    使全量/增量/补同步逻辑对三表完全通用，避免重复代码。

    【Java→Python】Java 的 `private static class SyncTask` → 模块级类，
    文件末尾挂回 `LargeScaleDataSyncService.SyncTask` 保持访问路径。
    """

    def __init__(self, ds: Any, redisWatermarkKey: str,
                 reader: CursorReader, idExtractor: Function) -> None:
        self.ds = ds
        self.redisWatermarkKey = redisWatermarkKey
        self.reader = reader
        self.idExtractor = idExtractor

    def indexName(self, svc: EsIndexManageService) -> str:
        return svc.resolveIndexName(self.ds)

    def __repr__(self) -> str:
        return "SyncTask(ds=%s, watermarkKey=%s)" % (self.ds, self.redisWatermarkKey)


class TimeShard(object):
    """时间分片 - 简单的不可变数据类 / Immutable time shard.

    【Java→Python】`private static class TimeShard` → 模块级类 + 末尾挂回。
    原类没有 getter（同包/私有字段直接访问），Python 直接用公开属性。
    """

    def __init__(self, start: Any, end: Any) -> None:
        self.start = start
        self.end = end

    def __str__(self) -> str:
        # 【Java→Python】Java 的 toString 对应 Python 的 __str__；
        # 字符串拼接中的 Date.toString() 与 datetime.__str__ 格式不同（仅日志可读性差异）。
        return "[" + str(self.start) + "," + str(self.end) + ")"

    def __repr__(self) -> str:
        return self.__str__()


class LargeScaleDataSyncService(object):
    """超大规模数据同步服务（`@Service`）。"""

    #: Redis 水位 key 前缀（按表隔离）
    WATERMARK_PREFIX = "es:sync:watermark:"
    #: 增量水位向后缓冲秒数（规避 GaussDB 写入延迟造成漏读）
    WATERMARK_BACKOFF_SECONDS = 10

    def __init__(self,
                 snapshotMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 feeMapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 trailMapper: Optional[ZdataTrailFittingMapper] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 indexManageService: Optional[EsIndexManageService] = None) -> None:
        # ---- @Value 字段（先赋值，供 init() 使用）----
        self.esHost: str = Environment().value("${elasticsearch.host:127.0.0.1}", str)
        self.esPort: int = Environment().value("${elasticsearch.port:9200}", int)
        self.shardHours: int = Environment().value("${sync.shard.hours:1}", int)

        # ---- 构造器注入（Java: 5 参构造器）----
        # 【Java→Python】`@Autowired` 同类型单例 → 可选参数 + 缺省自建；
        # RedisTemplate 缺省用进程级单例（对应 Spring 唯一的 RedisTemplate Bean）。
        self.snapshotMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotMapper if snapshotMapper is not None
            else OdsRtSzdnSnapshotFlowAddcodeMapper())
        self.feeMapper: OdsLwzxsfsjFeeRecords01Mapper = (
            feeMapper if feeMapper is not None
            else OdsLwzxsfsjFeeRecords01Mapper())
        self.trailMapper: ZdataTrailFittingMapper = (
            trailMapper if trailMapper is not None
            else ZdataTrailFittingMapper())
        self.redisTemplate: RedisTemplate = (
            redisTemplate if redisTemplate is not None
            else defaultRedisTemplate())
        self.indexManageService: EsIndexManageService = (
            indexManageService if indexManageService is not None
            else EsIndexManageService())

        # ---- 背压队列：DB 读取线程与 ES 写入线程之间的有界缓冲 ----
        # 【Java→Python】`BlockingQueue<Object> syncQueue = new LinkedBlockingQueue<>(10000)`
        # → LinkedBlockingQueue(10000)
        self.syncQueue: Any = LinkedBlockingQueue(10000)

        # ---- 统计计数器（并发安全）----
        self.totalReadCount: AtomicLong = AtomicLong(0)
        self.totalWriteSuccessCount: AtomicLong = AtomicLong(0)
        self.totalWriteFailedCount: AtomicLong = AtomicLong(0)

        # ---- 读取线程池（默认 8 个并行分片）----
        # 【Java→Python】Java 的 7 参构造 → Python 同序参数（见 ThreadPoolExecutor.py）
        self.shardReaderPool: ThreadPoolExecutor = ThreadPoolExecutor(
            8, 16, 30, TimeUnit.SECONDS,
            LinkedBlockingQueue(500),
            _ShardReaderThreadFactory(),
            ThreadPoolExecutor.CallerRunsPolicy())

        # ---- Bulk 调度器 ----
        # 【Java→Python】Java 类型是 ScheduledExecutorService；替身的 Executors
        # 返回 ExecutorService（本工程只用到 shutdown()，见文件头第 16 条）。
        self.scheduler: Any = Executors.newScheduledThreadPool(
            1, _BulkSchedulerThreadFactory())

        # ---- @PostConstruct 生命周期 ----
        # Java: `client` / `bulkProcessor` 在 @PostConstruct 中创建（见文件头第 3 条）
        self.client: Optional[RestHighLevelClient] = None
        self.bulkProcessor: Optional[BulkProcessor] = None
        self.init()

    # ================================================================
    # 生命周期
    # ================================================================
    @PostConstruct
    def init(self) -> None:
        """在所有依赖（含 @Value）注入完成后再创建 ES 客户端与 BulkProcessor。"""
        # Java: `RestClient.builder(...).setRequestConfigCallback(b -> b
        #        .setConnectTimeout(10000).setSocketTimeout(120000)
        #        .setConnectionRequestTimeout(10000))`
        # 【Java→Python】lambda 的返回值就是链式调用结果（替身会使用返回值）。
        self.client = RestHighLevelClient(
            RestClient.builder(HttpHost(self.esHost, self.esPort, "http"))
            .setRequestConfigCallback(
                lambda builder: builder
                .setConnectTimeout(10000)
                .setSocketTimeout(120000)
                .setConnectionRequestTimeout(10000)))
        self.bulkProcessor = self.buildBulkProcessor()
        log.info("[数据同步服务] 初始化完成, ES=%s:%s", self.esHost, self.esPort)

    @PreDestroy
    def destroy(self) -> None:
        """`@PreDestroy`：关闭 BulkProcessor / ES 客户端 / 线程池。

        【Java→Python】Python 没有容器销毁回调，本方法需由应用关闭流程显式调用。
        """
        try:
            if self.bulkProcessor is not None:
                self.bulkProcessor.awaitClose(30, TimeUnit.SECONDS)
            if self.client is not None:
                self.client.close()
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[数据同步服务] 关闭异常", exc_info=True)
        self.shardReaderPool.shutdown()
        self.scheduler.shutdown()

    # ================================================================
    # 内部方法：构建 BulkProcessor（带失败重试）
    # ================================================================
    def buildBulkProcessor(self) -> BulkProcessor:
        """构建 BulkProcessor。

        【Java→Python】Java:
            BiConsumer<BulkRequest, ActionListener<BulkResponse>> bulkConsumer =
                (request, bulkListener) -> client.bulkAsync(request, RequestOptions.DEFAULT, bulkListener);
        Python 中 BiConsumer 就是普通 callable，用嵌套函数表达（lambda 亦可，
        但嵌套函数便于阅读且与 Java 的语句体 lambda 更接近）。
        """

        def _bulkConsumer(request: Any, bulkListener: Any) -> None:
            # self.client 一定非空（init() 中先赋值 client 再调用本方法）
            self.client.bulkAsync(request, RequestOptions.DEFAULT, bulkListener)

        # 【Java→Python】`new BulkProcessor.Listener() {...}` → 嵌套具名类
        listener = _SyncBulkListener(self)

        return (BulkProcessor.builder(_bulkConsumer, listener)
                .setBulkActions(1000)
                .setBulkSize(ByteSizeValue(10, ByteSizeUnit.MB))
                .setFlushInterval(TimeValue.timeValueSeconds(5))
                .setConcurrentRequests(4)
                .setBackoffPolicy(BackoffPolicy.exponentialBackoff(
                    TimeValue.timeValueMillis(1000), 5))
                .build())

    # ================================================================
    # 同步任务定义（三表统一）
    # ================================================================
    def buildSyncTasks(self) -> List[SyncTask]:
        """构建三表同步任务（每次调用重建，确保引用最新 Mapper）。"""
        # 【Java→Python】`new ArrayList<>(3)` → []（无需预分配）
        tasks: List[SyncTask] = []
        # 1) 门架抓拍流水：主键 datauuid，时间 snapshottime
        # 【Java→Python】Java 的 lambda 被隐式转成 CursorReader（函数式接口），
        # 调用点是 `task.reader.read(...)`，所以必须包一层 CursorReader，
        # 不能直接传 lambda（否则 reader 是 function，没有 .read 方法）。
        tasks.append(SyncTask(
            UnifiedQueryService.DataSource.SNAPSHOT,
            LargeScaleDataSyncService.WATERMARK_PREFIX + "snapshot",
            CursorReader(
                lambda s, e, ct, cu, lim: self.snapshotMapper.selectByCursorShard(
                    self.formatDateTime(s), self.formatDateTime(e), ct, cu, lim)),
            # 【Java→Python】`r -> ((OdsRtSzdnSnapshotFlowAddcode) r).getDatauuid()`
            # → 无强转，getter 即 dataclass 属性；外层 Function 保留 `.apply()` 调用形式
            Function(lambda r: r.datauuid)))
        # 2) 收费流水：主键 big_id，时间 transtime（物理车牌字段 vehicleplate）
        tasks.append(SyncTask(
            UnifiedQueryService.DataSource.FEE,
            LargeScaleDataSyncService.WATERMARK_PREFIX + "fee",
            CursorReader(
                lambda s, e, ct, cu, lim: self.feeMapper.selectByCursorShard(
                    self.formatDateTime(s), self.formatDateTime(e), ct, cu, lim)),
            Function(lambda r: r.big_id)))
        # 3) 车辆轨迹：主键 cid，时间 extime（车辆编号 envehicleid）
        tasks.append(SyncTask(
            UnifiedQueryService.DataSource.TRAIL,
            LargeScaleDataSyncService.WATERMARK_PREFIX + "trail",
            CursorReader(
                lambda s, e, ct, cu, lim: self.trailMapper.selectByCursorShard(
                    self.formatDateTime(s), self.formatDateTime(e), ct, cu, lim)),
            Function(lambda r: r.cid)))
        return tasks

    # ================================================================
    # 功能 1：全量同步（最近一年，三表）
    # ================================================================
    def fullSyncOneYear(self) -> None:
        """全量同步：对三张表分别按时间分片并行读取并写入 ES。"""
        cal: Calendar = Calendar.getInstance()
        endTime: Any = cal.getTime()
        cal.add(Calendar.YEAR, -1)
        startTime: Any = cal.getTime()

        log.info("[全量同步] 开始, 时间范围: %s ~ %s", startTime, endTime)
        startMs: int = System.currentTimeMillis()

        for task in self.buildSyncTasks():
            tableTotal: int = self.fullSyncTable(task, startTime, endTime)
            log.info("[全量同步] 表 %s 完成, 处理 %s 条", task.ds, tableTotal)

        self.bulkProcessor.flush()
        # 【Java→Python】Java 的整数除法向零截断 → Python 用 `//`（正数一致）
        cost: int = (System.currentTimeMillis() - startMs) // 1000
        log.info("[全量同步] 全部完成! 总读取 %s 条, 写入成功 %s, 失败 %s, 耗时 %s 秒",
                 self.totalReadCount.get(), self.totalWriteSuccessCount.get(),
                 self.totalWriteFailedCount.get(), cost)

    def fullSyncTable(self, task: SyncTask, startTime: Any, endTime: Any) -> int:
        """单表全量：按时间分片并行提交，汇总各分片读取条数。"""
        shards: List[TimeShard] = self.splitTimeRange(
            startTime, endTime, self.shardHours)
        futures: List[Any] = []

        for shard in shards:
            # 【Java→Python】Java 的 lambda 内含 try/catch，Python lambda 只能是
            # 表达式，因此改写为嵌套函数；循环变量 shard 用默认参数固定
            # （Java 的 lambda 捕获 effectively final 变量，Python 闭包是延迟绑定）。
            def _shardTask(shard: TimeShard = shard) -> int:
                try:
                    return self.readAndDispatch(task, shard)
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    log.error("[全量同步] 分片读取异常 task=%s, shard=%s",
                              task.ds, shard, exc_info=True)
                    return 0

            futures.append(self.shardReaderPool.submit(_shardTask))

        total: int = 0
        for future in futures:
            try:
                total += future.get(6, TimeUnit.HOURS)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.error("[全量同步] 等待分片异常 task=%s", task.ds, exc_info=True)
        return total

    # ================================================================
    # 功能 2：增量同步（每分钟，按 Redis 水位，三表）
    # ================================================================
    def incrementalSync(self) -> None:
        """增量同步：遍历三表，读取各自 Redis 水位之后的新数据写入 ES。

        水位设计：
          - 水位 = 已成功同步到的最大时间（存于 Redis）
          - 增量窗口上界 = now - 10s（留缓冲，规避 GaussDB 写入延迟导致漏读）
          - 同步成功才推进水位（at-least-once）；_id=业务主键 保证幂等
        """
        cal: Calendar = Calendar.getInstance()
        cal.add(Calendar.SECOND,
                -LargeScaleDataSyncService.WATERMARK_BACKOFF_SECONDS)
        upperBound: str = self.formatDateTime(cal.getTime())

        for task in self.buildSyncTasks():
            try:
                lastSyncTime: str = self.getLastSyncTimeFromRedis(
                    task.redisWatermarkKey)
                total: int = self.readAndDispatch(
                    task, TimeShard(self.parseDateTime(lastSyncTime),
                                    self.parseDateTime(upperBound)))
                if total > 0:
                    self.updateLastSyncTimeInRedis(task.redisWatermarkKey, upperBound)
                    log.info("[增量同步] 表 %s 完成, 本次同步 %s 条, 水位更新为 %s",
                             task.ds, total, upperBound)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.error("[增量同步] 异常 task=%s", task.ds, exc_info=True)

    # ================================================================
    # 功能 3：补同步（按数据源 + 时间窗，以 GaussDB 为准回灌 ES）
    # ================================================================
    def repairSync(self, ds: Any, startTime: Optional[str] = None,
                   endTime: Optional[str] = None) -> None:
        """补同步：重放指定时间窗，用于一致性对账修复。

        【Java→Python】Java 有两个重载：
            repairSync(DataSource ds, String startTime, String endTime)
            repairSync(String startTime, String endTime)      // 默认 SNAPSHOT
        Python 无重载，合并为一个方法：当第一个参数**不是** DataSource 时，
        按旧接口（只有起止时间）处理，数据源回退为 SNAPSHOT。
        """
        if not isinstance(ds, UnifiedQueryService.DataSource):
            # repairSync(String startTime, String endTime) 重载
            endTime = startTime
            startTime = ds
            ds = UnifiedQueryService.DataSource.SNAPSHOT

        # 【Java→Python】`buildSyncTasks().stream().filter(t -> t.ds == ds)
        #   .findFirst().orElseThrow(() -> new IllegalArgumentException(...))`
        # → for 循环 + 判空 + raise ValueError
        task: Optional[SyncTask] = None
        for candidate in self.buildSyncTasks():
            if candidate.ds is ds:
                task = candidate
                break
        if task is None:
            raise ValueError("未知数据源: " + str(ds))

        log.info("[补同步] 开始 ds=%s, 时间范围: %s ~ %s", ds, startTime, endTime)
        s: int = System.currentTimeMillis()
        try:
            total: int = self.readAndDispatch(
                task, TimeShard(self.parseDateTime(startTime),
                                self.parseDateTime(endTime)))
            self.bulkProcessor.flush()
            log.info("[补同步] 完成 ds=%s, 处理 %s 条, 耗时 %s 秒", ds, total,
                     (System.currentTimeMillis() - s) // 1000)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[补同步] 异常 ds=%s", ds, exc_info=True)

    # ================================================================
    # 通用游标读取与分发
    # ================================================================
    def readAndDispatch(self, task: SyncTask, shard: TimeShard) -> int:
        """单个时间分片的游标分页读取 + 分发 ES。

        关键 SQL 模式（替代 limit/offset，复杂度 O(total)）：
          SELECT ... WHERE time >= ? AND time < ?
            AND (time > cursorTime OR (time = cursorTime AND id > cursorUuid))
          ORDER BY time ASC, id ASC LIMIT 2000;
        """
        shardCount: int = 0
        cursorTime: Optional[str] = None
        cursorUuid: Optional[str] = None
        pageSize: int = 2000
        emptyCount: int = 0

        while True:
            batch: List[Any] = task.reader.read(
                shard.start, shard.end, cursorTime, cursorUuid, pageSize)
            if batch is None or len(batch) == 0:
                # 【Java→Python】Java 的 `if (++emptyCount >= 3)` → 先自增再比较
                emptyCount += 1
                if emptyCount >= 3:
                    break
                # 【Java→Python】Java 的 Thread.sleep 抛受检 InterruptedException，
                # Python 的 time.sleep 只有 KeyboardInterrupt，无需 try/catch。
                time.sleep(1.0)
                continue
            emptyCount = 0

            for record in batch:
                # 【原工程缺陷，忠实保留】记录只入队、**没有任何消费者**从
                # syncQueue 取数据；队列容量 10000，单表超过 1 万条后 put() 会
                # 永久阻塞读取线程（潜在死锁）。见文件末尾“缺陷说明”。
                self.syncQueue.put(record)
                doc_id: str = task.idExtractor.apply(record)
                self.dispatchToEs(task.indexName(self.indexManageService),
                                  doc_id, record)
                shardCount += 1
                self.totalReadCount.incrementAndGet()

            # 【Java→Python】`batch.get(batch.size() - 1)` → 下标访问（负数索引亦可，
            # 这里保持与 Java 相同的显式下标写法）
            last: Any = batch[len(batch) - 1]
            cursorTime = self.resolveCursorTime(task.ds, last)
            cursorUuid = task.idExtractor.apply(last)

            if len(batch) < pageSize:
                break
        return shardCount

    def resolveCursorTime(self, ds: Any, last: Any) -> Optional[str]:
        """提取上一批最后一条记录的时间游标（用于 keyset 推进）。

        【Java→Python】Java 的强制类型转换 + getter → dataclass 属性访问。
        """
        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return self.formatDateTime(last.snapshottime)
        if ds is UnifiedQueryService.DataSource.FEE:
            return self.formatDateTime(last.transtime)
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return self.formatDateTime(last.extime)
        return None

    def dispatchToEs(self, indexName: str, doc_id: str, record: Any) -> None:
        """将单条记录写入 ES BulkProcessor（以业务主键为 _id，保证幂等）。"""
        try:
            request: IndexRequest = (IndexRequest(indexName)
                                     .id(doc_id)  # 业务主键 = _id，重复写入自动覆盖（幂等）
                                     .source(JSON.toJSONString(record),
                                             XContentType.JSON))
            self.bulkProcessor.add(request)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.warning("[分发ES] 单条记录分发失败 index=%s, id=%s",
                        indexName, doc_id, exc_info=True)

    # ================================================================
    # Redis 水位真实读写
    # ================================================================
    def getLastSyncTimeFromRedis(self, key: str) -> str:
        """从 Redis 读取指定表的同步水位（不存在则返回 1 小时前，触发增量追赶）。"""
        try:
            v: Any = self.redisTemplate.opsForValue().get(key)
            if v is not None and len(str(v)) > 0:
                return str(v)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.warning("[增量同步] 读取 Redis 水位失败 key=%s, 使用默认值", key,
                        exc_info=True)
        cal: Calendar = Calendar.getInstance()
        cal.add(Calendar.HOUR, -1)
        return self.formatDateTime(cal.getTime())

    def updateLastSyncTimeInRedis(self, key: str, time_text: str) -> None:
        """更新 Redis 同步水位。"""
        try:
            self.redisTemplate.opsForValue().set(key, time_text)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.warning("[增量同步] 更新 Redis 水位失败 key=%s", key, exc_info=True)

    # ================================================================
    # 工具方法
    # ================================================================
    def splitTimeRange(self, start: Any, end: Any, stepHours: int) -> List[TimeShard]:
        """将 [start, end) 按 stepHours 小时切分为多个分片（每分片独立线程）。"""
        result: List[TimeShard] = []
        cursor: Calendar = Calendar.getInstance()
        cursor.setTime(start)
        while cursor.getTime() < end:  # Java: cursor.getTime().before(end)
            curStart: Any = cursor.getTime()
            cursor.add(Calendar.HOUR, stepHours)
            # Java: cursor.getTime().after(end) ? end : cursor.getTime()
            curEnd: Any = end if cursor.getTime() > end else cursor.getTime()
            result.append(TimeShard(curStart, curEnd))
        return result

    def formatDateTime(self, d: Any) -> str:
        """Date -> "yyyy-MM-dd HH:mm:ss"（每次新建 SimpleDateFormat，与 Java 一致）。"""
        return SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(d)

    def parseDateTime(self, s: str) -> Any:
        """"yyyy-MM-dd HH:mm:ss" -> Date。

        【Java→Python】`catch (Exception e) { throw new RuntimeException(e); }`
        → `raise RuntimeError(...) from error`（`from` 即 Java 的 cause 链）。
        """
        try:
            return SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(s)
        except Exception as error:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            raise RuntimeError(error) from error

    def __repr__(self) -> str:
        return ("LargeScaleDataSyncService(esHost=%s, esPort=%s, shardHours=%s)"
                % (self.esHost, self.esPort, self.shardHours))


# 【Java→Python】private static class 的访问路径还原
LargeScaleDataSyncService.SyncTask = SyncTask
LargeScaleDataSyncService.TimeShard = TimeShard
LargeScaleDataSyncService.CursorReader = CursorReader

# =====================================================================
# 【缺陷说明】原工程 readAndDispatch 中的背压队列
# ---------------------------------------------------------------------
# Java 代码：
#     syncQueue.put(record);
# 但整个工程**没有任何** `syncQueue.take()/poll()` 调用 —— 队列只进不出。
# 后果：单表同步超过 10000 条后，put() 阻塞读取线程，全量/增量/补同步全部挂住。
# 这是原工程既有缺陷（可能是“写入线程池”方案未完成），本次重构按“像素级 1:1”
# 要求**原样保留**，不做修复；如需修复，应由业务方在独立需求中补充消费者线程。
# =====================================================================
