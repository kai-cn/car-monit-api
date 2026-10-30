# -*- coding: utf-8 -*-
"""t08 单文件校验：DelayMonitoringService（无 Redis 依赖，用内存替身）。"""
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from org.springframework.core.env.Environment import Environment  # noqa: E402
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate  # noqa: E402
from com.ruoyi.base.service.impl.DelayMonitoringService import DelayMonitoringService  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


redis = RedisTemplate()
svc = DelayMonitoringService(redisTemplate=redis, environment=Environment())
check("default thresholds", (svc.deviceReportThresholdMs, svc.endToEndThresholdMs), (5000, 30000))

# 1) 设备上报延迟：采集时间早 8 秒 → 超阈值告警
svc.recordDeviceCaptureTime("D1", int(time.time() * 1000) - 8000)
delay = svc.recordServiceReceiveTime("D1", "DEV1")
check("delay over threshold", delay >= 7900, True)
check("alert written", redis.opsForValue().get("monitoring:alert:count:DEVICE_REPORT_DELAY:DEV1") is not None, True)

# 2) 告警抑制：1 分钟内再次告警不刷新时间
first_alert_time = redis.opsForValue().get("monitoring:alert:count:DEVICE_REPORT_DELAY:DEV1")
svc.recordDeviceCaptureTime("D2", int(time.time() * 1000) - 9000)
svc.recordServiceReceiveTime("D2", "DEV1")
check("alert suppressed", redis.opsForValue().get("monitoring:alert:count:DEVICE_REPORT_DELAY:DEV1"), first_alert_time)

# 3) 未记录采集时间 → -1
check("no capture time", svc.recordServiceReceiveTime("UNKNOWN", "DEV1"), -1)

# 4) 消息传输 / 数据处理 / 端到端
svc.recordMessageProduceTime("M1")
time.sleep(0.01)
check("transfer delay >= 10ms", svc.recordMessageConsumeTime("M1") >= 10, True)
svc.recordProcessStartTime("M2")
time.sleep(0.01)
check("process delay >= 10ms", svc.recordProcessEndTime("M2") >= 10, True)
check("e2e delay", svc.calculateEndToEndDelay("D3", 1000, 4000, "DEV2"), 3000)

# 5) 统计：device 列表内有 2 条超阈值延迟
stats = svc.calculateStats()
check("device max > 0", stats.device_report_max > 0, True)
check("device avg <= max", stats.device_report_avg <= stats.device_report_max, True)
check("e2e max", stats.end_to_end_max, 3000)
check("getter works", stats.getDeviceReportMax(), stats.device_report_max)

# 6) 空数据 -> 0
check("empty avg", svc.calculateAvg([]), 0)
check("empty max", svc.calculateMax([]), 0)
check("avg truncates", svc.calculateAvg([1, 2]), 1)

# 7) formatDate 为 yyyyMMdd
from datetime import datetime  # noqa: E402

check("formatDate", svc.formatDate(datetime(2026, 10, 21)), "20261021")

# 8) @Scheduled 元数据
check("scheduled fixedRate", getattr(svc.generateStatsReport, "__scheduled__")["fixedRate"], 600000)

print("checks:", total[0] - len(failures), "/", total[0])
for f in failures:
    print("FAIL", f)
print("DELAY SMOKE OK" if not failures else "DELAY SMOKE FAILED")
