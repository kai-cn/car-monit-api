package com.ruoyi.base.service.v3.es;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.util.EntityUtils;
import org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest;
import org.elasticsearch.action.admin.indices.alias.IndicesAliasesRequest.AliasActions;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.client.indices.CreateIndexRequest;
import org.elasticsearch.client.indices.GetIndexRequest;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.util.StreamUtils;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * V3 ES 月索引/模板/ILM 管理。
 *
 * <p>设计 §5.3：按月一个索引、1 主 1 副本、读别名 {@code *-read}、写别名 {@code *-write}。
 * 与旧版 {@code EsIndexManageService} 保持隔离：旧服务面向固定索引名，本服务面向
 * {@code snapshot-flow-YYYYMM} 等新索引，避免影响旧链路。</p>
 */
@Slf4j
@Service
public class TrafficEsIndexService {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    private static final String ILM_POLICY = "traffic_hot_warm_cold";

    /** 实时预警固定索引（非按月；设计 §5.4.4 car-warning） */
    public static final String CAR_WARNING_INDEX = "car-warning";
    public static final String CAR_WARNING_TEMPLATE_NAME = "car-warning-template";
    public static final String CAR_WARNING_TEMPLATE_FILE = "es/v3/car_warning_template.json";

    private static final Map<TrafficTable, String> TEMPLATE_FILES = new LinkedHashMap<>();
    private static final Map<TrafficTable, String> TEMPLATE_NAMES = new LinkedHashMap<>();

    static {
        TEMPLATE_FILES.put(TrafficTable.SNAPSHOT, "es/v3/snapshot_flow_template.json");
        TEMPLATE_FILES.put(TrafficTable.FEE, "es/v3/fee_records_template.json");
        TEMPLATE_FILES.put(TrafficTable.TRAIL, "es/v3/trail_fitting_template.json");
        TEMPLATE_NAMES.put(TrafficTable.SNAPSHOT, "snapshot-flow-template");
        TEMPLATE_NAMES.put(TrafficTable.FEE, "fee-records-template");
        TEMPLATE_NAMES.put(TrafficTable.TRAIL, "trail-fitting-template");
    }

    private final RestHighLevelClient esClient;
    private final TrafficV3Properties properties;

    public TrafficEsIndexService(RestHighLevelClient esClient, TrafficV3Properties properties) {
        this.esClient = esClient;
        this.properties = properties;
    }

    /**
     * 启动自动初始化（默认关闭）。开启后创建 ILM/模板/最近 N 个月索引；
     * 失败只记录日志，不阻断应用启动（设计“ES 故障可降级/异步恢复”）。
     */
    @PostConstruct
    public void init() {
        if (!properties.getEs().isAutoBootstrap()) {
            log.info("[V3 ES] auto-bootstrap=false，跳过自动初始化（请执行 scripts/v3/es-init.ps1）");
            return;
        }
        try {
            bootstrap(properties.getEs().getBootstrapMonths(), properties.getEs().getForwardMonths());
        } catch (Exception e) {
            log.error("[V3 ES] 自动初始化失败，应用继续启动（查询将返回 503）", e);
        }
    }

    /**
     * 创建 ILM 策略 + 三套月索引模板 + 月索引与读写别名。
     *
     * @param monthsBack    向前创建多少个月（含当前月）
     * @param monthsForward 向后预建多少个月
     */
    public Map<String, Object> bootstrap(int monthsBack, int monthsForward) throws IOException {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ilmPolicy", createIlmPolicyIfAbsent());
        result.put("templates", createTemplates());

        List<String> created = new ArrayList<>();
        List<String> skipped = new ArrayList<>();
        YearMonth current = YearMonth.now(ZONE);
        for (int offset = -(Math.max(1, monthsBack) - 1); offset <= Math.max(0, monthsForward); offset++) {
            YearMonth ym = current.plusMonths(offset);
            for (TrafficTable table : TrafficTable.values()) {
                boolean isCreated = ensureMonthlyIndex(table, ym);
                (isCreated ? created : skipped).add(table.monthlyIndex(ym));
            }
        }
        result.put("created", created);
        result.put("skipped", skipped);
        result.put("currentWriteMonth", current.toString());
        result.put("carWarningIndex", ensureCarWarningIndex() ? "created" : "exists");
        log.info("[V3 ES] bootstrap 完成: 新建 {} 个索引，跳过 {} 个", created.size(), skipped.size());
        return result;
    }

    /**
     * 确保实时预警索引 car-warning 存在（固定单索引，不挂 ILM，避免被转 warm/只读）。
     *
     * @return true=本次新建
     */
    public boolean ensureCarWarningIndex() throws IOException {
        if (indexExists(CAR_WARNING_INDEX)) {
            return false;
        }
        CreateIndexRequest request = new CreateIndexRequest(CAR_WARNING_INDEX);
        // settings/mappings 由 car-warning-template 自动应用
        request.source("{}", XContentType.JSON);
        esClient.indices().create(request, RequestOptions.DEFAULT);
        log.info("[V3 ES] 创建实时预警索引: {}", CAR_WARNING_INDEX);
        return true;
    }

    /** car-warning 索引是否存在（缺失时 warning/list 返回空列表而非 503） */
    public boolean carWarningIndexExists() {
        try {
            return indexExists(CAR_WARNING_INDEX);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 确保某月索引存在，并维护读别名；当月维护写别名。
     *
     * @return true=本次新建索引
     */
    public boolean ensureMonthlyIndex(TrafficTable table, YearMonth ym) throws IOException {
        String indexName = table.monthlyIndex(ym);
        boolean created = false;
        if (!indexExists(indexName)) {
            CreateIndexRequest request = new CreateIndexRequest(indexName);
            // 只设置别名；settings/mappings 由月索引模板自动应用
            request.source("{\"aliases\":{\"" + table.readAlias() + "\":{}}}", XContentType.JSON);
            esClient.indices().create(request, RequestOptions.DEFAULT);
            created = true;
            log.info("[V3 ES] 创建月索引: {}", indexName);
        } else {
            addAlias(indexName, table.readAlias());
        }

        if (YearMonth.now(ZONE).equals(ym)) {
            pointWriteAliasTo(table, indexName);
        }
        return created;
    }

    /**
     * 按事件时间定位月索引，并确保索引存在（用于同步/回灌，晚到事件写具体月索引）。
     */
    public String ensureIndexForEventTime(TrafficTable table, long epochMillis) throws IOException {
        YearMonth ym = YearMonth.from(Instant.ofEpochMilli(epochMillis).atZone(ZONE));
        ensureMonthlyIndex(table, ym);
        return table.monthlyIndex(ym);
    }

    /** 事件时间对应的月索引名（不保证已存在） */
    public String indexNameForEventTime(TrafficTable table, long epochMillis) {
        YearMonth ym = YearMonth.from(Instant.ofEpochMilli(epochMillis).atZone(ZONE));
        return table.monthlyIndex(ym);
    }

    public boolean indexExists(String indexName) throws IOException {
        GetIndexRequest request = new GetIndexRequest(indexName);
        return esClient.indices().exists(request, RequestOptions.DEFAULT);
    }

    /** 读别名是否存在（启动就绪检测用） */
    public boolean readAliasExists(TrafficTable table) {
        return aliasExists(table.readAlias());
    }

    /** 写别名是否存在（同步链路就绪检测用） */
    public boolean writeAliasExists(TrafficTable table) {
        return aliasExists(table.writeAlias());
    }

    /** 当前月索引是否存在 */
    public boolean currentIndexExists(TrafficTable table) {
        try {
            return indexExists(currentIndexName(table));
        } catch (Exception e) {
            return false;
        }
    }

    /** 别名是否存在（GET /_alias/{alias} 返回 200 即存在） */
    public boolean aliasExists(String aliasName) {
        return exists("/_alias/" + aliasName);
    }

    /** ES 是否可用（查询前置检查，不可用时不回退 GaussDB） */
    public boolean ping() {
        try {
            return esClient.ping(RequestOptions.DEFAULT);
        } catch (Exception e) {
            return false;
        }
    }

    // ============================================================
    // ILM / Template
    // ============================================================

    /**
     * 幂等创建 ILM 策略；已存在则跳过（避免覆盖运维调整）。
     */
    public String createIlmPolicyIfAbsent() throws IOException {
        if (exists("/_ilm/policy/" + ILM_POLICY)) {
            return "exists";
        }
        String body = readClasspath("es/v3/ilm_traffic_hot_warm_cold.json");
        Request request = new Request("PUT", "/_ilm/policy/" + ILM_POLICY);
        request.setJsonEntity(body);
        Response response = esClient.getLowLevelClient().performRequest(request);
        return response.getStatusLine().getStatusCode() == 200 ? "created" : "failed";
    }

    /**
     * 覆盖写三套月索引模板 + car-warning 模板（幂等，字段变更后重新执行即可）。
     */
    public List<String> createTemplates() throws IOException {
        List<String> done = new ArrayList<>();
        for (TrafficTable table : TrafficTable.values()) {
            String body = readClasspath(TEMPLATE_FILES.get(table));
            Request request = new Request("PUT", "/_index_template/" + TEMPLATE_NAMES.get(table));
            request.setJsonEntity(body);
            Response response = esClient.getLowLevelClient().performRequest(request);
            int status = response.getStatusLine().getStatusCode();
            if (status == 200 || status == 201) {
                done.add(TEMPLATE_NAMES.get(table));
            } else {
                throw new IOException("创建模板失败: " + TEMPLATE_NAMES.get(table) + ", status=" + status);
            }
        }

        String carWarningBody = readClasspath(CAR_WARNING_TEMPLATE_FILE);
        Request carWarningRequest = new Request("PUT", "/_index_template/" + CAR_WARNING_TEMPLATE_NAME);
        carWarningRequest.setJsonEntity(carWarningBody);
        Response carWarningResponse = esClient.getLowLevelClient().performRequest(carWarningRequest);
        int carWarningStatus = carWarningResponse.getStatusLine().getStatusCode();
        if (carWarningStatus == 200 || carWarningStatus == 201) {
            done.add(CAR_WARNING_TEMPLATE_NAME);
        } else {
            throw new IOException("创建模板失败: " + CAR_WARNING_TEMPLATE_NAME
                    + ", status=" + carWarningStatus);
        }
        return done;
    }

    // ============================================================
    // Alias
    // ============================================================

    /**
     * 读别名：幂等添加。
     */
    public void addAlias(String indexName, String aliasName) throws IOException {
        AliasActions action = new AliasActions(AliasActions.Type.ADD)
                .index(indexName).alias(aliasName);
        IndicesAliasesRequest request = new IndicesAliasesRequest();
        request.addAliasAction(action);
        esClient.indices().updateAliases(request, RequestOptions.DEFAULT);
    }

    /**
     * 写别名必须只指向当月索引：先移除其它索引上的写别名，再添加到目标索引。
     * 否则月初切换后写入会落到两个月索引，造成重复。
     */
    public void pointWriteAliasTo(TrafficTable table, String targetIndex) throws IOException {
        String alias = table.writeAlias();
        List<String> pointing = indicesForAlias(alias);
        IndicesAliasesRequest request = new IndicesAliasesRequest();
        for (String index : pointing) {
            if (!index.equals(targetIndex)) {
                request.addAliasAction(new AliasActions(AliasActions.Type.REMOVE)
                        .index(index).alias(alias));
            }
        }
        request.addAliasAction(new AliasActions(AliasActions.Type.ADD)
                .index(targetIndex).alias(alias));
        esClient.indices().updateAliases(request, RequestOptions.DEFAULT);
        log.info("[V3 ES] 写别名 {} -> {}", alias, targetIndex);
    }

    /** 查询别名当前指向的索引列表；别名不存在返回空列表。 */
    private List<String> indicesForAlias(String alias) {
        List<String> indices = new ArrayList<>();
        try {
            Response response = esClient.getLowLevelClient()
                    .performRequest(new Request("GET", "/_alias/" + alias));
            if (response.getStatusLine().getStatusCode() != 200) {
                return indices;
            }
            String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
            JsonNode node = MAPPER.readTree(body);
            // Jackson 3：JsonNode.fieldNames() 更名 propertyNames()
            node.propertyNames().forEach(indices::add);
        } catch (Exception e) {
            log.debug("[V3 ES] 读取别名 {} 失败（按不存在处理）: {}", alias, e.getMessage());
        }
        return indices;
    }

    // ============================================================
    // Helpers
    // ============================================================

    private boolean exists(String path) {
        try {
            Response response = esClient.getLowLevelClient().performRequest(new Request("GET", path));
            return response.getStatusLine().getStatusCode() == 200;
        } catch (Exception e) {
            return false;
        }
    }

    private String readClasspath(String path) throws IOException {
        ClassPathResource resource = new ClassPathResource(path);
        if (!resource.exists()) {
            throw new IOException("classpath 资源不存在: " + path);
        }
        try (InputStream is = resource.getInputStream()) {
            return StreamUtils.copyToString(is, StandardCharsets.UTF_8);
        }
    }

    /** 当前月索引名（运维/日志用） */
    public String currentIndexName(TrafficTable table) {
        return table.monthlyIndex(YearMonth.now(ZONE));
    }

    /** 日期格式辅助：LocalDate -> epoch millis（Asia/Shanghai 当天 00:00） */
    public static long startOfDayMillis(LocalDate date) {
        return date.atStartOfDay(ZONE).toInstant().toEpochMilli();
    }
}
