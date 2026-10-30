# -*- coding: utf-8 -*-
"""临时校验：LargeScaleDataSyncService（跑完即删）。"""
import os
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT,
           os.path.join(_ROOT, "pro-base-common", "src", "main", "java"),
           os.path.join(_ROOT, "pro-business-api", "src", "main", "java")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
    OdsRtSzdnSnapshotFlowAddcode,
)
from com.ruoyi.base.service.optimization.LargeScaleDataSyncService import (
    LargeScaleDataSyncService,
    SyncTask,
    TimeShard,
)
from com.ruoyi.base.service.optimization.UnifiedQueryService import UnifiedQueryService
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient

RestHighLevelClient.resetStore()
svc = LargeScaleDataSyncService()
print("svc:", svc)
print("client:", type(svc.client).__name__, "bulk:", type(svc.bulkProcessor).__name__)
print("pool core/max:", svc.shardReaderPool.getCorePoolSize(),
      svc.shardReaderPool.getMaximumPoolSize())
print("pool handler:", type(svc.shardReaderPool.getRejectedExecutionHandler()).__name__)
print("pool factory:", type(svc.shardReaderPool.getThreadFactory()).__name__)
print("scheduler:", type(svc.scheduler).__name__)
print("bulk cfg:", svc.bulkProcessor)

print("\n=== splitTimeRange ===")
shards = svc.splitTimeRange(datetime(2024, 1, 1, 0, 0), datetime(2024, 1, 1, 3, 0), 1)
print("count:", len(shards), [str(s) for s in shards])
print("partial tail:", [str(s) for s in svc.splitTimeRange(
    datetime(2024, 1, 1, 0, 0), datetime(2024, 1, 1, 1, 30), 1)])

print("\n=== buildSyncTasks ===")
tasks = svc.buildSyncTasks()
print("tasks:", [t.ds for t in tasks])
print("watermark keys:", [t.redisWatermarkKey for t in tasks])
print("index names:", [t.indexName(svc.indexManageService) for t in tasks])
print("idExtractor:", tasks[0].idExtractor(_mk := OdsRtSzdnSnapshotFlowAddcode()))
_mk.datauuid = "uuid-1"
print("idExtractor real:", tasks[0].idExtractor(_mk))

print("\n=== repairSync(ds, start, end) ===")
for i in range(3):
    row = OdsRtSzdnSnapshotFlowAddcode()
    row.big_id = "big-%d" % i
    row.datauuid = "uuid-%d" % i
    row.platenumber = "京A0000%d" % i
    row.snapshottime = datetime(2024, 1, 1, 10, i)
    svc.snapshotMapper.insert(row)
svc.repairSync(UnifiedQueryService.DataSource.SNAPSHOT,
               "2024-01-01 00:00:00", "2024-01-02 00:00:00")
docs = RestHighLevelClient.documents("snapshot_flow")
print("es docs:", len(docs), sorted(docs.keys()))
print("doc1:", docs.get("uuid-0"))
print("totalRead:", svc.totalReadCount.get(),
      "success:", svc.totalWriteSuccessCount.get(),
      "failed:", svc.totalWriteFailedCount.get())

print("\n=== repairSync(start, end) 旧接口重载 ===")
svc.repairSync("2024-01-01 00:00:00", "2024-01-02 00:00:00")
print("totalRead after legacy:", svc.totalReadCount.get())

print("\n=== incrementalSync ===")
svc.redisTemplate.opsForValue().set("es:sync:watermark:snapshot",
                                    "2020-01-01 00:00:00")
row = OdsRtSzdnSnapshotFlowAddcode()
row.big_id = "big-new"
row.datauuid = "uuid-new"
row.snapshottime = datetime(2024, 6, 1, 8, 0)
svc.snapshotMapper.insert(row)
svc.incrementalSync()
print("watermark now:", svc.redisTemplate.opsForValue().get("es:sync:watermark:snapshot"))
print("es docs after incremental:", len(RestHighLevelClient.documents("snapshot_flow")))

print("\n=== format/parse ===")
print("format:", svc.formatDateTime(datetime(2024, 1, 2, 3, 4, 5)))
print("parse:", svc.parseDateTime("2024-01-02 03:04:05"))
try:
    svc.parseDateTime("bad")
except RuntimeError as e:
    print("RuntimeError ok, cause:", type(e.__cause__).__name__)
try:
    svc.repairSync("X")
except ValueError as e:
    print("unknown ds ValueError ok:", str(e))

print("\n=== destroy ===")
svc.destroy()
print("pool shutdown:", svc.shardReaderPool.isShutdown(),
      "scheduler shutdown:", svc.scheduler.isShutdown())
