# -*- coding: utf-8 -*-
"""t08 单文件校验：DataReliabilityService（Kafka/Redis/Mapper 全用进程内替身）。"""
import logging
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.alibaba.fastjson2.JSON import JSON  # noqa: E402
from com.ruoyi.base.mapper.KafkaMessageRecordMapper import KafkaMessageRecordMapper  # noqa: E402
from com.ruoyi.base.service.impl.DataReliabilityService import (  # noqa: E402
    DataReliabilityService,
    MessageMeta,
    MessageStatus,
    ReliableMessageWrapper,
)
from java.lang.String import javaStringHashCode  # noqa: E402
from java.util.concurrent.TimeUnit import TimeUnit  # noqa: E402
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate  # noqa: E402
from org.springframework.kafka.core.KafkaTemplate import KafkaTemplate  # noqa: E402
from org.springframework.scheduling.annotation.Scheduled import _resolveMillis  # noqa: E402

failures = []
total = [0]


def check(label, actual, expected):
    total[0] += 1
    if actual != expected:
        failures.append("%s: expected=%r actual=%r" % (label, expected, actual))


def check_true(label, actual):
    check(label, bool(actual), True)


# 采集日志（Java 侧是 slf4j，Python 用 logging）
records = []


class _Capture(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


app_logger = logging.getLogger("com.ruoyi.base.service.impl.DataReliabilityService")
app_logger.setLevel(logging.DEBUG)
app_logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


def wait_until(predicate, timeout=6.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ---------------------------------------------------------------- 0) 枚举与注解
check("enum name()", MessageStatus.SENT.name(), "SENT")
check("enum str()", str(MessageStatus.PENDING), "PENDING")
try:
    MessageStatus.valueOf("NOPE")
    check("enum valueOf invalid", "no-exception", "ValueError")
except ValueError:
    check("enum valueOf invalid", "ValueError", "ValueError")
check("enum values()", [item.name() for item in MessageStatus.values()],
      ["PENDING", "SENT", "CONFIRMED", "DEAD"])

check("fixedRateString placeholder", _resolveMillis("${reliability.compensation-interval-seconds:60}000", "x"), 60000)
check("fixedRate int", _resolveMillis(300000, "x"), 300000)
check("fixedRate numeric string", _resolveMillis("5000", "x"), 5000)

# ---------------------------------------------------------------- 1) 正常发送流程
redis = RedisTemplate()
mapper = KafkaMessageRecordMapper()
kafka = KafkaTemplate()
svc = DataReliabilityService(kafkaTemplate=kafka, kafkaMessageRecordMapper=mapper,
                             redisTemplate=redis)
check("config messageTimeoutMs", svc.messageTimeoutMs, 30000)
check("config maxRetryCount", svc.maxRetryCount, 5)
check_true("executors created", svc.retryExecutor is not None and svc.compensationExecutor is not None)

payload = {"carNo": "赣A1", "speed": 88}
mid = svc.sendReliableMessage(payload, "data-1", "topic.snapshot")

check("kafka sent once", len(kafka.sentRecords()), 1)
check("kafka key is dataId", kafka.sentRecords()[0][1], "data-1")
content = redis.opsForValue().get(svc.MSG_CONTENT_PREFIX + mid)
check_true("content cached", content is not None)
wrapper = JSON.parseObject(content, ReliableMessageWrapper)
check("wrapper messageId", wrapper.getMessageId(), mid)
check("wrapper dataId", wrapper.getDataId(), "data-1")
check("wrapper operationType", wrapper.getOperationType(), "INSERT")
check("wrapper version", wrapper.getVersion(), 1)
check("wrapper data passthrough", wrapper.getData(), payload)
check_true("wrapper json camelCase", '"operationType":"INSERT"' in content)
check("checksum", wrapper.getChecksum(), svc.calculateChecksum(payload))
check("checksum is md5", len(svc.calculateChecksum(payload)), 32)

# Kafka ack 已同步回调：状态 SENT，offset 0
meta = svc.pendingMessages.get(mid)
check("meta status SENT", meta.getStatus(), MessageStatus.SENT)
check("meta kafkaOffset", meta.getKafkaOffset(), 0)
check("redis status SENT", redis.opsForValue().get(svc.MSG_STATUS_PREFIX + mid), "SENT")

# messageId 形如 millis-nano-uuid8-hash；
# 【注意】Java 的 String.hashCode() 可能为负，拼接后会多出一个 '-'（与 Java 输出完全一致），
# 因此不能用 split 后段数固定为 4 来断言。
parts = mid.split("-")
check("messageId first part is millis", len(parts[0]), 13)
check("messageId tail hash", mid.endswith("-" + str(javaStringHashCode("data-1"))), True)

# ---------------------------------------------------------------- 2) 消费端确认
svc.confirmConsumption(mid, "ES")
check("redis status CONFIRMED", redis.opsForValue().get(svc.MSG_STATUS_PREFIX + mid), "CONFIRMED")
check("meta removed", svc.pendingMessages.containsKey(mid), False)
latency_keys = [key for key in redis.keys(svc.LATENCY_STATS_PREFIX + "*")]
check("latency key", len(latency_keys), 1)
latency_values = redis.opsForList().range(list(latency_keys)[0], 0, -1)
check("latency recorded once", len(latency_values), 1)
check_true("latency non-negative", latency_values[0] >= 0)

# 幂等
check("isMessageProcessed after confirm", svc.isMessageProcessed(mid), True)
svc.markMessageProcessed("mid-idem")
check("markMessageProcessed", svc.isMessageProcessed("mid-idem"), True)
check("unknown not processed", svc.isMessageProcessed("mid-none"), False)

# ---------------------------------------------------------------- 3) 校验和
check("verifyChecksum ok", svc.verifyChecksum(payload, svc.calculateChecksum(payload)), True)
check("verifyChecksum bad", svc.verifyChecksum(payload, "deadbeef"), False)
check_true("verify checksum warn logged", logged("数据完整性校验失败"))

# ---------------------------------------------------------------- 4) 设备心跳 / 离线检测
svc.updateDeviceHeartbeat("DEV1")
check("heartbeat ttl", redis.getExpire(svc.DEVICE_HEARTBEAT_PREFIX + "DEV1", TimeUnit.SECONDS) > 0, True)
old_key = svc.DEVICE_HEARTBEAT_PREFIX + "OLD"
redis.opsForValue().set(old_key, int(time.time() * 1000) - 10 * 60 * 1000, 5, TimeUnit.MINUTES)
svc.checkOfflineDevices()
check_true("offline alert logged", logged("设备离线: deviceId=OLD"))
check("checkOfflineDevices scheduled", svc.checkOfflineDevices.__scheduled__["fixedRate"], 300000)
check("compensation scheduled string",
      svc.compensationTask.__scheduled__["fixedRateString"],
      "${reliability.compensation-interval-seconds:60}000")

# ---------------------------------------------------------------- 5) 发送失败 -> 指数退避重试
redis2, mapper2, kafka2 = RedisTemplate(), KafkaMessageRecordMapper(), KafkaTemplate()
svc2 = DataReliabilityService(kafkaTemplate=kafka2, kafkaMessageRecordMapper=mapper2,
                              redisTemplate=redis2)
kafka2.fail_next = RuntimeError("kafka down")
mid2 = svc2.sendReliableMessage({"carNo": "赣A2"}, "data-2", "topic.snapshot")
meta2 = svc2.pendingMessages.get(mid2)
check("retryCount after failure", meta2.getRetryCount(), 1)
check("no record on first failure", len(kafka2.sentRecords()), 0)
check_true("send failure logged", logged("消息发送失败"))
# 退避 2^1*1000 = 2000ms 后重发成功，回调把状态改为 SENT
check_true("retry resend", wait_until(lambda: len(kafka2.sentRecords()) == 1))
check("retry ack status", meta2.getStatus(), MessageStatus.SENT)

# ---------------------------------------------------------------- 6) 超限 -> 死信
os.environ["RELIABILITY_MAX_RETRY_COUNT"] = "1"
try:
    redis3, mapper3, kafka3 = RedisTemplate(), KafkaMessageRecordMapper(), KafkaTemplate()
    svc3 = DataReliabilityService(kafkaTemplate=kafka3, kafkaMessageRecordMapper=mapper3,
                                  redisTemplate=redis3)
    check("maxRetryCount override", svc3.maxRetryCount, 1)
    kafka3.always_fail = True
    mid3 = svc3.sendReliableMessage({"carNo": "赣A3"}, "data-3", "topic.snapshot")
    check("dead letter removed from pending", svc3.pendingMessages.containsKey(mid3), False)
    check("dead letter redis status", redis3.opsForValue().get(svc3.MSG_STATUS_PREFIX + mid3), "DEAD")
    dead_rows = mapper3.selectList()
    check("dead letter row count", len(dead_rows), 1)
    check("dead letter row status", dead_rows[0].status, 3)
    check("dead letter row retryCount", dead_rows[0].retry_count, 1)
    check("dead letter row dataId", dead_rows[0].data_id, "data-3")
    check_true("dead letter row messageJson", dead_rows[0].message_json is not None)
    check_true("dead letter alert", logged("[告警] [DEAD_LETTER]"))
    kafka3.always_fail = False
finally:
    os.environ.pop("RELIABILITY_MAX_RETRY_COUNT", None)

# ---------------------------------------------------------------- 7) 超时队列 + 补偿任务
redis4 = RedisTemplate()
svc4 = DataReliabilityService(kafkaTemplate=KafkaTemplate(),
                              kafkaMessageRecordMapper=KafkaMessageRecordMapper(),
                              redisTemplate=redis4)
svc4.handleMessageTimeout("mid-timeout", None)
check("timeout queue push", redis4.opsForList().size(svc4.TIMEOUT_QUEUE), 1)
check_true("timeout alert with null status", logged("状态: null"))

# 先清空超时队列，避免上面那条无状态的消息触发 switch(null) NPE 中断本轮
redis4.delete(svc4.TIMEOUT_QUEUE)

# DEAD / CONFIRMED 走空分支（switch 的 case 命中，不报错）
redis4.opsForValue().set(svc4.MSG_STATUS_PREFIX + "mid-dead", MessageStatus.DEAD.name())
redis4.opsForValue().set(svc4.MSG_STATUS_PREFIX + "mid-conf", MessageStatus.CONFIRMED.name())
redis4.opsForList().rightPush(svc4.TIMEOUT_QUEUE, "mid-dead")
redis4.opsForList().rightPush(svc4.TIMEOUT_QUEUE, "mid-conf")
svc4.compensationTask()
check_true("compensation drained queue",
           wait_until(lambda: redis4.opsForList().size(svc4.TIMEOUT_QUEUE) == 0, timeout=3.0))
check("no exception for known statuses", logged("补偿任务异常"), False)

# ghost 无状态 -> switch(null) NPE（被外层 catch）：该条先被 LREM，其余保留
redis4.opsForList().rightPush(svc4.TIMEOUT_QUEUE, "ghost")
redis4.opsForList().rightPush(svc4.TIMEOUT_QUEUE, "after-ghost")
svc4.compensationTask()
check_true("ghost removed before NPE",
           wait_until(lambda: redis4.opsForList().index(svc4.TIMEOUT_QUEUE, 0) == "after-ghost", timeout=3.0))
check_true("compensation NPE logged", wait_until(lambda: logged("补偿任务异常"), timeout=3.0))

# ---------------------------------------------------------------- 8) MessageMeta 默认值 / setter
meta_default = MessageMeta()
check("meta default offset", meta_default.kafka_offset, -1)
check("meta default retry", meta_default.retry_count, 0)
meta_default.incrementRetryCount()
check("meta increment", meta_default.getRetryCount(), 1)
meta_default.setMessageId("x")
check("meta setter chain", meta_default.getMessageId(), "x")

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
print("RELIABILITY SMOKE OK" if not failures else "RELIABILITY SMOKE FAILED")
