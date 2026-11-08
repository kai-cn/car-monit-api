# -*- coding: utf-8 -*-
"""t09e 冒烟测试：mq 包 6 个类 + ES/RabbitMQ/RocketMQ 框架替身。

运行：
    python refactor/_smoke_t09e.py

覆盖范围
1) 目录结构对照：com/ruoyi/mq 下 .java 与 .py 文件名集合一致（各 6 个）。
2) java.time.LocalDateTime 新增的 plusMonths / minusMonths / with* 系列。
3) ES 替身链路：RestClient 配置透传、index 版本、search 的 from/size、
   match/term/range/bool 的命中语义、集群不可用时的异常。
4) RabbitMQ 替身：Exchange / Queue（死信 + TTL）/ Binding（with_ 关键字规避）。
5) RocketMQ 替身：未 start 抛错、SEND_OK、失败注入。
6) ElasticsearchConfig / RabbitMqConfig / DataProcessService /
   RocketMqConsumer / RocketMqProducer / EsQueryService 的行为断言。

【注意】sys.path 的三个根目录必须都指向 refactor 内，否则会 import 到
原始 Java 目录（那里只有 .java，会抛 ModuleNotFoundError）。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------- 路径
_ROOT = os.path.dirname(os.path.abspath(__file__))  # .../refactor
for _path in (_ROOT,
              os.path.join(_ROOT, "pro-base-common", "src", "main", "java"),
              os.path.join(_ROOT, "pro-business-api", "src", "main", "java")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ---------------------------------------------------------------------- 断言工具
PASS = 0


def check(condition, label):
    global PASS
    if not condition:
        raise AssertionError("FAILED: " + label)
    PASS += 1
    print("  [OK] %s" % label)


def expect_raises(exc_type, func, label):
    """断言 func() 抛出 exc_type，返回捕获到的异常实例。"""
    global PASS
    try:
        func()
    except exc_type as error:  # noqa: BLE001 - 测试断言
        PASS += 1
        print("  [OK] %s" % label)
        return error
    except Exception as error:  # noqa: BLE001 - 类型不符也要报错
        raise AssertionError("FAILED(%s != %s): %s" %
                             (type(error).__name__, exc_type.__name__, label))
    raise AssertionError("FAILED(no raise): " + label)


def section(title):
    print("\n=== %s ===" % title)


# ====================================================================== 1 结构
section("1. 目录结构对照（com/ruoyi/mq）")

# Java 源在原始工程里，Python 在 refactor 里，两边按“相对 mq 包的路径”比对
_MQ_REL = os.path.join("pro-business-api", "src", "main", "java", "com", "ruoyi", "mq")
_MQ_PY_ROOT = os.path.join(_ROOT, _MQ_REL)
_MQ_JAVA_ROOT = os.path.join(os.path.dirname(_ROOT), _MQ_REL)
_mq_java = sorted(os.path.relpath(p, _MQ_JAVA_ROOT)[:-5].replace(os.sep, "/")
                  for p in glob.glob(os.path.join(_MQ_JAVA_ROOT, "**", "*.java"),
                                     recursive=True))
_mq_py = sorted(os.path.relpath(p, _MQ_PY_ROOT)[:-3].replace(os.sep, "/")
                for p in glob.glob(os.path.join(_MQ_PY_ROOT, "**", "*.py"),
                                   recursive=True))
print("  java: %s" % _mq_java)
print("  py  : %s" % _mq_py)
check(_mq_java == _mq_py and len(_mq_java) == 6,
      "mq 包 6 个类目录结构一一对应")

# ====================================================================== 2 时间
section("2. LocalDateTime.plusMonths / minusMonths / with*")

from java.time.LocalDateTime import LocalDateTime  # noqa: E402
from java.time.format.DateTimeFormatter import DateTimeFormatter  # noqa: E402

_FMT_D = DateTimeFormatter.ofPattern("yyyy-MM-dd")
_FMT_S = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

# Java 规则：目标月没有该日 → 取当月最后一天
check(LocalDateTime.of(2024, 1, 31).plusMonths(1).format(_FMT_D) == "2024-02-29",
      "2024-01-31 plusMonths(1) = 2024-02-29（闰年 clamp）")
check(LocalDateTime.of(2023, 1, 31).plusMonths(1).format(_FMT_D) == "2023-02-28",
      "2023-01-31 plusMonths(1) = 2023-02-28（平年 clamp）")
check(LocalDateTime.of(2024, 1, 15).plusMonths(13).format(_FMT_D) == "2025-02-15",
      "2024-01-15 plusMonths(13) = 2025-02-15（跨年）")
check(LocalDateTime.of(2024, 3, 15).minusMonths(5).format(_FMT_D) == "2023-10-15",
      "2024-03-15 minusMonths(5) = 2023-10-15（跨年倒推）")
check(LocalDateTime.of(2024, 5, 20, 13, 45, 30)
      .withDayOfMonth(1).withHour(0).withMinute(0).withSecond(0)
      .format(_FMT_S) == "2024-05-01 00:00:00",
      "withDayOfMonth/withHour/withMinute/withSecond 链式归零")

# ====================================================================== 3 ES 客户端
section("3. ElasticsearchConfig + ES 客户端替身")

from com.ruoyi.mq.config.ElasticsearchConfig import ElasticsearchConfig  # noqa: E402
from org.elasticsearch.client.RequestOptions import RequestOptions  # noqa: E402
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient  # noqa: E402
from org.elasticsearch.action.index.IndexRequest import IndexRequest  # noqa: E402
from org.elasticsearch.action.search.SearchRequest import SearchRequest  # noqa: E402
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder  # noqa: E402
from org.elasticsearch.search.SearchHit import SearchHit  # noqa: E402
from org.elasticsearch.search.SearchHits import SearchHits  # noqa: E402
from org.elasticsearch.action.search.SearchResponse import SearchResponse  # noqa: E402
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders  # noqa: E402
from org.elasticsearch.xcontent.XContentType import XContentType  # noqa: E402
from org.elasticsearch.core.TimeValue import TimeValue  # noqa: E402
from java.util.concurrent.TimeUnit import TimeUnit  # noqa: E402

RestHighLevelClient.resetStore()

_config = ElasticsearchConfig(host="es-node", port=9201, scheme="https",
                              connection_timeout=1234, socket_timeout=5678)
_config.setPort("9202")  # setter 内部 int(...) 转换（@Data 的 setPort(int)）
_client = _config.restHighLevelClient()
check(_client.ping(RequestOptions.DEFAULT) is True, "ping 可用时返回 True")

_host = _client.restClient.getHosts()[0]
check((_host.getHostName(), _host.getPort(), _host.getSchemeName())
      == ("es-node", 9202, "https"), "HttpHost(host, port, scheme) 透传正确")
check(_client.restClient.requestConfig.getConnectTimeout() == 1234,
      "lambda 回调把 connectTimeout 写入 RequestConfig")
check(_client.restClient.requestConfig.getSocketTimeout() == 5678,
      "lambda 回调把 socketTimeout 写入 RequestConfig")

_bind = ElasticsearchConfig.from_properties({
    "elasticsearch.host": "es2",
    "elasticsearch.port": "9300",
    "elasticsearch.scheme": "https",
    "elasticsearch.connection-timeout": 111,
    "elasticsearch.socketTimeout": 222,
})
check((_bind.host, _bind.port, _bind.scheme, _bind.connection_timeout,
       _bind.socket_timeout) == ("es2", 9300, "https", 111, 222),
      "@ConfigurationProperties 松散绑定（kebab + camel 混写）")
_default = ElasticsearchConfig.from_properties({})
check((_default.host, _default.port, _default.scheme, _default.username,
       _default.password, _default.connection_timeout, _default.socket_timeout)
      == ("localhost", 9200, "http", None, None, 30000, 30000),
      "缺失配置时保留 Java 字段默认值")

# index：首次 CREATED，同 id 覆盖 UPDATED + version 自增
_res1 = _client.index(
    IndexRequest("snapshot_flow").id("1").source(
        '{"id":"1","platenumber":"\u4eacA12345","snapshottime":"2024-03-05 10:00:00"}',
        XContentType.JSON), RequestOptions.DEFAULT)
check((_res1.getResult(), _res1.getVersion()) == ("CREATED", 1),
      "index 首次写入 → CREATED / version=1")
_res2 = _client.index(
    IndexRequest("snapshot_flow").id("1").source(
        '{"id":"1","platenumber":"\u4eacA12345","snapshottime":"2024-03-05 10:00:00"}',
        XContentType.JSON), RequestOptions.DEFAULT)
check((_res2.getResult(), _res2.getVersion()) == ("UPDATED", 2),
      "index 同 id 覆盖 → UPDATED / version=2")
_source_error = expect_raises(
    ValueError,
    lambda: _client.index(IndexRequest("snapshot_flow").id("x"),
                          RequestOptions.DEFAULT),
    "index 缺少 source → ValueError")
check(_source_error.args[0].endswith("不能为空"),
      "IndexRequest.source 为空的异常消息")

# search：无查询条件返回全部，from/size 由客户端侧裁剪
_client.index(IndexRequest("snapshot_flow").id("2").source(
    '{"id":"2","platenumber":"\u4eacA99999","snapshottime":"2024-04-05 10:00:00"}',
    XContentType.JSON), RequestOptions.DEFAULT)
_builder = SearchSourceBuilder()
_search = SearchRequest("snapshot_flow").source(_builder)
_hits = _client.search(_search, RequestOptions.DEFAULT).getHits()
check(_hits.getTotalHits() == 2 and len(_hits.getHits()) == 2,
      "search 无查询条件 → 返回索引内全部 2 条")
check(_hits.getHits()[0].getId() == "1", "替身按插入顺序返回（ES 默认 _doc 顺序）")

_page_builder = SearchSourceBuilder()
_page_search = SearchRequest("snapshot_flow").source(_page_builder)
_page_builder.from_(1).size(1)
_page_hits = _client.search(_page_search, RequestOptions.DEFAULT).getHits()
check([h.getId() for h in _page_hits.getHits()] == ["2"] and _page_hits.getTotalHits() == 2,
      "from_/size 分页：offset=1,size=1 → 第 2 条，total 不变")

# QueryBuilder 命中语义
_doc_plate = {"platenumber": "\u4eacA12345"}
check(QueryBuilders.matchQuery("platenumber", "A123").fuzziness("AUTO")
      .matches(_doc_plate) is True, "matchQuery(fuzziness=AUTO) 子串命中")
check(QueryBuilders.matchQuery("vehiclePlate", "A123").fuzziness("AUTO")
      .matches(_doc_plate) is False, "matchQuery 字段不存在 → 不命中（对应 ES unmapped）")
check(QueryBuilders.termQuery("platenumber", "\u4eacA12345").matches(_doc_plate) is True,
      "termQuery 全等命中")
check(QueryBuilders.termQuery("platenumber", "\u4eacA1").matches(_doc_plate) is False,
      "termQuery 不做分词/子串 → 不命中")
_range = QueryBuilders.rangeQuery("snapshottime").gte("2024-03-01 00:00:00").lt("2024-04-01 00:00:00")
check(_range.matches({"snapshottime": "2024-03-05 10:00:00"}) is True,
      "rangeQuery gte/lt 命中（日期字符串字典序可比）")
check(_range.matches({"snapshottime": "2024-04-05 10:00:00"}) is False,
      "rangeQuery 超出上界 → 不命中")

_tv = TimeValue(30, TimeUnit.SECONDS)
check((_tv.getTime(), _tv.getSeconds(), _tv.getMillis()) == (30, 30, 30000),
      "TimeValue(30, SECONDS) → 30s / 30000ms")

# ====================================================================== 4 RabbitMQ
section("4. RabbitMqConfig（@Bean → 工厂方法）")

from com.ruoyi.mq.config.RabbitMqConfig import RabbitMqConfig  # noqa: E402

_rabbit = RabbitMqConfig()  # 默认从 application.yml 读取（等价 Spring @Value）
check(_rabbit.snapshotFlowTopic == "topic_snapshot_flow",
      "@Value mq.topic.snapshot-flow = topic_snapshot_flow")
check(_rabbit.deadLetterExchangeName == "exchange.snapshot.flow.dlx",
      "@Value mq.dead-letter.exchange")
check(_rabbit.deadLetterQueueName == "queue.snapshot.flow.dlx",
      "@Value mq.dead-letter.queue")
check(_rabbit.deadLetterRoutingKey == "snapshot.flow.dlx",
      "@Value mq.dead-letter.routing-key")
check(callable(_rabbit.deadLetterExchange) and callable(_rabbit.deadLetterQueue),
      "字段改名后不再遮蔽同名 @Bean 方法（Python 特有坑）")

_ex = _rabbit.snapshotFlowExchange()
check((_ex.getName(), _ex.getType(), _ex.isDurable())
      == ("topic_snapshot_flow", "direct", True),
      "snapshotFlowExchange → direct + durable")
_queue = _rabbit.snapshotFlowQueue()
_args = _queue.getArguments()
check(_queue.getName() == "queue.snapshot.flow", "snapshotFlowQueue 名称固定")
check(_args.get("x-dead-letter-exchange") == "exchange.snapshot.flow.dlx",
      "队列参数 x-dead-letter-exchange")
check(_args.get("x-dead-letter-routing-key") == "snapshot.flow.dlx",
      "队列参数 x-dead-letter-routing-key")
check(_args.get("x-message-ttl") == 60000, "队列参数 x-message-ttl=60000（毫秒）")

_binding = _rabbit.snapshotFlowBinding(_queue, _ex)
check((_binding.getDestination(), _binding.getExchange(), _binding.getRoutingKey())
      == ("queue.snapshot.flow", "topic_snapshot_flow", "snapshot.flow"),
      "snapshotFlowBinding：with_(...) → 路由键 snapshot.flow")
_dlx = _rabbit.deadLetterExchange()
_dlq = _rabbit.deadLetterQueue()
_dlb = _rabbit.deadLetterBinding(_dlq, _dlx)
check((_dlx.getName(), _dlq.getName(), _dlb.getRoutingKey())
      == ("exchange.snapshot.flow.dlx", "queue.snapshot.flow.dlx", "snapshot.flow.dlx"),
      "死信交换机/队列/绑定")

# ====================================================================== 5 RocketMQ 替身
section("5. RocketMQ 生产者替身")

from org.apache.rocketmq.client.producer.DefaultMQProducer import DefaultMQProducer  # noqa: E402
from org.apache.rocketmq.client.producer.SendStatus import SendStatus  # noqa: E402
from org.apache.rocketmq.common.message.Message import Message  # noqa: E402

DefaultMQProducer.reset()
_producer = DefaultMQProducer("snapshot_flow_producer")
expect_raises(RuntimeError,
              lambda: _producer.send(Message("t", "tag", "k", b"{}")),
              "未 start() 直接 send → MQClientException（RuntimeError）")
_producer.start()
_result = _producer.send(Message("topic_snapshot_flow", "snapshot_flow", "1", b"{}"))
check(_result.getSendStatus().name == "SEND_OK",
      "枚举 name() → Python .name 属性（无括号）")
check(_result.getMessageQueue().getQueueId() == 0 and len(_result.getMsgId()) == 32,
      "SendResult 携带 MessageQueue / 32 位 msgId")
check(len(DefaultMQProducer.sentMessages()) == 1, "broker 侧记录 1 条消息")

# ====================================================================== 6 实体与基础设施
section("6. DataProcessService（@Transactional 降级为顺序执行）")

from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode  # noqa: E402
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper  # noqa: E402
from com.ruoyi.common.core.redis.RedisCache import RedisCache  # noqa: E402
from com.ruoyi.mq.service.DataProcessService import DataProcessService  # noqa: E402

RestHighLevelClient.resetStore()
_mapper = OdsRtSzdnSnapshotFlowAddcodeMapper()
_redis = RedisCache()
_es_client = ElasticsearchConfig().restHighLevelClient()
_data_service = DataProcessService(mapper=_mapper, redisCache=_redis, esClient=_es_client)

_entity = OdsRtSzdnSnapshotFlowAddcode(id="501", platenumber="\u4eacB00002",
                                       snapshottime=datetime(2024, 7, 15, 8, 30, 0))
check(_data_service.getTableName(_entity.getSnapshottime())
      == "ods_rt_szdn_snapshot_flow_addcode_202407",
      "getTableName(snapshottime) → 月分表后缀 202407")
check(_data_service.getTableName(None)
      == "ods_rt_szdn_snapshot_flow_addcode_" + datetime.now().strftime("%Y%m"),
      "getTableName(null) → 回退到当前月份")

# 与真实 GaussDB 解耦：process() 的 @Transactional 语义由 app.db.engine 提供
# 真实事务，需要一条可达的数据库连接；冒烟环境（CI / 本机无 DB）只验证编排
# 顺序（内存 mapper + shim ES/Redis），这里把 get_database 换成空事务替身。
import contextlib  # noqa: E402
import app.db.engine as _engine_mod  # noqa: E402


class _NoopDatabase(object):
    @contextlib.contextmanager
    def transaction(self):
        yield


_engine_mod.get_database = lambda: _NoopDatabase()
_data_service.process(_entity)
_docs = RestHighLevelClient.documents("snapshot_flow")
check("501" in _docs, "process → 写入 ES 索引 snapshot_flow（id=501）")
check(_docs["501"]["platenumber"] == "\u4eacB00002",
      "ES _source 保留实体原始字段名 platenumber")
check(_docs["501"]["snapshottime"] == "2024-07-15 08:30:00",
      "Date → 'yyyy-MM-dd HH:mm:ss' 字符串（fastjson 替身约定）")
check(len(_mapper._rows) == 1, "process → mapper.insert 落到内存表")
check(_mapper.getMaxSnapshotTime() == datetime(2024, 7, 15, 8, 30, 0),
      "mapper.getMaxSnapshotTime 取到刚插入的行")

check(_data_service.isProcessed("MSG-T09E-1") is False, "isProcessed 未命中 → False")
_data_service.markProcessed("MSG-T09E-1", 501)
check(_data_service.isProcessed("MSG-T09E-1") is True,
      "markProcessed 写入 mq:processed: 前缀键（TTL=7 DAYS）")


class _BoomMapper(OdsRtSzdnSnapshotFlowAddcodeMapper):
    """模拟数据库不可用。"""

    def insert(self, entity):
        raise RuntimeError("db down")


_boom_service = DataProcessService(mapper=_BoomMapper(), redisCache=_redis,
                                   esClient=_es_client)
_my_error = expect_raises(RuntimeError, lambda: _boom_service.insertIntoMysql(_entity),
                          "insertIntoMysql 异常 → RuntimeException('插入MySQL失败')")
check(str(_my_error) == "插入MySQL失败" and isinstance(_my_error.__cause__, RuntimeError),
      "raise ... from e 保留 Java 的 cause 链")

RestHighLevelClient.available = False
try:
    _es_error = expect_raises(RuntimeError, lambda: _data_service.insertIntoEs(_entity),
                              "ES 不可用 → RuntimeException('插入ES失败')")
    check(str(_es_error) == "插入ES失败", "插入 ES 失败时异常消息与 Java 一致")
    _down_client = ElasticsearchConfig().restHighLevelClient()
    check(_down_client is not None, "ping 失败只 warn，@Bean 仍返回客户端（与 Java 一致）")
finally:
    RestHighLevelClient.available = True

# ====================================================================== 7 消费者
section("7. RocketMqConsumer（幂等 + 异常包装）")

from com.ruoyi.mq.consumer.RocketMqConsumer import RocketMqConsumer  # noqa: E402
from org.apache.rocketmq.common.message.MessageExt import MessageExt  # noqa: E402
from java.nio.charset.StandardCharsets import StandardCharsets  # noqa: E402


class _FakeDataProcessService(object):
    """替身：只记录调用，不落库不落 ES。"""

    def __init__(self):
        self.processed = set()
        self.processed_calls = []
        self.marked_calls = []
        self.fail = None

    def isProcessed(self, msg_id):
        return msg_id in self.processed

    def process(self, data):
        if self.fail is not None:
            raise self.fail
        self.processed_calls.append(data)

    def markProcessed(self, msg_id, data_id):
        self.marked_calls.append((msg_id, data_id))
        self.processed.add(msg_id)


check(StandardCharsets.UTF_8 == "utf-8", "StandardCharsets.UTF_8 → 'utf-8'")

_fake_service = _FakeDataProcessService()
_consumer = RocketMqConsumer(_fake_service)
_body = ('{"id":"123","platenumber":"\u4eacA00001",'
         '"snapshottime":"2024-03-05 10:00:00"}')
_message = MessageExt(topic="topic_snapshot_flow",
                      body=_body.encode(StandardCharsets.UTF_8),
                      msg_id="MSG-T09E-A", reconsume_times=0)
_consumer.onMessage(_message)
check(len(_fake_service.processed_calls) == 1, "onMessage → process 被调用 1 次")
check(_fake_service.marked_calls == [("MSG-T09E-A", 123)],
      "markProcessed(msgId, int(data.getId()))：Long.valueOf → int()")
check(_fake_service.processed_calls[0].getSnapshottime() == datetime(2024, 3, 5, 10, 0, 0),
      "JSON.parseObject → 实体 snapshottime 反序列化为 datetime")

_consumer.onMessage(_message)
check(len(_fake_service.processed_calls) == 1, "重复投递 → 幂等检查命中，不再重复处理")

_fake_service.fail = ValueError("boom")
_bad_message = MessageExt(topic="topic_snapshot_flow",
                          body=b'{"id":"124"}',
                          msg_id="MSG-T09E-B", reconsume_times=3)
_consumer_error = expect_raises(RuntimeError, lambda: _consumer.onMessage(_bad_message),
                                "处理失败 → RuntimeException('消息处理失败')")
check(str(_consumer_error) == "消息处理失败"
      and isinstance(_consumer_error.__cause__, ValueError),
      "异常链保留原始 cause（reconsumeTimes=3 走死信日志分支）")

# ====================================================================== 8 生产者
section("8. RocketMqProducer（全量游标 / 增量位点 / 失败备份）")

from com.ruoyi.mq.producer.RocketMqProducer import RocketMqProducer  # noqa: E402


class _FakeSnapshotService(object):
    """替身：getMaxSnapshotTime + queryByCursor（按批次弹出）。"""

    def __init__(self, batches, max_time):
        self._batches = list(batches)
        self._max_time = max_time

    def getMaxSnapshotTime(self):
        return self._max_time

    def queryByCursor(self, cursor, max_snapshot_time, page_size):
        return self._batches.pop(0) if self._batches else []


_redis.deleteObject("mq:sync:lastSyncTime")
DefaultMQProducer.reset()
_empty_producer = RocketMqProducer(producer=_producer,
                                   snapshotFlowAddcodeService=_FakeSnapshotService([], None),
                                   redisCache=_redis)
check(_empty_producer.topic == "topic_snapshot_flow",
      "@Value 走注解默认值（application.yml 无 rocketmq.topic.snapshot-flow）")
check(_empty_producer.getLastSyncTime() == "2024-01-01 00:00:00",
      "Redis 无位点 → 默认 '2024-01-01 00:00:00'")
_empty_producer.syncFullData()
check(len(DefaultMQProducer.sentMessages()) == 0,
      "maxSnapshotTime 为空 → 跳过全量同步，不发送")

_d1 = OdsRtSzdnSnapshotFlowAddcode(id="1001", platenumber="\u4eacC00001",
                                   snapshottime=datetime(2024, 1, 1, 10, 0, 0))
_d2 = OdsRtSzdnSnapshotFlowAddcode(id="1002", platenumber="\u4eacC00002",
                                   snapshottime=datetime(2024, 1, 1, 10, 0, 5))
_full_producer = RocketMqProducer(
    producer=_producer,
    snapshotFlowAddcodeService=_FakeSnapshotService([[_d1, _d2]], "2024-01-01 10:00:05"),
    redisCache=_redis)
_full_producer.syncFullData()
_sent = DefaultMQProducer.sentMessages()
check(len(_sent) == 2, "全量同步：游标推进到 max 后结束，发送 2 条")
check((_sent[0][0], _sent[0][1], _sent[0][2])
      == ("topic_snapshot_flow", "snapshot_flow", "1001"),
      "Message(topic, tags, keys=str(getId()), body)")
check(json.loads(_sent[0][3].decode(StandardCharsets.UTF_8))["platenumber"]
      == "\u4eacC00001", "消息体为 UTF-8 编码的 JSON（getBytes → encode）")

_redis.deleteObject("mq:sync:lastSyncTime")
_incremental = RocketMqProducer(
    producer=_producer,
    snapshotFlowAddcodeService=_FakeSnapshotService([[_d1]], None),
    redisCache=_redis)
_incremental.syncIncrementalData()
check(_incremental.getLastSyncTime() != "2024-01-01 00:00:00",
      "增量同步成功 → updateLastSyncTime 写回 Redis 位点")
check(len(_incremental.getLastSyncTime()) == 19, "位点格式 yyyy-MM-dd HH:mm:ss（19 字符）")

_redis.deleteObject("mq:sync:lastSyncTime")
_no_new = RocketMqProducer(
    producer=_producer,
    snapshotFlowAddcodeService=_FakeSnapshotService([], None),
    redisCache=_redis)
_no_new.syncIncrementalData()
check(_no_new.getLastSyncTime() == "2024-01-01 00:00:00",
      "增量无数据 → 不更新 Redis 位点")

_backups = []
_full_producer.writeToLocalBackup = lambda data: _backups.append(data.getId())
DefaultMQProducer.reset()
_producer.fail_status = SendStatus.FLUSH_DISK_TIMEOUT
_full_producer.sendBatchMessages([_d1])
check(_backups == ["1001"], "sendStatus != SEND_OK → writeToLocalBackup(data)")
_producer.fail_status = None
_producer.fail_next = RuntimeError("RemotingException: broker down")
_full_producer.sendBatchMessages([_d2])
check(_backups == ["1001", "1002"], "send 抛异常 → 捕获后同样写本地备份")
check(len(DefaultMQProducer.sentMessages()) == 1,
      "异常消息不会进入 broker 记录（只有 SEND_OK 分支真正落地）")

_full_producer.destroy()
check(_full_producer.executorService.isShutdown() is True,
      "@PreDestroy destroy() → 线程池 shutdown")

# ====================================================================== 9 查询服务
section("9. EsQueryService（ES 优先 + MySQL 降级）")

from com.ruoyi.common.core.page.PageDomain import PageDomain  # noqa: E402
from com.ruoyi.mq.service.EsQueryService import EsQueryService  # noqa: E402

RestHighLevelClient.resetStore()
_query_client = ElasticsearchConfig().restHighLevelClient()
_es_query = EsQueryService(esClient=_query_client,
                           mapper=OdsRtSzdnSnapshotFlowAddcodeMapper())


def _index_doc(doc_id, payload):
    _query_client.index(IndexRequest("snapshot_flow").id(doc_id).source(
        json.dumps(payload, ensure_ascii=False), XContentType.JSON),
        RequestOptions.DEFAULT)


# 9.1 字段对齐（用 ES 里的 vehiclePlate/snapshotTime）→ 查询链路完整命中
_index_doc("q1", {"id": "q1", "vehiclePlate": "\u4eacA10003",
                  "snapshotTime": "2024-03-05 10:00:00", "sectionCode": "S1"})
_aligned = _es_query.query("\u4eacA10003", LocalDateTime.of(2024, 3, 5),
                           LocalDateTime.of(2024, 3, 6), "S1", None, None,
                           PageDomain(1, 10))
check([item.getId() for item in _aligned] == ["q1"],
      "match + range + term 组合命中（from_/size 分页链正常）")
check(_es_query.query("\u4eacA10003", LocalDateTime.of(2024, 3, 7), None, None,
                      None, None, PageDomain(1, 10)) == [],
      "startTime 超出快照时间 → rangeQuery 过滤掉")

# 9.2 原工程缺陷：查询字段与实体字段不一致 → 真实写入的数据查不到
RestHighLevelClient.resetStore()
_index_doc("d1", {"id": "d1", "platenumber": "\u4eacA10003",
                  "snapshottime": "2024-03-05 10:00:00", "sectioncode": "S1"})
check(_es_query.query("\u4eacA10003", None, None, None, None, None,
                      PageDomain(1, 10)) == [],
      "【原工程缺陷】查询 vehiclePlate，实体写入 platenumber → 永远查不到")

# 9.3 from_ / size 分页
RestHighLevelClient.resetStore()
for _i in range(1, 13):
    _index_doc("p%02d" % _i, {"id": "p%02d" % _i,
                              "vehiclePlate": "\u4eacA%05d" % (10000 + _i),
                              "snapshotTime": "2024-03-%02d 10:00:00"
                                             % (_i if _i <= 9 else 10)})
_paged = _es_query.query(None, None, None, None, None, None, PageDomain(2, 5))
check([item.getId() for item in _paged] == ["p06", "p07", "p08", "p09", "p10"],
      "分页：pageNum=2,pageSize=5 → from_=5,size=5 → p06..p10")

# 9.4 分表名切片
_tables = _es_query.getTableNames(LocalDateTime.of(2023, 12, 15),
                                  LocalDateTime.of(2024, 2, 10))
check(_tables == ["ods_rt_szdn_snapshot_flow_addcode_202312",
                  "ods_rt_szdn_snapshot_flow_addcode_202401",
                  "ods_rt_szdn_snapshot_flow_addcode_202402"],
      "getTableNames 按月切片（withDayOfMonth(1) 归零 + plusMonths(1) 推进）")
_now = datetime.now()
_prev_month = _now.replace(day=1) - timedelta(days=1)
check(_es_query.getTableNames(None, None)
      == ["ods_rt_szdn_snapshot_flow_addcode_" + _prev_month.strftime("%Y%m"),
          "ods_rt_szdn_snapshot_flow_addcode_" + _now.strftime("%Y%m")],
      "getTableNames(null, null) → 近一个月区间（2 张分表）")
check(_es_query.formatDateTime(LocalDateTime.of(2024, 1, 2, 3, 4, 5))
      == "2024-01-02 03:04:05", "formatDateTime 使用 yyyy-MM-dd HH:mm:ss")

# 9.5 坏 JSON 逐条跳过
_bad_response = SearchResponse(SearchHits(
    [SearchHit("snapshot_flow", "bad", "{not-json"),
     SearchHit("snapshot_flow", "ok", '{"id":"ok"}')], 2))
_parsed = _es_query.parseEsResponse(_bad_response)
check(len(_parsed) == 1 and _parsed[0].getId() == "ok",
      "parseEsResponse 逐条 try/catch，坏 JSON 跳过不影响其它命中")

# 9.6 ES 不可用 → 降级 MySQL（原工程固定返回空列表）
RestHighLevelClient.available = False
try:
    check(_es_query.query(None, None, None, None, None, None,
                          PageDomain(1, 10)) == [],
          "ES 不可用 → catch Exception 后降级 queryFromMysql → 空列表")
    expect_raises(ConnectionError,
                  lambda: _es_query.queryFromEs(None, None, None, None, None,
                                                None, PageDomain(1, 10)),
                  "queryFromEs 直接调用时向上抛 ConnectionError（等价 IOException）")
finally:
    RestHighLevelClient.available = True

# ====================================================================== 汇总
print("\n" + "=" * 60)
print("T09E SMOKE PASSED: %d assertions" % PASS)
print("=" * 60)
