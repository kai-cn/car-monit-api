# -*- coding: utf-8 -*-
"""com.ruoyi.mq.producer.RocketMqProducer

源文件：pro-business-api/src/main/java/com/ruoyi/mq/producer/RocketMqProducer.java

【Java→Python】关键差异
1) ``@Value("${rocketmq.topic.snapshot-flow:topic_snapshot_flow}")``
   → ``Environment().value("${rocketmq.topic.snapshot-flow:topic_snapshot_flow}")``。
   注意 application.yml 里**没有** ``rocketmq.topic.snapshot-flow``，所以实际取到的是
   注解里的默认值 ``topic_snapshot_flow``（与 Java 行为一致）。
2) ``ExecutorService executorService = Executors.newFixedThreadPool(4)``
   → ``Executors.newFixedThreadPool(4)``；``@PreDestroy`` → ``destroy()``，
   Python 侧没有容器生命周期回调，需要调用方显式调用（或在 ``__del__`` 里兜底）。
3) ``System.currentTimeMillis()`` → ``System.currentTimeMillis()``（java.lang.System 替身）；
   耗时 ``long duration = ...`` → Python ``int``。
4) ``"SEND_OK".equals(result.getSendStatus().name())``
   → ``"SEND_OK" == result.getSendStatus().name``：
   **Java 的枚举 ``name()`` 是方法，Python 的 ``Enum.name`` 是属性**，
   去掉括号即可（见 SendStatus.py）。
5) ``jsonData.getBytes(StandardCharsets.UTF_8)``
   → ``jsonData.encode(StandardCharsets.UTF_8)``（str → bytes）。
6) ``redisCache.getCacheObject(key)`` 未命中时 Java 返回 null → Python 返回 ``None``；
   三元表达式 ``lastSyncTime != null ? lastSyncTime : "2024-01-01 00:00:00"``
   → ``... if ... is not None else ...``（用 ``is not None`` 而非真值判断，
   避免空字符串被误判为未命中）。
7) ``import static com.ruoyi.common.utils.DateUtils.formatHour`` 在原工程中**从未使用**。
   Java 的静态导入把成员直接引入当前类作用域，Python 没有等价语法；而
   ``formatHour`` 在替身里是 ``DateUtils`` 的 ``@staticmethod``（不是模块级函数），
   不能 ``from ... import formatHour``。因此用模块级别名 ``formatHour = DateUtils.formatHour``
   保留“静态导入”的痕迹，同样保持未使用（``# noqa: F401``）。
8) ``log.error("...", data.getId(), e)``（末参为异常）→ ``exc_info=True``。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService import IOdsRtSzdnSnapshotFlowAddcodeService
from com.ruoyi.base.service.impl.OdsRtSzdnSnapshotFlowAddcodeServiceImpl import OdsRtSzdnSnapshotFlowAddcodeServiceImpl
from com.ruoyi.common.core.redis.RedisCache import RedisCache
from com.ruoyi.common.utils.DateUtils import DateUtils
from java.lang.System import System
from java.nio.charset.StandardCharsets import StandardCharsets
from java.time.LocalDateTime import LocalDateTime
from java.time.format.DateTimeFormatter import DateTimeFormatter
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from org.apache.rocketmq.client.producer.DefaultMQProducer import DefaultMQProducer
from org.apache.rocketmq.client.producer.SendResult import SendResult
from org.apache.rocketmq.common.message.Message import Message
from org.springframework.core.env.Environment import Environment

log = logging.getLogger(__name__)

# 【Java→Python】对应原工程的 `import static com.ruoyi.common.utils.DateUtils.formatHour;`：
# 静态导入无法用 import 语句表达（formatHour 是 DateUtils 的 @staticmethod），改用别名绑定，
# 并在下方方法体内保持“未使用”状态（与 Java 完全一致）。
formatHour = DateUtils.formatHour  # noqa: F401 - 原工程静态导入但未使用


class RocketMqProducer(object):
    """RocketMQ 生产者：从 GaussDB 读取数据并发送到消息队列（全量/增量）。"""

    def __init__(self,
                 producer: Optional[DefaultMQProducer] = None,
                 snapshotFlowAddcodeService: Optional[IOdsRtSzdnSnapshotFlowAddcodeService] = None,
                 redisCache: Optional[RedisCache] = None,
                 environment: Optional[Environment] = None) -> None:
        # 【Java→Python】@Value 注入 → 构造器解析（默认值写在占位符内）
        env = environment or Environment()
        self.topic = env.value("${rocketmq.topic.snapshot-flow:topic_snapshot_flow}")
        self.producer = producer or DefaultMQProducer()
        self.snapshotFlowAddcodeService = snapshotFlowAddcodeService \
            or OdsRtSzdnSnapshotFlowAddcodeServiceImpl()
        self.redisCache = redisCache or RedisCache()
        self.executorService: ExecutorService = Executors.newFixedThreadPool(4)
        log.info("[RocketMQ生产者] 初始化完成")

    # ------------------------------------------------------------------ 生命周期
    def destroy(self) -> None:
        """对应 ``@PreDestroy destroy()``：关闭线程池。"""
        self.executorService.shutdown()
        log.info("[RocketMQ生产者] 线程池关闭")

    # ------------------------------------------------------------------ 全量同步
    def syncFullData(self) -> None:
        """全量数据同步（游标分页查询 GaussDB 全量数据）。"""
        log.info("[RocketMQ生产者] 开始全量数据同步")
        startTime = System.currentTimeMillis()

        # 获取最大snapshottime作为游标终点
        maxSnapshotTime = self.snapshotFlowAddcodeService.getMaxSnapshotTime()
        if maxSnapshotTime is None or maxSnapshotTime == "":
            log.warning("[RocketMQ生产者] 未找到最大snapshottime，跳过全量同步")
            return

        currentCursor = "2000-01-01 00:00:00"
        pageSize = 1000
        totalCount = 0

        while currentCursor != maxSnapshotTime:
            # Java: final String cursor = currentCursor;
            # 该局部变量在 Java 里是为了让 lambda/匿名类捕获 effectively-final 值；
            # Python 直接使用 currentCursor 即可（没有该限制），保留语义注释。
            cursor = currentCursor

            # 查询当前游标范围内的数据
            batch: List[OdsRtSzdnSnapshotFlowAddcode] = \
                self.snapshotFlowAddcodeService.queryByCursor(
                    cursor, maxSnapshotTime, pageSize)

            if not batch:
                break

            # 更新游标为最后一条数据的时间
            currentCursor = DateUtils.parseDateToStr(
                DateUtils.YYYY_MM_DD_HH_MM_SS,
                batch[len(batch) - 1].getSnapshottime())

            # 批量发送消息
            self.sendBatchMessages(batch)
            totalCount += len(batch)

            log.info("[RocketMQ生产者] 全量同步进度: 已发送 %s 条数据", totalCount)

        duration = System.currentTimeMillis() - startTime
        log.info("[RocketMQ生产者] 全量数据同步完成, 共发送 %s 条, 耗时 %sms",
                 totalCount, duration)

    # ------------------------------------------------------------------ 增量同步
    def syncIncrementalData(self) -> None:
        """增量数据同步（定时任务调用）。"""
        log.info("[RocketMQ生产者] 开始增量数据同步")

        # 从Redis获取上次同步时间
        lastSyncTime = self.getLastSyncTime()
        currentTime = LocalDateTime.now().format(
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))

        # 查询增量数据
        batch = self.snapshotFlowAddcodeService.queryByCursor(
            lastSyncTime, currentTime, 1000)

        if batch:
            self.sendBatchMessages(batch)
            # 更新上次同步时间
            self.updateLastSyncTime(currentTime)
            log.info("[RocketMQ生产者] 增量同步完成, 发送 %s 条数据", len(batch))
        else:
            log.info("[RocketMQ生产者] 增量同步: 无新数据")

    # ------------------------------------------------------------------ 发送
    def sendBatchMessages(self, dataList: List[OdsRtSzdnSnapshotFlowAddcode]) -> None:
        """批量发送消息（同步发送保证可靠性）。"""
        for data in dataList:
            try:
                jsonData = JSON.toJSONString(data)
                message = Message(
                    self.topic,
                    "snapshot_flow",
                    str(data.getId()),
                    # Java: jsonData.getBytes(StandardCharsets.UTF_8)
                    jsonData.encode(StandardCharsets.UTF_8)
                )

                # 发送消息
                result: SendResult = self.producer.send(message)

                # Java: "SEND_OK".equals(result.getSendStatus().name())
                #   → Python: 枚举 name 是属性，不是方法
                if "SEND_OK" == result.getSendStatus().name:
                    log.debug("[RocketMQ生产者] 消息发送成功, msgId=%s, queueId=%s",
                              result.getMsgId(),
                              result.getMessageQueue().getQueueId())
                else:
                    log.error("[RocketMQ生产者] 消息发送失败, msgId=%s, status=%s",
                              result.getMsgId(), result.getSendStatus())
                    # 发送失败，写入本地备份
                    self.writeToLocalBackup(data)
            except Exception:  # noqa: BLE001 - Java 捕获 Exception
                log.error("[RocketMQ生产者] 发送消息异常, dataId=%s",
                          data.getId(), exc_info=True)
                # 写入本地备份，后续通过定时任务重试
                self.writeToLocalBackup(data)

    def writeToLocalBackup(self, data: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """将失败消息写入本地备份（原工程仅为日志占位实现）。"""
        # 实现本地文件备份逻辑（简化实现，实际项目中应写入可靠存储）
        log.warning("[RocketMQ生产者] 消息写入本地备份, dataId=%s", data.getId())

    # ------------------------------------------------------------------ 同步位点
    def getLastSyncTime(self) -> str:
        """从 Redis 获取上次同步时间。"""
        key = "mq:sync:lastSyncTime"
        lastSyncTime = self.redisCache.getCacheObject(key)
        return lastSyncTime if lastSyncTime is not None else "2024-01-01 00:00:00"

    def updateLastSyncTime(self, time: str) -> None:
        """更新 Redis 中的同步时间。"""
        key = "mq:sync:lastSyncTime"
        self.redisCache.setCacheObject(key, time)
