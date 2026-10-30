# -*- coding: utf-8 -*-
"""Live smoke test for the optimization services (no database, no real ES).

Indexes a handful of documents into the in-process ES emulation, then exercises
``LargeScaleQueryService`` end to end: fuzzy query (both Java overloads),
aggregation, async export (scroll + CSV on disk) and the export status map.

Run:  .venv\\Scripts\\python.exe tools\\smoke_largescale.py
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


def main() -> int:
    from com.ruoyi.base.service.optimization.LargeScaleQueryService import (
        LargeScaleQueryService,
    )
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.action.index.IndexRequest import IndexRequest
    from org.elasticsearch.client.RestClient import RestClient
    from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
    from org.elasticsearch.xcontent.XContentType import XContentType

    RestHighLevelClient.resetStore()
    if _EXPORT_DIR.exists():
        shutil.rmtree(_EXPORT_DIR)

    service = LargeScaleQueryService()
    index_name = service.resolve("snapshot").indexName
    print("resolved snapshot index:", index_name)

    client = RestHighLevelClient(
        RestClient.builder(HttpHost("127.0.0.1", 9200, "http")))
    rows = [
        {"datauuid": "u1", "platenumber": "B12345", "orgname": "O1",
         "snapshottime": "2025-06-01 10:00:00"},
        {"datauuid": "u2", "platenumber": "B12345", "orgname": "O1",
         "snapshottime": "2025-06-02 10:00:00"},
        {"datauuid": "u3", "platenumber": "B99999", "orgname": "O2",
         "snapshottime": "2025-06-03 10:00:00"},
        {"datauuid": "u4", "platenumber": "B00001", "orgname": "O3",
         "snapshottime": "2025-06-04 10:00:00"},
        {"datauuid": "u5", "platenumber": "", "orgname": "O3",
         "snapshottime": "2025-06-05 10:00:00"},
    ]
    for row in rows:
        client.index(IndexRequest(index_name).id(row["datauuid"])
                     .source(json.dumps(row, ensure_ascii=False), XContentType.JSON))
    print("indexed:", len(rows))

    start, end = "2025-01-01 00:00:00", "2025-12-31 23:59:59"

    # ---- 重载1：5 参（默认 snapshot）
    legacy = service.fuzzyQuery(start, end, None, 1, 20)
    print("fuzzyQuery(5 args) ->", len(legacy))

    # ---- 重载2：6 参 + 模糊字段（>=7 位走 term on .keyword）
    hits = service.fuzzyQuery("snapshot", start, end,
                              {"platenumber": "B12345"}, 1, 20)
    print("fuzzyQuery(platenumber=B12345) ->", len(hits))

    # ---- 浅分页：pageNum/pageSize
    page2 = service.fuzzyQuery("snapshot", start, end, None, 2, 2)
    print("fuzzyQuery(page 2, size 2) ->", len(page2))

    # ---- 统计：按 orgname 分组
    stats = service.aggregationStats("snapshot", start, end, "orgname",
                                     None, None, 100)
    print("aggregationStats(orgname) ->", stats)

    # ---- 统计：countField 指定字段
    stats2 = service.aggregationStats("snapshot", start, end, "orgname",
                                      "platenumber", None, 100)
    print("aggregationStats(platenumber count) ->", stats2)

    # ---- 异步导出：轮询状态
    task_id = service.submitExportTask("snapshot", start, end, None)
    print("export task:", task_id)
    status = service.getExportStatus(task_id)
    deadline = time.time() + 20
    while status.status in ("PENDING", "RUNNING") and time.time() < deadline:
        time.sleep(0.05)
        status = service.getExportStatus(task_id)
    print("export status: %s, total=%s, parts=%s, error=%s"
          % (status.status, status.totalExported, status.filePartCount,
             status.errorMessage))

    part_files = sorted(_EXPORT_DIR.glob("export_*.csv"))
    print("csv files:", [p.name for p in part_files])
    for part in part_files:
        lines = part.read_text(encoding="utf-8").splitlines()
        print("  %s: %d line(s)" % (part.name, len(lines)))
        for line in lines[:3]:
            print("   ", line[:120])

    # 清理导出产物，保持工作区干净
    shutil.rmtree(_EXPORT_DIR, ignore_errors=True)

    service.destroy()
    RestHighLevelClient.resetStore()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
