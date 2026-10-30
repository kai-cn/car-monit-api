# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.SnapshotFlowSyncService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowSyncService.java

抓拍流水同步服务（全量 + 增量）：把 MySQL 中的抓拍流水逐条推送到 Kafka/Pulsar。

【Java→Python 本文件重点差异】
1) `@Service` + 3 个 `@Autowired` → 构造器可选参数；缺省时
   `OdsRtSzdnSnapshotFlowAddcodeMapper()` + `KafkaProducerService()`（后者会顺带组装
   可靠性/丢失检测/延迟监控三个服务，等价 Spring 单例依赖链）+ `defaultRedisTemplate()`。
2) `@Autowired public RedisTemplate redisTemplate;`：原文这个字段是 **public**（其余是 private），
   Python 无访问修饰符，统一作为实例属性暴露。
3) `@Value("${sync.batch-size:1000}") private Integer` / `${sync.full-sync-enabled:true}` Boolean /
   `${sync.incremental-sync-interval:60000}` Long → `Environment.value(..., int/bool/int)`；
   Python 无包装类型，不会出现 null（配置缺失时用占位符默认值）。
4) `private static final String LAST_SYNC_TIME_KEY / LAST_SYNC_ID_KEY` → 类属性（全大写）。
5) `@PostConstruct init()` → `__init__` 末尾显式调用；`Executors.newFixedThreadPool(2)` 起两个
   daemon 线程（Java 线程池线程默认非守护，JVM 退出时由 shutdown hook 收尾）。
6) 方法引用 `this::fullSync` / `this::incrementalSync` → 直接传绑定方法（等价）。
7) MyBatis-Plus 的方法引用列名 `OdsRtSzdnSnapshotFlowAddcode::getBigId`
   → `lambda data: data.big_id`（Wrapper 通过读取实体属性求值）。
8) `wrapper.last("LIMIT " + batchSize)`：Java 的字符串 + Integer 会自动 toString，
   Python **必须显式** `str(self.batchSize)`，否则 TypeError。
9) Redis 强转：`(String) opsForValue().get(...)` / `(Date) opsForValue().get(...)`
   → Python 无需强转（值就是存入时的对象；替身用 deepcopy 模拟序列化隔离）。
   若 key 不存在，返回 None（对应 Java 的 null）。
10) `new Date()` → `datetime.now()`；`DateUtils.addDays(date, -1)` 同名方法。
11) `catch (Exception e)` 包住整个循环体（含 `Thread.sleep`）：这里同样如此，
    因此全量同步被中断时走的是“全量同步异常”分支（与原文一致，不是 InterruptedException 分支）。
12) 日志占位符 `{}` → `%s`；`log.error(msg, e)` → `log.exception(msg)`。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper import LambdaQueryWrapper
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.base.service.impl.KafkaProducerService import KafkaProducerService
from com.ruoyi.common.utils.DateUtils import DateUtils
from java.lang.Thread import InterruptedException, Thread
from java.util.concurrent.ExecutorService import ExecutorService
from java.util.concurrent.Executors import Executors
from org.springframework.core.env.Environment import Environment
from org.springframework.data.redis.core.RedisTemplate import RedisTemplate, defaultRedisTemplate

__all__ = ["SnapshotFlowSyncService"]

log = logging.getLogger(__name__)


class SnapshotFlowSyncService(object):
    """抓拍流水全量/增量同步服务（`@Service`）。"""

    # Redis 中记录“上次同步位置”的两个 key
    LAST_SYNC_TIME_KEY = "snapshot_flow:last_sync_time"
    LAST_SYNC_ID_KEY = "snapshot_flow:last_sync_id"

    def __init__(self,
                 snapshotFlowMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 kafkaProducerService: Optional[KafkaProducerService] = None,
                 redisTemplate: Optional[RedisTemplate] = None,
                 environment: Optional[Environment] = None) -> None:
        env = environment or Environment()

        self.snapshotFlowMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotFlowMapper or OdsRtSzdnSnapshotFlowAddcodeMapper())
        # 【Java→Python】缺省时新建一个 KafkaProducerService（Spring 里是唯一单例 Bean）
        self.kafkaProducerService: KafkaProducerService = (
            kafkaProducerService or KafkaProducerService())
        self.redisTemplate: RedisTemplate = redisTemplate or defaultRedisTemplate()

        # 每批同步数量，默认 1000
        self.batchSize: int = env.value("${sync.batch-size:1000}", int)
        # 是否启用全量同步，默认 true
        self.fullSyncEnabled: bool = env.value("${sync.full-sync-enabled:true}", bool)
        # 增量同步间隔（毫秒），默认 60000
        self.incrementalSyncInterval: int = env.value("${sync.incremental-sync-interval:60000}", int)

        # 同步线程池（固定 2 个线程：全量 + 增量）
        self.syncExecutor: Optional[ExecutorService] = None

        self.init()  # @PostConstruct

    def init(self) -> None:
        """初始化：启动全量（可关）与增量同步线程（`@PostConstruct`）。"""
        self.syncExecutor = Executors.newFixedThreadPool(2)

        if self.fullSyncEnabled:
            # Java: syncExecutor.submit(this::fullSync)
            self.syncExecutor.submit(self.fullSync)

        # Java: syncExecutor.submit(this::incrementalSync)
        self.syncExecutor.submit(self.incrementalSync)

    def fullSync(self) -> None:
        """全量同步方法：处理历史300G数据。

        思路：按主键ID分页，每次同步一批数据，确保不遗漏任何记录
        目的：将历史数据完整推送到Kafka，支持断点续传
        """
        log.info("开始全量同步数据")
        try:
            # 从Redis获取上次同步的最后一条ID，支持断点续传
            # 【Java→Python】原文是 `(String) get(...)`，Python 无需强转；key 不存在返回 None
            lastSyncId = self.redisTemplate.opsForValue().get(self.LAST_SYNC_ID_KEY)

            while True:
                # 创建MyBatis-Plus查询条件构造器
                wrapper = LambdaQueryWrapper()

                # 如果不是第一次同步，从上次同步的ID之后继续查询，避免重复
                if lastSyncId is not None:
                    # Java: wrapper.gt(OdsRtSzdnSnapshotFlowAddcode::getBigId, lastSyncId)
                    wrapper.gt(lambda data: data.big_id, lastSyncId)

                # 按主键ID升序排列，确保数据顺序一致
                wrapper.orderByAsc(lambda data: data.big_id)
                # 限制每批查询数量，防止一次性查询过多数据导致内存溢出
                # 【Java→Python】`"LIMIT " + batchSize` 隐式 toString → 这里必须 str(...)
                wrapper.last("LIMIT " + str(self.batchSize))

                # 执行分页查询
                dataList: List[OdsRtSzdnSnapshotFlowAddcode] = \
                    self.snapshotFlowMapper.selectList(wrapper)

                # 如果查询结果为空，说明全量同步已完成
                if dataList is None or len(dataList) == 0:
                    log.info("全量同步完成")
                    break

                # 遍历每一条数据，发送到Kafka
                for data in dataList:
                    # 发送数据到Kafka，消息key使用bigId确保分区有序
                    self.kafkaProducerService.sendSnapshotFlowData(data, data.getBigId())
                    # 更新当前批次的最后一条ID
                    lastSyncId = data.getBigId()

                # 将当前进度保存到Redis，支持服务重启后继续同步
                self.redisTemplate.opsForValue().set(self.LAST_SYNC_ID_KEY, lastSyncId)
                log.info("已同步 %s 条数据，当前进度: %s", len(dataList), lastSyncId)

                # 暂停100毫秒，避免对数据库造成过大压力
                Thread.sleep(100)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 【Java→Python】注意：InterruptedException 也在这里被捕获（原文如此），
            # 不会走 incrementalSync 那种“中断后 break”的分支。
            log.exception("全量同步异常")

    def incrementalSync(self) -> None:
        """增量同步方法：处理每日新增的50万条数据。

        思路：基于抓拍时间(snapshottime)进行时间窗口查询，定期拉取新增数据
        目的：实时推送新产生的抓拍数据到Kafka，确保消费端能及时获取最新数据
        """
        log.info("开始增量同步数据")
        while True:
            try:
                # 从Redis获取上次同步的时间点
                # 【Java→Python】`(Date) get(...)` → 无需强转；存入的就是 datetime
                lastSyncTime: Optional[datetime] = \
                    self.redisTemplate.opsForValue().get(self.LAST_SYNC_TIME_KEY)
                # 获取当前时间作为本次同步的截止时间
                currentTime = datetime.now()

                # 如果是第一次增量同步，从1天前开始同步，防止遗漏数据
                if lastSyncTime is None:
                    lastSyncTime = DateUtils.addDays(currentTime, -1)

                # 创建查询条件构造器
                wrapper = LambdaQueryWrapper()
                # 查询抓拍时间大于上次同步时间的记录（新数据）
                wrapper.gt(lambda data: data.snapshottime, lastSyncTime)
                # 查询抓拍时间小于等于当前时间的记录（防止未来数据）
                wrapper.le(lambda data: data.snapshottime, currentTime)
                # 按抓拍时间升序排列，确保数据按时间顺序推送
                wrapper.orderByAsc(lambda data: data.snapshottime)
                # 限制每批查询数量（同样需要显式 str）
                wrapper.last("LIMIT " + str(self.batchSize))

                # 执行查询获取新增数据
                dataList: List[OdsRtSzdnSnapshotFlowAddcode] = \
                    self.snapshotFlowMapper.selectList(wrapper)

                # 如果有新增数据，则发送到Kafka
                if dataList is not None and len(dataList) > 0:
                    for data in dataList:
                        # 发送数据到Kafka
                        self.kafkaProducerService.sendSnapshotFlowData(data, data.getBigId())
                        # 更新同步时间为当前记录的抓拍时间
                        if data.getSnapshottime() is not None:
                            lastSyncTime = data.getSnapshottime()

                    # 将本次同步的时间点保存到Redis
                    self.redisTemplate.opsForValue().set(
                        self.LAST_SYNC_TIME_KEY, lastSyncTime)
                    log.info("增量同步 %s 条数据，同步时间: %s", len(dataList), lastSyncTime)

                # 等待配置的间隔时间后再次同步
                Thread.sleep(self.incrementalSyncInterval)
            except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                log.exception("增量同步异常")
                try:
                    Thread.sleep(self.incrementalSyncInterval)
                except InterruptedException:
                    # 如果被中断，退出循环
                    Thread.currentThread().interrupt()
                    break
