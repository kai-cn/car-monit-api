# -*- coding: utf-8 -*-
"""Live smoke test for GaussEsConsistencyService (in-process ES + in-memory mappers).

Verifies the reconciliation math (CONSISTENT / DRIFT / ERROR), the report
toString format, ``triggerRepair``, the ``reconcileEnabled`` guard and the
month-by-month window computation.

Run:  .venv\\Scripts\\python.exe tools\\smoke_consistency.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import bootstrap  # noqa: E402  (registers the Java-mirrored import roots)


def _section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 60 - len(title)))


def main() -> int:
    from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
        OdsRtSzdnSnapshotFlowAddcode,
    )
    from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
        OdsRtSzdnSnapshotFlowAddcodeMapper,
    )
    from com.ruoyi.base.service.optimization.GaussEsConsistencyService import (
        GaussEsConsistencyService,
    )
    from com.ruoyi.base.service.optimization.UnifiedQueryService import (
        UnifiedQueryService,
    )
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.action.index.IndexRequest import IndexRequest
    from org.elasticsearch.client.RestClient import RestClient
    from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
    from org.elasticsearch.xcontent.XContentType import XContentType

    DataSource = UnifiedQueryService.DataSource
    RestHighLevelClient.resetStore()

    # ---- GaussDB 侧：内存 mapper 塞 3 条，时间落在 2025-06
    # （BaseMapper 未接 DB 时就是进程内 list，新建实例即空表）
    mapper = OdsRtSzdnSnapshotFlowAddcodeMapper()
    timestamps = ["2025-06-01 10:00:00", "2025-06-15 10:00:00", "2025-06-30 23:00:00"]
    for index, stamp in enumerate(timestamps):
        entity = OdsRtSzdnSnapshotFlowAddcode()
        entity.setDatauuid("u%d" % (index + 1))
        entity.setSnapshottime(stamp)
        mapper.insert(entity)
    print("gaussdb rows:", mapper.selectCount())

    service = GaussEsConsistencyService(
        indexManageService=None, snapshotMapper=mapper)
    print("reconcileEnabled :", service.reconcileEnabled)
    print("lookbackMonths   :", service.lookbackMonths)
    print("driftRatio       :", service.driftRatio)

    client = RestHighLevelClient(
        RestClient.builder(HttpHost("127.0.0.1", 9200, "http")))
    index_name = service.resolveIndexName(DataSource.SNAPSHOT)
    print("snapshot index   :", index_name)

    start, end = "2025-06-01 00:00:00", "2025-07-01 00:00:00"

    def _index(uuid, stamp):
        client.index(IndexRequest(index_name).id(uuid).source(
            json.dumps({"datauuid": uuid, "snapshottime": stamp}),
            XContentType.JSON))

    _section("ES 为空 -> DRIFT (gaussdb=3, es=0)")
    report = service.reconcile(DataSource.SNAPSHOT, start, end)
    print("  status=%s gaussDb=%s es=%s diff=%s" %
          (report.status, report.gaussDbCount, report.esCount, report.diff))
    print("  suggestion:", report.suggestion)
    print("  toString  :", str(report))
    print("  repr      :", repr(report))

    _section("ES 补齐 3 条 -> CONSISTENT")
    for index, stamp in enumerate(timestamps):
        _index("u%d" % (index + 1), stamp)
    report = service.reconcile(DataSource.SNAPSHOT, start, end)
    print("  status=%s gaussDb=%s es=%s diff=%s suggestion=%s" %
          (report.status, report.gaussDbCount, report.esCount, report.diff,
           report.suggestion))

    _section("ES 多 1 条 -> 差异 1/3 > 1% -> DRIFT")
    _index("u99", "2025-06-20 10:00:00")
    report = service.reconcile(DataSource.SNAPSHOT, start, end)
    print("  status=%s gaussDb=%s es=%s diff=%s" %
          (report.status, report.gaussDbCount, report.esCount, report.diff))

    _section("gaussDb=0 但 es=1 -> 三元表达式第二分支 ratio=1 -> DRIFT")
    # 窗口内只有 ES 有数据（GaussDB 侧 0 条），才能触发 gaussDbCount==0 的分支
    _index("u88", "2025-08-10 10:00:00")
    report = service.reconcile(DataSource.SNAPSHOT,
                               "2025-08-01 00:00:00", "2025-09-01 00:00:00")
    print("  status=%s gaussDb=%s es=%s diff=%s suggestion=%s" %
          (report.status, report.gaussDbCount, report.esCount, report.diff,
           report.suggestion))

    _section("两侧都为空 -> gaussDb=0, es=0 -> ratio=0 -> CONSISTENT")
    report = service.reconcile(DataSource.SNAPSHOT,
                               "2020-01-01 00:00:00", "2020-02-01 00:00:00")
    print("  status=%s gaussDb=%s es=%s diff=%s suggestion=%s" %
          (report.status, report.gaussDbCount, report.esCount, report.diff,
           report.suggestion))

    _section("非法时间格式 -> status=ERROR（parse 抛 RuntimeException 被兜住）")
    report = service.reconcile(DataSource.SNAPSHOT, "not-a-date", end)
    print("  status=%s suggestion=%s" % (report.status, report.suggestion))
    try:
        service.parse("not-a-date")
    except RuntimeError as error:
        print("  parse()   -> RuntimeError:", error,
              "| cause:", type(error.__cause__).__name__)

    _section("triggerRepair -> dataSyncService.repairSync + repairCounter")
    print("  counter before:", service.repairCounter.get())
    service.triggerRepair(DataSource.SNAPSHOT, start, end)
    print("  counter after :", service.repairCounter.get())

    _section("scheduledReconcile: 默认关闭 -> 直接 return")
    service.scheduledReconcile()
    print("  returned immediately (reconcileEnabled=%s)" % service.reconcileEnabled)

    _section("scheduledReconcile: 逐月窗口 = [上月1日, 本月1日)")
    # 包一层 reconcile 记录窗口，验证 Calendar 的月份回退逻辑与 Java 一致
    recorded = []
    original_reconcile = service.reconcile

    def _record(ds, start_time, end_time):
        recorded.append((ds.name, start_time, end_time))
        return original_reconcile(ds, start_time, end_time)

    service.reconcile = _record
    service.reconcileEnabled = True
    service.scheduledReconcile()
    service.reconcile = original_reconcile
    for entry in recorded:
        print("  %-8s [%s, %s)" % entry)
    print("  calls=%d (3 表 x %d 月)" % (len(recorded), service.lookbackMonths))
    print("  counter after run:", service.repairCounter.get())

    _section("未知数据源")
    for probe in ("UNKNOWN", None):
        try:
            service.resolveIndexName(probe)
        except ValueError as error:
            print("  resolveIndexName(%r) -> ValueError: %s" % (probe, error))

    RestHighLevelClient.resetStore()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
