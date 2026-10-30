# -*- coding: utf-8 -*-
"""t08 单文件校验：MultiSourceDataFlowService（独立内存 Redis + 真实 domain）。

覆盖：6 类数据源标准化、未知类型/空车牌/异常分支、实时轨迹创建与拼接、
7 天切割、待处理队列入队与重试（含 3 次放弃）。
"""
import logging
import os
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01  # noqa: E402
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01  # noqa: E402
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationExit01 import OdsLwzxsfsjFeeStationExit01  # noqa: E402
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode import (  # noqa: E402
    OdsRtSzdnSnapshotFlowStationcaptureAddcode,
)
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (  # noqa: E402
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
)
from com.ruoyi.base.domain.TrailBo import TrailBo  # noqa: E402
from com.ruoyi.base.domain.TrailInfo import TrailInfo  # noqa: E402
from com.ruoyi.base.service.impl.MultiSourceDataFlowService import (  # noqa: E402
    MultiSourceDataFlowService,
    PendingEvent,
)
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


app_logger = logging.getLogger("com.ruoyi.base.service.impl.MultiSourceDataFlowService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


# ---------------------------------------------------------------- 0) 常量与内部类
redis0 = RedisTemplate()
svc0 = MultiSourceDataFlowService(redisTemplate=redis0)
check("prefix realtime", svc0.REALTIME_TRAIL_KEY_PREFIX, "trail:realtime:")
check("prefix pending", svc0.PENDING_QUEUE_KEY_PREFIX, "trail:pending:")
check("ttl", svc0.REALTIME_TRAIL_TTL, 604800)
check("split threshold", svc0.TRAIL_SPLIT_THRESHOLD, 604800000)
check("retry interval (unused)", svc0.PENDING_RETRY_INTERVAL, 60)
check_true("PendingEvent alias", MultiSourceDataFlowService.PendingEvent is PendingEvent)
check("PendingEvent defaults", (PendingEvent().getRetryCount(), PendingEvent().getEvent()),
      (0, None))

# ---------------------------------------------------------------- 1) 六类数据转换
gantry_row = OdsRtSzdnSnapshotFlowAddcode()
gantry_row.setBigId("G-1")
gantry_row.setPlatenumber("赣A12345")
gantry_row.setSnapshottime(datetime(2026, 5, 1, 10, 0, 0))
gantry_row.setDeviceip("10.0.0.1")
gantry_row.setRoadcode("G001")
gantry_row.setSectioncode("S001")
gantry_row.setLon(113.5)
gantry_row.setLat(23.5)

border_row = OdsSzdnProvinceBorderVehicleWeightNewstructure()
border_row.setDatauuid("B-1")
border_row.setPlateNo("赣B00001")
border_row.setCheckTime(datetime(2026, 5, 1, 11, 0, 0))
border_row.setLocation("10.0.0.2")

station_row = OdsRtSzdnSnapshotFlowStationcaptureAddcode()
station_row.setBigId("S-1")
station_row.setPlatenumber("赣C00002")
station_row.setSnapshottime(datetime(2026, 5, 1, 12, 0, 0))
station_row.setDeviceip("10.0.0.3")

fee_row = OdsLwzxsfsjFeeRecords01()
fee_row.setBigId("F-1")
fee_row.setVehicleplate("赣D00003")
fee_row.setTranstime(datetime(2026, 5, 1, 13, 0, 0))

enter_row = OdsLwzxsfsjFeeStationEnter01()
enter_row.setBigId("E-1")
enter_row.setVehicleid("赣E00004")
enter_row.setEntime(datetime(2026, 5, 1, 14, 0, 0))
enter_row.setEntolllaneid("10.0.0.4")

exit_row = OdsLwzxsfsjFeeStationExit01()
exit_row.setBigId("X-1")
exit_row.setExvehicleid("赣F00005")
exit_row.setExtime(datetime(2026, 5, 1, 15, 0, 0))
exit_row.setExtolllaneid("10.0.0.5")

redis1 = RedisTemplate()
svc1 = MultiSourceDataFlowService(redisTemplate=redis1)

gantry_bo = svc1.convertToStandardEvent(gantry_row, "GantryCapture")
check("gantry uuid", gantry_bo.getPointUuid(), "G-1")
check("gantry plate", gantry_bo.getPlatenumber(), "赣A12345")
check("gantry time", gantry_bo.getCaptureTime(), "2026-05-01 10:00:00")
check("gantry locationCode", gantry_bo.getLocationCode(), "10.0.0.1")
check("gantry roadCode", gantry_bo.getRoadCode(), "G001")
check("gantry sectionCode", gantry_bo.getSectionCode(), "S001")
check("gantry lon", gantry_bo.getLon(), 113.5)
check("gantry lat", gantry_bo.getLat(), 23.5)
check("gantry stateType", gantry_bo.getStateType(), "GantryCapture")
check("gantry ipType", gantry_bo.getIpType(), "gantryip")
check_true("gantry BO ref", gantry_bo.getGantryCaptureBO() is gantry_row)
check_true("gantry pointJosn", '"bigId":"G-1"' in gantry_bo.getPointJosn())

border_bo = svc1.convertToStandardEvent(border_row, "BorderWeighingCapture")
check("border uuid", border_bo.getPointUuid(), "B-1")
check("border plate", border_bo.getPlatenumber(), "赣B00001")
check("border time", border_bo.getCaptureTime(), "2026-05-01 11:00:00")
check("border locationCode", border_bo.getLocationCode(), "10.0.0.2")
check_true("border BO ref", border_bo.getBorderWeighingCaptureBO() is border_row)

station_bo = svc1.convertToStandardEvent(station_row, "StationCapture")
check("station uuid", station_bo.getPointUuid(), "S-1")
check("station plate", station_bo.getPlatenumber(), "赣C00002")
check("station ipType", station_bo.getIpType(), "stationip")
check_true("station BO ref", station_bo.getStationCapture() is station_row)

fee_bo = svc1.convertToStandardEvent(fee_row, "FeeRecord")
check("fee uuid", fee_bo.getPointUuid(), "F-1")
check("fee plate", fee_bo.getPlatenumber(), "赣D00003")
check("fee time", fee_bo.getCaptureTime(), "2026-05-01 13:00:00")
check_true("fee BO ref", fee_bo.getFeeRecord() is fee_row)

enter_bo = svc1.convertToStandardEvent(enter_row, "FeeStationEnter")
check("enter uuid", enter_bo.getPointUuid(), "E-1")
check("enter plate", enter_bo.getPlatenumber(), "赣E00004")
check("enter locationCode", enter_bo.getLocationCode(), "10.0.0.4")
check("enter directionIn", enter_bo.getDirectionIn(), True)
check_true("enter BO ref", enter_bo.getFeeStationEnter() is enter_row)

exit_bo = svc1.convertToStandardEvent(exit_row, "FeeStationExit")
check("exit uuid", exit_bo.getPointUuid(), "X-1")
check("exit plate", exit_bo.getPlatenumber(), "赣F00005")
check("exit locationCode", exit_bo.getLocationCode(), "10.0.0.5")
check("exit directionIn", exit_bo.getDirectionIn(), False)
check_true("exit BO ref", exit_bo.getFeeStationExit() is exit_row)

check("unknown type", svc1.convertToStandardEvent(gantry_row, "Unknown"), None)
check_true("unknown type warn", logged("[数据转换] 未知的数据类型：Unknown"))

# String.valueOf(Long) 语义：null → "null"
null_id_row = OdsRtSzdnSnapshotFlowStationcaptureAddcode()
null_id_row.setBigId(None)
null_id_row.setSnapshottime(datetime(2026, 5, 1, 12, 0, 0))
check("String.valueOf(null)", svc1.convertToStandardEvent(
    null_id_row, "StationCapture").getPointUuid(), "null")

# ---------------------------------------------------------------- 2) processData：新轨迹 → 拼接 → 排序 → 7 天切割
redis2 = RedisTemplate()
svc2 = MultiSourceDataFlowService(redisTemplate=redis2)


def event(plate, moment):
    row = OdsRtSzdnSnapshotFlowAddcode()
    row.setBigId("%s-%s" % (plate, moment))
    row.setPlatenumber(plate)
    row.setSnapshottime(moment)
    row.setDeviceip("10.0.0.9")
    return row


plate = "赣A88888"
trail_key = MultiSourceDataFlowService.REALTIME_TRAIL_KEY_PREFIX + plate
svc2.processData(event(plate, datetime(2026, 6, 1, 10, 0, 0)), "GantryCapture")
trail = redis2.opsForValue().get(trail_key)
check_true("create new trail", isinstance(trail, TrailInfo))
check("new trail plateKey", trail.getTracks().getPlateKey(), plate)
check("new trail pointCount", trail.getTracks().getPointCount(), 1)
check("new trail type", trail.getTracks().getType(), 0)
check("new trail enter", trail.getTracks().getEnterTime(), datetime(2026, 6, 1, 10, 0, 0))
check("new trail exit", trail.getTracks().getExitTime(), datetime(2026, 6, 1, 10, 0, 0))
check("new trail uuid length", len(trail.getTracks().getUuid()), 32)
check("new trail uuid no dash", "-" in trail.getTracks().getUuid(), False)
check("new trail list", len(trail.getTrailList()), 1)
check_true("create log", logged("[轨迹拼接] 无现有轨迹，创建新轨迹"))

# 第二个事件（时间更晚）→ 追加
svc2.processData(event(plate, datetime(2026, 6, 1, 12, 0, 0)), "GantryCapture")
trail = redis2.opsForValue().get(trail_key)
check("append pointCount", trail.getTracks().getPointCount(), 2)
check("append type still incomplete", trail.getTracks().getType(), 0)
check("append enter", trail.getTracks().getEnterTime(), datetime(2026, 6, 1, 10, 0, 0))
check("append exit", trail.getTracks().getExitTime(), datetime(2026, 6, 1, 12, 0, 0))
check("append keep uuid", trail.getTracks().getUuid(),
      redis2.opsForValue().get(trail_key).getTracks().getUuid())

# 乱序：插入一个更早的事件 → 排序后进入时间前移
svc2.processData(event(plate, datetime(2026, 6, 1, 9, 0, 0)), "GantryCapture")
trail = redis2.opsForValue().get(trail_key)
check("reorder pointCount", trail.getTracks().getPointCount(), 3)
check("reorder type complete", trail.getTracks().getType(), 1)
check("reorder enter", trail.getTracks().getEnterTime(), datetime(2026, 6, 1, 9, 0, 0))
check("reorder exit", trail.getTracks().getExitTime(), datetime(2026, 6, 1, 12, 0, 0))
times = [p.getCaptureTime() for p in trail.getTrailList()]
check("reorder sorted", times,
      ["2026-06-01 09:00:00", "2026-06-01 10:00:00", "2026-06-01 12:00:00"])

# 超过 7 天 → 切割成新轨迹链
old_uuid = trail.getTracks().getUuid()
svc2.processData(event(plate, datetime(2026, 6, 20, 10, 0, 0)), "GantryCapture")
trail = redis2.opsForValue().get(trail_key)
check("split pointCount", trail.getTracks().getPointCount(), 1)
check_true("split new uuid", trail.getTracks().getUuid() != old_uuid)
check_true("split log", logged("[轨迹拼接] 时间差超过7天，开启新轨迹链"))

# ---------------------------------------------------------------- 3) processData：跳过与异常
records.clear()
svc3 = MultiSourceDataFlowService(redisTemplate=RedisTemplate())
no_plate = OdsRtSzdnSnapshotFlowAddcode()
no_plate.setBigId("NP-1")
no_plate.setSnapshottime(datetime(2026, 5, 1, 10, 0, 0))
svc3.processData(no_plate, "GantryCapture")
check_true("blank plate warn", logged("车牌号为空，跳过处理"))
check("blank plate not queued", svc3.redisTemplate.keys("trail:*"), set())

records.clear()
svc3.processData(object(), "GantryCapture")  # 类型不对 → getBigId 抛错
check_true("process exception logged", logged("[数据流转] 处理异常：dataType=GantryCapture"))

records.clear()
svc3.processData(gantry_row, "Unknown")
check_true("unknown skip warn", logged("数据转换失败，跳过"))

# ---------------------------------------------------------------- 4) 待处理队列
redis4 = RedisTemplate()
svc4 = MultiSourceDataFlowService(redisTemplate=redis4)

# 无队列
svc4.processPendingQueue()
check_true("empty queue log", logged("[待处理队列] 无待处理数据"))

# 构造队列：pending 里放一条正常事件，但实时轨迹缓存是脏数据 → tryAppend 失败
bad_plate = "赣Z99999"
bad_trail_key = MultiSourceDataFlowService.REALTIME_TRAIL_KEY_PREFIX + bad_plate
redis4.opsForValue().set(bad_trail_key, {"not": "a trail"})
pending = PendingEvent()
bad_event = TrailBo()
bad_event.setPointUuid("BAD-1")
bad_event.setPlatenumber(bad_plate)
bad_event.setCaptureTime("2026-07-01 10:00:00")
pending.setEvent(bad_event)
pending.setRetryCount(0)
queue_key = MultiSourceDataFlowService.PENDING_QUEUE_KEY_PREFIX + bad_plate
redis4.opsForList().rightPush(queue_key, pending)

svc4.processPendingQueue()
check("retry keeps queue", redis4.opsForList().size(queue_key), 1)
requeued = redis4.opsForList().range(queue_key, 0, -1)[0]
check("retry count 1", requeued.getRetryCount(), 1)
check_true("retry exception log", logged("[轨迹拼接] 异常：plateKey=赣Z99999"))

svc4.processPendingQueue()
check("retry count 2", redis4.opsForList().range(queue_key, 0, -1)[0].getRetryCount(), 2)

records.clear()
svc4.processPendingQueue()  # 第 3 次失败 → 放弃，不再入队
check("queue dropped after 3 retries", redis4.opsForList().size(queue_key), 0)
check_true("give up log", logged("超过最大重试次数，放弃"))

# 正常队列：成功处理后计数 +1
redis5 = RedisTemplate()
svc5 = MultiSourceDataFlowService(redisTemplate=redis5)
ok_plate = "赣Y12345"
ok_event = TrailBo()
ok_event.setPointUuid("OK-1")
ok_event.setPlatenumber(ok_plate)
ok_event.setCaptureTime("2026-08-01 10:00:00")
ok_pending = PendingEvent()
ok_pending.setEvent(ok_event)
redis5.opsForList().rightPush(
    MultiSourceDataFlowService.PENDING_QUEUE_KEY_PREFIX + ok_plate, ok_pending)
records.clear()
svc5.processPendingQueue()
check_true("queue processed log", logged("处理完成，成功数：1"))
check("processed queue removed",
      redis5.opsForList().size(
          MultiSourceDataFlowService.PENDING_QUEUE_KEY_PREFIX + ok_plate), 0)
ok_trail = redis5.opsForValue().get(
    MultiSourceDataFlowService.REALTIME_TRAIL_KEY_PREFIX + ok_plate)
check("processed created trail", ok_trail.getTracks().getPointCount(), 1)

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
