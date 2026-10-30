# -*- coding: utf-8 -*-
"""Live smoke test for BillionLevelQueryService (no database, no real ES).

Exercises the routing rules, the time-range math, the ``required = false``
dependency branches and the (intentionally preserved) reflection dead ends.

Run:  .venv\\Scripts\\python.exe tools\\smoke_billion.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import bootstrap  # noqa: E402  (registers the Java-mirrored import roots)


def _section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 60 - len(title)))


def main() -> int:
    from com.ruoyi.base.service.optimization.BillionLevelQueryService import (
        BillionLevelQueryService,
        QueryRouteRequest,
    )
    from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
        ElasticsearchQueryService,
    )
    from org.springframework.jdbc.core.JdbcTemplate import JdbcTemplate

    service = BillionLevelQueryService()
    print("esForceDays       :", service.esForceDays)
    print("esQueryTimeout    :", service.esQueryTimeout)
    print("scrollBatchSize   :", service.scrollBatchSize)
    print("hotDataDays       :", service.hotDataDays)
    print("es dependency     :", service.elasticsearchQueryService)
    print("jdbc dependency   :", service.jdbcTemplate)

    _section("QueryRouteRequest: JavaBean accessors + custom methods")
    request = QueryRouteRequest()
    print("default isAggregation/isExport/exportCount ->",
          request.isAggregation(), request.isExport(), request.getExportCount())
    print("hasFuzzyCondition (empty)                 ->", request.hasFuzzyCondition())
    request.setPlatenumber("赣A12345").setStartTime("2025-01-01 00:00:00") \
        .setEndTime("2025-02-01 00:00:00")
    print("hasFuzzyCondition (plate set)             ->", request.hasFuzzyCondition())
    print("getTimeRangeDays (31 天)                  ->", request.getTimeRangeDays())
    # 负数：Java 的整数除法向零截断 -> -1（用 // 会得到 -2）
    negative = QueryRouteRequest()
    negative.setStartTime("2025-02-01 00:00:00").setEndTime("2025-01-01 00:00:00")
    print("getTimeRangeDays (倒序, 向零截断)          ->", negative.getTimeRangeDays())
    broken = QueryRouteRequest()
    broken.setStartTime("not-a-date").setEndTime("2025-01-01 00:00:00")
    print("getTimeRangeDays (非法格式 -> 365)         ->", broken.getTimeRangeDays())
    missing = QueryRouteRequest()
    print("getTimeRangeDays (缺时间 -> 365)           ->", missing.getTimeRangeDays())
    print("isNotEmpty('  ') / isNotEmpty(' x ')       ->",
          request.isNotEmpty("  "), request.isNotEmpty(" x "))
    print("QueryRouteRequest repr                    ->", repr(request))

    _section("routeQuery: 4 rules + default")
    # 注意：规则2（时间跨度）排在规则3/4 之前，且**缺省时间跨度是 365 天**，
    # 所以不带 start/end 的请求永远会先命中规则2 → 想验证规则3/4 必须给窄时间范围。
    cases = [
        ("规则1 模糊条件", QueryRouteRequest(platenumber="赣A12345")),
        ("规则2 时间 31 天 > 30", QueryRouteRequest(start_time="2025-01-01 00:00:00",
                                               end_time="2025-02-01 00:00:00")),
        ("规则3 聚合统计", QueryRouteRequest(start_time="2025-01-01 00:00:00",
                                         end_time="2025-01-05 00:00:00",
                                         aggregation=True)),
        ("规则4 导出 1001 条", QueryRouteRequest(start_time="2025-01-01 00:00:00",
                                          end_time="2025-01-05 00:00:00",
                                          export=True, export_count=1001)),
        ("导出 1000 条（不超阈值→默认）", QueryRouteRequest(start_time="2025-01-01 00:00:00",
                                                 end_time="2025-01-05 00:00:00",
                                                 export=True, export_count=1000)),
        ("无时间范围（天数默认 365）", QueryRouteRequest(export=True, export_count=1)),
        ("精确查询（5 天内）", QueryRouteRequest(start_time="2025-01-01 00:00:00",
                                        end_time="2025-01-05 00:00:00")),
    ]
    for label, item in cases:
        print("  %-26s -> %s" % (label, service.routeQuery(item)))

    _section("ES 依赖未注入 -> emptyResult()")
    print("querySnapshotFlowFromES ->",
          service.querySnapshotFlowFromES("2025-01-01 00:00:00",
                                          "2025-12-31 23:59:59",
                                          "赣A12345", None, None, None, None,
                                          None, 1, 20))
    print("queryFeeRecordsFromES   ->",
          service.queryFeeRecordsFromES(None, None, "赣A", None, 1, 20))
    print("queryTrailFittingFromES ->",
          service.queryTrailFittingFromES(None, None, None, None, 1, 20))

    _section("ES 依赖已注入 -> 反射死路（方法不存在，返回空结果/0）")
    # 原文的反射目标 ElasticsearchQueryService.queryByConditions / scrollExport
    # 在 Java 侧同样不存在，所以这里必然走 NoSuchMethodException 分支。
    injected = BillionLevelQueryService(
        elasticsearchQueryService=ElasticsearchQueryService())
    print("has queryByConditions attr ->",
          callable(getattr(injected.elasticsearchQueryService,
                           "queryByConditions", None)))
    print("querySnapshotFlowFromES    ->",
          injected.querySnapshotFlowFromES("2025-01-01 00:00:00", None,
                                           "赣A12345", None, None, None, None,
                                           None, 1, 20))
    print("queryFeeRecordsFromES      ->",
          injected.queryFeeRecordsFromES(None, None, "赣A", None, 1, 20))
    print("queryTrailFittingFromES    ->",
          injected.queryTrailFittingFromES(None, None, None, None, 1, 20))
    print("invokeScrollExport         ->",
          injected.invokeScrollExport("snapshot_flow", {}, 2000))

    _section("asyncExport -> CompletableFuture (supplier 内部吃掉异常)")
    future = injected.asyncExport("snapshot_flow", {"platenumber": "赣A12345"})
    print("asyncExport join           ->", future.join())

    _section("archiveColdData: jdbc 未注入直接返回 / 注入后执行 SQL")
    service.archiveColdData()
    print("jdbc=None -> returned immediately")
    jdbc = JdbcTemplate()
    archiver = BillionLevelQueryService(jdbcTemplate=jdbc)
    archiver.archiveColdData()
    executed = jdbc.getExecutedSql()
    print("executed statements        ->", len(executed))
    for sql in executed:
        print("   ", sql[:110])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
