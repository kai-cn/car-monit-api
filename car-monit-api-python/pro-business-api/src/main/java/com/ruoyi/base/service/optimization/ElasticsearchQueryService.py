# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.ElasticsearchQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/ElasticsearchQueryService.java

====================================================================
方案二：Elasticsearch 全文检索方案
====================================================================

核心思路：
  1. 利用 ES 的倒排索引（Inverted Index）+ TF-IDF/BM25 算法
  2. 支持 like '%xxx%' 全模糊查询、多字段组合查询、中文分词查询
  3. 使用 RestHighLevelClient 客户端进行查询
  4. 支持按 snapshottime 范围查询 + 车牌模糊 + 路段精确匹配

索引结构设计：
  索引名：ods_rt_szdn_snapshot_flow_addcode
  Mapping字段：
    - snapshottime: date(时间范围查询，秒级精度)
    - platenumber: keyword + text(精确匹配/模糊查询)
    - platenumber_keyword: keyword(精确匹配、排序、aggregation)
    - gantrycode: keyword(门架编号)
    - sectioncode: keyword(路段编号)
    - roadname: text + keyword(道路名称，支持模糊查询)
    - orgcode: keyword(管理中心编号)
    - gantryname: text(门架名称，模糊查询)

【Java→Python 本文件重点差异】
1) 6 个 `@Value` → 构造器里 `Environment().value(...)`；`@Service` → 普通类。
2) `@PostConstruct init()` → `@PostConstruct` 恒等装饰器 + **构造器末尾显式调用**
   `self.init()`：Java 由 Spring 容器在注入后反射调用，Python 没有容器，
   所以在构造器里手动触发（方法体保持原样，便于单独调用/测试）。
   `@PreDestroy destroy()` 同理：装饰器只是占位，需要显式调用（或用
   `atexit.register` 注册）。
3) `import javax.annotation.PostConstruct/PreDestroy` → 本工程替身
   （恒等装饰器，见 `javax/annotation/*.py` 的说明）。
4) `import java.io.IOException` → **不建替身**：Java 的 IOException 是受检异常，
   `catch (IOException e)` 在这里改为 `except OSError`（Python 的 I/O 异常基类）；
   `client.close()` 的替身不会抛异常，分支保留只为忠实还原。
5) `import java.util.stream.Collectors` 在 Java 里**未被使用**（IDE 会报冗余
   import）—— Python 侧不引入任何东西，在此注释说明，保持“无副作用”。
6) `List<X> results = new ArrayList<>()` → `list`；`Collections.emptyList()` → `[]`。
7) `plateNumber.toUpperCase()` → `plateNumber.upper()`（**与 Java 一样是
   区域无关的默认行为**；Java 的 toUpperCase() 用默认 Locale，Python 的 upper()
   用 Unicode 大小写映射，对车牌 ASCII 字符结果一致）。
8) `JSON.parseObject(hit.getSourceAsString(), X.class)` → 同名替身方法
   （Python 传类对象而不是 `X.class`）。
9) `sourceBuilder.from(...)` → `from_(...)`：`from` 是 Python 关键字
   （详见 SearchSourceBuilder 替身说明）。
10) `new org.elasticsearch.core.TimeValue(30, TimeUnit.SECONDS)` → 同名替身；
    Java 的全限定名写法在这里保留为 `TimeValue(...)` + 顶部 import。
11) `log.warn(msg, e)` → `log.warning(msg, exc_info=True)`。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import OdsRtSzdnSnapshotFlowAddcode
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from javax.annotation.PostConstruct import PostConstruct
from javax.annotation.PreDestroy import PreDestroy
from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.action.search.SearchRequest import SearchRequest
from org.elasticsearch.action.search.SearchResponse import SearchResponse
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.core.TimeValue import TimeValue
from org.elasticsearch.index.query.BoolQueryBuilder import BoolQueryBuilder
from org.elasticsearch.index.query.QueryBuilder import QueryBuilder
from org.elasticsearch.index.query.QueryBuilders import QueryBuilders
from org.elasticsearch.index.query.RangeQueryBuilder import RangeQueryBuilder
from org.elasticsearch.search.SearchHit import SearchHit
from org.elasticsearch.search.builder.SearchSourceBuilder import SearchSourceBuilder
from org.elasticsearch.search.sort.SortOrder import SortOrder
from org.springframework.core.env.Environment import Environment
from java.util.concurrent.TimeUnit import TimeUnit

__all__ = ["ElasticsearchQueryService"]

log = logging.getLogger(__name__)


class ElasticsearchQueryService(object):
    """Elasticsearch 全文检索服务（`@Service`）。"""

    def __init__(self) -> None:
        # ES主机地址
        self.esHost: str = Environment().value("${elasticsearch.host:127.0.0.1}", str)
        # ES端口
        self.esPort: int = Environment().value("${elasticsearch.port:9200}", int)
        # ES快照流量索引名
        self.snapshotIndex: str = Environment().value(
            "${elasticsearch.index.snapshot:ods_rt_szdn_snapshot_flow_addcode}", str)
        # ES交易记录索引名
        self.feeIndex: str = Environment().value(
            "${elasticsearch.index.fee:ods_lwzxsfsj_fee_records_01}", str)
        # ES轨迹索引名
        self.trailIndex: str = Environment().value(
            "${elasticsearch.index.trail:zdata_trail_fitting}", str)

        # ES高级客户端（Java: private RestHighLevelClient client;）
        self.client: Optional[RestHighLevelClient] = None

        # 【Java→Python】Spring 的 @PostConstruct 回调 → 构造器里显式调用
        self.init()

    # ====================================================================
    # 生命周期
    # ====================================================================
    @PostConstruct
    def init(self) -> None:
        """初始化 ES 客户端"""
        log.info("[ES查询服务] 初始化 Elasticsearch 客户端，host=%s, port=%s",
                 self.esHost, self.esPort)
        self.client = RestHighLevelClient(
            RestClient.builder(HttpHost(self.esHost, self.esPort, "http"))
        )

    @PreDestroy
    def destroy(self) -> None:
        """销毁 ES 客户端（Java 由容器调用；Python 需显式调用/注册 atexit）。"""
        try:
            if self.client is not None:
                self.client.close()
                log.info("[ES查询服务] ES 客户端已关闭")
        except OSError:
            # 【Java→Python】`catch (IOException e)` → `except OSError`
            log.error("[ES查询服务] 关闭客户端异常", exc_info=True)

    # ====================================================================
    # 门架抓拍流水 ES 查询
    # ====================================================================
    def querySnapshotFlowByEs(
        self,
        startTime: str,
        endTime: str,
        plateNumber: str,
        gantryCode: str,
        sectionCode: str,
        orgCode: str,
        pageNum: int,
        pageSize: int,
    ) -> List[OdsRtSzdnSnapshotFlowAddcode]:
        """门架抓拍流水 ES 查询（模糊查询 + 时间范围查询）

        性能优化：
          1. platenumber 字段使用 keyword + text 双类型
          2. 完整车牌走 keyword 精确匹配(B+树结构)
          3. 模糊车牌走 text 字段 + wildcard/terms 查询
          4. snapshottime 走 range 查询
          5. 采用滚动游标 / search_after 分页
        """
        log.info("[ES查询服务] 门架抓拍流水查询 start=%s, end=%s, plate=%s, gantry=%s, section=%s, page=%s/%s",
                 startTime, endTime, plateNumber, gantryCode, sectionCode,
                 pageNum, pageSize)

        try:
            # ============== 1. 构建查询条件 ================
            boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()

            # 2. 时间范围查询（必须条件，缩小搜索范围）
            timeQuery: RangeQueryBuilder = (
                QueryBuilders.rangeQuery("snapshottime")
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime))
            boolQuery.filter(timeQuery)

            # 3. 车牌号查询（根据长度判断是精确/前缀/模糊）
            if plateNumber is not None and len(plateNumber) != 0:
                plateQuery: QueryBuilder = self.buildPlateQuery(plateNumber)
                boolQuery.filter(plateQuery)

            # 4. 门架编号（精确匹配）
            if gantryCode is not None and len(gantryCode) != 0:
                boolQuery.filter(QueryBuilders.termQuery("gantrycode", gantryCode))

            # 5. 路段编号（精确匹配）
            if sectionCode is not None and len(sectionCode) != 0:
                boolQuery.filter(QueryBuilders.termQuery("sectioncode", sectionCode))

            # 6. 管理中心编号
            if orgCode is not None and len(orgCode) != 0:
                boolQuery.filter(QueryBuilders.termQuery("orgcode", orgCode))

            # ============== 2. 构建搜索请求 ==================
            sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
            sourceBuilder.query(boolQuery)
            # 【Java→Python】`from(int)` → `from_(int)`（from 是 Python 关键字）
            sourceBuilder.from_((pageNum - 1) * pageSize)
            sourceBuilder.size(pageSize)
            sourceBuilder.sort("snapshottime", SortOrder.DESC)
            # 超时设置
            sourceBuilder.timeout(TimeValue(30, TimeUnit.SECONDS))

            searchRequest: SearchRequest = SearchRequest(self.snapshotIndex)
            searchRequest.source(sourceBuilder)

            # ============== 3. 执行查询 ==========================
            response: SearchResponse = self.client.search(
                searchRequest, RequestOptions.DEFAULT)

            # ============== 4. 解析结果 =========================
            results: List[OdsRtSzdnSnapshotFlowAddcode] = []
            for hit in response.getHits().getHits():
                try:
                    record: OdsRtSzdnSnapshotFlowAddcode = JSON.parseObject(
                        hit.getSourceAsString(), OdsRtSzdnSnapshotFlowAddcode)
                    results.append(record)
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
                    log.warning("[ES查询服务] 解析 ES 文档失败 doc=%s", hit.getId(),
                                exc_info=True)

            log.info("[ES查询服务] 命中记录 total=%s, 当前页大小 pageSize=%s",
                     response.getHits().getTotalHits().value, len(results))
            return results

        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[ES查询服务] ES 查询失败，降级返回空/走数据库备份", exc_info=True)
            # 降级处理：返回空列表，前端可重试
            return []

    # ====================================================================
    # 车牌查询策略
    # ====================================================================
    def buildPlateQuery(self, plateNumber: str) -> QueryBuilder:
        """根据车牌号的长度智能构建查询策略

        策略：
          1. 完整车牌(7-8位)：termQuery精确匹配
          2. 2-6位前缀车牌：wildcard 前缀匹配(性能较好)
          3. 1位字符或中间查询：match / fuzzyQuery模糊查询
        """
        if len(plateNumber) >= 7:
            # 完整车牌：精确匹配
            log.debug("[ES查询] 完整车牌精确匹配 plate=%s", plateNumber)
            return QueryBuilders.termQuery("platenumber_keyword", plateNumber)
        elif len(plateNumber) >= 3:
            # 部分车牌：前缀匹配（性能较好）
            log.debug("[ES查询] 车牌前缀匹配 plate=%s", plateNumber)
            return QueryBuilders.prefixQuery(
                "platenumber_keyword", plateNumber.upper())
        else:
            # 1-2字符：通配符模糊查询
            log.debug("[ES查询] 车牌模糊匹配 plate=%s", plateNumber)
            return QueryBuilders.wildcardQuery(
                "platenumber_keyword", "*" + plateNumber.upper() + "*")

    # ====================================================================
    # 交易流水 ES 查询
    # ====================================================================
    def queryFeeRecordsByEs(
        self,
        startTime: str,
        endTime: str,
        vehiclePlate: str,
        gantryId: str,
        sectionCode: str,
        pageNum: int,
        pageSize: int,
    ) -> List[OdsLwzxsfsjFeeRecords01]:
        """交易流水 ES 查询

        与门架抓拍类似，但字段不同：
          - vehicleplate: 车牌号
          - transtime: 交易时间（作为范围查询条件）
          - gantryid: 门架编号
          - section_code: 路段编号（从门架表查询）
        """
        log.info("[ES查询服务] 交易流水查询 start=%s, end=%s, plate=%s, gantry=%s, section=%s, page=%s/%s",
                 startTime, endTime, vehiclePlate, gantryId, sectionCode,
                 pageNum, pageSize)

        try:
            boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()

            # 时间范围
            timeQuery: RangeQueryBuilder = (
                QueryBuilders.rangeQuery("transtime")
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime))
            boolQuery.filter(timeQuery)

            # 车牌号
            if vehiclePlate is not None and len(vehiclePlate) != 0:
                plateQuery: QueryBuilder = self.buildPlateQuery(vehiclePlate)
                boolQuery.filter(plateQuery)

            # 门架编号
            if gantryId is not None and len(gantryId) != 0:
                boolQuery.filter(QueryBuilders.termQuery("gantryid", gantryId))

            # 路段编号
            if sectionCode is not None and len(sectionCode) != 0:
                boolQuery.filter(QueryBuilders.termQuery("sectioncode", sectionCode))

            sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
            sourceBuilder.query(boolQuery)
            sourceBuilder.from_((pageNum - 1) * pageSize)
            sourceBuilder.size(pageSize)
            sourceBuilder.sort("transtime", SortOrder.DESC)
            sourceBuilder.timeout(TimeValue(30, TimeUnit.SECONDS))

            searchRequest: SearchRequest = SearchRequest(self.feeIndex)
            searchRequest.source(sourceBuilder)
            response: SearchResponse = self.client.search(
                searchRequest, RequestOptions.DEFAULT)

            results: List[OdsLwzxsfsjFeeRecords01] = []
            for hit in response.getHits().getHits():
                try:
                    record: OdsLwzxsfsjFeeRecords01 = JSON.parseObject(
                        hit.getSourceAsString(), OdsLwzxsfsjFeeRecords01)
                    results.append(record)
                except Exception:  # noqa: BLE001
                    log.warning("[ES查询服务] 解析 ES 文档失败 doc=%s", hit.getId(),
                                exc_info=True)

            log.info("[ES查询服务] 命中记录 total=%s, 当前页 size=%s",
                     response.getHits().getTotalHits().value, len(results))
            return results

        except Exception:  # noqa: BLE001
            log.error("[ES查询服务] ES 查询失败", exc_info=True)
            return []

    # ====================================================================
    # 轨迹拟合 ES 查询
    # ====================================================================
    def queryTrailFittingByEs(
        self,
        startTime: str,
        endTime: str,
        envehicleid: str,
        stationName: str,
        pageNum: int,
        pageSize: int,
    ) -> List[ZdataTrailFitting]:
        """轨迹拟合 ES 查询（原注释：类似逻辑，略写）"""
        try:
            boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()

            # 时间范围
            timeQuery: RangeQueryBuilder = (
                QueryBuilders.rangeQuery("extime")
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime))
            boolQuery.filter(timeQuery)

            # 车牌号精确查询
            if envehicleid is not None and len(envehicleid) != 0:
                boolQuery.filter(QueryBuilders.termQuery(
                    "envehicleid_keyword", envehicleid))

            # 站名称模糊查询
            if stationName is not None and len(stationName) != 0:
                boolQuery.should(QueryBuilders.wildcardQuery(
                    "entollstationname", "*" + stationName + "*"))
                boolQuery.should(QueryBuilders.wildcardQuery(
                    "extollstationname", "*" + stationName + "*"))
                boolQuery.minimumShouldMatch(1)

            sourceBuilder: SearchSourceBuilder = SearchSourceBuilder()
            sourceBuilder.query(boolQuery)
            sourceBuilder.from_((pageNum - 1) * pageSize)
            sourceBuilder.size(pageSize)
            sourceBuilder.sort("extime", SortOrder.DESC)
            sourceBuilder.timeout(TimeValue(30, TimeUnit.SECONDS))

            searchRequest: SearchRequest = SearchRequest(self.trailIndex)
            searchRequest.source(sourceBuilder)
            response: SearchResponse = self.client.search(
                searchRequest, RequestOptions.DEFAULT)

            results: List[ZdataTrailFitting] = []
            for hit in response.getHits().getHits():
                # 【注意】原工程此处**没有** try/catch（与前两个方法不同），
                # 单条文档解析失败会导致整个查询走 catch 返回空列表 —— 缺陷保留。
                record: ZdataTrailFitting = JSON.parseObject(
                    hit.getSourceAsString(), ZdataTrailFitting)
                results.append(record)
            return results
        except Exception:  # noqa: BLE001
            log.error("[ES查询服务] ES 查询失败", exc_info=True)
            return []

    # ====================================================================
    # 健康检查
    # ====================================================================
    def checkHealth(self) -> bool:
        """测试 ES 连接健康状态

        :return: true 正常 false 异常
        """
        try:
            return self.client.ping(RequestOptions.DEFAULT)
        except Exception:  # noqa: BLE001
            log.error("[ES查询服务] ES 连接异常", exc_info=True)
            return False

    def __repr__(self) -> str:
        return ("ElasticsearchQueryService(host=%s, port=%d, snapshotIndex=%s)" %
                (self.esHost, self.esPort, self.snapshotIndex))
