# -*- coding: utf-8 -*-
"""com.ruoyi.mq.service.EsQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/mq/service/EsQueryService.java

【Java→Python】关键差异
1) **``sourceBuilder.from(...)`` 必须改写为 ``from_``**：``from`` 是 Python 关键字，
   属性名/方法名都不能用它（``sourceBuilder.from(...)`` 直接 SyntaxError）。
   替身在 SearchSourceBuilder 里同时提供 ``from_`` 与 ``setFrom``。
2) ``queryFromMysql`` 的注释写明“mapper.queryFromTables 方法不存在, 降级返回空列表”，
   即 **ES 一旦不可用，查询必然返回空列表**（降级逻辑形同虚设）。这是原工程现状，
   忠实保留（同时保留“未找到匹配的分表”分支）。
3) ``queryFromMysql`` 只用到 ``startTime/endTime``，其余过滤参数
   （vehiclePlate/sectionCode/manageCenterCode/gantryCode）**完全没有参与查询** ——
   原工程缺陷，忠实保留。
4) **ES 查询字段名与实体字段名不一致**（原工程缺陷）：
   - 查询用 ``vehiclePlate`` / ``snapshotTime`` / ``sectionCode`` /
     ``manageCenterCode`` / ``gantryCode``
   - 实体 ``OdsRtSzdnSnapshotFlowAddcode`` 的字段是 ``platenumber`` /
     ``snapshottime`` / ``sectioncode`` / （无 manageCenterCode、无 gantryCode）
   真实 ES 中未映射字段的 match/term/range 一律不命中，因此该查询在真实环境
   大概率查不到数据；Python 替身严格实现“字段缺失即不命中”，与真实 ES 一致。
5) ``TimeValue`` 在 Java 里用全限定名 ``new org.elasticsearch.core.TimeValue(...)``；
   Python 不能写全限定名 new，改为顶部 import 后 ``TimeValue(30, TimeUnit.SECONDS)``。
6) ``e.getMessage()`` → ``str(e)``；``log.error(msg, e)``
   （末参是异常、无占位符）→ ``log.error(msg, exc_info=True)``。
7) Java 的 ``throw new Exception``（受检异常）→ Python 无受检异常，直接向上抛；
   本类里 ``queryFromEs`` 未显式抛出，只有 ES 客户端替身会抛 ``ConnectionError``。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import OdsRtSzdnSnapshotFlowAddcodeMapper
from com.ruoyi.common.core.page.PageDomain import PageDomain
from java.time.LocalDateTime import LocalDateTime
from java.time.format.DateTimeFormatter import DateTimeFormatter
from java.util.concurrent.TimeUnit import TimeUnit
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchResponse import SearchResponse
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder

log = logging.getLogger(__name__)


class EsQueryService(object):
    """ES 查询服务：优先从 ES 查询，ES 不可用时降级到 MySQL 分表。"""

    #: ES 索引名称
    ES_INDEX = "snapshot_flow"

    def __init__(self,
                 esClient: Optional[RestHighLevelClient] = None,
                 mapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None) -> None:
        self.esClient = esClient or RestHighLevelClient(_defaultRestClientBuilder())
        self.mapper = mapper or OdsRtSzdnSnapshotFlowAddcodeMapper()
        log.info("[ES查询服务] 初始化完成")

    # ------------------------------------------------------------------ 综合查询
    def query(self, vehiclePlate: Optional[str],
              startTime: Optional[LocalDateTime],
              endTime: Optional[LocalDateTime],
              sectionCode: Optional[str],
              manageCenterCode: Optional[str],
              gantryCode: Optional[str],
              page: PageDomain) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """优先从 ES 查询，ES 不可用时降级到 MySQL 分表。"""
        try:
            # 优先从ES查询
            return self.queryFromEs(vehiclePlate, startTime, endTime, sectionCode,
                                    manageCenterCode, gantryCode, page)
        except Exception as e:  # noqa: BLE001 - Java 捕获 Exception
            log.error("[ES查询服务] ES查询失败，降级到MySQL, error=%s", str(e))
            # ES不可用，降级到MySQL分表
            return self.queryFromMysql(vehiclePlate, startTime, endTime, sectionCode,
                                       manageCenterCode, gantryCode, page)

    # ------------------------------------------------------------------ ES 查询
    def queryFromEs(self, vehiclePlate: Optional[str],
                    startTime: Optional[LocalDateTime],
                    endTime: Optional[LocalDateTime],
                    sectionCode: Optional[str],
                    manageCenterCode: Optional[str],
                    gantryCode: Optional[str],
                    page: PageDomain) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """从 ES 查询（Java 侧声明 ``throws Exception``）。"""
        log.debug("[ES查询服务] 从ES查询数据")

        # 创建ES搜索请求
        searchRequest = SearchRequest(EsQueryService.ES_INDEX)
        sourceBuilder = SearchSourceBuilder()

        # 构建查询条件
        boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()

        # 车牌号模糊查询
        # 【原工程缺陷，忠实保留】字段名 vehiclePlate 在实体中不存在（实体为 platenumber）
        if vehiclePlate is not None and vehiclePlate != "":
            boolQuery.must(QueryBuilders.matchQuery("vehiclePlate", vehiclePlate)
                           .fuzziness("AUTO"))

        # 时间范围查询（使用 < 代替 <=，符合分区裁剪原则）
        # 【原工程缺陷，忠实保留】字段名 snapshotTime 在实体中不存在（实体为 snapshottime）
        if startTime is not None:
            boolQuery.filter(QueryBuilders.rangeQuery("snapshotTime")
                             .gte(self.formatDateTime(startTime)))
        if endTime is not None:
            boolQuery.filter(QueryBuilders.rangeQuery("snapshotTime")
                             .lt(self.formatDateTime(endTime.plusDays(1))))

        # 等值查询
        # 【原工程缺陷，忠实保留】sectionCode / manageCenterCode / gantryCode
        #   与实体字段（sectioncode 等）大小写/命名不一致
        if sectionCode is not None and sectionCode != "":
            boolQuery.filter(QueryBuilders.termQuery("sectionCode", sectionCode))
        if manageCenterCode is not None and manageCenterCode != "":
            boolQuery.filter(QueryBuilders.termQuery("manageCenterCode",
                                                     manageCenterCode))
        if gantryCode is not None and gantryCode != "":
            boolQuery.filter(QueryBuilders.termQuery("gantryCode", gantryCode))

        # 设置查询条件和分页
        sourceBuilder.query(boolQuery)
        # 【Java→Python】Java: sourceBuilder.from(...)；from 是 Python 关键字 → from_
        sourceBuilder.from_((page.getPageNum() - 1) * page.getPageSize())
        sourceBuilder.size(page.getPageSize())

        # 设置超时时间（Java: new org.elasticsearch.core.TimeValue(30, TimeUnit.SECONDS)）
        sourceBuilder.timeout(TimeValue(30, TimeUnit.SECONDS))

        searchRequest.source(sourceBuilder)

        # 执行查询
        response: SearchResponse = self.esClient.search(searchRequest,
                                                        RequestOptions.DEFAULT)

        # 解析结果
        return self.parseEsResponse(response)

    # ------------------------------------------------------------------ MySQL 降级
    def queryFromMysql(self, vehiclePlate: Optional[str],
                       startTime: Optional[LocalDateTime],
                       endTime: Optional[LocalDateTime],
                       sectionCode: Optional[str],
                       manageCenterCode: Optional[str],
                       gantryCode: Optional[str],
                       page: PageDomain) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """从 MySQL 分表查询（原工程未实现，固定返回空列表）。"""
        log.debug("[ES查询服务] 从MySQL分表查询数据")

        # 确定需要查询的分表
        tableNames = self.getTableNames(startTime, endTime)

        if not tableNames:
            log.warning("[ES查询服务] 未找到匹配的分表")
            return []

        # 动态查询多个分表 (使用BaseMapper的基础查询方法)
        # mapper.queryFromTables 方法不存在, 降级返回空列表
        # 【原工程缺陷，忠实保留】其余过滤参数（vehiclePlate 等）完全未参与查询
        log.warning("[ES查询服务] 分表查询未实现, 返回空列表")
        return []

    # ------------------------------------------------------------------ 分表名
    def getTableNames(self, startTime: Optional[LocalDateTime],
                      endTime: Optional[LocalDateTime]) -> List[str]:
        """获取需要查询的分表列表（按月切片）。"""
        tableNames: List[str] = []

        if startTime is None:
            startTime = LocalDateTime.now().minusMonths(1)
        if endTime is None:
            endTime = LocalDateTime.now()

        # 遍历时间范围内的每个月份，生成对应的分表名
        current = (startTime.withDayOfMonth(1)
                   .withHour(0).withMinute(0).withSecond(0))
        while not current.isAfter(endTime):
            tableName = ("ods_rt_szdn_snapshot_flow_addcode_" +
                         current.format(DateTimeFormatter.ofPattern("yyyyMM")))
            tableNames.append(tableName)
            current = current.plusMonths(1)

        return tableNames

    # ------------------------------------------------------------------ 解析响应
    def parseEsResponse(self, response: SearchResponse) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """解析 ES 响应。"""
        results: List[OdsRtSzdnSnapshotFlowAddcode] = []

        # Java 里 getHits() 不会为 null，这里的双重判空是防御性冗余（忠实保留）
        if response.getHits() is not None and response.getHits().getHits() is not None:
            for hit in response.getHits().getHits():
                try:
                    data = JSON.parseObject(hit.getSourceAsString(),
                                            OdsRtSzdnSnapshotFlowAddcode)
                    results.append(data)
                except Exception:  # noqa: BLE001 - Java 捕获 Exception
                    log.error("[ES查询服务] 解析ES响应失败, id=%s", hit.getId(),
                              exc_info=True)

        log.debug("[ES查询服务] ES查询结果数量: %s", len(results))
        return results

    # ------------------------------------------------------------------ 工具
    def formatDateTime(self, dateTime: LocalDateTime) -> str:
        """格式化日期时间为字符串。"""
        return dateTime.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))


def _defaultRestClientBuilder() -> Any:
    """构造默认的 RestHighLevelClient 入参（等价 Spring 注入的 ES Bean）。"""
    from org.apache.http.HttpHost import HttpHost
    from org.elasticsearch.client.RestClient import RestClient
    return RestClient.builder(HttpHost("localhost", 9200, "http"))
