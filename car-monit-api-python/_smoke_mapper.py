# -*- coding: utf-8 -*-
"""mapper 层冒烟测试（临时工具）：导入 23 个 Mapper + 校验自定义 SQL 语义。"""
import importlib
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "pro-base-common/src/main/java"))
sys.path.insert(0, str(BASE / "pro-business-api/src/main/java"))

JAVA_MAPPER_DIR = BASE.parent / "pro-business-api/src/main/java/com/ruoyi/base/mapper"
names = sorted(p.stem for p in JAVA_MAPPER_DIR.glob("*.java"))
print("mapper count:", len(names))
for name in names:
    importlib.import_module(f"com.ruoyi.base.mapper.{name}")
print("import all mappers OK")

from com.ruoyi.base.domain.KafkaMessageRecord import KafkaMessageRecord
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.CarParaVO import CarParaVO
from com.ruoyi.base.domain.ZdataTrailTracks import ZdataTrailTracks
from com.ruoyi.base.mapper.KafkaMessageRecordMapper import KafkaMessageRecordMapper
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import OdsLwzxsfsjFeeRecords01Mapper
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.base.mapper.ZdataTrailTracksMapper import ZdataTrailTracksMapper
from com.ruoyi.base.mapper.OdsSzdnGantryIpMapper import OdsSzdnGantryIpMapper
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp

# 1) Kafka mapper: 主键自动生成 + 失败重试查询 + 状态更新 + 重试自增
kafka = KafkaMessageRecordMapper()
for i, (status, retry) in enumerate([(0, 0), (2, 3), (1, 0)]):
    kafka.insert(KafkaMessageRecord(status=status, retry_count=retry, create_time=datetime(2026, 10, 20, 10, i)))
failed = kafka.selectFailedRecords(5, 10)
print("kafka failed:", len(failed), "table:", kafka.getTableName(), "pk:", kafka.getPkName())
first_id = failed[0].id
print("updateStatus:", kafka.updateStatusById(first_id, 1, datetime(2026, 10, 21, 9, 0)))
print("incrementRetry:", kafka.incrementRetryCount(first_id, "boom"),
      kafka.selectById(first_id).status, kafka.selectById(first_id).retry_count)

# 2) 游标分片（收费流水）
fee = OdsLwzxsfsjFeeRecords01Mapper()
for i in range(5):
    fee.insert(OdsLwzxsfsjFeeRecords01(big_id=f"id{i}", transtime=datetime(2026, 10, 21, 8, i), gantryid=f"G{i % 2}"))
batch1 = fee.selectByCursorShard("2026-10-21 00:00:00", "2026-10-21 23:59:59", None, None, 2)
last = batch1[-1]
batch2 = fee.selectByCursorShard("2026-10-21 00:00:00", "2026-10-21 23:59:59", last.transtime, last.big_id, 2)
print("cursor batch:", [b.big_id for b in batch1], [b.big_id for b in batch2])
print("gantry num:", fee.selectGantryNum(OdsLwzxsfsjFeeRecords01()))

# 3) 快照最大时间 + UUID 批量查
snap = OdsRtSzdnSnapshotFlowAddcodeMapper()
print("empty max snapshottime is now:", abs((snap.getMaxSnapshotTime() - datetime.now()).total_seconds()) < 5)
snap.insert(OdsRtSzdnSnapshotFlowAddcode(big_id="b1", datauuid="u1", snapshottime=datetime(2026, 10, 21, 7, 0)))
snap.insert(OdsRtSzdnSnapshotFlowAddcode(big_id="b2", datauuid="u2", snapshottime=datetime(2026, 10, 21, 9, 0)))
print("max snapshottime:", snap.getMaxSnapshotTime())
print("by uuid list:", [r.big_id for r in snap.selectOdsRtSzdnSnapshotFlowAddcodeByUuidList(["u1", "u2", "u9"])])

# 4) 轨迹游标分页（CarParaVO）
trail = ZdataTrailTracksMapper()
for i in range(4):
    trail.insert(ZdataTrailTracks(uuid=f"t{i}", plate_key="赣A1", exit_time=datetime(2026, 10, 21, 6, i), type=i % 2))
vo = CarParaVO()
vo.setApplyTime1("2026-10-21 00:00:00").setApplyTime2("2026-10-21 23:59:59").setPageSize(2)
page1 = trail.getLatestTrailByCursor(vo)
vo.setLastExitTime(page1[-1].getExitTime())
page2 = trail.getLatestTrailByCursor(vo)
print("trail cursor:", [t.uuid for t in page1], [t.uuid for t in page2])
print("history by carNoList:", len(trail.getHistoryTrail(CarParaVO(car_no_list=["赣A1"]))),
      "unfitting:", len(trail.getUnFitting(CarParaVO())))

# 5) Set 查询
gantry = OdsSzdnGantryIpMapper()
for ip in ["1.1.1.1", "1.1.1.1", "2.2.2.2", None]:
    gantry.insert(OdsSzdnGantryIp(ip=ip))
print("ip set:", gantry.selectIPSet())
print("ALL MAPPER SMOKE OK")
