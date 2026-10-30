# -*- coding: utf-8 -*-
"""t08 单文件校验：SnapshotFlowPulsarConsumer + DebeziumReadonlyPulsarConsumer。"""
import json
import logging
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "pro-base-common", "src", "main", "java"))
sys.path.insert(0, os.path.join(BASE, "pro-business-api", "src", "main", "java"))

from com.alibaba.fastjson2.JSONObject import JSONObject  # noqa: E402
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper  # noqa: E402
from com.ruoyi.base.service.IEsService import IEsService  # noqa: E402
from com.ruoyi.base.service.impl.DebeziumReadonlyPulsarConsumer import DebeziumReadonlyPulsarConsumer  # noqa: E402
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import OdsRtSzdnSnapshotFlowAddcodeServiceImpl  # noqa: E402
from com.ruoyi.base.service.impl.SnapshotFlowPulsarConsumer import SnapshotFlowPulsarConsumer  # noqa: E402
from java.util.concurrent.TimeUnit import TimeUnit  # noqa: E402
from org.apache.pulsar.client.api.Consumer import Consumer  # noqa: E402
from org.springframework.data.redis.core.StringRedisTemplate import StringRedisTemplate  # noqa: E402

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


for logger_name in ("com.ruoyi.base.service.impl.SnapshotFlowPulsarConsumer",
                    "com.ruoyi.base.service.impl.DebeziumReadonlyPulsarConsumer"):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_Capture())


def logged(fragment):
    return any(fragment in message for message in records)


class _StubEs(IEsService):
    """替身：IEsService 在 Java 工程里没有实现类，测试用桩验证调用顺序与失败分支。"""

    def __init__(self):
        self.saved = []
        self.deleted = []
        self.fail = False

    def saveSnapshotFlow(self, flowData):
        if self.fail:
            return False
        self.saved.append(flowData.getBigId())
        return True

    def deleteSnapshotFlow(self, dataId):
        if self.fail:
            return False
        self.deleted.append(dataId)
        return True


def message_of(operation, data_id, **extra):
    body = {"operationType": operation, "data": {"bigId": data_id}}
    body.update(extra)
    return json.dumps(body, ensure_ascii=False)


def _obj(mapping):
    return JSONObject(mapping)


# ================================================================ 主消费者
mapper = OdsRtSzdnSnapshotFlowAddcodeMapper()
flowService = OdsRtSzdnSnapshotFlowAddcodeServiceImpl(
    odsRtSzdnSnapshotFlowAddcodeMapper=mapper)
es = _StubEs()
redis = StringRedisTemplate()
consumer = Consumer(topic="persistent://public/default/ods-rt-szdn-snapshot-flow",
                    subscription_name="ods-rt-szdn-snapshot-flow-sub")
svc = SnapshotFlowPulsarConsumer(snapshotFlowConsumer=consumer,
                                 snapshotFlowService=flowService,
                                 esService=es, redisTemplate=redis)

# ---------------------------------------------------------------- 0) 构造与配置
check("idempotent prefix", svc.IDEMPOTENT_KEY_PREFIX, "pulsar:msg:processed:")
# application.yml 显式配置了 spring.pulsar.idempotent-ttl-seconds=86400
check("idempotent ttl", svc.idempotentTtlSeconds, 86400)
check_true("consumer executor created", svc.consumerExecutor is not None)
check("consumer topic", consumer.getTopic(), "persistent://public/default/ods-rt-szdn-snapshot-flow")
check("consumer subscription", consumer.getSubscription(), "ods-rt-szdn-snapshot-flow-sub")

# ---------------------------------------------------------------- 1) INSERT 全链路
consumer.enqueue("D1", message_of("INSERT", "D1"))
check_true("insert acked", wait_until(lambda: len(consumer.ackedMessages()) == 1))
inserted = mapper.selectById("D1")
check_true("insert writes mysql", inserted is not None)
check("insert writes es", es.saved, ["D1"])
check_true("insert logged", logged("INSERT 操作成功: dataId=D1"))
check_true("ack logged with messageId", logged("消息处理成功并确认: dataId=D1, messageId=0:1:-1:-1"))

idem_key = svc.IDEMPOTENT_KEY_PREFIX + "D1"
check("idempotent key written", redis.hasKey(idem_key), True)
check_true("idempotent ttl positive", redis.getExpire(idem_key, TimeUnit.SECONDS) > 0)
check_true("idempotent value is millis", str(redis.opsForValue().get(idem_key)).isdigit())
check("no negative ack yet", len(consumer.negativeAckedMessages()), 0)

# ---------------------------------------------------------------- 2) 幂等去重（同 dataId）
consumer.enqueue("D1", message_of("INSERT", "D1"))
check_true("duplicate acked", wait_until(lambda: len(consumer.ackedMessages()) == 2))
check_true("duplicate skipped", logged("消息已处理（幂等去重）: dataId=D1"))
check("duplicate not saved to es", es.saved, ["D1"])

# ---------------------------------------------------------------- 3) 缺字段消息：确认丢弃
consumer.enqueue("X2", json.dumps({"data": {"bigId": "X2"}}))
check_true("missing field acked", wait_until(lambda: len(consumer.ackedMessages()) == 3))
check_true("missing field logged", logged("消息缺少必要字段"))

# ---------------------------------------------------------------- 4) UPDATE：存在 → updateById；不存在 → saveOrUpdate
existing = OdsRtSzdnSnapshotFlowAddcode()
existing.setBigId("U2")
mapper.insert(existing)
es.saved.clear()
consumer.enqueue("U2", message_of("UPDATE", "U2", data={"bigId": "U2",
                                                         "snapshottime": "2026-10-21 10:00:00"}))
check_true("update acked", wait_until(lambda: len(consumer.ackedMessages()) == 4))
check_true("update writes es", wait_until(lambda: es.saved == ["U2"]))
check_true("update logged", logged("UPDATE 操作成功: dataId=U2"))
check_true("update row has snapshot time", mapper.selectById("U2").getSnapshottime() is not None)

consumer.enqueue("U3", message_of("UPDATE", "U3"))
check_true("update missing acked", wait_until(lambda: len(consumer.ackedMessages()) == 5))
check_true("update fallback logged", logged("UPDATE MySQL 失败（记录可能不存在）: dataId=U3"))
check_true("update fallback inserts", mapper.selectById("U3") is not None)

# ---------------------------------------------------------------- 5) DELETE
delete_row = OdsRtSzdnSnapshotFlowAddcode()
delete_row.setBigId("D3")
mapper.insert(delete_row)
es.deleted.clear()
consumer.enqueue("D3", message_of("DELETE", "D3"))
check_true("delete acked", wait_until(lambda: len(consumer.ackedMessages()) == 6))
check_true("delete removes mysql", mapper.selectById("D3") is None)
check("delete writes es", es.deleted, ["D3"])
check_true("delete logged", logged("DELETE 操作完成: dataId=D3"))

# ---------------------------------------------------------------- 6) 直接调用 processMessage 的分支
# 非法 JSON：解析抛异常 → false（走重投）
check("malformed json returns false", svc.processMessage("BAD", "not-json"), False)
check_true("malformed logged", logged("processMessage 异常: dataId=BAD"))
# 未知操作类型 → true（确认丢弃）
check("unknown op returns true", svc.processMessage("K1", message_of("PATCH", "K1")), True)
check_true("unknown op logged", logged("未知操作类型"))
# ES 失败 → false（走重投）
es.fail = True
check("es failure returns false", svc.processMessage("E1", message_of("INSERT", "E1")), False)
check_true("es failure logged", logged("写入 Elasticsearch 失败: dataId=E1"))
es.fail = False
# MySQL 已写入但 ES 失败：数据留在 MySQL（下次重投会命中幂等键 → 实际不会再写 ES，属原文设计）
check_true("es failure row in mysql", mapper.selectById("E1") is not None)

# ---------------------------------------------------------------- 7) 主消费者销毁
svc.destroy()
check("consumer closed", consumer.isConnected(), False)
check("consumer executor shutdown", svc.consumerExecutor.isShutdown(), True)
check_true("destroy logged", logged("[Pulsar快照消费者] Consumer 已关闭"))

# ================================================================ CDC 消费者
cdc_mapper = OdsRtSzdnSnapshotFlowAddcodeMapper()
cdc_service = OdsRtSzdnSnapshotFlowAddcodeServiceImpl(
    odsRtSzdnSnapshotFlowAddcodeMapper=cdc_mapper)
cdc_es = _StubEs()
cdc_redis = StringRedisTemplate()
cdc_consumer = Consumer(topic="persistent://public/default/ods-rt-szdn-snapshot-flow",
                        subscription_name="debezium-readonly-sub")
cdc = DebeziumReadonlyPulsarConsumer(debeziumReadonlyConsumer=cdc_consumer,
                                     snapshotFlowService=cdc_service,
                                     esService=cdc_es, redisTemplate=cdc_redis)

check("cdc prefix", cdc.CDC_IDEMPOTENT_KEY_PREFIX, "pulsar:cdc:processed:")
# 【注意】原文默认 604800，但 application.yml 覆盖为 86400，与主消费者共用同一配置项
check("cdc ttl from yml", cdc.idempotentTtlSeconds, 86400)
check("cdc subscription", cdc_consumer.getSubscription(), "debezium-readonly-sub")

# ---------------------------------------------------------------- 8) extractLsn 优先级
check("lsn from lsn", cdc.extractLsn(_obj({"lsn": "100"}), "D"), "100")
check("lsn numeric zero", cdc.extractLsn(_obj({"xid": 0}), "D"), "0")
check("lsn from txId", cdc.extractLsn(_obj({"txId": "t-1"}), "D"), "t-1")
check("lsn empty falls through", cdc.extractLsn(_obj({"lsn": "", "pos": "P1"}), "D"), "P1")
check("lsn all empty falls back", cdc.extractLsn(_obj({"lsn": ""}), "D"), "D")
check("lsn change_lsn", cdc.extractLsn(_obj({"change_lsn": "C3"}), "D"), "C3")
check("lsn scn", cdc.extractLsn(_obj({"scn": 42}), "D"), "42")
check("lsn no source", cdc.extractLsn(None, "D"), "D")

# ---------------------------------------------------------------- 9) CDC 消息分发（循环）
cdc_consumer.enqueue("C1", message_of("INSERT", "C1", source={"lsn": "L1"}))
check_true("cdc insert acked", wait_until(lambda: len(cdc_consumer.ackedMessages()) == 1))
check_true("cdc insert writes mysql", cdc_mapper.selectById("C1") is not None)
check("cdc insert writes es", cdc_es.saved, ["C1"])
check("cdc idempotent key", cdc_redis.hasKey(cdc.CDC_IDEMPOTENT_KEY_PREFIX + "L1"), True)

# 同一 LSN、不同 dataId：CDC 去重按 LSN，C2 应被跳过
cdc_consumer.enqueue("C2", message_of("INSERT", "C2", source={"lsn": "L1"}))
check_true("cdc duplicate acked", wait_until(lambda: len(cdc_consumer.ackedMessages()) == 2))
check_true("cdc duplicate logged", logged("LSN 消息已处理（幂等去重）: lsn=L1, dataId=C2"))
check("cdc duplicate not in mysql", cdc_mapper.selectById("C2"), None)

# CREATE 与 INSERT 同分支
cdc_consumer.enqueue("C3", message_of("CREATE", "C3", source={"lsn": "L3"}))
check_true("cdc create acked", wait_until(lambda: len(cdc_consumer.ackedMessages()) == 3))
check_true("cdc create inserts", cdc_mapper.selectById("C3") is not None)

# DELETE：忽略返回值，不抛异常即成功
check("cdc delete missing returns true", cdc.handleDelete("NOPE"), True)

# ---------------------------------------------------------------- 10) CDC 直接调用分支
check("cdc malformed returns false", cdc.processMessage("BAD", "not-json", None), False)
check_true("cdc malformed logged", logged("[Pulsar-CDC消费者] processMessage 异常: dataId=BAD"))
check("cdc missing field returns true",
      cdc.processMessage("X9", json.dumps({"data": {"bigId": "X9"}}), None), True)
check_true("cdc missing field logged", logged("[Pulsar-CDC消费者] 消息缺少必要字段"))
cdc_es.fail = True
check("cdc es failure returns false",
      cdc.processMessage("CE1", message_of("INSERT", "CE1", source={"lsn": "LC9"}), None), False)
check_true("cdc es failure logged", logged("[Pulsar-CDC消费者] 写入 Elasticsearch 失败: dataId=CE1"))
cdc_es.fail = False

# ---------------------------------------------------------------- 11) CDC 销毁 + 替身语义
cdc.destroy()
check("cdc consumer closed", cdc_consumer.isConnected(), False)
check_true("cdc destroy logged", logged("[Pulsar-CDC消费者] Consumer 已关闭"))

lonely = Consumer()
try:
    lonely.receive(1, TimeUnit.MILLISECONDS)
    timeout_raised = False
except RuntimeError as error:
    timeout_raised = "TimeoutException" in str(error)
check("receive timeout raises", timeout_raised, True)
lonely.close()
try:
    lonely.receive()
    closed_raised = False
except RuntimeError as error:
    closed_raised = "Consumer 已关闭" in str(error)
check("receive after close raises", closed_raised, True)

print("checks:", total[0] - len(failures), "/", total[0])
for failure in failures:
    print("FAIL", failure)
