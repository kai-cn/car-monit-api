# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DebeziumReadonlyPulsarConsumer

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DebeziumReadonlyPulsarConsumer.java

Debezium CDC 只读 Pulsar 消费者（原注释保留）

功能说明（与原 DebeziumReadonlyKafkaConsumer 等价）：
- 消费 Pulsar 中的 CDC 变更消息（由 Debezium 从源数据库捕获）
- 保证消息幂等：基于 Redis SETNX + LSN（Log Sequence Number）
- 保证数据不丢失：先持久化到 MySQL，再写入 Elasticsearch

设计背景：
- 原方案使用 Debezium 监听源 GaussDB 的数据变更（逻辑复制槽）
- 生产者将 Debezium 产出的变更事件转换为统一消息格式并发送到 Pulsar
- 消费者端（本类）从 Pulsar 消费这些变更事件
- 源数据库只有查询权限，因此 CDC 是"只读"模式（Debezium snapshot.locking.mode=none）

消息格式（与生产者约定）：
  {
    "operationType": "INSERT",                // INSERT / UPDATE / DELETE
    "data": { ... },                          // OdsRtSzdnSnapshotFlowAddcode 对象
    "source": {                               // Debezium source 元数据（可选）
      "lsn": "123456",                        // 日志序列号（用于幂等性判断）
      "ts_ms": 1719897600000                  // 事件时间戳
    }
  }

Pulsar 消费者特性（与 Kafka 的区别）：
-----------------------------------------------------------------------------
原 Kafka 机制             Pulsar 对应机制
-----------------------------------------------------------------------------
@KafkaListener 注解       手动 while(true) 循环 receive()
consumer.commitAsync()    consumer.acknowledgeAsync(message)
consumer.seekToBeginning() consumer.seek(messageId) / seekByTime()
auto.offset.reset=earliest subscriptionInitialPosition=Earliest
consumer group 负载均衡   SubscriptionType.Key_Shared（按 key 路由保证有序）
-----------------------------------------------------------------------------

可靠性保证（4 层机制）：
1. LSN 幂等检查：同一 LSN 的消息只处理一次（Redis SETNX）
2. 数据持久化：先写 MySQL，成功后写 Elasticsearch
3. 手动确认：业务处理成功后才 acknowledge，否则 negativeAcknowledge 重投
4. 死信队列：超过 max-retry-times 次重投失败的消息路由到 DLQ

【Java→Python 本文件重点差异】
1) `//@Service`（注释掉的注解）→ 普通类；`__init__` 末尾执行 `init()`（= `@PostConstruct`）。
2) `@Autowired Consumer<String> debeziumReadonlyConsumer` → 构造器可选参数；缺省按
   `PulsarConsumerConfig.debeziumReadonlyConsumer()` 的订阅名 `debezium-readonly-sub` 造替身。
3) `@Autowired IEsService`：Java 工程无实现类（同 SnapshotFlowPulsarConsumer），
   缺省注入 `_UnimplementedEsService`（调用即抛错 → 走重投分支）。
4) `@Value("${spring.pulsar.idempotent-ttl-seconds:604800}") private long` → int（默认 7 天）。
5) `private static final String CDC_IDEMPOTENT_KEY_PREFIX` → 类属性。
6) `consumer.acknowledgeAsync(msg)` 返回 `CompletableFuture<Void>`，Java 里作为语句丢弃；
   Python 同样丢弃返回值（替身返回已完成的 CompletableFuture）。
7) `while (!Thread.currentThread().isInterrupted())` + `catch (InterruptedException)` 原样保留。
8) `String[] lsnFields = {...}` → tuple；`value.toString().isEmpty()` → `str(value) == ""`
   （注意 Java 的 isEmpty() 只看长度，Python 用 `== ""` 等价；不要用 `not value`，
   因为数字 0 在 Java 里 `toString()` 是 "0"、并不为空）。
9) `switch` 的 **case 穿透**：`case "INSERT": case "CREATE":` 落到同一分支
   → Python 用 `operation in ("INSERT", "CREATE")` 表达。
10) `dataObj.toString()` → `str(dataObj)`；`JSONObject.parseObject(text, clazz)` 同名。
11) `boolean isNew` 的 null 判断（`isNew == null || !isNew`）→ `is_new is None or not is_new`。
12) 日志占位符 `{}` → `%s`；`log.error(msg, e)` → `log.exception(msg)`。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.service.IEsService import IEsService
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import IOdsRtSzdnSnapshotFlowAddcodeService
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import OdsRtSzdnSnapshotFlowAddcodeServiceImpl
from java.lang.System import System
from java.lang.Thread import InterruptedException, Thread
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from java.util.concurrent.TimeUnit import TimeUnit
from org.apache.pulsar.client.api.Consumer import Consumer
from org.apache.pulsar.client.api.Message import Message
from org.apache.pulsar.client.api.MessageId import MessageId
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.StringRedisTemplate import defaultStringRedisTemplate

__all__ = ["DebeziumReadonlyPulsarConsumer"]

log = logging.getLogger(__name__)


class _UnimplementedEsService(IEsService):
    """缺省占位：对应“Java 工程里 IEsService 没有实现类”的事实（同 SnapshotFlowPulsarConsumer）。"""

    def saveSnapshotFlow(self, flowData: OdsRtSzdnSnapshotFlowAddcode) -> bool:
        raise RuntimeError("com.ruoyi.base.service.IEsService 没有实现类（原工程未提供 Bean）")

    def deleteSnapshotFlow(self, dataId: str) -> bool:
        raise RuntimeError("com.ruoyi.base.service.IEsService 没有实现类（原工程未提供 Bean）")


class DebeziumReadonlyPulsarConsumer(object):
    """Debezium CDC 只读 Pulsar 消费者（`//@Service` → 普通类）。"""

    # Redis 幂等性 Key 前缀（CDC 专用，避免与主消费者冲突）
    CDC_IDEMPOTENT_KEY_PREFIX = "pulsar:cdc:processed:"

    def __init__(self,
                 debeziumReadonlyConsumer: Optional[Consumer] = None,
                 snapshotFlowService: Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 esService: Optional[IEsService] = None,
                 redisTemplate: Any = None,
                 environment: Optional[Environment] = None) -> None:
        env = environment or Environment()

        # 注入 Pulsar CDC 消费者（Key_Shared 订阅：同一 key 路由到同一 consumer，保证有序）
        # 【Java→Python】缺省时按 PulsarConsumerConfig 的配置造替身：同 topic + "debezium-readonly-sub"
        self.debeziumReadonlyConsumer: Consumer = (
            debeziumReadonlyConsumer if debeziumReadonlyConsumer is not None else Consumer(
                topic=env.value(
                    "${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}", str),
                subscription_name="debezium-readonly-sub",
            ))
        # 业务服务：MySQL 分表写入（与主消费者共享同一服务实例）
        self.snapshotFlowService: IOdsRtSzdnSnapshotFlowAddcodeService = (
            snapshotFlowService if snapshotFlowService is not None
            else OdsRtSzdnSnapshotFlowAddcodeServiceImpl())
        # 业务服务：Elasticsearch 写入
        self.esService: IEsService = esService if esService is not None else _UnimplementedEsService()
        # Redis 模板：幂等性检查用
        self.redisTemplate = redisTemplate or defaultStringRedisTemplate()

        # 幂等性过期时间（秒）：默认 7 天（CDC 消息可能需要回放）
        self.idempotentTtlSeconds: int = env.value(
            "${spring.pulsar.idempotent-ttl-seconds:604800}", int)

        # 消费线程池（单线程即可，因为 Key_Shared 模式下同一 key 的消息有序）
        self.consumerExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    def init(self) -> None:
        """初始化（与 SnapshotFlowPulsarConsumer 相同的生命周期模式）。"""
        self.consumerExecutor = Executors.newSingleThreadExecutor()
        self.startConsume()
        log.info("[Pulsar-CDC消费者] 初始化完成，开始消费 CDC 主题")

    def destroy(self) -> None:
        """销毁（`@PreDestroy`）。"""
        log.info("[Pulsar-CDC消费者] 正在关闭...")
        if self.consumerExecutor is not None:
            self.consumerExecutor.shutdownNow()
        try:
            if self.debeziumReadonlyConsumer is not None:
                self.debeziumReadonlyConsumer.close()
                log.info("[Pulsar-CDC消费者] Consumer 已关闭")
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar-CDC消费者] 关闭异常")

    def startConsume(self) -> None:
        """启动消费循环（CDC 专用）。

        设计思路：
        1. 使用 while(true) 循环不断 receive() 消息（与 Kafka 消费者等价）
        2. receive() 阻塞等待，收到消息后解析并处理
        3. CDC 场景额外需要检查 LSN / 事务 ID 的幂等性
        4. 处理成功：acknowledge 确认（异步 ack，提高吞吐）
        5. 处理失败：negativeAcknowledge 触发重投
        """

        def _consumeLoop() -> None:
            log.info("[Pulsar-CDC消费者] CDC 消费循环已启动")

            while not Thread.currentThread().isInterrupted():
                msg: Optional[Message] = None
                try:
                    # 阻塞接收消息（Pulsar 核心 API）
                    msg = self.debeziumReadonlyConsumer.receive()

                    if msg is None:
                        continue

                    messageId: MessageId = msg.getMessageId()
                    dataId: str = msg.getKey()
                    messageJson: str = msg.getValue()

                    log.debug("[Pulsar-CDC消费者] 收到消息: dataId=%s, messageId=%s",
                              dataId, messageId)

                    # 处理消息（业务逻辑）
                    success = self.processMessage(dataId, messageJson, messageId)

                    if success:
                        # 异步确认：不阻塞当前消费循环，提高吞吐
                        # 与 Kafka consumer.commitAsync() 等价
                        # 【Java→Python】返回的 CompletableFuture 在 Java 里也被丢弃
                        self.debeziumReadonlyConsumer.acknowledgeAsync(msg)

                        log.info("[Pulsar-CDC消费者] 消息处理成功（异步确认）: dataId=%s", dataId)
                    else:
                        # 业务处理失败：触发重投（Broker 会立即重新投递该消息）
                        self.debeziumReadonlyConsumer.negativeAcknowledge(msg)

                        log.warning("[Pulsar-CDC消费者] 消息处理失败，触发重投: dataId=%s", dataId)

                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    log.exception("[Pulsar-CDC消费者] 消费异常")

                    if msg is not None:
                        try:
                            self.debeziumReadonlyConsumer.negativeAcknowledge(msg)
                        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ackEx) 一致
                            log.exception("[Pulsar-CDC消费者] 负确认异常")

                    try:
                        TimeUnit.SECONDS.sleep(5)
                    except InterruptedException:
                        Thread.currentThread().interrupt()
                        break

            log.info("[Pulsar-CDC消费者] 消费循环已退出")

        self.consumerExecutor.submit(_consumeLoop)

    def processMessage(self, dataId: str, messageJson: str, messageId: MessageId) -> bool:
        """处理单条 CDC 消息（核心业务逻辑，Java 为 private）。

        设计思路（与原 Kafka DebeziumReadonlyKafkaConsumer 等价）：
        1. 解析 JSON：{ operationType, data, source.lsn }
        2. LSN 幂等检查：基于 LSN + dataId 的组合 key
        3. 解析 data 为 OdsRtSzdnSnapshotFlowAddcode 对象
        4. 根据 operationType 分发到 INSERT / UPDATE / DELETE 处理

        :param dataId: 消息 key
        :param messageJson: 消息体
        :param messageId: Pulsar messageId（用于日志）
        :return: True=成功；False=失败
        """
        try:
            # 1. 解析消息 JSON
            messageObj: Optional[JSONObject] = JSONObject.parseObject(messageJson)
            if messageObj is None:
                log.error("[Pulsar-CDC消费者] 消息格式错误: messageJson=%s", messageJson)
                return True

            operationType: Optional[str] = messageObj.getString("operationType")
            dataObj: Any = messageObj.get("data")
            sourceObj: Optional[JSONObject] = messageObj.getJSONObject("source")

            if operationType is None or dataObj is None:
                log.error("[Pulsar-CDC消费者] 消息缺少必要字段: operationType=%s, data=%s",
                          operationType, dataObj)
                return True

            # 2. LSN 幂等检查（CDC 特有，基于 Redis SETNX）
            #    从 source 字段提取 lsn / xid / txId 等可用于去重的标识
            #    如果无 lsn，则退化为按 dataId 去重（与主消费者相同）
            lsn: str = self.extractLsn(sourceObj, dataId)
            idempotentKey = self.CDC_IDEMPOTENT_KEY_PREFIX + lsn

            isNew = self.redisTemplate.opsForValue().setIfAbsent(
                idempotentKey, str(System.currentTimeMillis()),
                self.idempotentTtlSeconds, TimeUnit.SECONDS)

            if isNew is None or not isNew:
                log.info("[Pulsar-CDC消费者] LSN 消息已处理（幂等去重）: lsn=%s, dataId=%s",
                         lsn, dataId)
                return True  # 已处理：直接确认，不重试

            # 3. 解析 data 为业务对象
            flowData: Optional[OdsRtSzdnSnapshotFlowAddcode] = None
            try:
                if isinstance(dataObj, JSONObject):
                    flowData = dataObj.toJavaObject(OdsRtSzdnSnapshotFlowAddcode)
                else:
                    flowData = JSONObject.parseObject(
                        str(dataObj), OdsRtSzdnSnapshotFlowAddcode)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception parseEx) 一致
                log.exception("[Pulsar-CDC消费者] data 解析失败: dataId=%s", dataId)
                return True  # 解析失败：确认丢弃

            if flowData is None:
                log.error("[Pulsar-CDC消费者] flowData 解析为 null: dataId=%s", dataId)
                return True

            # 4. 分发操作类型
            # 【Java→Python】Java 的 case 穿透（"INSERT" 与 "CREATE" 共用一个分支）
            # → Python 用 `in (...)` 元组判断表达。
            operation = operationType.upper()
            if operation in ("INSERT", "CREATE"):   # Debezium 对 MySQL 的 CREATE 操作标识
                return self.handleInsert(flowData, dataId)
            elif operation == "UPDATE":
                return self.handleUpdate(flowData, dataId)
            elif operation == "DELETE":
                return self.handleDelete(dataId)
            else:
                log.warning("[Pulsar-CDC消费者] 未知操作类型: operationType=%s, dataId=%s",
                            operationType, dataId)
                return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar-CDC消费者] processMessage 异常: dataId=%s", dataId)
            return False

    def extractLsn(self, sourceObj: Optional[JSONObject], dataId: str) -> str:
        """从 source 对象中提取 LSN（Log Sequence Number）。

        思路：
        1. LSN 是数据库事务日志的序列号，每个变更事件都有唯一的 LSN
        2. Debezium 对不同数据库使用不同的字段名：
           - PostgreSQL/GaussDB: lsn
           - MySQL: file + pos 组合
           - SQL Server: change_lsn
        3. 如果没有 source 字段，则退化到 dataId 作为去重 key

        :param sourceObj: source 元数据对象（可能为 None）
        :param dataId: 业务数据ID（兜底方案）
        :return: LSN 或 dataId
        """
        if sourceObj is None:
            return dataId  # 无 source：使用 dataId

        # 常见字段名优先级（适配不同数据库的 Debezium 输出）
        # 【Java→Python】`String[]` → tuple；遍历顺序即优先级
        lsnFields = ("lsn", "xid", "txId", "txId", "pos", "change_lsn", "scn")
        for field in lsnFields:
            value: Any = sourceObj.get(field)
            # Java: value != null && !value.toString().isEmpty()
            # 【Java→Python】不能写成 `if value`：数字 0 / False 在 Python 里为假，
            # 但 Java 的 "0"/"false" 都是非空字符串，应视为有效 LSN。
            if value is not None and str(value) != "":
                return str(value)

        # 退化为 dataId
        return dataId

    def handleInsert(self, flowData: OdsRtSzdnSnapshotFlowAddcode, dataId: str) -> bool:
        """处理 INSERT / CREATE：写入 MySQL + 写入 Elasticsearch。

        :param flowData: 业务数据
        :param dataId: 数据ID
        :return: True=成功；False=失败
        """
        try:
            # 写入 MySQL 分表（MyBatis-Plus 自动分表策略）
            dbSuccess: bool = self.snapshotFlowService.saveOrUpdate(flowData)
            if not dbSuccess:
                log.error("[Pulsar-CDC消费者] 写入 MySQL 失败: dataId=%s", dataId)
                return False

            # 写入 Elasticsearch
            esSuccess: bool = self.esService.saveSnapshotFlow(flowData)
            if not esSuccess:
                log.error("[Pulsar-CDC消费者] 写入 Elasticsearch 失败: dataId=%s", dataId)
                return False

            log.info("[Pulsar-CDC消费者] INSERT 操作成功: dataId=%s", dataId)
            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar-CDC消费者] handleInsert 异常: dataId=%s", dataId)
            return False

    def handleUpdate(self, flowData: OdsRtSzdnSnapshotFlowAddcode, dataId: str) -> bool:
        """处理 UPDATE。"""
        try:
            dbSuccess: bool = self.snapshotFlowService.updateById(flowData)
            if not dbSuccess:
                log.warning("[Pulsar-CDC消费者] UPDATE MySQL 失败（记录可能不存在）: dataId=%s", dataId)
                dbSuccess = self.snapshotFlowService.saveOrUpdate(flowData)
                # 【Java→Python】Java 的 `if (!dbSuccess) return false;` 单行写法保持同义
                if not dbSuccess:
                    return False

            esSuccess: bool = self.esService.saveSnapshotFlow(flowData)
            if not esSuccess:
                log.error("[Pulsar-CDC消费者] UPDATE Elasticsearch 失败: dataId=%s", dataId)
                return False

            log.info("[Pulsar-CDC消费者] UPDATE 操作成功: dataId=%s", dataId)
            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar-CDC消费者] handleUpdate 异常: dataId=%s", dataId)
            return False

    def handleDelete(self, dataId: str) -> bool:
        """处理 DELETE。

        【Java→Python】与主消费者不同：这里**忽略**两次删除的返回值，只要不抛异常就算成功。
        """
        try:
            self.snapshotFlowService.removeById(dataId)
            self.esService.deleteSnapshotFlow(dataId)
            log.info("[Pulsar-CDC消费者] DELETE 操作完成: dataId=%s", dataId)
            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar-CDC消费者] handleDelete 异常: dataId=%s", dataId)
            return False
