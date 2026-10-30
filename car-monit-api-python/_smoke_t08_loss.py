# -*- coding: utf-8 -*-
"""t08 单文件校验：DataLossDetectionService（内存 Mapper + Redis 替身）。"""
import logging
import os
import sys
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper  # noqa: E402
from com.ruoyi.base.service.impl.DataLossDetectionService import (  # noqa: E402
    DataLossDetectionService,
    DetectionResult,
)
from java.util.concurrent.TimeUnit import TimeUnit  # noqa: E402
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate  # noqa: E402
from org.springframework.scheduling.annotation.Scheduled import _resolveMillis  # noqa: E402

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


app_logger = logging.getLogger("com.ruoyi.base.service.impl.DataLossDetectionService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


def wait_until(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class _StubReliabilityService:
    """替身：只记录 retrySend 调用（等价 Spring 里注入的同一个 Service 单例）。"""

    def __init__(self):
        self.retried = []

    def retrySend(self, messageId):
        self.retried.append(messageId)


def add_row(mapper, big_id, snapshottime):
    row = OdsRtSzdnSnapshotFlowAddcode()
    row.setBigId(big_id)
    row.setSnapshottime(snapshottime)
    mapper.insert(row)


# ---------------------------------------------------------------- 0) 构造与配置
redis = RedisTemplate()
mapper = OdsRtSzdnSnapshotFlowAddcodeMapper()
reliability = _StubReliabilityService()
svc = DataLossDetectionService(snapshotFlowMapper=mapper, redisTemplate=redis,
                               reliabilityService=reliability)
check("window size", svc.windowSizeMinutes, 60)
check("interval minutes", svc.intervalMinutes, 30)
check("loss threshold", svc.lossThresholdPercent, 5.0)
check_true("executor created", svc.detectionExecutor is not None)
# 原文的 fixedRateString 只补了 3 个 0 → 30000ms（30 秒），非 30 分钟
check("scheduled fixedRateString", svc.scheduledDetection.__scheduled__["fixedRateString"],
      "${detection.interval-minutes:30}000")
check("fixedRateString resolves to 30000", _resolveMillis("${detection.interval-minutes:30}000", "x"), 30000)

# ---------------------------------------------------------------- 1) 记录上报消息
now = datetime.now()
ts_now = int(now.timestamp() * 1000)
from com.ruoyi.common.utils.DateUtils import DateUtils  # noqa: E402

svc.recordReportedMessage("m1", "DEV1", ts_now)
svc.recordReportedMessage("m3", "DEV1", ts_now)
hour_key = svc.REPORTED_MSG_PREFIX + DateUtils.formatHour(now)
members = redis.opsForSet().members(hour_key)
check("reported set", sorted(members), ["m1", "m3"])
check("reported ttl hours", redis.getExpire(hour_key, TimeUnit.HOURS) > 0, True)

device_key = svc.DEVICE_COUNT_PREFIX + "DEV1:" + DateUtils.formatDate(now)
check("device count", redis.opsForValue().get(device_key), 2)
check("device count ttl", redis.getExpire(device_key, TimeUnit.DAYS) > 0, True)

# ---------------------------------------------------------------- 2) 检测：丢失 + 重复
window_start = now - timedelta(minutes=60)
window_end = now + timedelta(minutes=1)
add_row(mapper, "m1", now - timedelta(minutes=10))     # 已存储
add_row(mapper, "m2", now - timedelta(minutes=20))     # 已存储
add_row(mapper, "m2", now - timedelta(minutes=21))     # 重复
add_row(mapper, "out", now - timedelta(minutes=180))   # 窗口外，不应计入

result = svc.detectDataLoss(window_start, window_end)
check("reportedCount", result.getReportedCount(), 2)
check("storedCount", result.getStoredCount(), 3)
check("lostCount", result.getLostCount(), 1)
check("lostMessageIds", result.getLostMessageIds(), {"m3"})
check("lossRate", result.getLossRate(), 50.0)
check("duplicateCount", result.getDuplicateCount(), 1)
check("duplicateMessageIds", result.getDuplicateMessageIds(), {"m2"})
check("isPassed false", result.isPassed(), False)
check_true("detect log with 2 decimals", logged("丢失率=50.00%"))

# 空窗口：必须跳到**另一个小时桶**。
# 【Java 语义】上报消息按“整点小时”存储（formatHour），所以同一小时内的任意子窗口
# 都会取到该小时桶的全部消息；换小时才能得到真正的空集合。
empty_start = now + timedelta(hours=2)
empty_end = empty_start + timedelta(minutes=1)
empty_result = svc.detectDataLoss(empty_start, empty_end)
check("empty reported", empty_result.getReportedCount(), 0)
check("empty stored", empty_result.getStoredCount(), 0)
check("empty lossRate", empty_result.getLossRate(), 0)
check("empty passed", empty_result.isPassed(), True)

# ---------------------------------------------------------------- 3) 报告 + 告警
svc.generateReport(result, window_start, window_end)
report_keys = redis.keys(svc.REPORT_PREFIX + "*")
check("report written", len(report_keys), 1)
report = redis.opsForValue().get(list(report_keys)[0])
check("report fields", sorted(report.keys()),
      ["duplicateCount", "endTime", "generatedTime", "lossRate", "lostCount",
       "reportId", "reportedCount", "startTime", "storedCount"])
check("report lostCount", report["lostCount"], 1)
check("report ttl days", redis.getExpire(list(report_keys)[0], TimeUnit.DAYS) > 0, True)

svc.sendAlert(result)
check_true("alert logged", logged("数据丢失率超过阈值"))
check_true("alert contains rate", logged("50.00%"))

# ---------------------------------------------------------------- 4) 定时任务（异步）
svc.scheduledDetection()
check_true("scheduled detection generated report",
           wait_until(lambda: len(redis.keys(svc.REPORT_PREFIX + "*")) == 2))

# ---------------------------------------------------------------- 5) 补偿拉取
reliability.retried.clear()
redis.opsForValue().set("reliability:msg:content:m3", "{}")
compensate_result = DetectionResult()
compensate_result.setLostCount(2)
compensate_result.setLostMessageIds({"m3", "m4"})  # m4 无缓存内容
svc.triggerCompensation(compensate_result)
check("retry only cached message", reliability.retried, ["m3"])
check_true("expired content warned", logged("丢失消息内容已过期: messageId=m4"))

# lostCount == 0 时直接返回
reliability.retried.clear()
zero_result = DetectionResult()
zero_result.setLostCount(0)
svc.triggerCompensation(zero_result)
check("no retry when nothing lost", reliability.retried, [])

# ---------------------------------------------------------------- 6) 设备统计
stats_one = svc.getDeviceReportStats("DEV1", now)
check("stats single device", stats_one, {"DEV1": 2})
stats_missing = svc.getDeviceReportStats("DEV2", now)
check("stats missing device zero", stats_missing, {"DEV2": 0})

svc.recordReportedMessage("m9", "DEV2", ts_now)
stats_all = svc.getDeviceReportStats(None, now)
check("stats all devices", sorted(stats_all.keys()), ["DEV1", "DEV2"])
check("stats all DEV2 count", stats_all["DEV2"], 1)

# ---------------------------------------------------------------- 7) DetectionResult 默认值
default_result = DetectionResult()
check("default reportedCount", default_result.reported_count, 0)
check("default lossRate", default_result.loss_rate, 0.0)
check("default lostMessageIds", default_result.lost_message_ids, None)
check("default passed", default_result.isPassed(), True)
check("nested class alias", DataLossDetectionService.DetectionResult, DetectionResult)

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
print("LOSS DETECTION SMOKE OK" if not failures else "LOSS DETECTION SMOKE FAILED")
