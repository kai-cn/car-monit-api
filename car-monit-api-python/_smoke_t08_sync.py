# -*- coding: utf-8 -*-
"""t08 单文件校验：SnapshotFlowSyncService（内存 Mapper + Redis + 生产者桩）。"""
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper  # noqa: E402
from com.ruoyi.base.service.impl.SnapshotFlowSyncService import SnapshotFlowSyncService  # noqa: E402
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


def check_true(label, actual):
    check(label, bool(actual), True)


def wait_until(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


records = []


class _Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


app_logger = logging.getLogger("com.ruoyi.base.service.impl.SnapshotFlowSyncService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


class _StubEnvironment(object):
    """只覆盖本文件用到的 3 个 sync.* 配置（默认值取自 @Value 占位符）。"""

    def __init__(self, **overrides):
        self.overrides = overrides

    def value(self, placeholder, target_type=str):
        body = placeholder.strip()
        if body.startswith("${") and body.endswith("}"):
            body = body[2:-1]
        key, _, default = body.partition(":")
        raw = self.overrides.get(key, default)
        if target_type is bool:
            return str(raw).strip().lower() in ("true", "1", "yes", "y")
        if target_type is int:
            return int(raw)
        return str(raw)


class _StubProducer(object):
    """替身：记录 sendSnapshotFlowData 调用（Spring 里是 KafkaProducerService 单例）。"""

    def __init__(self):
        self.sent = []
        self.fail = False

    def sendSnapshotFlowData(self, data, dataId):
        if self.fail:
            raise RuntimeError("kafka unavailable")
        self.sent.append((dataId, data))
        return dataId


class _NoAutoStart(SnapshotFlowSyncService):
    """禁止 init() 自动起线程，便于在主线程里确定性调用 fullSync / incrementalSync。"""

    def init(self):
        self.syncExecutor = None


def add_row(mapper, big_id, snapshottime=None):
    row = OdsRtSzdnSnapshotFlowAddcode()
    row.setBigId(big_id)
    if snapshottime is not None:
        row.setSnapshottime(snapshottime)
    mapper.insert(row)


# ---------------------------------------------------------------- 0) 配置默认值
redis0 = RedisTemplate()
svc0 = _NoAutoStart(snapshotFlowMapper=OdsRtSzdnSnapshotFlowAddcodeMapper(),
                    kafkaProducerService=_StubProducer(), redisTemplate=redis0)
# application.yml: sync.batch-size=1000 / full-sync-enabled=true / incremental-sync-interval=60000
check("batchSize", svc0.batchSize, 1000)
check("fullSyncEnabled", svc0.fullSyncEnabled, True)
check("incrementalSyncInterval", svc0.incrementalSyncInterval, 60000)
check("last sync id key", SnapshotFlowSyncService.LAST_SYNC_ID_KEY, "snapshot_flow:last_sync_id")
check("last sync time key", SnapshotFlowSyncService.LAST_SYNC_TIME_KEY, "snapshot_flow:last_sync_time")

# ---------------------------------------------------------------- 1) 全量同步：分批 + 断点续传
mapper1 = OdsRtSzdnSnapshotFlowAddcodeMapper()
for index in range(1, 6):
    add_row(mapper1, "A%d" % index)
redis1 = RedisTemplate()
producer1 = _StubProducer()
svc1 = _NoAutoStart(snapshotFlowMapper=mapper1, kafkaProducerService=producer1,
                    redisTemplate=redis1,
                    environment=_StubEnvironment(**{"sync.batch-size": 2}))
check("batchSize override", svc1.batchSize, 2)

svc1.fullSync()
check("full sync sends all", [item[0] for item in producer1.sent], ["A1", "A2", "A3", "A4", "A5"])
check("full sync saves progress", redis1.opsForValue().get(svc1.LAST_SYNC_ID_KEY), "A5")
check_true("full sync batch log", logged("已同步 2 条数据，当前进度: A2"))
check_true("full sync done log", logged("全量同步完成"))

# 断点续传：Redis 里已有进度 → 只发后面的
mapper2 = OdsRtSzdnSnapshotFlowAddcodeMapper()
for big_id in ("B1", "B2", "B3", "B4"):
    add_row(mapper2, big_id)
redis2 = RedisTemplate()
redis2.opsForValue().set(SnapshotFlowSyncService.LAST_SYNC_ID_KEY, "B2")
producer2 = _StubProducer()
svc2 = _NoAutoStart(snapshotFlowMapper=mapper2, kafkaProducerService=producer2,
                    redisTemplate=redis2,
                    environment=_StubEnvironment(**{"sync.batch-size": 10}))
svc2.fullSync()
check("resume from last id", [item[0] for item in producer2.sent], ["B3", "B4"])

# 空表：直接结束
producer3 = _StubProducer()
svc3 = _NoAutoStart(snapshotFlowMapper=OdsRtSzdnSnapshotFlowAddcodeMapper(),
                    kafkaProducerService=producer3, redisTemplate=RedisTemplate())
svc3.fullSync()
check("empty full sync", producer3.sent, [])

# 异常分支：发送抛错 → 记录“全量同步异常”并退出（不是中断分支）
producer4 = _StubProducer()
producer4.fail = True
mapper4 = OdsRtSzdnSnapshotFlowAddcodeMapper()
add_row(mapper4, "C1")
svc4 = _NoAutoStart(snapshotFlowMapper=mapper4, kafkaProducerService=producer4,
                    redisTemplate=RedisTemplate())
svc4.fullSync()
check_true("full sync exception logged", logged("全量同步异常"))

# ---------------------------------------------------------------- 2) 增量同步：时间窗口 + 进度
mapper5 = OdsRtSzdnSnapshotFlowAddcodeMapper()
now = datetime.now()
add_row(mapper5, "D1", now - timedelta(hours=2))     # 1 天窗口内
add_row(mapper5, "D2", now - timedelta(hours=1))     # 1 天窗口内
add_row(mapper5, "D3", now + timedelta(days=1))      # 未来数据，应被 le 条件排除
redis5 = RedisTemplate()
producer5 = _StubProducer()
svc5 = _NoAutoStart(snapshotFlowMapper=mapper5, kafkaProducerService=producer5,
                    redisTemplate=redis5,
                    environment=_StubEnvironment(**{"sync.incremental-sync-interval": 3600000}))

worker = threading.Thread(target=svc5.incrementalSync, daemon=True)
worker.start()
check_true("incremental syncs window rows",
           wait_until(lambda: len(producer5.sent) == 2))
check("incremental order by snapshottime", [item[0] for item in producer5.sent], ["D1", "D2"])
check_true("incremental saves last time",
           wait_until(lambda: redis5.opsForValue().get(svc5.LAST_SYNC_TIME_KEY) is not None))
check("incremental progress is last row time",
      redis5.opsForValue().get(svc5.LAST_SYNC_TIME_KEY), now - timedelta(hours=1))
check_true("incremental log", logged("增量同步 2 条数据"))

# ---------------------------------------------------------------- 3) init()：线程池与自动启动
mapper6 = OdsRtSzdnSnapshotFlowAddcodeMapper()
producer6 = _StubProducer()
svc6 = SnapshotFlowSyncService(snapshotFlowMapper=mapper6,
                               kafkaProducerService=producer6,
                               redisTemplate=RedisTemplate(),
                               environment=_StubEnvironment(**{
                                   "sync.full-sync-enabled": False,
                                   "sync.incremental-sync-interval": 3600000}))
check("fullSyncEnabled false", svc6.fullSyncEnabled, False)
check_true("syncExecutor created", svc6.syncExecutor is not None)
check("syncExecutor not shutdown", svc6.syncExecutor.isShutdown(), False)
# full-sync 关闭 → 不会立即全量发送（mapper 为空也无从发送）
check("no auto full sync", producer6.sent, [])

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
