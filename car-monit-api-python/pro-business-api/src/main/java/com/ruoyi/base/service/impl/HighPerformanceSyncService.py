# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.HighPerformanceSyncService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/HighPerformanceSyncService.java

高性能同步可疑车辆服务：4 种实现（多线程游标分页 / ForkJoin 分治 / Stream 管道 /
时间分片并行），最终把可疑车辆写入 Redis。

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → `logging.getLogger(__name__)` + 普通类。
2) 7 个 `@Autowired` → 构造器可选参数；缺省按 Spring 单例关系 `new XxxServiceImpl()`。
   其中 `snapshotFlowAddcodeService`、`feeRecords01Service` 在原文中**注入后从未使用**，
   原样保留字段（并标 noqa 提示）。
3) `@Value("${isLocalhost}")`（**无默认值**）→ `Environment().value("${isLocalhost}", str)`；
   application.yml 中配置值为 `local`，因此 pageSize 默认 6000（否则 2000）。
4) `private static final` 常量 → 类属性。注意原文里 `redisTimeKey` 等 4 个常量是
   **小写/驼峰命名**（不是全大写），为了一比一保留原拼写。
   `MAX_POOL_SIZE` / `QUEUE_CAPACITY` / `KEEP_ALIVE_TIME` 定义了但从未使用，原样保留。
5) `Runtime.getRuntime().availableProcessors()` → `java.lang.Runtime` 替身（os.cpu_count）。
6) `new ThreadFactory() {...}` 匿名内部类 → 模块级 `_SyncThreadFactory(ThreadFactory)`：
   `Thread` 在 Python 里是 `threading.Thread(target=..., name=...)`，
   daemon 由 ExecutorService 替身统一设置。
7) 4 个静态内部类（`SyncConfig`/`PreloadedData`/`DateRange`/`TrackTrailTuple`）
   → 模块级 `@dataclass`；末尾挂到 `HighPerformanceSyncService.Xxx` 保持 Java 访问路径。
   这些内部类**没有 Lombok @Data**，Java 直接访问字段（`config.starTime`）；
   Python 统一为 snake_case 字段（`config.star_time`），这是必要的命名差异。
8) `Optional.ofNullable(v).map(Object::toString).filter(CommonUtil::isNotBlank)`
   → Python 直接返回 `Optional[str]`（None 表示空），调用处用 `if value is not None`；
   Java 的 `ifPresent` → Python 的 `if`。
9) `CompletableFuture.supplyAsync(supplier, executor)` / `allOf(...).join()` /
   `future.get()` → 同名替身。替身用线程池真实并发；`get()` 会把任务异常重新抛出
   （对应 Java 的 `ExecutionException`）。
10) `Collectors.toMap(g -> code, g -> g)`：**重复 key 在 Java 抛 IllegalStateException**；
    Python `dict` 会静默覆盖。此处保留 dict 推导并注释该行为差异。
11) `Collectors.groupingBy(i -> list.indexOf(i) / batchSize)` 是实现上的一个坑：
    `List#indexOf` 用的是 **equals**，重复元素都返回首次出现下标，
    因此内容相同的轨迹会被归到同一批。Python 的 `_indexOf` 按 `==` 逐项查找，
    与 Lombok `@Data` 生成的 equals（字段比较）一致，**同样保留这个坑**。
    另外 Java `groupingBy` 返回 HashMap（顺序不保证），Python dict 保插入序（key 升序）。
12) `Calendar.add(DAY_OF_MONTH, -starTime)` → `DateUtils.addDays(now, -starTime)`；
    `SimpleDateFormat("yyyyMMdd"/"yyyy-MM-dd")` → `strftime("%Y%m%d"/"%Y-%m-%d")`。
13) `long totalMillis / sliceCount`（long 除法）→ Python `//`；
    `calendar.add(Calendar.MILLISECOND, (int) sliceMillis)` 的 `(int)` 强转在 Python
    里没有意义（int 即任意精度），但为了对齐语义仍显式 `int(...)`。
14) `sdf.parse(...)` 的 `ParseException` → `datetime.strptime` 的 `ValueError`，
    对应 catch 分支同样“解析失败则把原始范围当成单个分片”。
15) `String.valueOf(Date)` 调用的是 `Date#toString()`（格式 `EEE MMM dd HH:mm:ss zzz yyyy`），
    不是 `yyyy-MM-dd`。本文件的 `_javaDateToString()` 复刻该格式，因此
    `extractDate(...)` 得到的永远是 `"Thu Jun 01"` 这类串，
    **与节假日配置（yyyy-MM-dd）永远匹配不上** —— 原工程缺陷，忠实保留。
16) `datetime.substring(0, 10)` → `_javaSubstring()`：Java 越界抛
    `StringIndexOutOfBoundsException`，Python 切片不会抛，故显式校验。
17) `ForkJoinPool` / `RecursiveTask` 在 Python 中没有 work-stealing 对应物
    → 替身串行展开分治（切分与合并顺序不变，仅无并行加速）。
18) `SpringUtils.getBean(ISysUtilService.class)` → 同名替身按类型查找；
    未注册时替身返回 None（Java 抛 NoSuchBeanDefinitionException），
    随后调用 `.getTrailBoList(...)` 抛 AttributeError，同样落入 catch → 返回空列表。
19) `log.error(msg, e)` → `log.exception(msg)`；`log.warn` → `log.warning`。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Set

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection
from com.ruoyi.base.domain.TrailBo import TrailBo
from com.ruoyi.base.domain.TrailInfo import TrailInfo
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.service.ISysUtilService import ISysUtilService
from com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service import IOdsLwzxsfsjFeeRecords01Service
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import IOdsRtSzdnSnapshotFlowAddcodeService
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.IOdsSzdnSectionService import IOdsSzdnSectionService
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService
from com.ruoyi.base.service.impl.OdsLwzxsfsjFeeRecords01ServiceImpl import (
    OdsLwzxsfsjFeeRecords01ServiceImpl,
)
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import (
    OdsRtSzdnSnapshotFlowAddcodeServiceImpl,
)
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.base.service.impl.OdsSzdnSectionServiceImpl import OdsSzdnSectionServiceImpl
from com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl import ZdataLocationDictServiceImpl
from com.ruoyi.base.service.impl.ZdataTrailTracksServiceImpl import ZdataTrailTracksServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils.DateUtils import DateUtils
from com.ruoyi.common.utils.spring.SpringUtils import SpringUtils
from java.lang.Runtime import Runtime
from java.lang.Thread import Thread
from java.util.concurrent.CompletableFuture import CompletableFuture
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors, ThreadFactory
from java.util.concurrent.ForkJoinPool import ForkJoinPool
from java.util.concurrent.RecursiveTask import RecursiveTask
from java.util.concurrent.atomic.AtomicInteger import AtomicInteger
from org.springframework.core.env.Environment import Environment

__all__ = [
    "HighPerformanceSyncService",
    "SyncConfig",
    "PreloadedData",
    "DateRange",
    "TrackTrailTuple",
    "SuspiciousVehicleTask",
]

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ 辅助函数
def _javaDateToString(value: Optional[datetime]) -> str:
    """等价 `String.valueOf(Date)` → `Date#toString()`。

    Java 格式为 ``EEE MMM dd HH:mm:ss zzz yyyy``（如 ``Thu Jun 01 10:00:00 CST 2026``）。
    值为 null 时返回 ``"null"``（`String.valueOf(null)` 的语义）。
    """
    if value is None:
        return "null"
    return value.strftime("%a %b %d %H:%M:%S %Z %Y")


def _javaSubstring(text: str, begin: int, end: int) -> str:
    """等价 `String#substring(begin, end)`：越界抛 IndexError（Java 抛 StringIndexOutOfBoundsException）。"""
    if begin < 0 or end > len(text) or begin > end:
        raise IndexError(
            "StringIndexOutOfBoundsException: begin %d, end %d, length %d" % (begin, end, len(text)))
    return text[begin:end]


def _indexOf(items: List[Any], target: Any) -> int:
    """等价 `List#indexOf(Object)`：按 equals 查找首次出现位置，找不到返回 -1。

    【Java→Python】Lombok `@Data` 生成的 equals 是字段比较，Python dataclass 的
    `==` 同样是字段比较，两者语义一致。
    """
    for index, value in enumerate(items):
        if value == target:
            return index
    return -1


def _epochMillis(value: Optional[datetime]) -> int:
    """等价 `Date#getTime()`（epoch 毫秒）；None 时抛 AttributeError（Java 为 NPE）。"""
    return int(value.timestamp() * 1000)


# ------------------------------------------------------------------ 内部类
@dataclass
class SyncConfig(JavaBean):
    """同步配置（Java 静态内部类 SyncConfig）。"""

    page_size: int = 0  # Java: int pageSize;
    star_time: int = 0  # Java: int starTime;
    end_time: int = 0  # Java: int endTime;
    bite: Optional[float] = None  # Java: BigDecimal bite;（Python 统一用 float）
    supoer_mjnum: int = 0  # Java: int supoerMjnum;
    road_supoer_mjnum: int = 0  # Java: int roadSupoerMjnum;


@dataclass
class PreloadedData(JavaBean):
    """预加载数据（Java 静态内部类 PreloadedData）。"""

    gantry_map: Optional[dict[str, OdsSzdnGantry]] = None  # Java: Map<String, OdsSzdnGantry>
    location_map: Optional[dict[str, ZdataLocationDict]] = None  # Java: Map<String, ZdataLocationDict>
    section_list: Optional[List[OdsSzdnSection]] = None  # Java: List<OdsSzdnSection>
    section_codes: Optional[Set[str]] = None  # Java: Set<String>
    holiday_dates: Optional[Set[str]] = None  # Java: Set<String>


@dataclass
class DateRange(JavaBean):
    """时间范围（Java 静态内部类 DateRange）。"""

    start_time: Optional[str] = None  # Java: String startTime;
    end_time: Optional[str] = None  # Java: String endTime;
    formatted_date: Optional[str] = None  # Java: String formattedDate;


@dataclass
class TrackTrailTuple(JavaBean):
    """轨迹和轨迹点的元组（Java 静态内部类 TrackTrailTuple）。"""

    tracks: Optional[ZdataTrailTracks] = None  # Java: ZdataTrailTracks tracks;
    trail_bo_list: Optional[List[TrailBo]] = None  # Java: List<TrailBo> trailBoList;


class _SyncThreadFactory(ThreadFactory):
    """`new ThreadFactory() {...}` 匿名内部类 → 模块级类。

    线程命名规则与原实现一致：`sync-suspicious-car-<自增序号>`，且为 daemon 线程。
    """

    def __init__(self) -> None:
        self.counter = AtomicInteger(0)

    def newThread(self, target: Any) -> Any:
        # 【Java→Python】Java 里 new Thread(runnable, name) + setDaemon(true)；
        # Python 只能返回 threading.Thread，daemon 由执行器统一置位。
        thread = threading.Thread(
            target=target, name="sync-suspicious-car-%d" % self.counter.incrementAndGet())
        thread.daemon = True
        return thread


class HighPerformanceSyncService(object):
    """高性能同步可疑车辆服务（`@Service`）。"""

    # 配置常量
    redisTimeKey = "sys_config:syncSuspiciousCar_time"
    redisBiteKey = "sys_config:syncSuspiciousCar_bite"
    supoer_mjnum = "sys_config:supoer_mjnum"
    road_supoer_mjnum = "sys_config:road_supoer_mjnum"

    # 线程池配置
    CORE_POOL_SIZE = Runtime.getRuntime().availableProcessors()
    MAX_POOL_SIZE = CORE_POOL_SIZE * 2  # 原文件定义但未使用
    QUEUE_CAPACITY = 1000  # 原文件定义但未使用
    KEEP_ALIVE_TIME = 60  # 原文件定义但未使用（Java: 60L）

    def __init__(self,
                 redisCache: Optional[RedisCache] = None,
                 zdataTrailTracksService: Optional[IZdataTrailTracksService] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 zdataLocationDictService: Optional[IZdataLocationDictService] = None,
                 sectionService: Optional[IOdsSzdnSectionService] = None,
                 snapshotFlowAddcodeService: Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 feeRecords01Service: Optional[IOdsLwzxsfsjFeeRecords01Service] = None,
                 environment: Optional[Environment] = None) -> None:
        env = environment or Environment()

        self.redisCache: RedisCache = redisCache or RedisCache()
        self.zdataTrailTracksService: IZdataTrailTracksService = (
            zdataTrailTracksService or ZdataTrailTracksServiceImpl())
        self.odsSzdnGantryService: IOdsSzdnGantryService = (
            odsSzdnGantryService or OdsSzdnGantryServiceImpl())
        self.zdataLocationDictService: IZdataLocationDictService = (
            zdataLocationDictService or ZdataLocationDictServiceImpl())
        self.sectionService: IOdsSzdnSectionService = (
            sectionService or OdsSzdnSectionServiceImpl())
        # 以下两个依赖在原文中注入后从未使用，保留字段以对齐结构
        self.snapshotFlowAddcodeService: IOdsRtSzdnSnapshotFlowAddcodeService = (  # noqa: E501
            snapshotFlowAddcodeService or OdsRtSzdnSnapshotFlowAddcodeServiceImpl())
        self.feeRecords01Service: IOdsLwzxsfsjFeeRecords01Service = (  # noqa: E501
            feeRecords01Service or OdsLwzxsfsjFeeRecords01ServiceImpl())

        # 【Java→Python】@Value("${isLocalhost}") 无默认值；配置缺失时 Python 返回 None，
        # 而 Java 会在容器启动阶段直接失败。本工程的 application.yml 有该配置（local）。
        self.isLocalhost: Optional[str] = env.value("${isLocalhost}", str)

        # 高性能线程池：固定大小 + 自定义线程工厂（等价 private final ExecutorService）
        self.executorService: ExecutorService = Executors.newFixedThreadPool(
            HighPerformanceSyncService.CORE_POOL_SIZE, _SyncThreadFactory())

    # ==================== 对外 4 个入口 ====================

    def syncSuspiciousCarHighPerformance(self, startNum: int, endNum: int) -> None:
        """方法1：多线程 + 游标分页的高性能同步方法。

        核心优化点：
        1. 使用游标分页（基于ID或时间戳）避免offset分页的性能问题
        2. 多线程并行处理不同的数据块
        3. 批量查询和批量写入
        4. 数据预处理和缓存

        :param startNum: 起始页码（原文未使用，仅打日志）
        :param endNum: 结束页码（原文未使用，仅打日志）
        """
        startTime = _epochMillis(datetime.now())
        log.info("[高性能同步] 开始执行，页码范围: %s-%s", startNum, endNum)

        # 1. 加载配置和缓存数据（预加载，避免重复查询）
        config = self.loadSyncConfig()
        preloadedData = self.preloadData()

        # 2. 计算时间范围
        dateRange = self.calculateDateRange(config.star_time, config.end_time)
        log.info("[高性能同步] 时间范围: %s - %s", dateRange.start_time, dateRange.end_time)

        # 3. 使用游标分页查询轨迹数据
        allTrailTracks = self.queryTrailTracksWithCursor(dateRange, config.page_size)
        log.info("[高性能同步] 查询到轨迹数据: %s 条", len(allTrailTracks))

        # 4. 多线程并行处理可疑车辆分析
        suspiciousVehicles = self.processSuspiciousVehiclesParallel(
            allTrailTracks, preloadedData, config, dateRange.formatted_date)

        # 5. 批量写入Redis
        self.batchWriteToRedis(suspiciousVehicles, dateRange.formatted_date)

        duration = _epochMillis(datetime.now()) - startTime
        log.info("[高性能同步] 完成，耗时: %sms, 可疑车辆: %s 辆", duration, len(suspiciousVehicles))

    def syncSuspiciousCarForkJoin(self, startNum: int, endNum: int) -> None:
        """方法2：使用ForkJoinPool的递归并行处理版本。

        适合超大数据量场景，采用分治策略
        """
        startTime = _epochMillis(datetime.now())
        log.info("[ForkJoin同步] 开始执行")

        config = self.loadSyncConfig()
        preloadedData = self.preloadData()
        dateRange = self.calculateDateRange(config.star_time, config.end_time)

        # 获取所有轨迹数据
        allTrailTracks = self.queryTrailTracksWithCursor(dateRange, config.page_size)

        # 使用ForkJoinPool进行并行处理
        # 【Java→Python】替身串行执行 compute()，切分/合并顺序与原文一致
        forkJoinPool = ForkJoinPool(HighPerformanceSyncService.CORE_POOL_SIZE)
        try:
            task = SuspiciousVehicleTask(
                allTrailTracks, 0, len(allTrailTracks), preloadedData, config,
                dateRange.formatted_date)
            suspiciousVehicles = forkJoinPool.invoke(task)

            # 批量写入Redis
            self.batchWriteToRedis(suspiciousVehicles, dateRange.formatted_date)

            duration = _epochMillis(datetime.now()) - startTime
            log.info("[ForkJoin同步] 完成，耗时: %sms, 可疑车辆: %s 辆",
                     duration, len(suspiciousVehicles))
        finally:
            forkJoinPool.shutdown()

    def syncSuspiciousCarStream(self, startNum: int, endNum: int) -> None:
        """方法3：流式处理 + 管道模式版本。

        使用Java 8 Stream API实现流式处理，代码更简洁
        """
        startTime = _epochMillis(datetime.now())
        log.info("[流式同步] 开始执行")

        config = self.loadSyncConfig()
        preloadedData = self.preloadData()
        dateRange = self.calculateDateRange(config.star_time, config.end_time)

        # 流式处理管道
        # 【Java→Python】Stream 的 filter/map/collect 三段 → for 循环 + 条件判断，
        # 惰性与短路语义在“一次性 collect 到 List”时无差别。
        suspiciousVehicles: List[TrailInfo] = []
        for track in self.queryTrailTracksWithCursor(dateRange, config.page_size):
            # 1. 过滤：只处理非节假日的跨省车辆
            if not self.filterNonHolidayCrossProvince(track, preloadedData.holiday_dates):
                continue
            # 2. 转换：解析轨迹点
            tuple_ = self.parseTrailPoints(track, preloadedData.section_codes)
            # 3. 过滤：可疑车辆判断
            if not self.isSuspiciousVehicle(tuple_, config):
                continue
            # 4. 转换：构建TrailInfo
            suspiciousVehicles.append(
                self.buildTrailInfo(tuple_.tracks, tuple_.trail_bo_list, preloadedData))

        # 批量写入Redis
        self.batchWriteToRedis(suspiciousVehicles, dateRange.formatted_date)

        duration = _epochMillis(datetime.now()) - startTime
        log.info("[流式同步] 完成，耗时: %sms, 可疑车辆: %s 辆", duration, len(suspiciousVehicles))

    def syncSuspiciousCarByTimeRange(self, startNum: int, endNum: int) -> None:
        """方法4：时间范围分片 + 多线程游标查询（推荐方案）。

        核心思路：
        1. 将大的时间范围按小时/天分片，避免全表扫描
        2. 每个分片使用独立线程并行查询
        3. 每个分片内部继续使用游标分页优化性能
        4. 最后合并所有结果并排序

        适用场景：数据量非常大（>100万条），需要极致查询性能

        :param startNum: 起始页码（原文未使用）
        :param endNum: 结束页码（原文未使用）
        """
        startTime = _epochMillis(datetime.now())
        log.info("[时间分片同步] 开始执行，页码范围: %s-%s", startNum, endNum)

        # 1. 加载配置和缓存数据（预加载，避免重复查询）
        config = self.loadSyncConfig()
        preloadedData = self.preloadData()

        # 2. 计算时间范围
        dateRange = self.calculateDateRange(config.star_time, config.end_time)
        log.info("[时间分片同步] 原始时间范围: %s - %s", dateRange.start_time, dateRange.end_time)

        # 3. 时间范围分片（按小时分片，线程数=CPU核心数）
        subRanges = self.splitDateRangeByHour(
            dateRange, HighPerformanceSyncService.CORE_POOL_SIZE)
        log.info("[时间分片同步] 分片数量: %s, 每个分片独立查询", len(subRanges))

        # 4. 多线程并行查询每个时间分片的数据
        allTrailTracks = self.queryTrailTracksParallelByRange(subRanges, config.page_size)
        log.info("[时间分片同步] 总查询轨迹数据: %s 条", len(allTrailTracks))

        # 5. 多线程并行处理可疑车辆分析
        suspiciousVehicles = self.processSuspiciousVehiclesParallel(
            allTrailTracks, preloadedData, config, dateRange.formatted_date)

        # 6. 批量写入Redis
        self.batchWriteToRedis(suspiciousVehicles, dateRange.formatted_date)

        duration = _epochMillis(datetime.now()) - startTime
        log.info("[时间分片同步] 完成，耗时: %sms, 可疑车辆: %s 辆",
                 duration, len(suspiciousVehicles))

    # ==================== 核心辅助方法 ====================

    def loadSyncConfig(self) -> SyncConfig:
        """加载同步配置。"""
        config = SyncConfig()
        # Java: "local".equals(isLocalhost) —— 常量在前，对 null 安全；Python 的 == 同样安全
        config.page_size = 6000 if "local" == self.isLocalhost else 2000
        config.star_time = 2
        config.end_time = 4
        config.bite = float("0.3")  # Java: new BigDecimal("0.3")
        config.supoer_mjnum = 5
        config.road_supoer_mjnum = 3

        # 从Redis加载配置（Java Optional.ifPresent → Python if 判断）
        value = self.loadConfigValue(HighPerformanceSyncService.redisTimeKey)
        if value is not None:
            config.star_time = int(value)  # Java: Integer.parseInt(v)
        value = self.loadConfigValue(HighPerformanceSyncService.redisBiteKey)
        if value is not None:
            config.bite = float(value)  # Java: new BigDecimal(v)
        value = self.loadConfigValue(HighPerformanceSyncService.supoer_mjnum)
        if value is not None:
            config.supoer_mjnum = int(value)
        value = self.loadConfigValue(HighPerformanceSyncService.road_supoer_mjnum)
        if value is not None:
            config.road_supoer_mjnum = int(value)

        return config

    def loadConfigValue(self, key: str) -> Optional[str]:
        """从Redis加载配置值并过滤空值。

        辅助方法，解决类型不匹配问题：
        1. 从Redis获取值（类型可能为String或其他类型）
        2. 统一转换为String
        3. 过滤空值后返回Optional

        :param key: Redis键
        :return: 非空配置值（Java 的 Optional<String> → Python Optional[str]）
        """
        # 【Java→Python】Optional.ofNullable(...).map(Object::toString).filter(isNotBlank)
        raw = self.redisCache.getCacheObject(key)
        if raw is None:
            return None
        text = str(raw)  # Java: Object::toString
        return text if CommonUtil.isNotBlank(text) else None

    def preloadData(self) -> PreloadedData:
        """预加载数据（一次性加载所有需要的缓存数据）。"""
        data = PreloadedData()

        # 并行加载多个数据源
        gantryFuture = CompletableFuture.supplyAsync(
            self.odsSzdnGantryService.getGantryRedis, self.executorService)

        locationFuture = CompletableFuture.supplyAsync(
            self.zdataLocationDictService.getRedisList, self.executorService)

        sectionFuture = CompletableFuture.supplyAsync(
            self.sectionService.getSectionList, self.executorService)

        CompletableFuture.allOf(gantryFuture, locationFuture, sectionFuture).join()

        try:
            # 【Java→Python】Collectors.toMap 遇到重复 key 会抛 IllegalStateException；
            # Python dict 推导是“后者覆盖前者”，属于已知差异（原数据 gantryCode 应唯一）。
            data.gantry_map = {
                g.getGantryCode(): g
                for g in gantryFuture.get()
                if CommonUtil.isNotBlank(g.getGantryCode())
            }

            data.location_map = locationFuture.get()

            data.section_list = sectionFuture.get()
            data.section_codes = {
                section.getSectionCode()
                for section in data.section_list
                if CommonUtil.isNotBlank(section.getSectionCode())
            }

            # 获取节假日配置
            holidayValue = CommonUtil.isNull(
                self.redisCache.getCacheObject("sys_config:jholiday_time"))
            # Java: Arrays.stream(holidayValue.split(",")).filter(isNotBlank).collect(toSet())
            data.holiday_dates = (
                set()
                if CommonUtil.isBlank(holidayValue)
                else {item for item in holidayValue.split(",") if CommonUtil.isNotBlank(item)}
            )

        except Exception:  # noqa: BLE001
            # 【Java→Python】原文 `catch (InterruptedException | ExecutionException e)`。
            # 注意：`allOf(...).join()` 写在 **try 之外**，它抛的是非受检的 CompletionException，
            # 因此上游失败会直接向上抛、不会进入本 catch；而 allOf 已 join 成功后，
            # 下面各个 `get()` 也不可能再抛 → **该 catch 块在原文中是不可达死代码**。
            # 这里保留结构以对齐源码，不改变行为。
            log.exception("[预加载数据] 失败")
            Thread.currentThread().interrupt()

        return data

    def calculateDateRange(self, starTime: int, endTime: int) -> DateRange:
        """计算时间范围。"""
        result = DateRange()
        now = datetime.now()

        # 格式化日期
        result.formatted_date = now.strftime("%Y%m%d")  # SimpleDateFormat("yyyyMMdd")

        # 计算查询日期（当前时间往前推starTime天）
        queryDate = DateUtils.addDays(now, -starTime)  # Calendar.DAY_OF_MONTH - starTime

        dateStr = queryDate.strftime("%Y-%m-%d")  # SimpleDateFormat("yyyy-MM-dd")

        result.start_time = dateStr + " 00:00:00"
        result.end_time = dateStr + " 23:59:59"

        return result

    def queryTrailTracksWithCursor(self, dateRange: DateRange, pageSize: int) -> List[ZdataTrailTracks]:
        """使用游标分页查询轨迹数据。

        游标分页相比offset分页的优势：
        1. 避免大offset导致的全表扫描
        2. 性能更稳定，不受数据量影响
        3. 适合大数据量场景
        """
        allResults: List[ZdataTrailTracks] = []
        lastExitTime: Optional[datetime] = None
        hasMore = True

        while hasMore:
            carParaVO = CarParaVO()
            carParaVO.setApplyTime1(dateRange.start_time)
            carParaVO.setApplyTime2(dateRange.end_time)
            carParaVO.setPageSize(pageSize)
            carParaVO.setLastExitTime(lastExitTime)  # 游标

            pageResults: List[ZdataTrailTracks] = \
                self.zdataTrailTracksService.getLatestTrailByCursor(carParaVO)

            if len(pageResults) == 0 or len(pageResults) < pageSize:
                hasMore = False
            else:
                lastExitTime = pageResults[len(pageResults) - 1].getExitTime()

            allResults.extend(pageResults)
            log.debug("[游标分页] 获取到 %s 条数据，累计 %s 条", len(pageResults), len(allResults))

        return allResults

    def splitDateRangeByHour(self, original: DateRange, sliceCount: int) -> List[DateRange]:
        """时间范围分片：将大的时间范围分割成多个小时段。

        核心思路：
        1. 将一天的时间按小时或小时数的倍数分割
        2. 每个分片独立查询，避免单线程查询大量数据
        3. 分片数量 = CPU核心数，充分利用多核CPU

        :param original: 原始时间范围
        :param sliceCount: 分片数量
        :return: 分片后的时间范围列表
        """
        ranges: List[DateRange] = []

        try:
            # Java: new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(...)
            startDate = datetime.strptime(original.start_time, "%Y-%m-%d %H:%M:%S")
            endDate = datetime.strptime(original.end_time, "%Y-%m-%d %H:%M:%S")

            # 计算时间跨度（毫秒）
            totalMillis = _epochMillis(endDate) - _epochMillis(startDate)
            # 每个分片的时间跨度（毫秒）—— Java 的 long 除法 → //
            sliceMillis = totalMillis // sliceCount
            # 保证每个分片至少1小时
            minSliceMillis = 60 * 60 * 1000
            sliceMillis = max(sliceMillis, minSliceMillis)

            current = startDate

            # Java: while (calendar.getTime().before(endDate))
            while current < endDate:
                subRange = DateRange()
                subRange.start_time = current.strftime("%Y-%m-%d %H:%M:%S")
                subRange.formatted_date = original.formatted_date

                # 计算分片结束时间
                # Java: calendar.add(Calendar.MILLISECOND, (int) sliceMillis)
                current = DateUtils.addMilliseconds(current, int(sliceMillis))
                subEnd = endDate if current > endDate else current
                subRange.end_time = subEnd.strftime("%Y-%m-%d %H:%M:%S")

                ranges.append(subRange)
                log.debug("[时间分片] 创建分片: %s - %s", subRange.start_time, subRange.end_time)

        except ValueError:
            # Java: catch (ParseException e)
            log.exception("[时间分片] 解析时间失败")
            # 失败时返回原始范围作为单个分片
            ranges.append(original)

        return ranges

    def queryTrailTracksParallelByRange(self,
                                        subRanges: List[DateRange],
                                        pageSize: int) -> List[ZdataTrailTracks]:
        """多线程并行查询多个时间分片的数据。

        核心思路：
        1. 每个时间分片使用独立线程并行查询
        2. 每个分片内部使用游标分页继续优化
        3. 使用CompletableFuture实现非阻塞并行
        4. 最后合并所有结果并按时间排序

        :param subRanges: 时间分片列表
        :param pageSize: 每页大小
        :return: 合并后的轨迹数据列表
        """
        # 为每个分片创建并行查询任务
        def _query(subRange: DateRange) -> List[ZdataTrailTracks]:
            log.info("[并行查询] 开始查询分片: %s - %s", subRange.start_time, subRange.end_time)
            result = self.queryTrailTracksWithCursor(subRange, pageSize)
            log.info("[并行查询] 分片完成: %s - %s, 获取 %s 条",
                     subRange.start_time, subRange.end_time, len(result))
            return result

        futures: List[CompletableFuture[List[ZdataTrailTracks]]] = [
            CompletableFuture.supplyAsync(lambda r=subRange: _query(r), self.executorService)
            for subRange in subRanges
        ]

        # 等待所有查询任务完成
        allResults: List[ZdataTrailTracks] = []
        for future in futures:
            allResults.extend(future.join())

        # 按出站时间排序，保证数据顺序一致性
        allResults.sort(key=lambda track: track.getExitTime())

        return allResults

    def processSuspiciousVehiclesParallel(self,
                                          trailTracks: List[ZdataTrailTracks],
                                          preloadedData: PreloadedData,
                                          config: SyncConfig,
                                          formattedDate: str) -> List[TrailInfo]:
        """多线程并行处理可疑车辆分析。"""
        # 将数据分成多个批次
        batches = self.partitionList(trailTracks, 1000)

        # 并行处理每个批次
        futures: List[CompletableFuture[List[TrailInfo]]] = [
            CompletableFuture.supplyAsync(
                lambda b=batch: self.processBatch(b, preloadedData, config, formattedDate),
                self.executorService)
            for batch in batches
        ]

        # 等待所有任务完成并合并结果
        result: List[TrailInfo] = []
        for future in futures:
            result.extend(future.join())
        return result

    def processBatch(self,
                     batch: List[ZdataTrailTracks],
                     preloadedData: PreloadedData,
                     config: SyncConfig,
                     formattedDate: str) -> List[TrailInfo]:
        """处理单个批次的数据。"""
        result: List[TrailInfo] = []
        for track in batch:
            if not HighPerformanceSyncService.isNonHolidayCrossProvince(
                    track, preloadedData.holiday_dates):
                continue
            trailBoList = HighPerformanceSyncService.parseTrailPointsJson(track.getTrailPoints())
            analyzed = HighPerformanceSyncService.analyzeSuspiciousVehicle(
                track, trailBoList, preloadedData, config)
            if analyzed is not None:  # Java: filter(Objects::nonNull)
                result.append(analyzed)
        return result

    @staticmethod
    def isNonHolidayCrossProvince(track: ZdataTrailTracks, holidayDates: Set[str]) -> bool:
        """判断是否为非节假日的跨省车辆。"""
        trailtype = CommonUtil.isNull(track.getTrailtype())
        firstName = CommonUtil.repalaceSzdnTollName(track.getEntollstationname())
        endName = CommonUtil.repalaceSzdnTollName(track.getExtollstationname())

        # 外省进外省出的车辆
        isCrossProvince = ("0" == trailtype
                           and "门架" in firstName
                           and "门架" in endName)

        # 非节假日
        # 【Java→Python】String.valueOf(Date) 走的是 Date#toString()（"Thu Jun 01 ..."），
        # 前 10 个字符是 "Thu Jun 01"，与 yyyy-MM-dd 的节假日配置永远不匹配 —— 原缺陷保留。
        enterDate = HighPerformanceSyncService.extractDate(_javaDateToString(track.getEnterTime()))
        isNonHoliday = enterDate not in holidayDates

        return isCrossProvince and isNonHoliday

    @staticmethod
    def parseTrailPointsJson(trailPoints: Optional[str]) -> List[TrailBo]:
        """解析轨迹点JSON。"""
        if CommonUtil.isBlank(trailPoints):
            return []
        try:
            # 【Java→Python】SpringUtils.getBean(Class) → 按类型查找；未注册返回 None
            sysUtilService: ISysUtilService = SpringUtils.getBean(ISysUtilService)
            return sysUtilService.getTrailBoList(trailPoints)
        except Exception as error:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 【Java→Python】e.getMessage() 可能为 null，str(error) 恒为字符串
            log.warning("[解析轨迹点] JSON解析失败: %s", error)
            return []

    @staticmethod
    def analyzeSuspiciousVehicle(track: ZdataTrailTracks,
                                 trailBoList: List[TrailBo],
                                 preloadedData: PreloadedData,
                                 config: SyncConfig) -> Optional[TrailInfo]:
        """分析可疑车辆。

        【Java→Python】`preloadedData` 在方法体内未使用（原文如此），保留参数对齐签名。
        """
        # 统计门架抓拍和流水抓拍数量
        gantryCaptureCount = 0
        for item in trailBoList:
            if "GantryCapture" == item.getStateType():
                gantryCaptureCount += 1

        feeRecordCount = 0
        for item in trailBoList:
            if "FeeRecord" == item.getStateType():
                feeRecordCount += 1

        # 判断是否为可疑车辆
        if gantryCaptureCount > config.supoer_mjnum and feeRecordCount == 0:
            # 构建TrailInfo
            trailInfo = HighPerformanceSyncService.buildTrailInfo(
                track, trailBoList, preloadedData)
            trailInfo.getTracks().setEscapedType(Constants.escapedType_20)
            trailInfo.getTracks().setEscapedTypeRemark(
                "跨省全程屏蔽：门架牌识流水:" + str(gantryCaptureCount)
                + "，门架交易流水:" + str(feeRecordCount))
            trailInfo.getTracks().setEscapedTfcj("1")

            return trailInfo

        return None

    @staticmethod
    def buildTrailInfo(track: ZdataTrailTracks,
                       trailBoList: List[TrailBo],
                       preloadedData: PreloadedData) -> TrailInfo:
        """构建TrailInfo（`preloadedData` 原文未使用）。"""
        trailInfo = TrailInfo()
        trailInfo.setTracks(track)
        trailInfo.setTrailList(trailBoList)

        # 设置轨迹UUID
        trailInfo.setTrailUuid(CommonUtil.isNull(track.getPlateKey()))

        return trailInfo

    def batchWriteToRedis(self, suspiciousVehicles: List[TrailInfo],
                          formattedDate: str) -> None:
        """批量写入Redis。"""
        if len(suspiciousVehicles) == 0:
            return

        # 批量操作优化：使用管道或批量命令
        for trailInfo in suspiciousVehicles:
            carNo = CommonUtil.isNull(trailInfo.getTrailUuid())
            key = Constants.car_uspicious + formattedDate + ":" + carNo
            self.redisCache.setCacheObject(key, trailInfo)

        log.info("[批量写入Redis] 写入 %s 条数据", len(suspiciousVehicles))

    def partitionList(self, items: List[Any], batchSize: int) -> List[List[Any]]:
        """将列表分成指定大小的批次。

        【Java→Python】原文 `groupingBy(i -> list.indexOf(i) / batchSize)`：
        `indexOf` 用 equals 查找**首次**出现的位置，因此内容相同的元素会落到同一批。
        Python 的 `_indexOf` 复刻该行为，属于原实现缺陷，不在此修复。
        """
        groups: dict[int, List[Any]] = {}
        for item in items:
            key = _indexOf(items, item) // batchSize  # Java int 除法
            groups.setdefault(key, []).append(item)
        return [list(group) for group in groups.values()]

    @staticmethod
    def extractDate(datetime_text: Optional[str]) -> str:
        """从时间字符串中提取日期。"""
        if CommonUtil.isBlank(datetime_text):
            return ""
        # 【Java→Python】substring(0,10) 越界时会抛异常，这里用 _javaSubstring 保持一致
        return _javaSubstring(datetime_text, 0, 10)

    def filterNonHolidayCrossProvince(self, track: ZdataTrailTracks,
                                      holidayDates: Set[str]) -> bool:
        """过滤非节假日的跨省车辆（用于流式处理）。"""
        return HighPerformanceSyncService.isNonHolidayCrossProvince(track, holidayDates)

    def parseTrailPoints(self, track: ZdataTrailTracks,
                         sectionCodes: Set[str]) -> TrackTrailTuple:
        """解析轨迹点（用于流式处理）。

        【Java→Python】`sectionCodes` 在方法体内未使用（原文如此），保留参数。
        """
        tuple_ = TrackTrailTuple()
        tuple_.tracks = track
        tuple_.trail_bo_list = HighPerformanceSyncService.parseTrailPointsJson(
            track.getTrailPoints())
        return tuple_

    def isSuspiciousVehicle(self, tuple_: TrackTrailTuple, config: SyncConfig) -> bool:
        """判断是否为可疑车辆（用于流式处理）。"""
        gantryCount = 0
        for item in tuple_.trail_bo_list:
            if "GantryCapture" == item.getStateType():
                gantryCount += 1
        feeCount = 0
        for item in tuple_.trail_bo_list:
            if "FeeRecord" == item.getStateType():
                feeCount += 1
        return gantryCount > config.supoer_mjnum and feeCount == 0


class SuspiciousVehicleTask(RecursiveTask[List[TrailInfo]]):
    """ForkJoin任务：并行处理可疑车辆（Java 静态内部类 SuspiciousVehicleTask）。"""

    THRESHOLD = 1000

    def __init__(self,
                 trailTracks: List[ZdataTrailTracks],
                 start: int,
                 end: int,
                 preloadedData: PreloadedData,
                 config: SyncConfig,
                 formattedDate: str) -> None:
        super().__init__()
        self.trailTracks = trailTracks
        self.start = start
        self.end = end
        self.preloadedData = preloadedData
        self.config = config
        self.formattedDate = formattedDate

    def compute(self) -> List[TrailInfo]:
        if self.end - self.start <= SuspiciousVehicleTask.THRESHOLD:
            # 直接处理
            return self.processSubList(self.trailTracks[self.start:self.end])

        # 分治处理
        mid = (self.start + self.end) // 2  # Java: (start + end) / 2（int 除法）
        left = SuspiciousVehicleTask(
            self.trailTracks, self.start, mid, self.preloadedData, self.config,
            self.formattedDate)
        right = SuspiciousVehicleTask(
            self.trailTracks, mid, self.end, self.preloadedData, self.config,
            self.formattedDate)

        left.fork()
        rightResult = right.compute()
        leftResult = left.join()

        # 合并结果
        result: List[TrailInfo] = list(leftResult)
        result.extend(rightResult)
        return result

    def processSubList(self, subList: List[ZdataTrailTracks]) -> List[TrailInfo]:
        """处理分片列表（等价原文的 stream + filter + map + filter）。"""
        result: List[TrailInfo] = []
        for track in subList:
            if not HighPerformanceSyncService.isNonHolidayCrossProvince(
                    track, self.preloadedData.holiday_dates):
                continue
            trailBoList = HighPerformanceSyncService.parseTrailPointsJson(track.getTrailPoints())
            analyzed = HighPerformanceSyncService.analyzeSuspiciousVehicle(
                track, trailBoList, self.preloadedData, self.config)
            if analyzed is not None:  # Java: filter(Objects::nonNull)
                result.append(analyzed)
        return result


# 【Java→Python】保持 Java 中 `HighPerformanceSyncService.Xxx` 的嵌套访问路径
HighPerformanceSyncService.SyncConfig = SyncConfig
HighPerformanceSyncService.PreloadedData = PreloadedData
HighPerformanceSyncService.DateRange = DateRange
HighPerformanceSyncService.TrackTrailTuple = TrackTrailTuple
HighPerformanceSyncService.SuspiciousVehicleTask = SuspiciousVehicleTask
