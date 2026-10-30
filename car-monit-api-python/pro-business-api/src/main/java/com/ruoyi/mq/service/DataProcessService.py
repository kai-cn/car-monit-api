# -*- coding: utf-8 -*-
"""com.ruoyi.mq.service.DataProcessService

源文件：pro-business-api/src/main/java/com/ruoyi/mq/service/DataProcessService.java

【Java→Python】关键差异
1) ``@Transactional(rollbackFor = Exception.class)`` 在 Python 侧**没有事务管理器**：
   这里不引入数据库连接/事务，只保留顺序（先 MySQL 后 ES），并在注释中标注。
   Java 的“MySQL 成功、ES 失败 → MySQL 回滚”语义在纯 Python 内存实现中无法复现。
2) ``@Service`` → 普通类；构造器注入（mapper / redisCache / esClient）改为**可选参数**，
   缺省时各自 ``new`` 一个实现，等价于 Spring 的唯一 Bean。
3) ``RedisCache.setCacheObject(key, dataId, 7, TimeUnit.DAYS)``
   → ``setCacheObject(key, dataId, PROCESS_EXPIRE_DAYS, TimeUnit.DAYS)``
   （TimeUnit 枚举来自 RedisCache 替身，见 java/util/concurrent/TimeUnit.py）。
4) ``Date.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime()``：
   Python 的 ``datetime``（naive）本身就是本地时间，**无需** Instant/ZoneId 中转，
   直接 ``strftime("%Y%m")`` 即与 Java 结果一致（时区同为系统默认时区）。
5) **原工程缺陷（忠实保留）**：``insertIntoMysql`` 里计算了 ``tableName``
   却**从未使用**（分表路由没有生效，最终仍写入 mapper 配置的固定表）；
   ``getTableName`` 方法因此只被调用、不产生效果。此处按原样保留并标注。
6) ``log.debug("...{}", a, b)`` → ``%s``；``log.error(msg, id, e)``
   （末参为异常）→ ``log.error(msg, id, exc_info=True)``。
7) ``throw new RuntimeException("插入MySQL失败", e)``
   → ``raise RuntimeError("插入MySQL失败") from e``。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.common.core.redis.RedisCache import RedisCache, TimeUnit
from java.time.format.DateTimeFormatter import DateTimeFormatter
from org.elasticsearch.action.index.IndexRequest import IndexRequest
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.xcontent.XContentType import XContentType

log = logging.getLogger(__name__)


class DataProcessService(object):
    """数据处理服务：把消费到的数据写入 MySQL 分表与 ES。"""

    #: Redis 缓存键前缀，用于记录已处理的消息
    PROCESS_PREFIX = "mq:processed:"

    #: 缓存过期时间（7天）
    PROCESS_EXPIRE_DAYS = 7

    #: ES 索引名称
    ES_INDEX = "snapshot_flow"

    def __init__(self,
                 mapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 redisCache: Optional[RedisCache] = None,
                 esClient: Optional[RestHighLevelClient] = None) -> None:
        self.mapper = mapper or OdsRtSzdnSnapshotFlowAddcodeMapper()
        self.redisCache = redisCache or RedisCache()
        self.esClient = esClient or RestHighLevelClient(_defaultRestClientBuilder())
        log.info("[数据处理服务] 初始化完成")

    # ------------------------------------------------------------------ 幂等
    def isProcessed(self, msgId: str) -> bool:
        """检查消息是否已处理（幂等性检查）。"""
        key = DataProcessService.PROCESS_PREFIX + msgId
        return self.redisCache.hasKey(key)

    def markProcessed(self, msgId: str, dataId: int) -> None:
        """标记消息已处理。"""
        key = DataProcessService.PROCESS_PREFIX + msgId
        self.redisCache.setCacheObject(key, dataId,
                                       DataProcessService.PROCESS_EXPIRE_DAYS,
                                       TimeUnit.DAYS)
        log.debug("[数据处理服务] 标记消息已处理, msgId=%s, dataId=%s", msgId, dataId)

    # ------------------------------------------------------------------ 处理
    def process(self, data: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """处理数据：存入 MySQL 分表和 ES。

        【Java→Python】原方法带 ``@Transactional(rollbackFor = Exception.class)``；
        Python 侧没有事务管理器，这里按原顺序执行，异常直接向上抛。
        """
        log.debug("[数据处理服务] 开始处理数据, dataId=%s", data.getId())

        # 1. 写入MySQL分表
        self.insertIntoMysql(data)

        # 2. 写入ES
        self.insertIntoEs(data)

        log.debug("[数据处理服务] 数据处理完成, dataId=%s", data.getId())

    # ------------------------------------------------------------------ MySQL
    def insertIntoMysql(self, data: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """根据 snapshottime 字段插入对应的月分表。"""
        # 根据snapshottime确定分表名
        # 【原工程缺陷，忠实保留】tableName 计算出后从未使用：
        #   分表名没有传给 mapper，实际写入的仍是 mapper 中固定的表名。
        #   若将来要修复，应改为动态表名（如 mapper.insertInto(tableName, data)）。
        tableName = self.getTableName(data.getSnapshottime())
        _ = tableName  # 消除“未使用变量”告警，同时保留 Java 的赋值语义

        try:
            # 写入MySQL（使用BaseMapper的insert方法）
            self.mapper.insert(data)
            log.debug("[数据处理服务] 插入MySQL成功, dataId=%s", data.getId())
        except Exception as e:  # noqa: BLE001 - Java 捕获 Exception
            log.error("[数据处理服务] 插入MySQL失败, dataId=%s", data.getId(),
                      exc_info=True)
            raise RuntimeError("插入MySQL失败") from e

    def getTableName(self, snapshottime: Optional[datetime]) -> str:
        """获取分表名：``ods_rt_szdn_snapshot_flow_addcode_202401``。"""
        if snapshottime is None:
            # 如果时间为空，使用当前时间（Java: new Date()）
            snapshottime = datetime.now()
        # 【Java→Python】Java 走 toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime()；
        # Python 的 naive datetime 已是本地时间，无需时区转换，直接格式化即可。
        suffix = DateTimeFormatter.ofPattern("yyyyMM").format(snapshottime)
        return "ods_rt_szdn_snapshot_flow_addcode_" + suffix

    # ------------------------------------------------------------------ ES
    def insertIntoEs(self, data: OdsRtSzdnSnapshotFlowAddcode) -> None:
        """插入 ES。"""
        try:
            # 创建ES索引请求
            request = (IndexRequest(DataProcessService.ES_INDEX)
                       .id(str(data.getId()))
                       .source(JSON.toJSONString(data), XContentType.JSON))

            # 执行索引操作
            response = self.esClient.index(request, RequestOptions.DEFAULT)

            log.debug("[数据处理服务] 插入ES成功, index=%s, id=%s, result=%s",
                      DataProcessService.ES_INDEX, data.getId(),
                      response.getResult())
        except Exception as e:  # noqa: BLE001 - Java 捕获 Exception
            log.error("[数据处理服务] 插入ES失败, id=%s", data.getId(),
                      exc_info=True)
            raise RuntimeError("插入ES失败") from e


def _defaultRestClientBuilder() -> Any:
    """构造默认的 RestHighLevelClient 入参（等价 Spring 注入的 ES Bean）。"""
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.client.RestClient import RestClient
    return RestClient.builder(HttpHost("localhost", 9200, "http"))
