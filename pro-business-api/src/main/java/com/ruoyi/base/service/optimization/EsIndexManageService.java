package com.ruoyi.base.service.optimization;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.util.EntityUtils;
import org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest;
import org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest.AliasActions;
import org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest;
import org.elasticsearch.action.support.master.AcknowledgedResponse;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.client.indices.CreateIndexRequest;
import org.elasticsearch.client.indices.CreateIndexResponse;
import org.elasticsearch.client.indices.GetIndexRequest;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.util.StreamUtils;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

/**
 * ES 索引管理服务 / Elasticsearch Index Management Service
 *
 * =================================================================================
 * 职责 / Responsibilities:
 *   1. 三张大表对应 ES 索引的创建/初始化（ngram 分词 + .ngram 子字段）
 *      Create/initialize ES indices for the three large tables (ngram + .ngram sub-field)
 *   2. ILM 生命周期策略（hot/warm/cold/frozen）的创建与挂载
 *      Create & attach ILM lifecycle policy (hot/warm/cold/frozen)
 *   3. 索引别名管理（hot/warm 数据分层时使用）
 *      Alias management for hot/warm data tiering
 *   4. 索引健康检查
 *      Index health check
 *
 * 索引设计原则 / Index design principles:
 *   - 通用模糊查询字段统一使用 keyword 基字段（天然充当 .keyword）+ text.ngram 双映射
 *     Fuzzy fields use a keyword base field (serves as .keyword) plus a text.ngram sub-field
 *   - ngram analyzer: min_gram=2, max_gram=4, 仅保留 letter/digit 字符
 *     ngram analyzer keeps only letter/digit tokens
 *   - 时间字段使用 date 类型，支持多格式兼容
 *     Time fields use the date type with multiple format compatibility
 *
 * 索引说明 / Index mapping:
 *   - snapshot_flow  -> ods_rt_szdn_snapshot_flow_addcode  (时间字段: snapshottime)
 *   - fee_records    -> ods_lwzxsfsj_fee_records_01        (时间字段: transtime)
 *   - trail_fitting  -> zdata_trail_fitting                 (时间字段: extime)
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class EsIndexManageService {

    @Autowired
    private RestHighLevelClient esClient;

    /** 三张表对应的索引名，通过 application.yml 可覆盖 */
    @Value("${elasticsearch.index.snapshot:snapshot_flow}")
    private String snapshotIndex;

    @Value("${elasticsearch.index.fee:fee_records}")
    private String feeIndex;

    @Value("${elasticsearch.index.trail:trail_fitting}")
    private String trailIndex;

    /** 索引创建时的分片数（按 ES 集群 3+ 节点场景，建议 6-12） */
    @Value("${elasticsearch.index.shards:6}")
    private int numberOfShards;

    @Value("${elasticsearch.index.replicas:1}")
    private int numberOfReplicas;

    /** 是否在启动时自动创建缺失索引（仅开发环境建议开启） */
    @Value("${elasticsearch.index.auto-create:false}")
    private boolean autoCreate;

    /** ILM 策略名称（hot/warm/cold/frozen 统一管理三表索引） */
    @Value("${elasticsearch.index.ilm-policy:car_monit_ilm_policy}")
    private String ilmPolicyName;

    /** 是否在创建索引时挂载 ILM 策略（生产环境建议开启，实现冷热分层） */
    @Value("${elasticsearch.index.attach-ilm:false}")
    private boolean attachIlm;

    /** Jackson 解析器，用于校验 ILM 策略是否已存在 */
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    /** 三张表的索引清单（classpath 下的 mapping JSON 文件名与之一一对应） */
    private static final List<String> ALL_INDEXES = Arrays.asList(
            "snapshot_flow", "fee_records", "trail_fitting"
    );

    /**
     * 应用启动时自动检查并创建缺失的索引 + ILM 策略
     * Auto-create missing indices and the ILM policy on startup.
     *
     * 仅在 elasticsearch.index.auto-create=true 时生效；生产环境建议通过运维脚本初始化，
     * 但 ILM 策略无论 auto-create 是否开启都尝试创建（幂等），保证生命周期管理可用。
     * Only effective when auto-create=true; the ILM policy is created idempotently regardless.
     */
    @PostConstruct
    public void init() {
        // ILM 策略幂等创建（不依赖 auto-create 开关）
        try {
            createIndexLifecyclePolicyIfAbsent(ilmPolicyName);
        } catch (Exception e) {
            log.warn("[ES索引管理] ILM 策略创建失败(可忽略, 后续重试): {}", e.getMessage());
        }

        if (!autoCreate) {
            log.info("[ES索引管理] auto-create=false, 跳过索引自动创建。索引将需要手动初始化。");
            return;
        }
        try {
            log.info("[ES索引管理] auto-create=true, 开始检查并创建缺失索引...");
            createIndexIfAbsent(snapshotIndex, "es/index/snapshot_flow.json");
            createIndexIfAbsent(feeIndex,     "es/index/fee_records.json");
            createIndexIfAbsent(trailIndex,   "es/index/trail_fitting.json");
            log.info("[ES索引管理] 索引检查完成");
        } catch (Exception e) {
            log.error("[ES索引管理] 初始化失败，业务仍可启动但ES查询可能不可用", e);
        }
    }

    /**
     * 创建索引（若不存在）/ Create index if absent.
     *
     * @param indexName 索引名 / index name
     * @param classpathMapping classpath 下的 Mapping JSON 路径 / classpath mapping JSON path
     * @return true 表示新建；false 表示已存在跳过 / true=newly created, false=already existed
     */
    public boolean createIndexIfAbsent(String indexName, String classpathMapping) throws IOException {
        GetIndexRequest existsReq = new GetIndexRequest(indexName);
        if (esClient.indices().exists(existsReq, RequestOptions.DEFAULT)) {
            log.info("[ES索引管理] 索引已存在, 跳过创建: {}", indexName);
            return false;
        }

        String settings = buildSettingsAndMapping(classpathMapping);
        CreateIndexRequest createReq = new CreateIndexRequest(indexName);
        createReq.source(settings, XContentType.JSON);

        // 挂载 ILM 策略：索引滚动/分层由 ILM 接管
        if (attachIlm) {
            createReq.settings("{\"index.lifecycle.name\":\"" + ilmPolicyName + "\"}", XContentType.JSON);
        }

        CreateIndexResponse resp = esClient.indices().create(createReq, RequestOptions.DEFAULT);
        log.info("[ES索引管理] 索引创建成功: {}, acknowledged={}", indexName, resp.isAcknowledged());
        return true;
    }

    /**
     * 删除索引（运维使用，慎用）/ Drop index (operation use, with caution).
     */
    public boolean dropIndex(String indexName) throws IOException {
        DeleteIndexRequest deleteReq = new DeleteIndexRequest(indexName);
        AcknowledgedResponse resp = esClient.indices().delete(deleteReq, RequestOptions.DEFAULT);
        log.warn("[ES索引管理] 索引已删除: {}, acknowledged={}", indexName, resp.isAcknowledged());
        return resp.isAcknowledged();
    }

    /**
     * 为索引添加别名（hot/warm 分层时使用）/ Add alias for hot/warm tiering.
     *
     * 例如: 将 ods_snapshot_hot_202606 添加到别名 ods_snapshot_hot
     *      前端查询只使用别名，自动路由到具体索引 / Queries use alias only.
     */
    public boolean addAlias(String indexName, String aliasName) throws IOException {
        AliasActions action = new AliasActions(AliasActions.Type.ADD)
                .alias(aliasName).index(indexName);
        IndicesAliasesRequest request = new IndicesAliasesRequest();
        request.addAliasAction(action);
        AcknowledgedResponse resp = esClient.indices().updateAliases(request, RequestOptions.DEFAULT);
        log.info("[ES索引管理] 别名已添加: {} -> {}, acknowledged={}",
                indexName, aliasName, resp.isAcknowledged());
        return resp.isAcknowledged();
    }

    /**
     * 检查 ES 与索引健康状态 / Health check for the given index.
     */
    public boolean isIndexHealthy(String indexName) {
        try {
            GetIndexRequest req = new GetIndexRequest(indexName);
            return esClient.indices().exists(req, RequestOptions.DEFAULT);
        } catch (Exception e) {
            log.error("[ES索引管理] 索引健康检查失败 index={}", indexName, e);
            return false;
        }
    }

    // ============================================================
    // ILM 生命周期管理 / ILM lifecycle management
    // ============================================================

    /**
     * 创建 ILM 策略（幂等）：hot(0-30d) -> warm(30-90d) -> cold(90-365d) -> delete(>365d)
     * Create ILM policy (idempotent) with hot/warm/cold/delete phases.
     *
     * 设计思路 / Design rationale:
     *   - hot：最近 30 天高频查询，多分片、低 refresh，保证写入与查询性能
     *         last 30 days, hot tier, more shards & low refresh for write/read performance
     *   - warm：30-90 天降频查询，shrink 到 1 分片 + forcemerge 1 segment，节省资源
     *         30-90 days, shrink to 1 shard + forcemerge, save resources
     *   - cold：90-365 天低频查询，freeze 冻结，几乎不占内存
     *         90-365 days, freeze for rarely accessed data
     *   - delete：超过 365 天自动删除（原始明细已由 GaussDB 分区保留，ES 无需长期留存）
     *         >365 days auto-delete (GaussDB keeps the source of truth)
     *
     * 实现说明：7.17 的 rest-high-level-client 未暴露 ILM 高层 API，故使用低层 REST 客户端
     * PUT /_ilm/policy/{name} 写入策略 JSON，保证编译兼容。
     * Note: HLRC 7.17 has no ILM high-level API, so we use the low-level REST client.
     */
    public boolean createIndexLifecyclePolicyIfAbsent(String policyName) throws IOException {
        // 已存在则跳过（避免覆盖运维可能调整的阈值）
        if (ilmPolicyExists(policyName)) {
            log.info("[ES索引管理] ILM 策略已存在, 跳过创建: {}", policyName);
            return false;
        }
        String policyJson = buildIlmPolicyJson();
        Request request = new Request("PUT", "/_ilm/policy/" + policyName);
        request.setJsonEntity(policyJson);
        Response response = esClient.getLowLevelClient().performRequest(request);
        int status = response.getStatusLine().getStatusCode();
        boolean created = status == 200 || status == 201;
        log.info("[ES索引管理] ILM 策略创建: {}, status={}", policyName, status);
        return created;
    }

    /**
     * 将已有索引挂载到 ILM 策略 / Attach an existing index to the ILM policy.
     *
     * 通过 PUT /{index}/_settings 设置 index.lifecycle.name 实现冷热分层接管。
     */
    public boolean attachLifecyclePolicy(String indexName, String policyName) throws IOException {
        Request request = new Request("PUT", "/" + indexName + "/_settings");
        request.setJsonEntity("{\"index.lifecycle.name\":\"" + policyName + "\"}");
        Response response = esClient.getLowLevelClient().performRequest(request);
        int status = response.getStatusLine().getStatusCode();
        log.info("[ES索引管理] 挂载 ILM 策略: index={}, policy={}, status={}", indexName, policyName, status);
        return status == 200 || status == 201;
    }

    /**
     * 判断 ILM 策略是否已存在 / Check whether the ILM policy already exists.
     */
    private boolean ilmPolicyExists(String policyName) {
        try {
            Request request = new Request("GET", "/_ilm/policy/" + policyName);
            Response response = esClient.getLowLevelClient().performRequest(request);
            if (response.getStatusLine().getStatusCode() == 200) {
                String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
                JsonNode node = OBJECT_MAPPER.readTree(body);
                return node.has(policyName);
            }
            return false;
        } catch (Exception e) {
            // 404 表示不存在；其它异常按不存在处理，由调用方重试创建
            return false;
        }
    }

    /**
     * 构建 ILM 策略 JSON（hot/warm/cold/delete）/ Build the ILM policy JSON.
     */
    private String buildIlmPolicyJson() {
        return "{\n" +
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
                "}";
    }

    // ============================================================
    // 私有辅助方法 / Private helpers
    // ============================================================

    /**
     * 加载 classpath 下的索引 Mapping 文件，并注入分片/副本配置
     * Load the classpath mapping JSON and inject shard/replica settings.
     */
    private String buildSettingsAndMapping(String classpathMapping) throws IOException {
        ClassPathResource resource = new ClassPathResource(classpathMapping);
        if (!resource.exists()) {
            throw new IOException("Mapping 文件不存在: " + classpathMapping
                    + "。请确保 src/main/resources 下存在对应文件。");
        }
        try (InputStream is = resource.getInputStream()) {
            String mapping = StreamUtils.copyToString(is, StandardCharsets.UTF_8);
            // 注入分片/副本配置（覆盖占位符）
            return mapping.replace("__NUMBER_OF_SHARDS__", String.valueOf(numberOfShards))
                          .replace("__NUMBER_OF_REPLICAS__", String.valueOf(numberOfReplicas));
        }
    }

    // ============================================================
    // Getter (供其它服务引用索引名) / Getters for index names
    // ============================================================
    public String getSnapshotIndex() { return snapshotIndex; }
    public String getFeeIndex()     { return feeIndex;     }
    public String getTrailIndex()   { return trailIndex;   }
    public String getIlmPolicyName() { return ilmPolicyName; }

    /**
     * 按统一数据源枚举解析索引名（供同步/查询/对账服务共用，保证索引名一致）
     * Resolve the index name by the unified DataSource enum (shared by sync/query/reconcile services).
     *
     * @param ds 数据源 / data source
     * @return 索引名 / index name
     */
    public String resolveIndexName(UnifiedQueryService.DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return snapshotIndex;
            case FEE:      return feeIndex;
            case TRAIL:    return trailIndex;
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }
}
