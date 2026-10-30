# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.TimeRangeParallelQueryExample

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/TimeRangeParallelQueryExample.java
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from java.util.concurrent.CompletableFuture import CompletableFuture
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors, ThreadFactory
from java.util.concurrent.atomic.AtomicInteger import AtomicInteger

from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.service.IZdataTrailTracksService import IZdataTrailTracksService

__all__ = ["TimeRangeParallelQueryExample"]

log = logging.getLogger(__name__)

# Java 的 SimpleDateFormat("yyyy-MM-dd HH:mm:ss")：线程不安全，此处用 strptime 替代
_DATE_PATTERN = "%Y-%m-%d %H:%M:%S"


def _exitTimeKey(track: ZdataTrailTracks) -> datetime:
    """等价 Java 的 `Comparator.comparing(ZdataTrailTracks::getExitTime)`。

    【Java→Python】`Comparator.comparing` 在 key 为 null 时抛 NullPointerException；
    Python 的 sort 遇到 None 会抛 TypeError（同样中断执行）。这里显式检查并
    抛出带 Java 语义的 TypeError，避免“看起来能跑、排序结果却不对”的静默偏差。
    """
    if track.exit_time is None:
        raise TypeError("java.lang.NullPointerException: exitTime 为 null，Comparator.comparing 无法比较")
    return track.exit_time


class _TimeRangeQueryThreadFactory(ThreadFactory):
    """`Executors.newFixedThreadPool(..., new ThreadFactory(){...})` 的匿名内部类。

    【Java→Python】Java 的匿名 ThreadFactory 用 AtomicInteger 生成线程名
    `time-range-query-N` 并把线程设为 daemon；Python 的 threading.Thread 同样支持
    daemon=True，这里用原子计数器还原命名逻辑。
    """

    def __init__(self) -> None:
        self.counter = AtomicInteger(0)

    def newThread(self, target) -> threading.Thread:
        return threading.Thread(
            target=target,
            name="time-range-query-%d" % self.counter.incrementAndGet(),
            daemon=True,
        )


class TimeRangeParallelQueryExample(object):
    """时间范围分片 + 多线程游标查询示例

    【Java→Python】
    1) `@Slf4j @Component` → 模块级 logger + 普通类；`@Autowired` 字段 → 构造器注入，
       缺省时 new 一个实现（等价 Spring 找不到 Bean 时无法启动，这里放宽以便独立运行）。
    2) `CORE_POOL_SIZE = Runtime.getRuntime().availableProcessors()` → `os.cpu_count()`。
       注意：Java 返回“可用处理器数”，Python 的 os.cpu_count() 返回“逻辑 CPU 数”，
       在容器/cgroup 限额下两者可能不同，这里保持 Java 的语义（不做 cgroup 解析）。
    3) `ExecutorService` 字段在 Java 里是**单例 Bean 的成员**，进程存活期间不 shutdown；
       本类的 executor 同样常驻（daemon 线程，不阻塞进程退出）。
    """

    FMT = _DATE_PATTERN

    CORE_POOL_SIZE = os.cpu_count() or 1  # Runtime.getRuntime().availableProcessors()

    def __init__(self,
                 zdataTrailTracksService: Optional[IZdataTrailTracksService] = None,
                 executorService: Optional[ExecutorService] = None) -> None:
        if zdataTrailTracksService is None:
            from com.ruoyi.base.service.impl.ZdataTrailTracksServiceImpl import ZdataTrailTracksServiceImpl

            zdataTrailTracksService = ZdataTrailTracksServiceImpl()
        self.zdataTrailTracksService = zdataTrailTracksService
        # Java: 字段初始化即创建线程池（构造期内完成）
        self.executorService = executorService or Executors.newFixedThreadPool(
            TimeRangeParallelQueryExample.CORE_POOL_SIZE,
            _TimeRangeQueryThreadFactory(),
        )

    # ------------------------------------------------------------------ 分片
    def splitDateRangeByHour(self, startTime: str, endTime: str, sliceCount: int) -> List["TimeRangeParallelQueryExample.DateRange"]:
        """时间范围分片：将大的时间范围分割成多个小时段

        【Java→Python】
        1) `SimpleDateFormat.parse` 失败抛 ParseException → Python `strptime` 抛 ValueError，
           `except` 分支照原样“返回原始范围作为单个分片”。
        2) Java 的 long 除法 `totalMillis / sliceCount` 是**截断取整**，
           这里用 `int(total_millis / slice_count)` 而不是 `//`（`//` 对负数是向下取整，
           与 Java 的“向零取整”不一致；时间跨度为负时结果会差 1 毫秒）。
        3) `Calendar.add(MILLISECOND, (int) sliceMillis)` → `timedelta(milliseconds=...)`。
           注意 Java 强转 int 可能溢出（分片跨度 > 24.8 天），Python 无此限制（见下方注释）。
        4) `endDate.before/after` → Python 的 `<` / `>`（datetime 可直接比较）。
        """
        ranges: List[TimeRangeParallelQueryExample.DateRange] = []

        try:
            start_date = datetime.strptime(startTime, self.FMT)
            end_date = datetime.strptime(endTime, self.FMT)

            # 计算时间跨度（毫秒）
            total_millis = int((end_date - start_date).total_seconds() * 1000)
            # 每个分片的时间跨度（毫秒）
            slice_millis = int(total_millis / sliceCount)  # Java long 除法：向零取整
            # 保证每个分片至少1小时
            min_slice_millis = 60 * 60 * 1000
            slice_millis = max(slice_millis, min_slice_millis)

            current = start_date  # Java: Calendar.getInstance().setTime(startDate)
            while current < end_date:  # Java: calendar.getTime().before(endDate)
                sub_range = TimeRangeParallelQueryExample.DateRange()
                sub_range.start_time = current.strftime(self.FMT)
                sub_range.formatted_date = ""

                # 计算分片结束时间
                # 【Java→Python】Java 的 `(int) sliceMillis` 在跨度超过 Integer.MAX_VALUE
                # 时会溢出成负数；这里不做溢出模拟（业务上分片跨度远小于该上限）。
                current = current + timedelta(milliseconds=slice_millis)
                sub_end = end_date if current > end_date else current
                sub_range.end_time = sub_end.strftime(self.FMT)

                ranges.append(sub_range)
                log.info("[时间分片] 创建分片: %s - %s", sub_range.start_time, sub_range.end_time)

        except ValueError:
            log.error("[时间分片] 解析时间失败", exc_info=True)
            # 失败时返回原始范围作为单个分片
            original = TimeRangeParallelQueryExample.DateRange()
            original.start_time = startTime
            original.end_time = endTime
            ranges.append(original)

        return ranges

    # ------------------------------------------------------------------ 单分片
    def querySingleRangeByCursor(self, startTime: str, endTime: str, pageSize: int) -> List[ZdataTrailTracks]:
        """使用游标分页查询单个时间分片的数据

        【Java→Python】`Date lastExitTime = null;` → `last_exit_time = None`；
        Java 的 `List.addAll` → `list.extend`；`pageResults.get(size - 1)` →
        `page_results[len(page_results) - 1]`（负数下标虽然等价，但这里保持 Java 的写法）。
        """
        all_results: List[ZdataTrailTracks] = []
        last_exit_time: Optional[datetime] = None
        has_more = True

        while has_more:
            car_para_vo = CarParaVO()
            car_para_vo.setApplyTime1(startTime)
            car_para_vo.setApplyTime2(endTime)
            car_para_vo.setPageSize(pageSize)
            car_para_vo.setLastExitTime(last_exit_time)  # 使用时间游标

            page_results = self.zdataTrailTracksService.getLatestTrailByCursor(car_para_vo)

            # 【Java→Python】Java 先判断 isEmpty 再取最后一个元素；顺序不能颠倒，
            # 否则空列表会 IndexError（Java 里是 IndexOutOfBoundsException）。
            if not page_results or len(page_results) < pageSize:
                has_more = False
            else:
                last_exit_time = page_results[len(page_results) - 1].getExitTime()

            all_results.extend(page_results)
            log.debug("[游标分页] 分片 %s - %s 获取 %d 条，累计 %d 条",
                      startTime, endTime, len(page_results), len(all_results))

        return all_results

    # ------------------------------------------------------------------ 并行
    def queryParallelByRange(self, subRanges: List["TimeRangeParallelQueryExample.DateRange"], pageSize: int) -> List[ZdataTrailTracks]:
        """多线程并行查询多个时间分片的数据

        【Java→Python】
        1) `subRanges.stream().map(subRange -> CompletableFuture.supplyAsync(...))` 在 Java 里
           lambda 捕获的是**每次迭代的 final 变量**；Python 的循环变量是**共享的可变引用**，
           必须用默认参数 `sr=sub_range` 在创建 lambda 时绑定当前值，否则所有任务都会
           读到最后一个分片（经典闭包陷阱，见下方代码注释）。
        2) `futures.stream().map(CompletableFuture::join).flatMap(List::stream).sorted(...)`
           → 依次 join + extend + 排序；Java 的 sorted 是稳定排序，Python 的 list.sort 同样稳定。
        """
        start_time = int(time.time() * 1000)  # System.currentTimeMillis()
        log.info("[并行查询] 开始，分片数量: %d", len(subRanges))

        # 为每个分片创建并行查询任务
        futures: List[CompletableFuture] = []
        for sub_range in subRanges:
            # 【Java→Python】`sr=sub_range` 是必须的：默认参数在 lambda 定义时求值，
            # 等价 Java 里捕获“本轮循环的 final 变量”。
            futures.append(
                CompletableFuture.supplyAsync(
                    lambda sr=sub_range: self._querySlice(sr, pageSize),
                    self.executorService,
                )
            )

        # 等待所有查询任务完成
        all_results: List[ZdataTrailTracks] = []
        for future in futures:
            all_results.extend(future.join())
        # 按出站时间排序，保证数据顺序一致性
        all_results.sort(key=_exitTimeKey)

        total_cost = int(time.time() * 1000) - start_time
        log.info("[并行查询] 完成，总数据量: %d，总耗时: %d ms", len(all_results), total_cost)

        return all_results

    def _querySlice(self, subRange: "TimeRangeParallelQueryExample.DateRange", pageSize: int) -> List[ZdataTrailTracks]:
        """Java 中 supplyAsync 内联的 lambda 体（含耗时日志）。

        【Java→Python】Java 的 lambda 直接写在外层方法里；Python 里抽成私有方法，
        避免 lambda 过长（不影响语义）。
        """
        log.info("[并行查询] 开始查询分片: %s - %s", subRange.start_time, subRange.end_time)
        slice_start = int(time.time() * 1000)
        result = self.querySingleRangeByCursor(subRange.start_time, subRange.end_time, pageSize)
        slice_cost = int(time.time() * 1000) - slice_start
        log.info("[并行查询] 分片完成: %s - %s, 获取 %d 条，耗时 %d ms",
                 subRange.start_time, subRange.end_time, len(result), slice_cost)
        return result

    # ------------------------------------------------------------------ 示例
    def completeExample(self, startTime: str, endTime: str, pageSize: int) -> None:
        """完整示例：时间分片+多线程游标查询"""
        log.info("[完整示例] 开始，时间范围: %s - %s, 每页大小: %d", startTime, endTime, pageSize)

        # 1. 时间分片（分片数量 = CPU核心数）
        sub_ranges = self.splitDateRangeByHour(startTime, endTime, self.CORE_POOL_SIZE)

        # 2. 并行查询所有分片
        all_tracks = self.queryParallelByRange(sub_ranges, pageSize)

        # 3. 后续处理（这里仅作为示例，实际可根据需要处理数据）
        log.info("[完整示例] 完成，总处理数据量: %d", len(all_tracks))

    # ------------------------------------------------------------------ 内部类
    @dataclass
    class DateRange:
        """时间范围内部类

        【Java→Python】
        1) `public static class DateRange` → 类内 `@dataclass`（Python 的嵌套类天然是“静态”的，
           不需要 static 关键字）。
        2) Java 的三个**包级私有字段** startTime/endTime/formattedDate → snake_case 属性，
           Java 字段默认 null → Python 默认 None。
        3) Java 里 `new DateRange()` 后逐字段赋值；dataclass 提供同样的“无参构造 + 赋值”用法。
        """

        start_time: Optional[str] = None  # Java: String startTime;
        end_time: Optional[str] = None  # Java: String endTime;
        formatted_date: Optional[str] = None  # Java: String formattedDate;
