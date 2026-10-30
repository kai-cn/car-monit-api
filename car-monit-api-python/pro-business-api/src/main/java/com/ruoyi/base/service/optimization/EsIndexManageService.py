# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.optimization.EsIndexManageService

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/optimization/EsIndexManageService.java

====================================================================
ES 索引管理服务 / Elasticsearch Index Management Service
====================================================================

职责 / Responsibilities:
  1. 三张大表对应 ES 索引的创建/初始化（ngram 分词 + .ngram 子字段）
  2. ILM 生命周期策略（hot/warm/cold/frozen）的创建与挂载
  3. 索引别名管理（hot/warm 数据分层时使用）
  4. 索引健康检查

索引说明 / Index mapping:
  - snapshot_flow  -> ods_rt_szdn_snapshot_flow_addcode  (时间字段: snapshottime)
  - fee_records    -> ods_lwzxsfsj_fee_records_01        (时间字段: transtime)
  - trail_fitting  -> zdata_trail_fitting                 (时间字段: extime)

【Java→Python 本文件重点差异】
1) 7 个 `@Value` → 构造器里 `Environment().value(...)`；`@Service` → 普通类。
2) `@Autowired RestHighLevelClient esClient` → 构造器可选参数；未注入时
   用默认 host/port 自建一个（等价于本工程 `ElasticsearchConfig` 的默认 Bean）。
3) `@PostConstruct init()` → `@PostConstruct` 恒等装饰器 + **构造器末尾显式调用**。
4) `private static final ObjectMapper OBJECT_MAPPER` → 类属性（Jackson 替身无状态，
   共享无副作用）。`private static final List<String> ALL_INDEXES` → 类属性 list；
   **原工程定义了但从未使用**（死代码），此处忠实保留并标注。
5) `throws IOException` → **Python 不声明受检异常**；方法签名里去掉，抛出的位置
   改为 `raise OSError(...)`（Python 中 I/O 异常的基类，对应 java.io.IOException）。
6) `try (InputStream is = resource.getInputStream()) {...}` → `with ... as is:`
   （try-with-resources 与 Python with 语义一致：离开块自动 close）。
7) `String.valueOf(numberOfShards)` → `str(...)`。
8) `Arrays.asList(a, b, c)` → `[a, b, c]`（Java 的固定长度 List → Python list）。
9) `switch (ds)` 的枚举分支 → `if/elif`；`DataSource` 的 import 放在**方法内延迟导入**
   —— 因为 `UnifiedQueryService` 反过来 import 本类（`resolveIndexName` 的调用方），
   模块级互相 import 会形成循环依赖（Python 直接报 ImportError），延迟导入可解。
10) `IllegalArgumentException` → `ValueError`（Python 的“非法参数”惯例）。
11) `log.warn("...{}...", e.getMessage())` → `log.warning("...%s...", str(e))`。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from com.fasterxml.jackson.databind.JsonNode import JsonNode
from com.fasterxml.jackson.databind.ObjectMapper import ObjectMapper
from java.io.InputStream import InputStream
from java.nio.charset.StandardCharsets import StandardCharsets
from javax.annotation.PostConstruct import PostConstruct
from org.apache.http.util.EntityUtils import EntityUtils
from org.apache.http.HttpHost import HttpHost
from org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest import (
    AliasActions,
    IndicesAliasesRequest,
)
from org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest import (
    DeleteIndexRequest,
)
from org.elasticsearch.action.support.master.AcknowledgedResponse import (
    AcknowledgedResponse,
)
from org.elasticsearch.client.Request import Request
from org.elasticsearch.client.RequestOptions import RequestOptions
from org.elasticsearch.client.Response import Response
from org.elasticsearch.client.RestClient import RestClient
from org.elasticsearch.client.RestHighLevelClient import RestHighLevelClient
from org.elasticsearch.client.indices.CreateIndexRequest import CreateIndexRequest
from org.elasticsearch.client.indices.CreateIndexResponse import CreateIndexResponse
from org.elasticsearch.client.indices.GetIndexRequest import GetIndexRequest
from org.elasticsearch.xcontent.XContentType import XContentType
from org.springframework.core.env.Environment import Environment
from org.springframework.core.io.ClassPathResource import ClassPathResource
from org.springframework.util.StreamUtils import StreamUtils

__all__ = ["EsIndexManageService"]

log = logging.getLogger(__name__)


class EsIndexManageService(object):
    """ES 索引管理服务（`@Service`）。"""

    #: Jackson 解析器，用于校验 ILM 策略是否已存在
    #: 【Java→Python】`private static final ObjectMapper` → 类属性
    OBJECT_MAPPER = ObjectMapper()

    #: 三张表的索引清单（classpath 下的 mapping JSON 文件名与之一一对应）
    #: 【注意】原工程定义了该常量但**从未引用**（死代码），此处原样保留。
    ALL_INDEXES: List[str] = ["snapshot_flow", "fee_records", "trail_fitting"]

    def __init__(self, esClient: Optional[RestHighLevelClient] = None) -> None:
        # 【Java→Python】`@Autowired` 字段注入 → 构造器可选参数
        if esClient is not None:
            self.esClient: RestHighLevelClient = esClient
        else:
            # 等价于本工程 ElasticsearchConfig 的默认 Bean（host/port 交给 Environment）
            host: str = Environment().value("${elasticsearch.host:127.0.0.1}", str)
            port: int = Environment().value("${elasticsearch.port:9200}", int)
            self.esClient = RestHighLevelClient(
                RestClient.builder(HttpHost(host, port, "http")))

        # 三张表对应的索引名，通过 application.yml 可覆盖
        self.snapshotIndex: str = Environment().value(
            "${elasticsearch.index.snapshot:snapshot_flow}", str)
        self.feeIndex: str = Environment().value(
            "${elasticsearch.index.fee:fee_records}", str)
        self.trailIndex: str = Environment().value(
            "${elasticsearch.index.trail:trail_fitting}", str)

        # 索引创建时的分片数（按 ES 集群 3+ 节点场景，建议 6-12）
        self.numberOfShards: int = Environment().value(
            "${elasticsearch.index.shards:6}", int)
        self.numberOfReplicas: int = Environment().value(
            "${elasticsearch.index.replicas:1}", int)

        # 是否在启动时自动创建缺失索引（仅开发环境建议开启）
        self.autoCreate: bool = Environment().value(
            "${elasticsearch.index.auto-create:false}", bool)

        # ILM 策略名称（hot/warm/cold/frozen 统一管理三表索引）
        self.ilmPolicyName: str = Environment().value(
            "${elasticsearch.index.ilm-policy:car_monit_ilm_policy}", str)

        # 是否在创建索引时挂载 ILM 策略（生产环境建议开启，实现冷热分层）
        self.attachIlm: bool = Environment().value(
            "${elasticsearch.index.attach-ilm:false}", bool)

        # 【Java→Python】Spring 的 @PostConstruct 回调 → 构造器里显式调用
        self.init()

    # ====================================================================
    # 启动初始化
    # ====================================================================
    @PostConstruct
    def init(self) -> None:
        """应用启动时自动检查并创建缺失的索引 + ILM 策略

        仅在 elasticsearch.index.auto-create=true 时生效；生产环境建议通过运维脚本初始化，
        但 ILM 策略无论 auto-create 是否开启都尝试创建（幂等），保证生命周期管理可用。
        """
        # ILM 策略幂等创建（不依赖 auto-create 开关）
        try:
            self.createIndexLifecyclePolicyIfAbsent(self.ilmPolicyName)
        except Exception as error:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.warning("[ES索引管理] ILM 策略创建失败(可忽略, 后续重试): %s", str(error))

        if not self.autoCreate:
            log.info("[ES索引管理] auto-create=false, 跳过索引自动创建。索引将需要手动初始化。")
            return

        try:
            log.info("[ES索引管理] auto-create=true, 开始检查并创建缺失索引...")
            self.createIndexIfAbsent(self.snapshotIndex, "es/index/snapshot_flow.json")
            self.createIndexIfAbsent(self.feeIndex, "es/index/fee_records.json")
            self.createIndexIfAbsent(self.trailIndex, "es/index/trail_fitting.json")
            log.info("[ES索引管理] 索引检查完成")
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[ES索引管理] 初始化失败，业务仍可启动但ES查询可能不可用",
                      exc_info=True)

    # ====================================================================
    # 索引 CRUD
    # ====================================================================
    def createIndexIfAbsent(self, indexName: str, classpathMapping: str) -> bool:
        """创建索引（若不存在）

        :param indexName: 索引名
        :param classpathMapping: classpath 下的 Mapping JSON 路径
        :return: true 表示新建；false 表示已存在跳过
        """
        existsReq: GetIndexRequest = GetIndexRequest(indexName)
        if self.esClient.indices().exists(existsReq, RequestOptions.DEFAULT):
            log.info("[ES索引管理] 索引已存在, 跳过创建: %s", indexName)
            return False

        settings: str = self.buildSettingsAndMapping(classpathMapping)
        createReq: CreateIndexRequest = CreateIndexRequest(indexName)
        createReq.source(settings, XContentType.JSON)

        # 挂载 ILM 策略：索引滚动/分层由 ILM 接管
        if self.attachIlm:
            createReq.settings('{"index.lifecycle.name":"' + self.ilmPolicyName + '"}',
                               XContentType.JSON)

        resp: CreateIndexResponse = self.esClient.indices().create(
            createReq, RequestOptions.DEFAULT)
        log.info("[ES索引管理] 索引创建成功: %s, acknowledged=%s",
                 indexName, resp.isAcknowledged())
        return True

    def dropIndex(self, indexName: str) -> bool:
        """删除索引（运维使用，慎用）"""
        deleteReq: DeleteIndexRequest = DeleteIndexRequest(indexName)
        resp: AcknowledgedResponse = self.esClient.indices().delete(
            deleteReq, RequestOptions.DEFAULT)
        log.warning("[ES索引管理] 索引已删除: %s, acknowledged=%s",
                    indexName, resp.isAcknowledged())
        return resp.isAcknowledged()

    def addAlias(self, indexName: str, aliasName: str) -> bool:
        """为索引添加别名（hot/warm 分层时使用）

        例如: 将 ods_snapshot_hot_202606 添加到别名 ods_snapshot_hot
             前端查询只使用别名，自动路由到具体索引
        """
        # 【Java→Python】`new AliasActions(AliasActions.Type.ADD)`：内部类路径保持不变
        action: AliasActions = (AliasActions(AliasActions.Type.ADD)
                                .alias(aliasName).index(indexName))
        request: IndicesAliasesRequest = IndicesAliasesRequest()
        request.addAliasAction(action)
        resp: AcknowledgedResponse = self.esClient.indices().updateAliases(
            request, RequestOptions.DEFAULT)
        log.info("[ES索引管理] 别名已添加: %s -> %s, acknowledged=%s",
                 indexName, aliasName, resp.isAcknowledged())
        return resp.isAcknowledged()

    def isIndexHealthy(self, indexName: str) -> bool:
        """检查 ES 与索引健康状态"""
        try:
            req: GetIndexRequest = GetIndexRequest(indexName)
            return self.esClient.indices().exists(req, RequestOptions.DEFAULT)
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            log.error("[ES索引管理] 索引健康检查失败 index=%s", indexName, exc_info=True)
            return False

    # ====================================================================
    # ILM 生命周期管理
    # ====================================================================
    def createIndexLifecyclePolicyIfAbsent(self, policyName: str) -> bool:
        """创建 ILM 策略（幂等）：hot(0-30d) -> warm(30-90d) -> cold(90-365d) -> delete(>365d)

        实现说明：7.17 的 rest-high-level-client 未暴露 ILM 高层 API，故使用低层 REST 客户端
        PUT /_ilm/policy/{name} 写入策略 JSON，保证编译兼容。
        """
        # 已存在则跳过（避免覆盖运维可能调整的阈值）
        if self.ilmPolicyExists(policyName):
            log.info("[ES索引管理] ILM 策略已存在, 跳过创建: %s", policyName)
            return False
        policyJson: str = self.buildIlmPolicyJson()
        request: Request = Request("PUT", "/_ilm/policy/" + policyName)
        request.setJsonEntity(policyJson)
        response: Response = self.esClient.getLowLevelClient().performRequest(request)
        status: int = response.getStatusLine().getStatusCode()
        created: bool = status == 200 or status == 201
        log.info("[ES索引管理] ILM 策略创建: %s, status=%s", policyName, status)
        return created

    def attachLifecyclePolicy(self, indexName: str, policyName: str) -> bool:
        """将已有索引挂载到 ILM 策略

        通过 PUT /{index}/_settings 设置 index.lifecycle.name 实现冷热分层接管。
        """
        request: Request = Request("PUT", "/" + indexName + "/_settings")
        request.setJsonEntity('{"index.lifecycle.name":"' + policyName + '"}')
        response: Response = self.esClient.getLowLevelClient().performRequest(request)
        status: int = response.getStatusLine().getStatusCode()
        log.info("[ES索引管理] 挂载 ILM 策略: index=%s, policy=%s, status=%s",
                 indexName, policyName, status)
        return status == 200 or status == 201

    def ilmPolicyExists(self, policyName: str) -> bool:
        """判断 ILM 策略是否已存在"""
        try:
            request: Request = Request("GET", "/_ilm/policy/" + policyName)
            response: Response = self.esClient.getLowLevelClient().performRequest(request)
            if response.getStatusLine().getStatusCode() == 200:
                body: str = EntityUtils.toString(
                    response.getEntity(), StandardCharsets.UTF_8)
                node: JsonNode = EsIndexManageService.OBJECT_MAPPER.readTree(body)
                return node.has(policyName)
            return False
        except Exception:  # noqa: BLE001 - 与 Java 的 catch (Exception e) 一致
            # 404 表示不存在；其它异常按不存在处理，由调用方重试创建
            return False

    def buildIlmPolicyJson(self) -> str:
        """构建 ILM 策略 JSON（hot/warm/cold/delete）"""
        # 【Java→Python】Java 的 `"..." + "..."` 字符串拼接 → Python 的 `+` 拼接
        # （逐行照搬，保持 JSON 文本与原工程完全一致）
        return ("{\n" +
                "  \"policy\": {\n" +
                "    \"phases\": {\n" +
                "      \"hot\": {\n" +
                "        \"min_age\": \"0ms\",\n" +
                "        \"actions\": {\n" +
                "          \"set_priority\": { \"priority\": 100 },\n" +
                "          \"rollover\": { \"max_age\": \"30d\", \"max_primary_shard_size\": \"50gb\" }\n" +
                "        }\n" +
                "      },\n" +
                "      \"warm\": {\n" +
                "        \"min_age\": \"30d\",\n" +
                "        \"actions\": {\n" +
                "          \"set_priority\": { \"priority\": 50 },\n" +
                "          \"forcemerge\": { \"max_num_segments\": 1 },\n" +
                "          \"shrink\": { \"number_of_shards\": 1 }\n" +
                "        }\n" +
                "      },\n" +
                "      \"cold\": {\n" +
                "        \"min_age\": \"90d\",\n" +
                "        \"actions\": {\n" +
                "          \"set_priority\": { \"priority\": 0 },\n" +
                "          \"freeze\": {}\n" +
                "        }\n" +
                "      },\n" +
                "      \"delete\": {\n" +
                "        \"min_age\": \"365d\",\n" +
                "        \"actions\": { \"delete\": {} }\n" +
                "      }\n" +
                "    }\n" +
                "  }\n" +
                "}")

    # ====================================================================
    # 私有辅助方法
    # ====================================================================
    def buildSettingsAndMapping(self, classpathMapping: str) -> str:
        """加载 classpath 下的索引 Mapping 文件，并注入分片/副本配置"""
        resource: ClassPathResource = ClassPathResource(classpathMapping)
        if not resource.exists():
            # 【Java→Python】`throw new IOException(msg)` → `raise OSError(msg)`
            raise OSError("Mapping 文件不存在: " + classpathMapping
                          + "。请确保 src/main/resources 下存在对应文件。")
        # 【Java→Python】try-with-resources → `with ... as is:`
        with resource.getInputStream() as is_stream:
            mapping: str = StreamUtils.copyToString(
                is_stream, StandardCharsets.UTF_8)
            # 注入分片/副本配置（覆盖占位符）
            return (mapping.replace("__NUMBER_OF_SHARDS__", str(self.numberOfShards))
                    .replace("__NUMBER_OF_REPLICAS__", str(self.numberOfReplicas)))

    # ====================================================================
    # Getter（供其它服务引用索引名）
    # ====================================================================
    def getSnapshotIndex(self) -> str:
        return self.snapshotIndex

    def getFeeIndex(self) -> str:
        return self.feeIndex

    def getTrailIndex(self) -> str:
        return self.trailIndex

    def getIlmPolicyName(self) -> str:
        return self.ilmPolicyName

    def resolveIndexName(self, ds) -> str:
        """按统一数据源枚举解析索引名（供同步/查询/对账服务共用，保证索引名一致）

        :param ds: 数据源 / data source
        :return: 索引名 / index name
        """
        # 【Java→Python】延迟导入：UnifiedQueryService 反向 import 本类，
        # 模块级 import 会形成循环依赖（详见文件头第 9 条）
        from com.ruoyi.base.service.optimization.UnifiedQueryService import (
            UnifiedQueryService,
        )

        if ds is UnifiedQueryService.DataSource.SNAPSHOT:
            return self.snapshotIndex
        if ds is UnifiedQueryService.DataSource.FEE:
            return self.feeIndex
        if ds is UnifiedQueryService.DataSource.TRAIL:
            return self.trailIndex
        # default: `throw new IllegalArgumentException("未知数据源: " + ds)`
        raise ValueError("未知数据源: " + str(ds))

    def __repr__(self) -> str:
        return ("EsIndexManageService(snapshotIndex=%s, feeIndex=%s, trailIndex=%s, "
                "autoCreate=%s)" % (self.snapshotIndex, self.feeIndex,
                                    self.trailIndex, self.autoCreate))

