# -*- coding: utf-8 -*-
"""Live smoke test for UnifiedExportService (in-process ES emulation + CSV on disk).

Covers all three data sources (snapshot / fee / trail), CSV escaping, file
splitting via ``optimization.export.file-batch``, status polling and
``cleanExpiredTasks``.

Run:  .venv\\Scripts\\python.exe tools\\smoke_unified_export.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import bootstrap  # noqa: E402  (registers the Java-mirrored import roots)

_EXPORT_DIR = _ROOT / "tools" / "_export_tmp"
# 【Java→Python】Spring 的松弛绑定：optimization.export.dir -> OPTIMIZATION_EXPORT_DIR
os.environ["OPTIMIZATION_EXPORT_DIR"] = str(_EXPORT_DIR)
# 强制切分文件：scroll 每批 2 条 + file-batch 2 条 -> 5 条文档切 3 个 part
# （若一整批就返回全部 5 条，循环只进一次，exportBatchSize 永远命中不了
#    `totalCount % exportBatchSize == 0` 的切入条件 —— 这是 Java 原文的行为）
os.environ["OPTIMIZATION_EXPORT_SCROLL_BATCH"] = "2"
os.environ["OPTIMIZATION_EXPORT_FILE_BATCH"] = "2"


def _section(title: str) -> None:
    print("\n=== " + title + " " + "=" * max(0, 60 - len(title)))


def main() -> int:
    from com.ruoyi.base.service.optimization.UnifiedExportService import (
        UnifiedExportService,
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
    if _EXPORT_DIR.exists():
        shutil.rmtree(_EXPORT_DIR)

    service = UnifiedExportService()
    print("exportDir              :", service.exportDir)
    print("scrollBatchSize        :", service.scrollBatchSize)
    print("exportBatchSize        :", service.exportBatchSize)
    print("scrollKeepaliveMin     :", service.scrollKeepaliveMin)

    client = RestHighLevelClient(
        RestClient.builder(HttpHost("127.0.0.1", 9200, "http")))

    _section("resolveIndexName / resolveTimeField")
    for ds in (DataSource.SNAPSHOT, DataSource.FEE, DataSource.TRAIL):
        print("  %-8s -> index=%s, timeField=%s"
              % (ds.name, service.resolveIndexName(ds), service.resolveTimeField(ds)))
    try:
        service.resolveTimeField("UNKNOWN")
    except ValueError as error:
        print("  UNKNOWN  -> ValueError:", error)

    _section("seed documents")
    snapshot_index = service.resolveIndexName(DataSource.SNAPSHOT)
    fee_index = service.resolveIndexName(DataSource.FEE)
    trail_index = service.resolveIndexName(DataSource.TRAIL)
    snapshot_rows = [
        {"datauuid": "u1", "platenumber": "B12345", "orgname": "O1",
         "snapshottime": "2025-06-01 10:00:00"},
        # 含逗号 + 双引号：验证 CSV 加引号并转义内部双引号
        {"datauuid": "u2", "platenumber": 'B1"2', "orgname": "O1,X",
         "snapshottime": "2025-06-02 10:00:00"},
        # 字段缺失 -> CSV 该列留空
        {"datauuid": "u3", "platenumber": "B99", "orgname": "O2",
         "snapshottime": "2025-06-03 10:00:00"},
        # 缺 orgname / platenumber：对应列留空（Java 的 `if (v != null)` 分支）
        {"datauuid": "u4", "snapshottime": "2025-06-04 10:00:00"},
        {"datauuid": "u5", "platenumber": "B5", "orgname": "O3",
         "snapshottime": "2025-06-05 10:00:00"},
    ]
    for row in snapshot_rows:
        client.index(IndexRequest(snapshot_index).id(row["datauuid"])
                     .source(json.dumps(row, ensure_ascii=False), XContentType.JSON))
    client.index(IndexRequest(fee_index).id("f1").source(json.dumps(
        {"big_id": "f1", "vehicleplate": "B12345", "transtime": "2025-06-10 08:00:00",
         "fee": 12.5}, ensure_ascii=False), XContentType.JSON))
    client.index(IndexRequest(trail_index).id("c1").source(json.dumps(
        {"cid": "c1", "envehicleid": "V1", "entime": "2025-06-10 09:00:00",
         "extime": "2025-06-10 11:00:00"}, ensure_ascii=False), XContentType.JSON))
    print("snapshot docs:", len(snapshot_rows), "| fee: 1 | trail: 1")

    start, end = "2025-01-01 00:00:00", "2025-12-31 23:59:59"

    def _run_export(label, ds, fuzzy=None):
        task_id = service.submitExportTask(ds, start, end, fuzzy)
        status = service.getExportStatus(task_id)
        deadline = time.time() + 20
        while status.status in ("PENDING", "RUNNING") and time.time() < deadline:
            time.sleep(0.05)
            status = service.getExportStatus(task_id)
        print("  %-9s task=%s status=%s total=%s parts=%s files=%d err=%s"
              % (label, task_id[:8], status.status, status.totalExported,
                 status.filePartCount, len(status.filePaths), status.errorMessage))
        return status

    _section("submitExportTask x3 data sources")
    snapshot_status = _run_export("snapshot", DataSource.SNAPSHOT)
    _run_export("fee", DataSource.FEE)
    _run_export("trail", DataSource.TRAIL)
    _run_export("fuzzy", DataSource.SNAPSHOT, {"platenumber": "B12345"})

    _section("CSV content (snapshot, split into parts)")
    for path_text in snapshot_status.filePaths:
        part = Path(path_text)
        lines = part.read_text(encoding="utf-8").splitlines()
        print("  %s: %d line(s)" % (part.name, len(lines)))
        for line in lines[:4]:
            print("     ", line[:160])

    _section("cleanExpiredTasks(0) removes COMPLETED tasks")
    print("before:", service.taskStatusMap.size())
    service.cleanExpiredTasks(0)
    print("after :", service.taskStatusMap.size())
    print("getExportStatus(completed) ->",
          service.getExportStatus(snapshot_status.taskId))

    shutil.rmtree(_EXPORT_DIR, ignore_errors=True)
    service.destroy()
    RestHighLevelClient.resetStore()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
