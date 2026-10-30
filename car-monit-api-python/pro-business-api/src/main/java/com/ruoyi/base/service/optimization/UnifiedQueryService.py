# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.UnifiedQueryService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedQueryService.java

====================================================================
统一查询路由服务（3 大表共用）
====================================================================
设计目标：
  面向“日增 70W、单表 8 亿、最近一年查询 + 任意字段全模糊”场景，
  提供一致的查询入口，屏蔽单表差异：
    1. 自动路由到 Elasticsearch（默认），不可用时降级到 MySQL
    2. 任意模糊字段统一按 ngram match 走倒排索引
    3. 分页使用 from+size（窗口内）+ search_after（深分页可选扩展）

路由策略：
  if (存在模糊查询字段 || 时间范围超过 30 天) {
      优先走 ES；
  } else if (主键精确查询) {
      走 MySQL；
  } else {
      可走 MySQL（小范围精确，结合分区裁剪）；
  }
  ES 异常时自动降级 MySQL。

数据源抽象（DataSource Meta）：
  ┌─────────────┬──────────────────────┬──────────────┐
  │ 业务表      │ ES 索引              │ 时间范围字段 │
  ├─────────────┼──────────────────────┼──────────────┤
  │ 门架抓拍    │ snapshot_flow        │ snapshottime │
  │ 收费流水    │ fee_records          │ transtime    │
  │ 车辆轨迹    │ trail_fitting        │ extime       │
  └─────────────┴──────────────────────┴──────────────┘

【Java→Python 本文件重点差异】
1) 内部枚举 `public enum DataSource` → **模块级 `class DataSource(Enum)`**，
   文件末尾 `UnifiedQueryService.DataSource = DataSource` 挂回类属性，
   保证 `UnifiedQueryService.DataSource.SNAPSHOT` 的访问路径与 Java 一致
   （EsIndexManageService.resolveIndexName 就在用这个路径）。
2) `@Autowired` 五个字段 → 构造器可选参数；缺省时按 Java Bean 关系自建：
   - esClient：**复用 indexManageService 内部的同一个 client**（Java 里两者注入的是
     同一个 `RestHighLevelClient` Bean，不是两个连接池）。
   - indexManageService / 3 个 Mapper：`or new XxxImpl()`。
3) `@Value` 三个字段 → `Environment().value(...)`；`long` 字段在 Python 就是 int。
4) `List<?>` → `List[Any]`；`Collections.emptyList()` → `[]`（空 list）。
5) `new ArrayList<>(capacity)` → `[]`；Java 预分配容量，Python list 无需预分配。
6) `new ArrayList<>(all.subList(from, to))` → `list(all_rows[from:to])`
   （subList 是**视图**，必须复制成新 list 才能对齐 `new ArrayList<>(...)` 的语义）。
7) `java.sql.Timestamp.valueOf(time).getTime()` → `int(Timestamp.valueOf(time).timestamp() * 1000)`
   —— Timestamp 替身的 valueOf 返回 `datetime`（见 java/sql/Timestamp.py 说明）。
8) `new java.sql.Timestamp(millis)` → `Timestamp(millis)`（返回值为 `datetime`）。
9) `{@code List<?> query(...)}` 的 `throws Exception` 在 queryFromEs 上 → **Python 不声明
   受检异常**，签名里去掉，异常照常向上抛。
10) `throw new IllegalStateException(msg)` → `raise RuntimeError(msg)`
    （IllegalStateException 继承 RuntimeException，Python 用内置 RuntimeError 对应）。
11) `switch (ds) { case A: ... default: throw ... }` → `if/elif` + 末尾 `raise`
    （与原工程“default 分支抛异常”完全同构）。
12) `Map.Entry<String,String>` 遍历 → `dict.items()`；`getOrDefault(k, k)` → `dict.get(k, k)`。
13) `new java.util.HashMap<>()` → `{}`（Python dict 即哈希表）。
14) `Class<?> targetClass` → Python 的 `type` 对象，`JSON.parseObject(str, clazz)`
    替身已支持传入类对象。
15) `Math.max/Math.min` → 内置 `max/min`。
16) `System.currentTimeMillis()` → `java.lang.System` 替身的同名静态方法。
17) `finally { log.info(...) }` → Python `finally:` 语义一致（return 之后、方法退出之前执行）。
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.baomidou.mybatisplus.core.conditions.query.QueryWrapper import QueryWrapper
from com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01 import OdsLwzxsfsjFeeRecords01
from com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode import (
    OdsRtSzdnSnapshotFlowAddcode,
)
from com.ruoyi.base.domain.ZdataTrailFitting import ZdataTrailFitting
from com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper import (
    OdsLwzxsfsjFeeRecords01Mapper,
)
from com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper import (
    OdsRtSzdnSnapshotFlowAddcodeMapper,
)
from com.ruoyi.base.mapper.ZdataTrailFittingMapper import ZdataTrailFittingMapper
from com.ruoyi.base.service.optimization.EsIndexManageService import (
    EsIndexManageService,
)
from java.lang.System import System
from java.sql.Timestamp import Timestamp
from java.util.concurrent.TimeUnit import TimeUnit
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

__all__ = ["UnifiedQueryService", "DataSource"]

log = logging.getLogger(__name__)


class DataSource(Enum):
    """三种业务数据源类型

    【Java→Python】`public enum DataSource { SNAPSHOT, FEE, TRAIL }`（内部枚举）
    → 模块级 Enum；文件末尾挂回 `UnifiedQueryService.DataSource`。
    枚举成员用 `is` 比较（Java 的 `==` 也是引用比较，语义一致）。
    """

    SNAPSHOT = "SNAPSHOT"
    FEE = "FEE"
    TRAIL = "TRAIL"

    @classmethod
    def values(cls) -> List["DataSource"]:
        """对应 Java 枚举编译器隐式生成的 `static DataSource[] values()`。

        【Java→Python】Java 枚举自带 `values()` / `valueOf(String)`；Python 的 Enum
        只提供 `list(EnumClass)` 与 `EnumClass[name]`。为了让业务代码（如
        GaussEsConsistencyService 的 `DataSource.values()`）与 Java 逐字一致，
        这里显式补上同名静态方法；返回顺序 = 定义顺序，与 Java 相同。
        """
        return list(cls)


class UnifiedQueryService(object):
    """统一查询路由服务（`@Service`）。"""

    #: 三种业务数据源类型（Java 内部枚举的访问路径；末尾赋值）
    DataSource = DataSource

    def __init__(self,
                 esClient: Optional[RestHighLevelClient] = None,
                 indexManageService: Optional[EsIndexManageService] = None,
                 snapshotMapper: Optional[OdsRtSzdnSnapshotFlowAddcodeMapper] = None,
                 feeMapper: Optional[OdsLwzxsfsjFeeRecords01Mapper] = None,
                 trailMapper: Optional[ZdataTrailFittingMapper] = None) -> None:
        # 【Java→Python】`@Autowired` 字段注入 → 构造器可选参数
        self.indexManageService: EsIndexManageService = (
            indexManageService if indexManageService is not None
            else EsIndexManageService())

        if esClient is not None:
            self.esClient: RestHighLevelClient = esClient
        else:
            # Java 中本类与 EsIndexManageService 注入的是**同一个** RestHighLevelClient
            # Bean（Spring 单例），这里直接复用其内部实例，避免出现两个“集群连接”。
            self.esClient = self.indexManageService.esClient

        self.snapshotMapper: OdsRtSzdnSnapshotFlowAddcodeMapper = (
            snapshotMapper if snapshotMapper is not None
            else OdsRtSzdnSnapshotFlowAddcodeMapper())
        self.feeMapper: OdsLwzxsfsjFeeRecords01Mapper = (
            feeMapper if feeMapper is not None
            else OdsLwzxsfsjFeeRecords01Mapper())
        self.trailMapper: ZdataTrailFittingMapper = (
            trailMapper if trailMapper is not None
            else ZdataTrailFittingMapper())

        # 单次 ES 查询超时（毫秒；Java 字段类型 long）
        self.queryTimeoutMs: int = Environment().value(
            "${optimization.query.timeout-ms:30000}", int)

        # from + size 单次最大返回文档数（ES 默认 max_result_window = 10000）
        self.maxWindow: int = Environment().value(
            "${optimization.query.max-window:10000}", int)

        # 时间范围超过多少天时强制走 ES
        self.esForceDays: int = Environment().value(
            "${optimization.query.es-force-days:30}", int)

    # ============================================================
    # 公共入口
    # ============================================================
    def query(self, ds: DataSource, startTime: str, endTime: str,
              fuzzyFields: Optional[Dict[str, str]],
              pageNum: int, pageSize: int) -> List[Any]:
        """统一查询接口

        :param ds: 数据源类型
        :param startTime: 开始时间 (yyyy-MM-dd HH:mm:ss)
        :param endTime: 结束时间
        :param fuzzyFields: 通用全模糊字段（key=字段名，value=模糊内容）
                            支持字段：platenumber/orgname/sectionname/roadname/gantryname/tollname
        :param pageNum: 页码 (1-based)
        :param pageSize: 每页条数
        :return: 查询结果列表（已根据数据源反向化为对应 domain）
        """
        # 1. 路由决策
        useEs: bool = self.shouldRouteToEs(startTime, endTime, fuzzyFields, ds)
        t0: int = System.currentTimeMillis()

        try:
            if useEs:
                return self.queryFromEs(ds, startTime, endTime, fuzzyFields,
                                        pageNum, pageSize)
            return self.queryFromMysql(ds, startTime, endTime, fuzzyFields,
                                       pageNum, pageSize)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 【Java→Python】`log.error(fmt, a, b, c, e)`（最后一个参数是 Throwable）
            # → `log.error(fmt, a, b, c, exc_info=True)`。
            log.error("[统一查询] 查询失败 ds=%s, useEs=%s, 耗时=%sms",
                      ds, useEs, System.currentTimeMillis() - t0, exc_info=True)
            # ES 查询失败 -> 降级 MySQL
            if useEs:
                log.warning("[统一查询] ES 查询失败，尝试降级到 MySQL, ds=%s", ds)
                try:
                    return self.queryFromMysql(ds, startTime, endTime,
                                               fuzzyFields, pageNum, pageSize)
                except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ex) 一致
                    log.error("[统一查询] 降级 MySQL 也失败, ds=%s", ds,
                              exc_info=True)
                    return []
            return []
        finally:
            # 【Java→Python】finally 中读取 t0：与 Java 一致（无论 return 还是抛出都执行）
            cost: int = System.currentTimeMillis() - t0
            log.info("[统一查询] ds=%s, useEs=%s, cost=%sms, page=%s/%s",
                     ds, useEs, cost, pageNum, pageSize)

    # ============================================================
    # 路由策略
    # ============================================================
    def shouldRouteToEs(self, startTime: str, endTime: str,
                        fuzzyFields: Optional[Dict[str, str]],
                        ds: DataSource) -> bool:
        """是否应该路由到 ES

        触发 ES 的条件（满足任一）：
          1. 存在任意模糊查询字段（MySQL like '%xxx%' 走不了索引）
          2. 时间范围超过 esForceDays 天
          3. 数据源是收费流水或轨迹（这两张表分区裁剪效果较难保证）

        不触发时：
          - 小范围精确查询：MySQL + 分区裁剪 + B-tree 索引效率更好
          - 例如最近 1 周 + 单个门架代码 + 完整车牌
        """
        # 条件 1：任意模糊字段非空
        if fuzzyFields is not None:
            # 【Java→Python】`for (Map.Entry<String,String> e : map.entrySet())`
            # → `for key, value in map.items()`
            for key, value in fuzzyFields.items():
                if value is not None and len(value) > 0:
                    return True
        # 条件 2：时间跨度 > esForceDays（粗略判断，避免误差不影响路由选择）
        try:
            start: int = self.parseToMillis(startTime)
            end: int = self.parseToMillis(endTime)
            # 【Java→Python】`(long) esForceDays * 24 * 3600 * 1000L`
            # → Python int 无溢出，直接相乘（无需 long 强转）
            if end - start > self.esForceDays * 24 * 3600 * 1000:
                return True
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception ignored) 一致
            # 时间格式异常时保守走 ES（ES 对时间格式更宽容）
            return True
        # 条件 3：轨迹数据和收费流水默认走 ES（场景复杂、字段更多）
        return ds is DataSource.FEE or ds is DataSource.TRAIL

    def parseToMillis(self, time: Optional[str]) -> int:
        """时间字符串 -> 毫秒时间戳（空串返回 0）

        【Java→Python】`java.sql.Timestamp.valueOf(time).getTime()`：Timestamp 替身
        的 `valueOf` 返回 `datetime`（见 java/sql/Timestamp.py），`getTime()` 对应
        `int(dt.timestamp() * 1000)`。
        注意：`valueOf` 解析失败时 Java 抛 IllegalArgumentException，这里替身返回
        `None`（见 Timestamp.py 第 2 条），因此补一次 None 判断保持调用方的
        “解析失败即异常”语义。
        """
        if time is None or len(time) == 0:
            return 0
        parsed = Timestamp.valueOf(time)
        if parsed is None:
            # 对应 Java 中 valueOf 抛 IllegalArgumentException 的路径
            raise ValueError("无法解析时间: " + time)
        return int(parsed.timestamp() * 1000)

    # ============================================================
    # ES 查询实现（3 表统一）
    # ============================================================
    def queryFromEs(self, ds: DataSource, startTime: str, endTime: str,
                    fuzzyFields: Optional[Dict[str, str]],
                    pageNum: int, pageSize: int) -> List[Any]:
        """走 ES 的查询实现

        【Java→Python】原方法声明 `throws Exception`，Python 无受检异常，签名去掉，
        异常照常向上抛（由 query() 统一捕获并降级）。
        """
        indexName: str = self.resolveIndexName(ds)
        timeField: str = self.resolveTimeField(ds)
        targetClass: type = self.resolveDomainClass(ds)

        # 1. 构建查询
        boolQuery: BoolQueryBuilder = QueryBuilders.boolQuery()

        # 时间范围（必填，过滤到最近一年）
        timeRange: RangeQueryBuilder = (QueryBuilders.rangeQuery(timeField)
                                        .format("yyyy-MM-dd HH:mm:ss")
                                        .gte(startTime)
                                        .lte(endTime))
        boolQuery.filter(timeRange)

        # 通用全模糊字段（统一走 ngram 倒排索引）
        # 先翻译逻辑字段名 -> 物理字段名（如 FEE 的 platenumber -> vehicleplate），对调用方透明
        translation: Dict[str, str] = self.buildFieldTranslation(ds)
        if fuzzyFields is not None:
            for key, value in fuzzyFields.items():
                if value is None or len(value) == 0:
                    continue
                # 【Java→Python】`map.getOrDefault(key, key)` → `dict.get(key, key)`
                physicalField: str = translation.get(key, key)
                boolQuery.must(self.buildFuzzyQuery(physicalField, value))

        # 2. 分页参数
        fromIndex: int = max(0, (pageNum - 1) * pageSize)
        size: int = min(pageSize, self.maxWindow)
        if fromIndex + size > self.maxWindow:
            # 【Java→Python】`IllegalStateException` → 内置 `RuntimeError`
            raise RuntimeError(
                "浅分页超过 max_result_window=" + str(self.maxWindow)
                + "，请使用 export 接口或 search_after")

        sourceBuilder: SearchSourceBuilder = (SearchSourceBuilder()
                                              .query(boolQuery)
                                              .from_(fromIndex)
                                              .size(size)
                                              .sort(timeField, SortOrder.DESC)
                                              .timeout(TimeValue(
                                                  self.queryTimeoutMs,
                                                  TimeUnit.MILLISECONDS)))

        request: SearchRequest = SearchRequest(indexName)
        request.source(sourceBuilder)

        # 3. 执行查询
        response: SearchResponse = self.esClient.search(request, RequestOptions.DEFAULT)

        # 4. 解析结果 -> 反向化为 domain 对象
        # 【Java→Python】`new ArrayList<>(hits.length)` 预分配 → Python 空 list（无需预分配）
        results: List[Any] = []
        for hit in response.getHits().getHits():
            obj: Any = JSON.parseObject(hit.getSourceAsString(), targetClass)
            results.append(obj)

        log.debug("[统一查询-ES] ds=%s, index=%s, timeField=%s, totalHits=%s, returned=%s",
                  ds, indexName, timeField,
                  response.getHits().getTotalHits().value, len(results))
        return results

    def buildFuzzyQuery(self, fieldName: str, value: str) -> QueryBuilder:
        """智能构建全模糊查询条件

        字段长度策略：
          - 长度>=7 且为编号/车牌类字段：直接 term 精确匹配（最高性能）
          - 长度 3-6：ngram match 走倒排索引（核心路径）
          - 长度 1-2：wildcard 通配符兜底（语义正确但性能较低，避免高频使用）

        注意：所有模糊字段都必须在 ES Mapping 中已定义 “.ngram” 子字段，
              否则 match 会报错。索引管理服务已确保 mapping 完整。
        """
        # 完整编号类（>= 7 字符）：精确匹配
        if len(value) >= 7 and (fieldName == "platenumber"
                                or fieldName == "gantrycode"
                                or fieldName == "sectioncode"):
            return QueryBuilders.termQuery(fieldName + ".keyword", value)
        # 3-6 字符：ngram match（核心路径）
        if len(value) >= 3:
            return QueryBuilders.matchQuery(fieldName + ".ngram", value)
        # 1-2 字符：wildcard 兜底
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*")

    # ============================================================
    # MySQL 降级查询实现
    # ============================================================
    def queryFromMysql(self, ds: DataSource, startTime: str, endTime: str,
                       fuzzyFields: Optional[Dict[str, str]],
                       pageNum: int, pageSize: int) -> List[Any]:
        """ES 不可用 / 未启用时的降级查询路径（兜底，非主路径）

        说明：
          - 依赖 GaussDB 月度分区裁剪 + pg_trgm GIN 索引保证基本可用
          - MySQL 的 like '%xxx%' 走不了 B-tree 索引，8 亿级数据下性能差，仅作兜底
          - 时间范围 + 模糊字段翻译后，使用 MyBatis-Plus QueryWrapper 构建，最后内存分页
        """
        timeField: str = self.resolveTimeField(ds)
        translation: Dict[str, str] = self.buildFieldTranslation(ds)

        # 使用裸类型 QueryWrapper 以兼容三张表的不同实体类型（运行期安全，编译期 unchecked）
        # 【Java→Python】Java 的裸类型（Raw Type）警告在 Python 不存在；
        # 为保持“三张表共用一个 wrapper”的原意，这里同样不传类型参数。
        qw: QueryWrapper = QueryWrapper()
        # 时间范围（分区裁剪核心）
        if startTime is not None and len(startTime) > 0:
            # 【Java→Python】`new java.sql.Timestamp(millis)` → `Timestamp(millis)`
            qw.ge(timeField, Timestamp(self.parseToMillis(startTime)))
        if endTime is not None and len(endTime) > 0:
            qw.le(timeField, Timestamp(self.parseToMillis(endTime)))
        # 模糊字段（翻译为物理字段后走 like）
        if fuzzyFields is not None:
            for key, value in fuzzyFields.items():
                if value is None or len(value) == 0:
                    continue
                physical: str = translation.get(key, key)
                qw.like(physical, value)
        qw.last("LIMIT 1000")  # 降级路径限量，防止全表拉爆内存

        # 【Java→Python】`switch (ds) { case SNAPSHOT: all = ...; break; ... default: return []; }`
        # → if/elif + 末尾 return []（与 Java default 分支一致）
        if ds is DataSource.SNAPSHOT:
            all_rows: List[Any] = self.snapshotMapper.selectList(qw)
        elif ds is DataSource.FEE:
            all_rows = self.feeMapper.selectList(qw)
        elif ds is DataSource.TRAIL:
            all_rows = self.trailMapper.selectList(qw)
        else:
            return []
        # 内存分页（降级场景，结果集已 LIMIT 1000）
        fromIndex: int = max(0, (pageNum - 1) * pageSize)
        to: int = min(len(all_rows), fromIndex + pageSize)
        return ([] if fromIndex >= len(all_rows)
                # 【Java→Python】`new ArrayList<>(all.subList(from, to))`
                # → `list(all_rows[from:to])`（切片本身就是新 list，等价于复制）
                else list(all_rows[fromIndex:to]))

    # ============================================================
    # 逻辑字段 -> 物理字段翻译表
    # ============================================================
    @staticmethod
    def buildFieldTranslation(ds: DataSource) -> Dict[str, str]:
        """逻辑字段 -> 物理字段翻译表（对调用方透明）

        说明：收费流水表的车牌物理字段为 vehicleplate，轨迹表的车辆编号物理字段为
        envehicleid，对外统一以 platenumber 作为通用查询入参，在此翻译为对应物理字段。

        【Java→Python】`private static` 方法 → `@staticmethod`
        """
        # 【Java→Python】`new java.util.HashMap<>()` → `{}`
        m: Dict[str, str] = {}
        m["orgname"] = "orgname"
        m["sectionname"] = "sectionname"
        m["roadname"] = "roadname"
        m["gantryname"] = "gantryname"
        m["tollname"] = "tollname"
        if ds is DataSource.SNAPSHOT:
            m["platenumber"] = "platenumber"
        elif ds is DataSource.FEE:
            m["platenumber"] = "vehicleplate"
        elif ds is DataSource.TRAIL:
            # 轨迹表仅支持 platenumber，物理字段为入口车辆编号
            m["platenumber"] = "envehicleid"
        # default: break（Java 的 default 空分支在 Python 中即“什么都不做”）
        return m

    # ============================================================
    # 元数据映射
    # ============================================================
    def resolveIndexName(self, ds: DataSource) -> str:
        """数据源 -> ES 索引名"""
        if ds is DataSource.SNAPSHOT:
            return self.indexManageService.getSnapshotIndex()
        if ds is DataSource.FEE:
            return self.indexManageService.getFeeIndex()
        if ds is DataSource.TRAIL:
            return self.indexManageService.getTrailIndex()
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + str(ds))

    def resolveTimeField(self, ds: DataSource) -> str:
        """数据源 -> 时间字段名"""
        if ds is DataSource.SNAPSHOT:
            return "snapshottime"
        if ds is DataSource.FEE:
            return "transtime"
        if ds is DataSource.TRAIL:
            return "extime"
        raise ValueError("未知数据源: " + str(ds))

    def resolveDomainClass(self, ds: DataSource) -> type:
        """数据源 -> 实体类

        【Java→Python】Java 的 `Class<?>` → Python 的 `type`；
        `OdsXxx.class` → 直接引用类对象 `OdsXxx`。
        """
        if ds is DataSource.SNAPSHOT:
            return OdsRtSzdnSnapshotFlowAddcode
        if ds is DataSource.FEE:
            return OdsLwzxsfsjFeeRecords01
        if ds is DataSource.TRAIL:
            return ZdataTrailFitting
        raise ValueError("未知数据源: " + str(ds))


# 【Java→Python】内部枚举的访问路径还原（见文件头第 1 条）
UnifiedQueryService.DataSource = DataSource
