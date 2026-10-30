# -*- coding: utf-8 -*-
"""t08 单文件校验：HighPerformanceSyncService（桩 service + 独立 Redis）。

覆盖：配置加载、日期范围/时间分片、游标分页、预加载、跨省+节假日判断、
可疑车辆判定、Redis 批量写入、分批坑位、4 个入口的端到端流程。
"""
import logging
import os
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.CarParaVO import CarParaVO  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry  # noqa: E402
from com.ruoyi.base.domain.OdsSzdnSection import OdsSzdnSection  # noqa: E402
from com.ruoyi.base.domain.TrailBo import TrailBo  # noqa: E402
from com.ruoyi.base.domain.TrailInfo import TrailInfo  # noqa: E402
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks  # noqa: E402
from com.ruoyi.base.service.ISysUtilService import ISysUtilService  # noqa: E402
from com.ruoyi.base.service.impl.HighPerformanceSyncService import (  # noqa: E402
    DateRange,
    HighPerformanceSyncService,
    PreloadedData,
    SuspiciousVehicleTask,
    SyncConfig,
    TrackTrailTuple,
)
from com.ruoyi.common.core.redis.RedisCache import RedisCache  # noqa: E402
from com.ruoyi.common.utils.spring.SpringUtils import SpringUtils  # noqa: E402
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


def check_true(label, actual):
    check(label, bool(actual), True)


records = []


class _Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


app_logger = logging.getLogger("com.ruoyi.base.service.impl.HighPerformanceSyncService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


# ---------------------------------------------------------------- 桩
def bo(state_type, uuid="P"):
    row = TrailBo()
    row.setPointUuid(uuid)
    row.setStateType(state_type)
    return row


class _StubSysUtil(ISysUtilService):
    """按 trailPoints 这个“暗号”返回不同的轨迹点列表。"""

    def __init__(self):
        self.calls = 0

    def getTrailBoList(self, paraTrailPoints):
        self.calls += 1
        if paraTrailPoints == "BOOM":
            raise ValueError("bad json")
        mapping = {
            "G7": [bo("GantryCapture", "g%d" % i) for i in range(7)],
            "G6F1": ([bo("GantryCapture", "g%d" % i) for i in range(6)]
                     + [bo("FeeRecord", "f1")]),
            "G3": [bo("GantryCapture", "g%d" % i) for i in range(3)],
        }
        return mapping.get(paraTrailPoints, [])

    def changeData(self, tracks, josnList):
        return TrailInfo()

    def syncSuspiciousCar(self, carParaVO):
        return {}

    def getByTrailBo(self, trailBo):
        return trailBo


# 【Java→Python】Python 的 ABC 会强制要求实现全部 abstractmethod（Java 接口同理，
# 但本测试只关心 getTrailBoList）；这里给桩未定义的方法补空实现并清空抽象方法集。
# 注意 __abstractmethods__ 包含接口的全部方法（含桩已实现的），必须跳过已有实现。
for _name in list(getattr(ISysUtilService, "__abstractmethods__", ())):
    if _name not in _StubSysUtil.__dict__:
        setattr(_StubSysUtil, _name, lambda self, *args, **kwargs: None)
_StubSysUtil.__abstractmethods__ = frozenset()


def track(plate_key, trailtype, enter_name, exit_name, enter_time, trail_points,
          exit_time=None):
    row = ZdataTrailTracks()
    row.setPlateKey(plate_key)
    row.setTrailtype(trailtype)
    row.setEntollstationname(enter_name)
    row.setExtollstationname(exit_name)
    row.setEnterTime(enter_time)
    # 游标分页以 exitTime 为游标，必须显式赋值，否则游标永远为 None → 死循环
    row.setExitTime(enter_time if exit_time is None else exit_time)
    row.setTrailPoints(trail_points)
    return row


class _StubTrailService(object):
    """按 pageSize 分页返回，记录每次请求的游标。"""

    def __init__(self, rows, ignore_page_size=False):
        self.rows = rows
        self.ignore_page_size = ignore_page_size
        self.requests = []

    def getLatestTrailByCursor(self, carParaVO):
        self.requests.append((carParaVO.getApplyTime1(), carParaVO.getApplyTime2(),
                              carParaVO.getPageSize(), carParaVO.getLastExitTime()))
        page_size = carParaVO.getPageSize()
        last = carParaVO.getLastExitTime()
        if self.ignore_page_size:
            # 模拟“忽略分页参数”的实现：一次全返回
            return list(self.rows)
        start = 0
        if last is not None:
            start = -1
            for index, row in enumerate(self.rows):
                if row.getExitTime() == last:
                    start = index + 1
                    break
            if start < 0:
                # 游标不存在（数据到底）：Java 端 SQL 会返回空集
                return []
        return list(self.rows[start:start + page_size])


class _StubGantryService(object):
    def __init__(self, rows, fail=False):
        self.rows = rows
        self.fail = fail

    def getGantryRedis(self):
        if self.fail:
            raise RuntimeError("gantry cache down")
        return list(self.rows)


class _StubLocationService(object):
    def __init__(self, mapping):
        self.mapping = mapping

    def getRedisList(self):
        return dict(self.mapping)


class _StubSectionService(object):
    def __init__(self, rows):
        self.rows = rows

    def getSectionList(self):
        return list(self.rows)


def new_service(rows=None, gantry_rows=None, section_rows=None,
                mapping=None, redis=None, is_local="local"):
    class _Env(object):
        def value(self, placeholder, target_type=str):
            return is_local

    redis_cache = RedisCache(redis or RedisTemplate())
    return HighPerformanceSyncService(
        redisCache=redis_cache,
        zdataTrailTracksService=_StubTrailService(rows or []),
        odsSzdnGantryService=_StubGantryService(gantry_rows or []),
        zdataLocationDictService=_StubLocationService(mapping or {}),
        sectionService=_StubSectionService(section_rows or []),
        snapshotFlowAddcodeService=object(),
        feeRecords01Service=object(),
        environment=_Env(),
    )


# ---------------------------------------------------------------- 0) 常量/内部类别名
svc0 = new_service()
check("redisTimeKey", HighPerformanceSyncService.redisTimeKey, "sys_config:syncSuspiciousCar_time")
check("redisBiteKey", HighPerformanceSyncService.redisBiteKey, "sys_config:syncSuspiciousCar_bite")
check("supoer_mjnum key", HighPerformanceSyncService.supoer_mjnum, "sys_config:supoer_mjnum")
check("road key", HighPerformanceSyncService.road_supoer_mjnum, "sys_config:road_supoer_mjnum")
check("max pool unused", HighPerformanceSyncService.MAX_POOL_SIZE,
      HighPerformanceSyncService.CORE_POOL_SIZE * 2)
check("queue capacity", HighPerformanceSyncService.QUEUE_CAPACITY, 1000)
check("keep alive (long)", HighPerformanceSyncService.KEEP_ALIVE_TIME, 60)
check("isLocalhost", svc0.isLocalhost, "local")
check_true("SyncConfig alias", HighPerformanceSyncService.SyncConfig is SyncConfig)
check_true("PreloadedData alias", HighPerformanceSyncService.PreloadedData is PreloadedData)
check_true("DateRange alias", HighPerformanceSyncService.DateRange is DateRange)
check_true("TrackTrailTuple alias", HighPerformanceSyncService.TrackTrailTuple is TrackTrailTuple)
check_true("Task alias",
           HighPerformanceSyncService.SuspiciousVehicleTask is SuspiciousVehicleTask)

# ---------------------------------------------------------------- 1) 配置加载
config = svc0.loadSyncConfig()
check("local pageSize 6000", config.page_size, 6000)
check("starTime default", config.star_time, 2)
check("endTime default", config.end_time, 4)
check("bite default", config.bite, 0.3)
check("supoerMjnum default", config.supoer_mjnum, 5)
check("roadSupoerMjnum default", config.road_supoer_mjnum, 3)

redis_cfg = RedisTemplate()
redis_cfg.opsForValue().set("sys_config:syncSuspiciousCar_time", "7")
redis_cfg.opsForValue().set("sys_config:syncSuspiciousCar_bite", "0.5")
redis_cfg.opsForValue().set("sys_config:supoer_mjnum", 8)
redis_cfg.opsForValue().set("sys_config:road_supoer_mjnum", "  ")
svc_cfg = new_service(redis=redis_cfg)
config2 = svc_cfg.loadSyncConfig()
check("redis starTime override", config2.star_time, 7)
check("redis bite override", config2.bite, 0.5)
check("redis mjnum override", config2.supoer_mjnum, 8)
check("blank road mjnum keeps default", config2.road_supoer_mjnum, 3)

svc_nonlocal = new_service(is_local="prod")
check("non-local pageSize 2000", svc_nonlocal.loadSyncConfig().page_size, 2000)
# 回收：本次会话创建的线程池全部 shutdown，避免退出时线程堆积
for owner in (svc0, svc_cfg, svc_nonlocal):
    owner.executorService.shutdown()

# ---------------------------------------------------------------- 2) 日期范围与分片
range_today = svc0.calculateDateRange(0, 4)
today = datetime.now().strftime("%Y-%m-%d")
check("range start", range_today.start_time, today + " 00:00:00")
check("range end", range_today.end_time, today + " 23:59:59")
check("range formatted", range_today.formatted_date, datetime.now().strftime("%Y%m%d"))

slices = svc0.splitDateRangeByHour(range_today, 4)
check("4 slices", len(slices), 4)
check("first slice start", slices[0].start_time, today + " 00:00:00")
# 总跨度是 00:00:00 ~ 23:59:59（86,399,000ms），//4 = 21,599,750ms = 5h59m59.75s，
# 按 yyyy-MM-dd HH:mm:ss 格式化后秒位被截断 → 05:59:59（原 Java 行为一致）
check("first slice end", slices[0].end_time, today + " 05:59:59")
check("last slice end", slices[-1].end_time, today + " 23:59:59")
check("slice keeps formattedDate", slices[0].formatted_date, range_today.formatted_date)

# 分片数远超 24 → 每片最少 1 小时
many = svc0.splitDateRangeByHour(range_today, 1000)
check("min 1h per slice", len(many), 24)
check("min slice span", (datetime.strptime(many[1].start_time, "%Y-%m-%d %H:%M:%S")
                         - datetime.strptime(many[0].start_time, "%Y-%m-%d %H:%M:%S")),
      timedelta(hours=1))

bad_range = DateRange()
bad_range.start_time = "not-a-time"
bad_range.end_time = "also-bad"
bad_range.formatted_date = "X"
bad_slices = svc0.splitDateRangeByHour(bad_range, 4)
check("parse failure returns original", len(bad_slices), 1)
check_true("parse failure same object", bad_slices[0] is bad_range)
check_true("parse failure log", logged("[时间分片] 解析时间失败"))

# ---------------------------------------------------------------- 3) 游标分页
rows3 = [track("A%d" % i, "0", "门架1", "门架2",
               datetime(2026, 9, 1, 10, i, 0), "G3") for i in range(5)]
stub3 = _StubTrailService(rows3)
svc3 = HighPerformanceSyncService(
    redisCache=RedisCache(RedisTemplate()), zdataTrailTracksService=stub3,
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
dr = svc3.calculateDateRange(0, 4)
page = svc3.queryTrailTracksWithCursor(dr, 2)
check("cursor page size", len(page), 5)
check("cursor requests", len(stub3.requests), 3)
check("cursor first page no cursor", stub3.requests[0][3], None)
check("cursor second page cursor", stub3.requests[1][3], datetime(2026, 9, 1, 10, 1, 0))
check("cursor last page cursor", stub3.requests[2][3], datetime(2026, 9, 1, 10, 3, 0))

# 恰好整除：最后一页满 pageSize 时还会再查一次空的
stub4 = _StubTrailService(rows3[:4])
svc4 = HighPerformanceSyncService(
    redisCache=RedisCache(RedisTemplate()), zdataTrailTracksService=stub4,
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
check("exact pages fetched", len(svc4.queryTrailTracksWithCursor(dr, 2)), 4)
check("exact pages requests", len(stub4.requests), 3)  # 2 + 2 + 0(空)

# ---------------------------------------------------------------- 4) 预加载
gantry_a = OdsSzdnGantry()
gantry_a.setGantryCode("GC-1")
gantry_b = OdsSzdnGantry()
gantry_b.setGantryCode("")  # 空编码被过滤
section_a = OdsSzdnSection()
section_a.setSectionCode("S1")
section_b = OdsSzdnSection()
section_b.setSectionCode("")

redis_pl = RedisTemplate()
redis_pl.opsForValue().set("sys_config:jholiday_time", "2026-10-01,,2026-10-02")
svc_pl = new_service(gantry_rows=[gantry_a, gantry_b], section_rows=[section_a, section_b],
                     mapping={"k": object()}, redis=redis_pl)
preloaded = svc_pl.preloadData()
check("gantry map filtered", list(preloaded.gantry_map.keys()), ["GC-1"])
check("location map", list(preloaded.location_map.keys()), ["k"])
check("section list", len(preloaded.section_list), 2)
check("section codes filtered", preloaded.section_codes, {"S1"})
check("holiday dates", preloaded.holiday_dates, {"2026-10-01", "2026-10-02"})

# 节假日为空 → 空集
preloaded_empty = new_service().preloadData()
check("holiday empty", preloaded_empty.holiday_dates, set())

# 预加载失败 → 打日志 + 设置中断标志，返回空数据
svc_fail = HighPerformanceSyncService(
    redisCache=RedisCache(RedisTemplate()), zdataTrailTracksService=_StubTrailService([]),
    odsSzdnGantryService=_StubGantryService([], fail=True),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
# 预加载失败：allOf(...).join() 在原文 try 之外，抛的是非受检的 CompletionException，
# 不会被下面的 catch (InterruptedException | ExecutionException) 捕获 → 直接向上抛。
# 也就是说那个 catch 块是**不可达死代码**（get() 在 allOf 成功后不会再抛）。
raised = None
try:
    svc_fail.preloadData()
except RuntimeError as error:
    raised = str(error)
check("preload failure propagates", raised, "gantry cache down")
check("preload catch unreachable", logged("[预加载数据] 失败"), False)

# ---------------------------------------------------------------- 5) 跨省 + 节假日判断
enter_time = datetime(2026, 6, 1, 10, 0, 0)  # 2026-06-01 是周一 → Mon Jun 01
cross = track("赣A1", "0", "江西门架001", "江西门架002", enter_time, "G7")
check("cross province true", HighPerformanceSyncService.isNonHolidayCrossProvince(cross, set()), True)
# 原缺陷：extractDate(String.valueOf(Date)) 得到 "Mon Jun 01"，与 yyyy-MM-dd 永不匹配
check("extractDate of Date.toString",
      HighPerformanceSyncService.extractDate(
          enter_time.strftime("%a %b %d %H:%M:%S %Z %Y")), "Mon Jun 01")
check("holiday with yyyy-MM-dd never matches",
      HighPerformanceSyncService.isNonHolidayCrossProvince(cross, {"2026-06-01"}), True)
check("holiday with Date.toString prefix matches",
      HighPerformanceSyncService.isNonHolidayCrossProvince(cross, {"Mon Jun 01"}), False)

check("trailtype 1 not cross", HighPerformanceSyncService.isNonHolidayCrossProvince(
    track("赣A2", "1", "门架1", "门架2", enter_time, "G7"), set()), False)
check("station name not cross", HighPerformanceSyncService.isNonHolidayCrossProvince(
    track("赣A3", "0", "江西收费站", "门架2", enter_time, "G7"), set()), False)
check("null trailtype", HighPerformanceSyncService.isNonHolidayCrossProvince(
    track("赣A4", None, "门架1", "门架2", enter_time, "G7"), set()), False)

# extractDate 边界
check("extractDate blank", HighPerformanceSyncService.extractDate("  "), "")
check("extractDate normal", HighPerformanceSyncService.extractDate("2026-06-01 10:00:00"), "2026-06-01")
short_error = None
try:
    HighPerformanceSyncService.extractDate("null")
except IndexError:
    short_error = "IndexError"
check("extractDate short raises", short_error, "IndexError")

# ---------------------------------------------------------------- 6) 轨迹点解析
stub_util = _StubSysUtil()
SpringUtils.register_bean("ISysUtilService", stub_util)
check("parse blank", HighPerformanceSyncService.parseTrailPointsJson(None), [])
check("parse json", len(HighPerformanceSyncService.parseTrailPointsJson("G7")), 7)
check("parse boom", HighPerformanceSyncService.parseTrailPointsJson("BOOM"), [])
check_true("parse boom warn", logged("[解析轨迹点] JSON解析失败"))
# 未注册 → getBean 返回 None → AttributeError 被 catch
SpringUtils._beans.pop("ISysUtilService", None)
check("parse without bean", HighPerformanceSyncService.parseTrailPointsJson("G7"), [])

# ---------------------------------------------------------------- 7) 可疑车辆判定
cfg = SyncConfig()
cfg.supoer_mjnum = 5
points7 = _StubSysUtil().getTrailBoList("G7")
analyzed = HighPerformanceSyncService.analyzeSuspiciousVehicle(cross, points7, PreloadedData(), cfg)
check_true("analyzed not null", analyzed is not None)
check("analyzed escapedType", analyzed.getTracks().getEscapedType(), "20")
check("analyzed escapedTfcj", analyzed.getTracks().getEscapedTfcj(), "1")
check("analyzed remark", analyzed.getTracks().getEscapedTypeRemark(),
      "跨省全程屏蔽：门架牌识流水:7，门架交易流水:0")
check("analyzed trailUuid", analyzed.getTrailUuid(), "赣A1")
check_true("analyzed same track", analyzed.getTracks() is cross)

points6f1 = _StubSysUtil().getTrailBoList("G6F1")
check("with fee not suspicious", HighPerformanceSyncService.analyzeSuspiciousVehicle(
    cross, points6f1, PreloadedData(), cfg), None)
points3 = _StubSysUtil().getTrailBoList("G3")
check("below threshold", HighPerformanceSyncService.analyzeSuspiciousVehicle(
    cross, points3, PreloadedData(), cfg), None)

# ---------------------------------------------------------------- 8) 分批（indexOf 坑位）
svc_p = new_service()
check("partition 5/2", svc_p.partitionList([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
dup = ["x", "x", "x", "y", "y"]
# indexOf 返回首次出现位置：x→0//2=0，y→3//2=1 → 同值同批（原实现坑位，与 Java 一致）
check("partition duplicates by indexOf",
      svc_p.partitionList(dup, 2), [["x", "x", "x"], ["y", "y"]])

# ---------------------------------------------------------------- 9) 批量写 Redis
redis_w = RedisTemplate()
svc_w = new_service(redis=redis_w)
info = TrailInfo()
info.setTrailUuid("赣W1")
svc_w.batchWriteToRedis([info], "20261021")
check("write key", redis_w.opsForValue().get("car_uspicious20261021:赣W1") is not None, True)
check_true("write log", logged("[批量写入Redis] 写入 1 条数据"))

# ---------------------------------------------------------------- 10) 端到端：流式
SpringUtils.register_bean("ISysUtilService", stub_util)
suspect1 = track("赣S1", "0", "门架A", "门架B", datetime(2026, 6, 1, 10, 0, 0), "G7")
normal = track("赣N1", "1", "收费站1", "收费站2", datetime(2026, 6, 1, 11, 0, 0), "G7")
stub_e2e = _StubTrailService([suspect1, normal])
redis_e2e = RedisTemplate()
svc_e2e = HighPerformanceSyncService(
    redisCache=RedisCache(redis_e2e), zdataTrailTracksService=stub_e2e,
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())

svc_e2e.syncSuspiciousCarStream(0, 0)
date_str = datetime.now().strftime("%Y%m%d")
written = redis_e2e.opsForValue().get("car_uspicious" + date_str + ":赣S1")
check_true("stream wrote suspicious", written is not None)
check("stream wrote only one", redis_e2e.opsForValue().get(
    "car_uspicious" + date_str + ":赣N1"), None)
check_true("stream log", logged("[流式同步] 完成"))

# ---------------------------------------------------------------- 11) 端到端：高性能 / 时间分片 / ForkJoin
redis_hp = RedisTemplate()
svc_hp = HighPerformanceSyncService(
    redisCache=RedisCache(redis_hp), zdataTrailTracksService=_StubTrailService([suspect1]),
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
svc_hp.syncSuspiciousCarHighPerformance(0, 0)
check_true("high performance wrote", redis_hp.opsForValue().get(
    "car_uspicious" + date_str + ":赣S1") is not None)
check_true("high performance log", logged("[高性能同步] 完成"))

redis_tr = RedisTemplate()
svc_tr = HighPerformanceSyncService(
    redisCache=RedisCache(redis_tr), zdataTrailTracksService=_StubTrailService([suspect1]),
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
svc_tr.syncSuspiciousCarByTimeRange(0, 0)
check_true("time range wrote", redis_tr.opsForValue().get(
    "car_uspicious" + date_str + ":赣S1") is not None)
check_true("time range log", logged("[时间分片同步] 完成"))

redis_fj = RedisTemplate()
svc_fj = HighPerformanceSyncService(
    redisCache=RedisCache(redis_fj), zdataTrailTracksService=_StubTrailService([suspect1]),
    odsSzdnGantryService=_StubGantryService([]),
    zdataLocationDictService=_StubLocationService({}),
    sectionService=_StubSectionService([]),
    snapshotFlowAddcodeService=object(), feeRecords01Service=object(),
    environment=type("E", (), {"value": lambda self, p, t=str: "local"})())
svc_fj.syncSuspiciousCarForkJoin(0, 0)
check_true("forkjoin wrote", redis_fj.opsForValue().get(
    "car_uspicious" + date_str + ":赣S1") is not None)
check_true("forkjoin log", logged("[ForkJoin同步] 完成"))

# ForkJoin 分治：把阈值降到 1，强制走 fork/join 分支
original_threshold = SuspiciousVehicleTask.THRESHOLD
SuspiciousVehicleTask.THRESHOLD = 1
try:
    task = SuspiciousVehicleTask(
        [suspect1, normal], 0, 2, PreloadedData(gantry_map={}, location_map={},
                                                section_list=[], section_codes=set(),
                                                holiday_dates=set()),
        cfg, "20261021")
    task_result = task.compute()
    check("forkjoin recursion result", len(task_result), 1)
finally:
    SuspiciousVehicleTask.THRESHOLD = original_threshold

check("task threshold", SuspiciousVehicleTask.THRESHOLD, 1000)
check("date range fields", (DateRange().start_time, DateRange().end_time,
                            DateRange().formatted_date), (None, None, None))
check("tuple defaults", (TrackTrailTuple().tracks, TrackTrailTuple().trail_bo_list),
      (None, None))

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
