# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.HundredMillionLevelQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/HundredMillionLevelQueryService.java

亿级数据量查询优化服务 - Hundred Million Level Query Optimization Service

适用场景 / Applicable Scenario:
  单表数据量 5000万 ~ 5亿行，月增 2000万条
  Single table with 50M - 500M rows, monthly growth of 20M records

核心策略 / Core Strategies:
  1. 分区裁剪：按月分区表，查询时自动裁剪不需要的分区
  2. 游标分页（Keyset Pagination）：替代 OFFSET 分页，避免深翻页性能问题
  3. 物化视图：预计算统计聚合结果，加速统计类查询
  4. 覆盖索引（Covering Index）：索引包含查询所需所有字段，避免回表
  5. 并行分片查询：将大时间范围拆分为多个小分片，并行查询后合并

【Java→Python 本文件重点差异】
1) `@Slf4j @Service` → logger + 普通类；`@Autowired` → 构造器可选参数。
   `@Autowired(required = false) private JdbcTemplate jdbcTemplate;` 表示该 Bean
   **可能不存在** → Python 构造器默认 `None`，代码里 `if self.jdbcTemplate is None`
   的降级分支因此可被真实触发（与 Java 语义一致）。
2) `RedisTemplate` 是**原始类型**（无泛型），`opsForValue().get(...)` 返回 Object；
   Java 的 `(List<Map<String, Object>>) cached` 强制转换在 Python 里不存在，
   直接返回缓存值（类型由调用方保证）——已在代码处注释。
3) **lambda 捕获**：`executor.submit(() -> {...})` 里引用了循环变量 `shard`，
   Java 要求 effectively final（每次迭代是新变量）；Python 的闭包是**延迟绑定**，
   必须用默认参数 `shard=shard` 固定取值，否则所有任务都会用最后一个分片。
4) `List#sort(Comparator)` → `list.sort(key=cmp_to_key(_compare))`：
   Java 的比较器“null 排最后、其余按 snapshottime 倒序”逐行翻译成 `_compare`，
   用 `cmp_to_key` 保持三值比较语义（`key=` 无法表达 null 的特殊排序）。
5) `Executors.newFixedThreadPool(Math.min(shards.size(), PARALLEL_POOL_SIZE))`：
   Java 在分片数为 0 时会抛 IllegalArgumentException；替身 `ExecutorService`
   会把大小夹到最小 1（见其差异说明），不会抛。
   `Future#get(60, TimeUnit.SECONDS)` → 替身同名方法（超时抛 TimeoutError，
   任务异常重抛原始异常，对应 Java 的 ExecutionException）。
6) `SimpleDateFormat("yyyy-MM-dd HH:mm:ss")` → `strftime("%Y-%m-%d %H:%M:%S")`；
   `sdf.parse` 的 `ParseException` → `ValueError`（catch 分支同样“退回整段区间”）。
7) `Calendar` 是**可变**计算器 → `java.util.Calendar` 替身（内部 datetime 不可变，
   每次 set/add 重建）；`cal.getTime().before(end)` 直接写 `cal.getTime() < end`
   （Python 的 datetime 支持比较运算符）。
8) `new Date()` → `datetime.now()`；`java.sql.Timestamp.valueOf(...)` → `Timestamp.valueOf`。
9) `Collections.emptyList()` → 返回 `[]`（Python 列表即“空集合”）。
10) `redisTemplate.keys(...)` 返回 `set`；`redisTemplate.delete(keys)` 替身支持集合参数。
11) `log.error("[亿级查询] 分片查询失败", e)` → `exc_info=True`（slf4j 的堆栈打印）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import cmp_to_key
from typing import Any, Dict, List, Optional

from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import OdsLwzxsfsjFeeRecords01Mapper
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from java.sql.Timestamp import Timestamp
from java.util.Calendar import Calendar
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit
from org.springframework.data.redis.core.RedisTemplate import (
    RedisTemplate,
    defaultRedisTemplate,
)
from org.springframework.jdbc.core.JdbcTemplate import JdbcTemplate

__all__ = ["HundredMillionLevelQueryService"]

log = logging.getLogger(__name__)


class HundredMillionLevelQueryService(object):
    """亿级数据量查询优化服务。"""

    #: 游标分页默认每页大小 / Default page size for cursor pagination
    DEFAULT_PAGE_SIZE = 50
    #: 并行查询线程池大小 / Thread pool size for parallel queries
    PARALLEL_POOL_SIZE = 4
    #: 物化视图缓存前缀 / Cache prefix for materialized view results
    MV_CACHE_PREFIX = "mv:cache:"
    #: 物化视图缓存TTL（秒） / Cache TTL for materialized view results (seconds)
    MV_CACHE_TTL = 300

    def __init__(self,
                 snapshotFlowMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 feeRecordsMapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 trailFittingMapper: Optional[ZdataTrailFittingMapper] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 jdbcTemplate: Optional[JdbcTemplate] = None) -> None:
        # 【Java→Python】5 个 @Autowired → 构造器注入；RedisTemplate 缺省取进程级单例
        self.snapshotFlowMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotFlowMapper or OdsRtSzdnSnapshotFlowAddcodeMapper())
        self.feeRecordsMapper: OdsLwzxsfsjFeeRecords01Mapper = (
            feeRecordsMapper or OdsLwzxsfsjFeeRecords01Mapper())
        self.trailFittingMapper: ZdataTrailFittingMapper = (
            trailFittingMapper or ZdataTrailFittingMapper())
        self.redisTemplate: RedisTemplate = redisTemplate or defaultRedisTemplate()
        # 【Java→Python】`@Autowired(required = false)` → 默认 None（容器里可能没有该 Bean）
        self.jdbcTemplate: Optional[JdbcTemplate] = jdbcTemplate

    # ------------------------------------------------------------------ 游标分页
    def querySnapshotFlowByCursor(self, startTime: str, endTime: str,
                                  cursor: str, cursorUuid: str,
                                  pageSize: int) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """门架抓拍流水 - 游标分页查询 / Cursor pagination query。"""
        log.info("[亿级查询] 门架抓拍流水游标分页: start=%s, end=%s, cursor=%s, pageSize=%s",
                 startTime, endTime, cursor, pageSize)
        return self.snapshotFlowMapper.selectByCursorShard(
            startTime, endTime, cursor, cursorUuid, pageSize)

    def querySnapshotFlowParallel(self, startTime: str,
                                  endTime: str) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """门架抓拍流水 - 并行分片查询 / Parallel shard query。"""
        log.info("[亿级查询] 门架抓拍流水并行分片: start=%s, end=%s", startTime, endTime)
        shards: List[List[str]] = self.splitDateRangeByDay(startTime, endTime)
        log.info("[亿级查询] 拆分为 %s 个分片", len(shards))
        # 【Java→Python】分片数为 0 时 Java 会抛 IllegalArgumentException，
        # 替身 ExecutorService 夹到最小 1（见文件头第 5 条）
        executor = Executors.newFixedThreadPool(
            min(len(shards), HundredMillionLevelQueryService.PARALLEL_POOL_SIZE))
        futures: list = []
        for shard in shards:
            # 【Java→Python】**闭包延迟绑定**：必须用默认参数固定本次迭代的 shard
            def _query(shard=shard) -> List[OdsRtSzdnSnapshotFlowAddcode]:
                query: OdsRtSzdnSnapshotFlowAddcode = OdsRtSzdnSnapshotFlowAddcode()
                query.setApplyTime1(shard[0])
                query.setApplyTime2(shard[1])
                return self.snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query)

            futures.append(executor.submit(_query))
        merged: List[OdsRtSzdnSnapshotFlowAddcode] = []
        for future in futures:
            try:
                merged.extend(future.get(60, TimeUnit.SECONDS))
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.error("[亿级查询] 分片查询失败", exc_info=True)
        executor.shutdown()
        merged.sort(key=cmp_to_key(_compareSnapshotTimeDesc))
        log.info("[亿级查询] 并行查询完成，合并结果 %s 条", len(merged))
        return merged

    def queryFeeRecordsByCursor(self, startTime: str, endTime: str,
                               cursor: str, pageSize: int) -> List[OdsLwzxsfsjFeeRecords01]:
        """收费流水 - 游标分页查询。"""
        log.info("[亿级查询] 收费流水游标分页: start=%s, end=%s, cursor=%s, pageSize=%s",
                 startTime, endTime, cursor, pageSize)
        query: OdsLwzxsfsjFeeRecords01 = OdsLwzxsfsjFeeRecords01()
        query.setInApplyTime1(startTime)
        query.setInApplyTime2(endTime)
        return self.feeRecordsMapper.selectOdsLwzxsfsjFeeRecords01List(query)

    def queryTrailFittingByCursor(self, startTime: str, endTime: str,
                                  pageSize: int) -> List[ZdataTrailFitting]:
        """轨迹拟合 - 游标分页查询。"""
        log.info("[亿级查询] 轨迹拟合查询: start=%s, end=%s, pageSize=%s",
                 startTime, endTime, pageSize)
        query: ZdataTrailFitting = ZdataTrailFitting()
        if startTime is not None:
            query.setEntime(Timestamp.valueOf(startTime))
        if endTime is not None:
            query.setExtime(Timestamp.valueOf(endTime))
        return self.trailFittingMapper.selectZdataTrailFittingList(query)

    # ------------------------------------------------------------------ 物化视图
    def getSnapshotDailyStats(self, startDate: str,
                              endDate: str) -> List[Dict[str, Any]]:
        """门架抓拍 - 日粒度物化视图统计（带 Redis 缓存）。"""
        cacheKey: str = (HundredMillionLevelQueryService.MV_CACHE_PREFIX
                         + "snapshot_daily:" + startDate + ":" + endDate)
        cached: Any = self.redisTemplate.opsForValue().get(cacheKey)
        if cached is not None:
            log.info("[亿级查询] 物化视图统计命中缓存: %s", cacheKey)
            # 【Java→Python】Java 的 `(List<Map<String,Object>>) cached` 强转无对应语法
            return cached
        if self.jdbcTemplate is None:
            log.warning("[亿级查询] JdbcTemplate 未注入，返回空列表")
            return []
        sql: str = ("SELECT snapshot_date, sectioncode, sectionname, record_count, vehicle_count "
                    "FROM jl_data01.mv_snapshot_daily_section "
                    "WHERE snapshot_date >= ? AND snapshot_date <= ? "
                    "ORDER BY snapshot_date DESC")
        result: List[Dict[str, Any]] = self.jdbcTemplate.queryForList(
            sql, startDate, endDate)
        self.redisTemplate.opsForValue().set(
            cacheKey, result, HundredMillionLevelQueryService.MV_CACHE_TTL, TimeUnit.SECONDS)
        log.info("[亿级查询] 物化视图统计查询完成，%s 条记录已缓存", len(result))
        return result

    def getFeeMonthlyStats(self, startMonth: str,
                           endMonth: str) -> List[Dict[str, Any]]:
        """收费流水 - 月粒度物化视图统计（带 Redis 缓存）。"""
        cacheKey: str = (HundredMillionLevelQueryService.MV_CACHE_PREFIX
                         + "fee_monthly:" + startMonth + ":" + endMonth)
        cached: Any = self.redisTemplate.opsForValue().get(cacheKey)
        if cached is not None:
            return cached
        if self.jdbcTemplate is None:
            return []
        sql: str = ("SELECT trans_month, gantryid, record_count, total_fee, vehicle_count "
                    "FROM jl_data01.mv_fee_monthly "
                    "WHERE trans_month >= ? AND trans_month <= ? "
                    "ORDER BY trans_month DESC")
        result: List[Dict[str, Any]] = self.jdbcTemplate.queryForList(
            sql, startMonth, endMonth)
        self.redisTemplate.opsForValue().set(
            cacheKey, result, HundredMillionLevelQueryService.MV_CACHE_TTL, TimeUnit.SECONDS)
        return result

    def splitDateRangeByDay(self, startTime: str,
                            endTime: str) -> List[List[str]]:
        """把 [startTime, endTime) 按自然日切分成若干分片。

        【Java→Python】
        - `List<String[]>` → `List[List[str]]`（Python 无定长数组）
        - `SimpleDateFormat` + `Calendar` → `datetime` + `Calendar` 替身
          （`Calendar` 保持可变语义与 0 基 MONTH，见其替身说明）
        """
        result: List[List[str]] = []
        try:
            # Java: SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            start: datetime = _parseDateTime(startTime)
            # Java: Date end = endTime != null ? sdf.parse(endTime) : new Date();
            end: datetime = _parseDateTime(endTime) if endTime is not None else datetime.now()
            cal: Calendar = Calendar.getInstance()
            cal.setTime(start)
            cal.set(Calendar.HOUR_OF_DAY, 0)
            cal.set(Calendar.MINUTE, 0)
            cal.set(Calendar.SECOND, 0)
            # Java: while (cal.getTime().before(end))
            while cal.getTime() < end:
                dayStart: str = _formatDateTime(cal.getTime())
                cal.add(Calendar.DAY_OF_MONTH, 1)
                dayEnd: str = (_formatDateTime(cal.getTime())
                               if cal.getTime() < end
                               else _formatDateTime(end))
                result.append([dayStart, dayEnd])
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[亿级查询] 时间拆分失败", exc_info=True)
            result.append([startTime, endTime])
        return result

    def refreshMaterializedViews(self) -> None:
        """刷新物化视图并清理其缓存。"""
        if self.jdbcTemplate is None:
            return
        try:
            log.info("[亿级查询] 开始刷新物化视图")
            self.jdbcTemplate.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_snapshot_daily_section")
            self.jdbcTemplate.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_fee_monthly")
            keys = self.redisTemplate.keys(
                HundredMillionLevelQueryService.MV_CACHE_PREFIX + "*")
            if keys is not None and len(keys) > 0:
                # 【Java→Python】RedisTemplate#delete 替身支持传入集合（见 RedisCache 说明）
                self.redisTemplate.delete(keys)
            log.info("[亿级查询] 物化视图刷新完成")
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[亿级查询] 物化视图刷新失败", exc_info=True)

    def __repr__(self) -> str:
        return ("HundredMillionLevelQueryService(defaultPageSize=%d, "
                "parallelPoolSize=%d)" % (self.DEFAULT_PAGE_SIZE,
                                          self.PARALLEL_POOL_SIZE))


# ---------------------------------------------------------------------- 辅助函数
def _parseDateTime(text: str) -> datetime:
    """等价 `new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(text)`。

    【Java→Python】`ParseException` → `ValueError`，由调用方的 catch 分支处理。
    """
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _formatDateTime(value: datetime) -> str:
    """等价 `new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(date)`。"""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _compareSnapshotTimeDesc(a: OdsRtSzdnSnapshotFlowAddcode,
                             b: OdsRtSzdnSnapshotFlowAddcode) -> int:
    """逐行翻译原代码的 Comparator：

        if (a.getSnapshottime() == null && b.getSnapshottime() == null) return 0;
        if (a.getSnapshottime() == null) return 1;
        if (b.getSnapshottime() == null) return -1;
        return b.getSnapshottime().compareTo(a.getSnapshottime());   // 倒序

    【Java→Python】`Date#compareTo` → datetime 的大小比较；为保持“null 最大”的
    三值比较语义，不能简单用 `key=`（null 无法参与 datetime 比较）。
    """
    a_time = a.getSnapshottime()
    b_time = b.getSnapshottime()
    if a_time is None and b_time is None:
        return 0
    if a_time is None:
        return 1
    if b_time is None:
        return -1
    if a_time > b_time:
        return -1
    if a_time < b_time:
        return 1
    return 0
