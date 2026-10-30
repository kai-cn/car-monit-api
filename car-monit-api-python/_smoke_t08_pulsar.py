# -*- coding: utf-8 -*-
"""t08 单文件校验：PulsarProducerService（内存 Mapper + Pulsar 替身）。"""
import json
import logging
import os
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.domain.PulsarMessageRecord import PulsarMessageRecord  # noqa: E402
from com.ruoyi.base.mapper.PulsarMessageRecordMapper import PulsarMessageRecordMapper  # noqa: E402
from com.ruoyi.base.service.impl.PulsarProducerService import (  # noqa: E402
    PulsarProducerService,
    _messageOf,
)
from org.apache.pulsar.client.api.Producer import Producer  # noqa: E402

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


app_logger = logging.getLogger("com.ruoyi.base.service.impl.PulsarProducerService")
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


def rows_of(mapper, data_id):
    return mapper.selectWhere(lambda r: r.data_id == data_id)


# ---------------------------------------------------------------- 0) 构造与配置
mapper1 = PulsarMessageRecordMapper()
producer1 = Producer()
svc1 = PulsarProducerService(snapshotFlowProducer=producer1,
                            pulsarMessageRecordMapper=mapper1)
# application.yml: spring.pulsar.topic / spring.pulsar.max-retry-count
check("defaultTopic", svc1.defaultTopic,
      "persistent://public/default/ods-rt-szdn-snapshot-flow")
check("maxRetryCount", svc1.maxRetryCount, 10)
check_true("retryExecutor created", svc1.retryExecutor is not None)
check_true("producer healthy", svc1.isProducerHealthy())
check("producer topic bound", producer1.getTopic(), "persistent://public/default/default")

# ---------------------------------------------------------------- 1) 成功发送
data = OdsRtSzdnSnapshotFlowAddcode()
data.setBigId("D1")
check("sendSnapshotFlowData returns dataId", svc1.sendSnapshotFlowData(data, "D1"), "D1")

row = rows_of(mapper1, "D1")[0]
check("record topic", row.getTopic(), svc1.defaultTopic)
check("record status after ack", row.getStatus(), 1)
check("record retryCount", row.getRetryCount(), 0)
check_true("record sendTime set", row.getSendTime() is not None)
check_true("record id is uuid32", len(row.getId()) == 32 and "-" not in row.getId())
# MessageId.toString() = ledgerId:entryId:partitionIndex:batchIndex
check("record messageId", row.getMessageId(), "0:1:-1:-1")

payload = json.loads(row.getMessageJson())
check("message operationType", payload["operationType"], "INSERT")
check("message data serialized camelCase", payload["data"]["bigId"], "D1")
check("message data has no snake_case key", "big_id" in payload["data"], False)
check("producer key is dataId", producer1.sentMessages()[0][1], "D1")
check_true("send success logged", logged("发送成功: dataId=D1, messageId=0:1:-1:-1"))

# ---------------------------------------------------------------- 2) 发送失败：截断 + 累加
mapper2 = PulsarMessageRecordMapper()
producer2 = Producer()
svc2 = PulsarProducerService(snapshotFlowProducer=producer2,
                             pulsarMessageRecordMapper=mapper2)
producer2.fail_next = RuntimeError("E" * 600)
check("send failed still returns dataId", svc2.sendSnapshotFlowData(data, "D2"), "D2")

failed_row = rows_of(mapper2, "D2")[0]
check("failed status", failed_row.getStatus(), 2)
check("failed retryCount", failed_row.getRetryCount(), 1)
check("failed errorMsg length capped", len(failed_row.getErrorMsg()), 500)
check("failed errorMsg content", failed_row.getErrorMsg(), "E" * 500)
check_true("failed sendTime empty", failed_row.getSendTime() is None)
check("producer healthy after failure", svc2.isProducerHealthy(), True)
check_true("send failure logged", logged("发送失败: dataId=D2"))

# ---------------------------------------------------------------- 3) 内部异常被 catch
original_send = svc2.sendMessage


def _boom(record):
    raise RuntimeError("mapper unavailable")


svc2.sendMessage = _boom
check("exception branch returns dataId", svc2.sendSnapshotFlowData(data, "D3"), "D3")
check("exception branch still inserted", rows_of(mapper2, "D3")[0].getStatus(), 0)
check_true("exception branch logged", logged("发送异常: dataId=D3"))
svc2.sendMessage = original_send

# ---------------------------------------------------------------- 4) 后台重试任务
mapper3 = PulsarMessageRecordMapper()
pending = PulsarMessageRecord()
pending.setId("rec-pending")
pending.setDataId("R1")
pending.setTopic("persistent://public/default/ods-rt-szdn-snapshot-flow")
pending.setMessageJson('{"operationType":"INSERT","data":{"bigId":"R1"}}')
pending.setStatus(0)
pending.setRetryCount(0)
pending.setCreateTime(datetime.now())
mapper3.insert(pending)

exhausted = PulsarMessageRecord()
exhausted.setId("rec-exhausted")
exhausted.setDataId("R2")
exhausted.setTopic("persistent://public/default/ods-rt-szdn-snapshot-flow")
exhausted.setMessageJson("{}")
exhausted.setStatus(2)
exhausted.setRetryCount(10)          # 已达 maxRetryCount，不应再被扫描
exhausted.setCreateTime(datetime.now())
mapper3.insert(exhausted)

producer3 = Producer()
svc3 = PulsarProducerService(snapshotFlowProducer=producer3,
                             pulsarMessageRecordMapper=mapper3)
check_true("retry task picks pending record",
           wait_until(lambda: rows_of(mapper3, "R1")[0].getStatus() == 1))
check("retry task marks messageId", rows_of(mapper3, "R1")[0].getMessageId(), "0:1:-1:-1")
check_true("retry task logged batch", logged("开始重试 1 条消息"))
check("exhausted record untouched", rows_of(mapper3, "R2")[0].getStatus(), 2)
check("exhausted retryCount untouched", rows_of(mapper3, "R2")[0].getRetryCount(), 10)

# ---------------------------------------------------------------- 5) destroy / 健康检查
svc3.destroy()
check("producer closed", producer3.isConnected(), False)
check("healthy false after destroy", svc3.isProducerHealthy(), False)
check("executor shutdown", svc3.retryExecutor.isShutdown(), True)
check_true("destroy logged", logged("正在关闭..."))

# ---------------------------------------------------------------- 6) 默认依赖 + getMessage 语义
svc4 = PulsarProducerService()
check("default mapper type", isinstance(svc4.pulsarMessageRecordMapper, PulsarMessageRecordMapper), True)
check("default producer topic", svc4.snapshotFlowProducer.getTopic(), svc4.defaultTopic)
check("_messageOf message", _messageOf(RuntimeError("boom")), "boom")
check("_messageOf empty", _messageOf(RuntimeError()), "")
svc4.destroy()

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
