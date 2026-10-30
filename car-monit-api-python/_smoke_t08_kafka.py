# -*- coding: utf-8 -*-
"""t08 单文件校验：KafkaProducerService（KafkaTemplate 替身 + 内存 Mapper + 桩服务）。"""
import logging
import os
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.alibaba.fastjson2.JSONObject import JSONObject  # noqa: E402
from com.ruoyi.base.domain.KafkaMessageRecord import KafkaMessageRecord  # noqa: E402
from com.ruoyi.base.mapper.KafkaMessageRecordMapper import KafkaMessageRecordMapper  # noqa: E402
from com.ruoyi.base.service.impl.DataLossDetectionService import DataLossDetectionService  # noqa: E402
from com.ruoyi.base.service.impl.DataReliabilityService import DataReliabilityService  # noqa: E402
from com.ruoyi.base.service.impl.DelayMonitoringService import DelayMonitoringService  # noqa: E402
from com.ruoyi.base.service.impl.KafkaProducerService import KafkaProducerService  # noqa: E402
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate, defaultKafkaTemplate  # noqa: E402

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


app_logger = logging.getLogger("com.ruoyi.base.service.impl.KafkaProducerService")
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


class _StubReliability(object):
    """替身：只记录调用（等价 Spring 里注入的 DataReliabilityService 单例）。"""

    def __init__(self, message_id="mid-1"):
        self.messageId = message_id
        self.sent = []
        self.acks = []
        self.failures = []
        self.raise_on_send = False

    def sendReliableMessage(self, data, dataId, topic):
        if self.raise_on_send:
            raise RuntimeError("可靠性服务不可用")
        self.sent.append((data, dataId, topic))
        return self.messageId

    def handleKafkaAck(self, messageId, offset):
        self.acks.append((messageId, offset))

    def handleSendFailure(self, messageId, error):
        self.failures.append((messageId, error))


class _StubLoss(object):
    def __init__(self):
        self.reported = []

    def recordReportedMessage(self, messageId, deviceId, timestamp):
        self.reported.append((messageId, deviceId, timestamp))


class _StubDelay(object):
    def __init__(self):
        self.produced = []

    def recordMessageProduceTime(self, messageId):
        self.produced.append(messageId)


def new_record(record_id, data_id, topic="t"):
    record = KafkaMessageRecord()
    record.setId(record_id)
    record.setDataId(data_id)
    record.setTopic(topic)
    record.setMessageJson('{"operationType":"INSERT","data":{"bigId":"%s"}}' % data_id)
    record.setStatus(0)
    record.setRetryCount(0)
    record.setCreateTime(datetime.now())
    return record


# ---------------------------------------------------------------- 0) 构造与配置
template = KafkaTemplate()
mapper1 = KafkaMessageRecordMapper()
rel = _StubReliability()
loss = _StubLoss()
delay = _StubDelay()
svc = KafkaProducerService(kafkaTemplate=template, kafkaMessageRecordMapper=mapper1,
                           reliabilityService=rel, lossDetectionService=loss,
                           delayMonitoringService=delay)
check("snapshotFlowTopic", svc.snapshotFlowTopic, "ods-rt-szdn-snapshot-flow")
check("maxRetryCount", svc.maxRetryCount, 10)
check_true("retryExecutor created", svc.retryExecutor is not None)

# ---------------------------------------------------------------- 1) sendSnapshotFlowData 三步协作
payload = JSONObject()
payload.put("bigId", "D1")
payload.put("deviceId", "DEV-A")
start_ms = int(time.time() * 1000)
check("sendSnapshotFlowData returns messageId", svc.sendSnapshotFlowData(payload, "D1"), "mid-1")

check("delay produce recorded", delay.produced, ["D1"])
check("reliability called once", len(rel.sent), 1)
check("reliability dataId", rel.sent[0][1], "D1")
check("reliability topic", rel.sent[0][2], "ods-rt-szdn-snapshot-flow")
check("reliability data passthrough", rel.sent[0][0] is payload, True)
check("loss reported messageId", loss.reported[0][0], "mid-1")
check("loss reported deviceId", loss.reported[0][1], "DEV-A")
check_true("loss reported millis", isinstance(loss.reported[0][2], int)
           and loss.reported[0][2] >= start_ms)
check_true("send logged", logged("发送消息: dataId=D1, messageId=mid-1"))

# ---------------------------------------------------------------- 2) sendMessage 成功回调
success_record = new_record("r1", "D1")
mapper1.insert(success_record)
svc.sendMessage(success_record)
# 【Java→Python】BaseMapper.insert 存入的是 deepcopy（模拟数据库往返），
# 回调更新的是“表里的行”，因此断言必须回表查询，不能看原对象。
success_row = mapper1.selectById("r1")
check("success status", success_row.getStatus(), 1)
check("success retryCount", success_row.getRetryCount(), 0)
check_true("success sendTime set", success_row.getSendTime() is not None)
check("template topic", template.sentRecords()[-1][0], "t")
check("template key is dataId", template.sentRecords()[-1][1], "D1")
check("template value is parsed json", dict(template.sentRecords()[-1][2]),
      {"operationType": "INSERT", "data": {"bigId": "D1"}})
# 原代码传的是 dataId（不是 messageId），并且 offset 从 0 开始
check("ack uses dataId", rel.acks, [("D1", 0)])
check_true("success logged", logged("消息发送成功: dataId=D1, offset=0"))

# ---------------------------------------------------------------- 3) sendMessage 失败回调
failure_record = new_record("r2", "D2")
mapper1.insert(failure_record)
template.fail_next = RuntimeError("boom-send")
svc.sendMessage(failure_record)
failure_row = mapper1.selectById("r2")
check("failure status", failure_row.getStatus(), 2)
check("failure retryCount", failure_row.getRetryCount(), 1)
check("failure errorMsg", failure_row.getErrorMsg(), "boom-send")
check_true("failure sendTime empty", failure_row.getSendTime() is None)
check("failure notified", rel.failures, [("D2", "boom-send")])
check_true("failure logged", logged("消息发送失败: dataId=D2, error=boom-send"))

# ---------------------------------------------------------------- 4) 后台重试任务
template2 = KafkaTemplate()
mapper2 = KafkaMessageRecordMapper()
rel2 = _StubReliability(message_id="mid-r")
mapper2.insert(new_record("rec-pending", "R1"))

exhausted = new_record("rec-exhausted", "R2")
exhausted.setStatus(2)
exhausted.setRetryCount(10)          # 已达 maxRetryCount，不应被扫描
mapper2.insert(exhausted)

svc2 = KafkaProducerService(kafkaTemplate=template2, kafkaMessageRecordMapper=mapper2,
                            reliabilityService=rel2, lossDetectionService=_StubLoss(),
                            delayMonitoringService=_StubDelay())
check_true("retry task resends pending",
           wait_until(lambda: mapper2.selectById("rec-pending").getStatus() == 1))
check("retry task ack", rel2.acks, [("R1", 0)])
check("retry task messageId unused", rel2.messageId, "mid-r")
check("exhausted untouched", mapper2.selectById("rec-exhausted").getStatus(), 2)
check("exhausted retryCount untouched", mapper2.selectById("rec-exhausted").getRetryCount(), 10)
check_true("retry batch logged", logged("开始重试 1 条消息"))

# ---------------------------------------------------------------- 5) extractDeviceId / extractDataId
check("deviceId", svc.extractDeviceId(JSONObject({"deviceId": "DEV-A"})), "DEV-A")
check("deviceid numeric", svc.extractDeviceId(JSONObject({"deviceid": 123})), "123")
check("gantrycode fallback", svc.extractDeviceId(JSONObject({"gantrycode": "G-01"})), "G-01")
check("device missing", svc.extractDeviceId(JSONObject({})), "unknown")
# 普通 dict 不是 JSONObject（与 Java 的 instanceof 一致）
check("plain dict not JSONObject", svc.extractDeviceId({"deviceId": "DEV-A"}), "unknown")

check("dataId bigId", svc.extractDataId(JSONObject({"bigId": "B1"})), "B1")
check("dataId priority", svc.extractDataId(JSONObject({"id": "I1", "bigId": "B1"})), "B1")
check("dataId id numeric", svc.extractDataId(JSONObject({"id": 7})), "7")
check("dataId uuid", svc.extractDataId(JSONObject({"uuid": "u-1"})), "u-1")
check("dataId missing", svc.extractDataId(JSONObject({})), None)
check("dataId plain dict", svc.extractDataId({"bigId": "B1"}), None)

# ---------------------------------------------------------------- 6) 批量发送
rel.sent.clear()
batch = [JSONObject({"bigId": "B1"}), JSONObject({}), "not-a-json-object"]
svc.sendBatchSnapshotFlowData(batch)
check("batch sent only valid", [item[1] for item in rel.sent], ["B1"])
check_true("batch count logged", logged("批量发送消息: count=3"))

rel.sent.clear()
rel.raise_on_send = True
svc.sendBatchSnapshotFlowData([JSONObject({"bigId": "B2"})])
check("batch sends nothing on error", rel.sent, [])
check_true("batch error logged", logged("批量发送异常"))
rel.raise_on_send = False

# ---------------------------------------------------------------- 7) 缺省依赖的 Spring 单例关系
svc3 = KafkaProducerService()
check("default reliability type", isinstance(svc3.reliabilityService, DataReliabilityService), True)
check("default loss type", isinstance(svc3.lossDetectionService, DataLossDetectionService), True)
check("default delay type", isinstance(svc3.delayMonitoringService, DelayMonitoringService), True)
check("default template singleton", svc3.kafkaTemplate is defaultKafkaTemplate(), True)
# Spring 里 reliabilityService 与本服务共享同一个 KafkaTemplate / Mapper Bean
check("reliability shares template",
      svc3.reliabilityService.kafkaTemplate is svc3.kafkaTemplate, True)
check("reliability shares mapper",
      svc3.reliabilityService.kafkaMessageRecordMapper is svc3.kafkaMessageRecordMapper, True)
check("loss shares reliability",
      svc3.lossDetectionService.reliabilityService is svc3.reliabilityService, True)

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
