# -*- coding: utf-8 -*-
"""t08 单文件校验：TimeRangeParallelQueryExample 分片 + 并行游标查询。"""
import os
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks  # noqa: E402
from com.ruoyi.base.service.impl.TimeRangeParallelQueryExample import (  # noqa: E402
    TimeRangeParallelQueryExample,
)

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


class FakeService(object):
    """按 CarParaVO.lastExitTime 做游标切片的假实现。"""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def getLatestTrailByCursor(self, carParaVO):
        self.calls.append((carParaVO.apply_time1, carParaVO.apply_time2,
                           carParaVO.last_exit_time, carParaVO.page_size))
        start = datetime.strptime(carParaVO.apply_time1, "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(carParaVO.apply_time2, "%Y-%m-%d %H:%M:%S")
        rows = [r for r in self.rows if start <= r.exit_time <= end]
        if carParaVO.last_exit_time is not None:
            rows = [r for r in rows if r.exit_time > carParaVO.last_exit_time]
        rows.sort(key=lambda r: r.exit_time)
        return rows[:carParaVO.page_size]


rows = [
    ZdataTrailTracks(uuid="1", exit_time=datetime(2026, 10, 21, 0, 30)),
    ZdataTrailTracks(uuid="2", exit_time=datetime(2026, 10, 21, 1, 30)),
    ZdataTrailTracks(uuid="3", exit_time=datetime(2026, 10, 21, 2, 30)),
    ZdataTrailTracks(uuid="4", exit_time=datetime(2026, 10, 21, 3, 30)),
]
svc = FakeService(rows)
example = TimeRangeParallelQueryExample(zdataTrailTracksService=svc)

# 1) 分片：4 小时跨度，2 片 → 每片 2 小时；除最后一片外都是 [start, start+2h)
ranges = example.splitDateRangeByHour("2026-10-21 00:00:00", "2026-10-21 04:00:00", 2)
check("slice count", len(ranges), 2)
check("slice 1", (ranges[0].start_time, ranges[0].end_time), ("2026-10-21 00:00:00", "2026-10-21 02:00:00"))
check("slice 2", (ranges[1].start_time, ranges[1].end_time), ("2026-10-21 02:00:00", "2026-10-21 04:00:00"))

# 2) 最小分片 1 小时：30 分钟跨度 / 4 片 → 仍按 1 小时切，只产生 1 片
ranges2 = example.splitDateRangeByHour("2026-10-21 00:00:00", "2026-10-21 00:30:00", 4)
check("min slice", len(ranges2), 1)
check("min slice end clamped", ranges2[0].end_time, "2026-10-21 00:30:00")

# 3) 解析失败 → 原样单分片（formattedDate 保持 None）
bad = example.splitDateRangeByHour("2026/10/21", "2026-10-21 04:00:00", 2)
check("parse fail fallback", [(r.start_time, r.end_time, r.formatted_date) for r in bad],
      [("2026/10/21", "2026-10-21 04:00:00", None)])

# 4) 单分片游标分页：pageSize=2，4 条 → 两页
svc.calls = []
one = example.querySingleRangeByCursor("2026-10-21 00:00:00", "2026-10-21 04:00:00", 2)
check("cursor all", [r.uuid for r in one], ["1", "2", "3", "4"])
# Java 语义：满页时不能判定“已无数据”，必须再查一次拿到空列表才停止 → 3 次调用
check("cursor three calls", len(svc.calls), 3)
check("cursor 2nd call cursor", svc.calls[1][2], rows[1].exit_time)
check("cursor 3rd call cursor", svc.calls[2][2], rows[3].exit_time)

# 5) 并行：两个分片并行查询后按 exitTime 合并排序
parallel = example.queryParallelByRange(ranges, 10)
check("parallel merged", [r.uuid for r in parallel], ["1", "2", "3", "4"])

# 6) exit_time 为 None → 等价 Java 的 NPE（TypeError）
null_row = ZdataTrailTracks(uuid="x")
try:
    example.queryParallelByRange([], 10)  # 空分片不触发比较
    example._querySlice = lambda sr, ps: [null_row, rows[0]]
    example.queryParallelByRange([ranges[0]], 10)
    check("null exit time", "no-raise", "TypeError")
except TypeError as error:
    check("null exit time", "NullPointerException" in str(error), True)

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("TIMERANGE SMOKE OK" if not failures else "TIMERANGE SMOKE FAILED")
