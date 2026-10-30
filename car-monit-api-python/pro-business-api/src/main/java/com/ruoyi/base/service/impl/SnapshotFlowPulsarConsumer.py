# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.SnapshotFlowPulsarConsumer

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowPulsarConsumer.java

门架抓拍流水 Pulsar 消费者服务（原注释保留）

功能说明（与原 SnapshotFlowKafkaConsumerV2 等价替换）：
- 消费 ods-rt-szdn-snapshot-flow 主题的 JSON 消息
- 将数据写入 MySQL 分表（ods_rt_szdn_snapshot_flow_addcode）
- 将数据同步写入 Elasticsearch（多字段模糊查询）
- 提供幂等性保证（基于 dataId + Redis SETNX）

消息格式（与生产者约定，必须一致）：
  {
    "operationType": "INSERT",        // 操作类型：INSERT / UPDATE / DELETE
    "data": { ... }                   // OdsRtSzdnSnapshotFlowAddcode 对象 JSON
  }

Pulsar 消费者模型说明（与 Kafka 的关键区别）：
-----------------------------------------------------------------------------
Kafka 机制                Pulsar 机制
-----------------------------------------------------------------------------
ConsumerRecords<>         Message<String> 流
record.offset()           message.getMessageId()
consumer.commitSync()     consumer.acknowledge(message)
consumer.seek(offset)     consumer.seek(messageId) / consumer.seekByTime()
@KafkaListener            while(true) { consumer.receive() } 或 MessageListener
-----------------------------------------------------------------------------

可靠性保证：
1. 手动确认（acknowledge）：业务处理完成后才确认消息
2. 消息重投（negativeAcknowledge）：业务处理失败时触发重投
3. 死信队列（DLQ）：超过 max-retry-times 次的消息自动路由到 DLQ
4. 业务幂等：Redis SETNX 记录 dataId，避免重复处理

【Java→Python 本文件重点差异】
1) 原类上的 `@Service` 同样是**被注释掉的**（`//@Service`），Spring 不会实例化它。
   Python 侧按正常服务类实现，并在 `__init__` 末尾执行 `init()` 启动消费循环
   （等价 `@PostConstruct`）。
2) `@Autowired Consumer<String>` → 构造器可选参数；缺省时按
   `PulsarConsumerConfig.snapshotFlowConsumer()` 的配置造一个 Consumer 替身
   （同 topic + 同 subscriptionName）。
3) `@Autowired IEsService esService`：**Java 工程里没有任何 IEsService 实现类**，
   属于原代码缺失的 Bean。Python 侧缺省注入 `_UnimplementedEsService`（调用即抛错），
   使 `handleInsert/handleUpdate` 的 catch 分支（返回 false → 重投）能如实复现；
   真正运行时请显式注入实现。
4) `@Autowired StringRedisTemplate` → `defaultStringRedisTemplate()`（与 RedisTemplate
   共享同一份进程内 Redis）。
5) `@Value("${spring.pulsar.idempotent-ttl-seconds:86400}") private long`
   → `Environment.value(..., int)`（Python 无 long/int 之分）。
6) `private static final String IDEMPOTENT_KEY_PREFIX` → 类属性（全大写）；
   Java 的 static final 是“编译期常量”，Python 只是约定，运行期可改。
7) `@PostConstruct init()` → `__init__` 末尾显式调用；`@PreDestroy destroy()` → 普通方法。
8) `while (!Thread.currentThread().isInterrupted())` → 同形写法（替身用线程本地中断标志）；
   `TimeUnit.SECONDS.sleep(5)` → 替身同名方法（中断时抛 InterruptedException）。
9) `Boolean isNew`（包装类型，可能为 null）→ Python 的 `True/False/None` 均可出现；
   原判断 `isNew == null || !isNew` 写成 `is_new is None or not is_new`。
10) `String.valueOf(System.currentTimeMillis())` → `str(System.currentTimeMillis())`。
11) `switch (operationType.toUpperCase())`（Java 7+ 字符串 switch）→ if/elif 链；
    Java 的 `String.toUpperCase()` → Python `str.upper()`（本工程消息均为 ASCII 操作类型）。
12) `dataObj instanceof JSONObject` → `isinstance(dataObj, JSONObject)`；
    强转 `(JSONObject) dataObj` 在 Python 无需转换。
    `dataObj.toString()` → `str(dataObj)`：JSONObject 的 str 是 Python 字典字面量
    （单引号），与 Java 的 JSON 文本不同 —— 该分支只在 data 不是对象时进入（本工程不出现）。
13) `long startTime` 在原文中**声明后从未使用**（疑似遗留的耗时统计），按一比一保留。
14) 日志占位符 `{}` → logging 的 `%s`；`log.error(msg, e)` → `log.exception(msg)`。
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

__all__ = ["SnapshotFlowPulsarConsumer"]

log = logging.getLogger(__name__)


class _UnimplementedEsService(IEsService):
    """缺省占位：对应“Java 工程里 IEsService 没有实现类”的事实。

    【Java→Python】Java 侧是注入失败（Bean 不存在）→ 容器启动报错；
    Python 侧退化为“调用即抛异常”，让消费循环走 `catch (Exception) → return false`
    的重投分支，避免静默丢数据。真正使用时应注入 `IEsServiceImpl` 之类的实现。
    """

    def saveSnapshotFlow(self, flowData: OdsRtSzdnSnapshotFlowAddcode) -> bool:
        raise RuntimeError("com.ruoyi.base.service.IEsService 没有实现类（原工程未提供 Bean）")

    def deleteSnapshotFlow(self, dataId: str) -> bool:
        raise RuntimeError("com.ruoyi.base.service.IEsService 没有实现类（原工程未提供 Bean）")


class SnapshotFlowPulsarConsumer(object):
    """门架抓拍流水 Pulsar 消费者（`//@Service` → 普通类，由调用方决定是否注册）。"""

    # Redis 幂等性 Key 前缀（Java: private static final String）
    IDEMPOTENT_KEY_PREFIX = "pulsar:msg:processed:"

    def __init__(self,
                 snapshotFlowConsumer: Optional[Consumer] = None,
                 snapshotFlowService: Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 esService: Optional[IEsService] = None,
                 redisTemplate: Any = None,
                 environment: Optional[Environment] = None) -> None:
        env = environment or Environment()

        # 注入 Pulsar 字符串消息消费者（对应 PulsarConsumerConfig#snapshotFlowConsumer）
        # 【Java→Python】缺省时按同一配置造替身：同 topic、同 subscriptionName
        self.snapshotFlowConsumer: Consumer = snapshotFlowConsumer if snapshotFlowConsumer is not None else Consumer(
            topic=env.value("${spring.pulsar.topic:persistent://public/default/ods-rt-szdn-snapshot-flow}", str),
            subscription_name=env.value(
                "${spring.pulsar.subscription-name:ods-rt-szdn-snapshot-flow-sub}", str),
        )
        # 业务服务：写入 MySQL 分表
        self.snapshotFlowService: IOdsRtSzdnSnapshotFlowAddcodeService = (
            snapshotFlowService if snapshotFlowService is not None
            else OdsRtSzdnSnapshotFlowAddcodeServiceImpl())
        # 业务服务：写入 Elasticsearch
        self.esService: IEsService = esService if esService is not None else _UnimplementedEsService()
        # Redis 辅助工具（幂等性）
        self.redisTemplate = redisTemplate or defaultStringRedisTemplate()

        # 幂等性过期时间（秒）：默认 1 天
        # 【Java→Python】`long` → int
        self.idempotentTtlSeconds: int = env.value(
            "${spring.pulsar.idempotent-ttl-seconds:86400}", int)

        # 消费线程池（@PostConstruct 中创建）
        self.consumerExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    def init(self) -> None:
        """初始化消费者（Spring Bean 初始化后启动）。

        思路：
        1. 创建一个单线程线程池
        2. 调用 startConsume() 启动消费循环
        3. 与原 Kafka @PostConstruct 行为保持一致
        """
        self.consumerExecutor = Executors.newSingleThreadExecutor()
        self.startConsume()
        log.info("[Pulsar快照消费者] 初始化完成，开始消费主题")

    def destroy(self) -> None:
        """销毁消费者（`@PreDestroy`）。

        思路：
        1. 关闭消费线程池
        2. 关闭 Pulsar Consumer（释放与 Broker 的连接）
        """
        log.info("[Pulsar快照消费者] 正在关闭...")
        if self.consumerExecutor is not None:
            self.consumerExecutor.shutdownNow()
        try:
            if self.snapshotFlowConsumer is not None:
                self.snapshotFlowConsumer.close()
                log.info("[Pulsar快照消费者] Consumer 已关闭")
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar快照消费者] 关闭异常")

    def startConsume(self) -> None:
        """启动消费循环（与原 Kafka @KafkaListener 等价）。

        思路：
        1. 使用 consumerExecutor.submit() 提交一个后台循环任务
        2. while(true) 循环中调用 consumer.receive() 阻塞获取消息
        3. 收到消息后：
           - 解析 JSON，提取 operationType 和 data
           - 检查幂等性（Redis SETNX）
           - 调用 processMessage() 处理业务
           - 成功：consumer.acknowledge(msg) 确认
           - 失败：consumer.negativeAcknowledge(msg) 触发重投
        4. 捕获异常：避免单条消息处理失败导致整个循环退出
        """

        def _consumeLoop() -> None:
            log.info("[Pulsar快照消费者] 消费循环已启动")

            while not Thread.currentThread().isInterrupted():
                # 【Java→Python】`Message<String> msg = null;` 必须在 try 之外声明，
                # 使 catch 分支能判断“异常发生时是否已经取到消息”。
                msg: Optional[Message] = None
                try:
                    # 阻塞接收下一条消息（等效于 Kafka consumer.poll()）
                    msg = self.snapshotFlowConsumer.receive()

                    if msg is None:
                        continue

                    # 提取消息元数据
                    messageId: MessageId = msg.getMessageId()
                    dataId: str = msg.getKey()          # 与 producer.newMessage().key() 对应
                    messageJson: str = msg.getValue()   # JSON 字符串消息体

                    # 处理消息（同步处理 + 明确确认）
                    success = self.processMessage(dataId, messageJson)

                    if success:
                        # 业务处理成功：手动确认消息（= Kafka consumer.commitSync()）
                        self.snapshotFlowConsumer.acknowledge(msg)

                        log.info("[Pulsar快照消费者] 消息处理成功并确认: dataId=%s, messageId=%s",
                                 dataId, messageId)
                    else:
                        # 业务处理失败（如数据库/ES 不可用）：触发重投
                        self.snapshotFlowConsumer.negativeAcknowledge(msg)

                        log.warning("[Pulsar快照消费者] 消息处理失败，触发重投: dataId=%s", dataId)

                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    # 其他异常：记录日志，继续下一条（避免死循环）
                    log.exception("[Pulsar快照消费者] 消费异常，跳过当前消息")

                    # 如果消息存在且未确认，触发负确认让 Broker 重投
                    if msg is not None:
                        try:
                            self.snapshotFlowConsumer.negativeAcknowledge(msg)
                        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ackEx) 一致
                            log.exception("[Pulsar快照消费者] 负确认异常")

                    # 短暂休眠，避免异常时 CPU 跑满
                    try:
                        TimeUnit.SECONDS.sleep(5)
                    except InterruptedException:
                        Thread.currentThread().interrupt()
                        break

            log.info("[Pulsar快照消费者] 消费循环已退出")

        self.consumerExecutor.submit(_consumeLoop)

    def processMessage(self, dataId: str, messageJson: str) -> bool:
        """处理单条消息（核心业务逻辑，Java 为 private）。

        思路（与原 Kafka 消费者完全一致）：
        1. 解析 JSON：{ operationType, data }
        2. 幂等性检查：Redis SETNX 标记 dataId
        3. 解析 data 为 OdsRtSzdnSnapshotFlowAddcode 对象
        4. 根据 operationType 执行对应的操作：
           - INSERT：写入 MySQL 分表 + 写入 Elasticsearch
           - UPDATE：更新 MySQL + 更新 Elasticsearch（按 dataId）
           - DELETE：删除 MySQL 记录 + 删除 Elasticsearch 文档

        :param dataId: 消息 key（业务数据ID）
        :param messageJson: 消息体（JSON 字符串）
        :return: True=处理成功；False=处理失败（触发重投）
        """
        # 【Java→Python】原文的 `long startTime` 声明后未使用，保留以逐行对照
        startTime: int = System.currentTimeMillis()  # noqa: F841

        try:
            # 1. 解析消息 JSON
            # 格式校验：必须包含 operationType 和 data 两个字段
            # 【Java→Python】messageJson 为 null 时返回 None；非法 JSON 则抛异常（与 fastjson 一致），
            # 由外层 catch 返回 False → 触发重投。
            messageObj: Optional[JSONObject] = JSONObject.parseObject(messageJson)
            if messageObj is None:
                log.error("[Pulsar快照消费者] 消息格式错误: messageJson=%s", messageJson)
                return True  # 格式错误的消息：直接确认丢弃，不重试

            operationType: Optional[str] = messageObj.getString("operationType")
            dataObj: Any = messageObj.get("data")

            if operationType is None or dataObj is None:
                log.error("[Pulsar快照消费者] 消息缺少必要字段: operationType=%s, data=%s",
                          operationType, dataObj)
                return True  # 缺失字段：确认丢弃，不重试

            # 2. 幂等性检查（Redis SETNX）
            # 设计：key = pulsar:msg:processed:{dataId}，值=时间戳
            # - 如果 SETNX 返回 true：首次处理，执行业务
            # - 如果 SETNX 返回 false：重复消息，直接确认跳过
            idempotentKey = self.IDEMPOTENT_KEY_PREFIX + dataId
            isNew = self.redisTemplate.opsForValue().setIfAbsent(
                idempotentKey, str(System.currentTimeMillis()),
                self.idempotentTtlSeconds, TimeUnit.SECONDS)

            # 【Java→Python】Java 的 Boolean 可能为 null；Python 用 None 表达同一状态
            if isNew is None or not isNew:
                log.info("[Pulsar快照消费者] 消息已处理（幂等去重）: dataId=%s", dataId)
                return True  # 已处理过：确认跳过，不重试

            # 3. 解析 data 为业务实体对象
            flowData: Optional[OdsRtSzdnSnapshotFlowAddcode] = None
            try:
                if isinstance(dataObj, JSONObject):
                    # Java: ((JSONObject) dataObj).toJavaObject(OdsRtSzdnSnapshotFlowAddcode.class)
                    flowData = dataObj.toJavaObject(OdsRtSzdnSnapshotFlowAddcode)
                else:
                    flowData = JSONObject.parseObject(
                        str(dataObj), OdsRtSzdnSnapshotFlowAddcode)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception parseEx) 一致
                log.exception("[Pulsar快照消费者] data 字段解析失败: dataId=%s", dataId)
                return True  # 解析失败：确认丢弃，避免重试死循环

            if flowData is None:
                log.error("[Pulsar快照消费者] flowData 解析为 null: dataId=%s", dataId)
                return True

            # 4. 执行操作（与原 Kafka processMessage 逻辑一致）
            #    根据 operationType 分发到不同的处理路径
            # 【Java→Python】`switch (operationType.toUpperCase())` → if/elif 链
            operation = operationType.upper()
            if operation == "INSERT":
                return self.handleInsert(flowData, dataId)
            elif operation == "UPDATE":
                return self.handleUpdate(flowData, dataId)
            elif operation == "DELETE":
                return self.handleDelete(dataId)
            else:
                log.warning("[Pulsar快照消费者] 未知操作类型: operationType=%s, dataId=%s",
                            operationType, dataId)
                return True  # 未知类型：确认丢弃，不重试

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar快照消费者] processMessage 异常: dataId=%s", dataId)
            return False  # 异常：返回 false，触发重投

    def handleInsert(self, flowData: OdsRtSzdnSnapshotFlowAddcode, dataId: str) -> bool:
        """处理 INSERT 操作：写入 MySQL 分表 + 写入 Elasticsearch。

        :param flowData: 业务数据实体
        :param dataId: 业务数据ID（消息 key）
        :return: True=成功；False=失败（触发重投）
        """
        try:
            # 1. 写入 MySQL 分表（MyBatis-Plus 自动按日期分表策略）
            dbSuccess: bool = self.snapshotFlowService.saveOrUpdate(flowData)

            if not dbSuccess:
                log.error("[Pulsar快照消费者] 写入 MySQL 失败: dataId=%s", dataId)
                return False  # 返回 false，触发消息重投

            # 2. 写入 Elasticsearch
            #    ES 的 saveSnapshotFlow 方法内部会捕获异常并返回 true/false
            esSuccess: bool = self.esService.saveSnapshotFlow(flowData)

            if not esSuccess:
                log.error("[Pulsar快照消费者] 写入 Elasticsearch 失败: dataId=%s", dataId)
                return False  # ES 失败：返回 false，触发重投

            log.info("[Pulsar快照消费者] INSERT 操作成功: dataId=%s", dataId)
            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar快照消费者] handleInsert 异常: dataId=%s", dataId)
            return False

    def handleUpdate(self, flowData: OdsRtSzdnSnapshotFlowAddcode, dataId: str) -> bool:
        """处理 UPDATE 操作：更新 MySQL + 更新 Elasticsearch。

        :param flowData: 业务数据实体（已包含更新后的值）
        :param dataId: 业务数据ID
        :return: True=成功；False=失败
        """
        try:
            # 1. 更新 MySQL
            dbSuccess: bool = self.snapshotFlowService.updateById(flowData)

            if not dbSuccess:
                log.warning("[Pulsar快照消费者] UPDATE MySQL 失败（记录可能不存在）: dataId=%s", dataId)
                # 记录不存在时：转为 INSERT，避免丢失更新
                dbSuccess = self.snapshotFlowService.saveOrUpdate(flowData)
                if not dbSuccess:
                    return False

            # 2. 更新 Elasticsearch（按 dataId 作为文档 ID）
            esSuccess: bool = self.esService.saveSnapshotFlow(flowData)

            if not esSuccess:
                log.error("[Pulsar快照消费者] UPDATE Elasticsearch 失败: dataId=%s", dataId)
                return False

            log.info("[Pulsar快照消费者] UPDATE 操作成功: dataId=%s", dataId)
            return True

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar快照消费者] handleUpdate 异常: dataId=%s", dataId)
            return False

    def handleDelete(self, dataId: str) -> bool:
        """处理 DELETE 操作：删除 MySQL 记录 + 删除 Elasticsearch 文档。

        :param dataId: 业务数据ID
        :return: True=成功；False=失败
        """
        try:
            # 1. 从 MySQL 删除
            dbSuccess: bool = self.snapshotFlowService.removeById(dataId)
            if not dbSuccess:
                log.warning("[Pulsar快照消费者] DELETE MySQL 失败（记录可能不存在）: dataId=%s", dataId)

            # 2. 从 Elasticsearch 删除
            esSuccess: bool = self.esService.deleteSnapshotFlow(dataId)
            if not esSuccess:
                log.warning("[Pulsar快照消费者] DELETE Elasticsearch 失败（文档可能不存在）: dataId=%s", dataId)

            log.info("[Pulsar快照消费者] DELETE 操作完成: dataId=%s", dataId)
            return True  # 即使两边都不存在也视为成功（幂等）

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.exception("[Pulsar快照消费者] handleDelete 异常: dataId=%s", dataId)
            return False
