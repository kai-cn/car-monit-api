package com.ruoyi.base.service.optimization;

import com.alibaba.fastjson2.JSON;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.HttpHost;
import org.elasticsearch.action.search.*;
import org.elasticsearch.client.*;
import org.elasticsearch.core.TimeValue;
import org.elasticsearch.index.query.*;
import org.elasticsearch.search.Scroll;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.aggregations.AggregationBuilders;
import org.elasticsearch.search.aggregations.bucket.terms.ParsedStringTerms;
import org.elasticsearch.search.aggregations.bucket.terms.Terms;
import org.elasticsearch.search.aggregations.metrics.ValueCount;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.stream.Collectors;

/**
 * 超大规模数据查询服务（导出 / 统计，三表统一）
 * Large-scale query service (export / aggregation, unified for 3 tables).
 *
 * ====================================================================
 * 核心设计思路（针对 8 亿条数据）/ Core design for 800M-row scale:
 *   1. 倒排索引分层：hot(0-30d)/warm(30-90d)/cold/frozen，由 ILM 管理
 *      Tiered storage managed by ILM
 *   2. 全字段模糊查询：ngram 倒排索引（match on .ngram，term/wildcard on .keyword）
 *      Full fuzzy via ngram inverted index
 *   3. 统计：ES aggregation 分布式并行，不拉原始数据到应用层
 *      Aggregation computed on shards in parallel
 *   4. 导出：PIT + search_after / Scroll 游标深翻页，流式写文件，避免 OOM
 *      Export via cursor pagination, streamed to disk
 *   5. 查询保障：search_after 替代 from+size 深翻页；terminate_after + timeout 双保险
 *      search_after instead of from+size; terminate_after + timeout guardrails
 *
 * 本服务支持三表（通过 type 参数区分）：snapshot / fee / trail
 * Supports 3 tables selected by the `type` parameter: snapshot / fee / trail
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class LargeScaleQueryService {

    private RestHighLevelClient client;

    @Value("${elasticsearch.host:127.0.0.1}")
    private String esHost;

    @Value("${elasticsearch.port:9200}")
    private int esPort;

    /** 导出文件根目录 / export file root dir */
    @Value("${optimization.export.dir:/data/export}")
    private String exportDir;

    /** 单次 ES 查询超时（秒） / single query timeout (s) */
    private static final int QUERY_TIMEOUT_SECONDS = 30;

    /** 单次 scroll 最大文档数 / max docs per scroll batch */
    private static final int SCROLL_BATCH_SIZE = 2000;

    /** 导出文件每 N 条切一个文件 / split a new file every N rows */
    private static final int EXPORT_BATCH_SIZE = 100000;

    private final ExecutorService queryExecutor = new ThreadPoolExecutor(
            4, 8, 60L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(500),
            new NamedThreadFactory("lq-worker"),
            new ThreadPoolExecutor.CallerRunsPolicy()
    );

    /** 导出任务追踪 Map (taskId -> status) / export task tracking */
    private final Map<String, ExportTaskStatus> exportTaskMap = new ConcurrentHashMap<>();

    /** 索引名解析（与同步/对账服务共用，保证索引名一致） / shared index name resolver */
    @Autowired
    private EsIndexManageService indexManageService;

    @PostConstruct
    public void init() {
        log.info("[大规模查询服务] 初始化 ES 客户端 host={}, port={}", esHost, esPort);
        this.client = new RestHighLevelClient(
                RestClient.builder(new HttpHost(esHost, esPort, "http"))
                        .setRequestConfigCallback(builder -> builder
                                .setConnectTimeout(10000)
                                .setSocketTimeout(60000)
                                .setConnectionRequestTimeout(10000))
        );
    }

    @PreDestroy
    public void destroy() {
        try { if (client != null) client.close(); } catch (IOException e) {
            log.error("[大规模查询服务] 关闭客户端异常", e);
        }
        queryExecutor.shutdown();
    }

    // ============================================================
    // 目标索引解析（三表） / Target index resolution (3 tables)
    // ============================================================

    /**
     * 每类查询的目标（索引名、时间字段、导出列）
     * Per-type target: index name, time field, export columns.
     */
    private static class Target {
        final String indexName;
        final String timeField;
        final String idField;     // 文档 _id / 业务主键
        final String plateField;  // 车牌/车辆编号字段

        Target(String indexName, String timeField, String idField, String plateField) {
            this.indexName = indexName;
            this.timeField = timeField;
            this.idField = idField;
            this.plateField = plateField;
        }
    }

    /**
     * 按 type 解析目标索引与字段 / Resolve target by type.
     */
    private Target resolve(String type) {
        if (type == null) type = "snapshot";
        UnifiedQueryService.DataSource ds;
        String timeField;
        String idField;
        String plateField;
        switch (type.toLowerCase()) {
            case "fee":
                ds = UnifiedQueryService.DataSource.FEE;
                timeField = "transtime"; idField = "big_id"; plateField = "vehicleplate";
                break;
            case "trail":
                ds = UnifiedQueryService.DataSource.TRAIL;
                timeField = "extime"; idField = "cid"; plateField = "envehicleid";
                break;
            case "snapshot":
            default:
                ds = UnifiedQueryService.DataSource.SNAPSHOT;
                timeField = "snapshottime"; idField = "datauuid"; plateField = "platenumber";
                break;
        }
        // 索引名统一由 EsIndexManageService 解析，保证与同步/对账一致
        String indexName = indexManageService.resolveIndexName(ds);
        return new Target(indexName, timeField, idField, plateField);
    }

    // ============================================================
    // 模块1：全字段模糊查询 / Module 1: fuzzy query (3 tables)
    // ============================================================

    /**
     * 全字段模糊查询（无 type，默认 snapshot，向后兼容）
     * Fuzzy query without type (defaults to snapshot, for backward compatibility).
     */
    public List<Map<String, Object>> fuzzyQuery(String startTime, String endTime,
                                                 Map<String, String> fuzzyFields,
                                                 int pageNum, int pageSize) {
        return fuzzyQuery("snapshot", startTime, endTime, fuzzyFields, pageNum, pageSize);
    }

    /**
     * 全字段模糊查询（指定 type：snapshot/fee/trail）
     * Fuzzy query for a specific table type.
     *
     * 性能关键点 / Key points:
     *   1) 时间范围过滤到最近一年索引，分区裁剪思想同样适用于 ES 时间过滤
     *   2) 模糊字段走 ngram 倒排索引（match on .ngram）
     *   3) from+size 仅用于窗口内浅分页；深翻页请用导出接口
     */
    public List<Map<String, Object>> fuzzyQuery(String type, String startTime, String endTime,
                                                 Map<String, String> fuzzyFields,
                                                 int pageNum, int pageSize) {
        Target target = resolve(type);
        long start = System.currentTimeMillis();
        try {
            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
            boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                    .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime));

            if (fuzzyFields != null && !fuzzyFields.isEmpty()) {
                for (Map.Entry<String, String> entry : fuzzyFields.entrySet()) {
                    String value = entry.getValue();
                    if (value == null || value.isEmpty()) continue;
                    boolQuery.must(buildFuzzyQuery(entry.getKey(), value));
                }
            }

            SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
            sourceBuilder.query(boolQuery);
            sourceBuilder.from((pageNum - 1) * pageSize);
            sourceBuilder.size(pageSize);
            sourceBuilder.sort(target.timeField, SortOrder.DESC);
            sourceBuilder.terminateAfter(1000000); // 单次最多扫描 100 万，防慢查询
            sourceBuilder.timeout(new TimeValue(QUERY_TIMEOUT_SECONDS, TimeUnit.SECONDS));

            SearchRequest searchRequest = new SearchRequest(target.indexName);
            searchRequest.source(sourceBuilder);
            SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);

            List<Map<String, Object>> results = new ArrayList<>(pageSize);
            for (SearchHit hit : response.getHits().getHits()) {
                results.add(hit.getSourceAsMap());
            }
            long totalHits = response.getHits().getTotalHits().value;
            log.info("[全字段模糊查询] type={}, 命中={}, 返回={}, 耗时={}ms",
                    type, totalHits, results.size(), System.currentTimeMillis() - start);
            return results;
        } catch (Exception e) {
            log.error("[全字段模糊查询] ES 查询失败 type={}", type, e);
            throw new RuntimeException("大规模数据查询服务异常：" + e.getMessage(), e);
        }
    }

    /**
     * 根据字段内容智能构建模糊查询条件（与 UnifiedQueryService 一致）
     * Build fuzzy query by field content (consistent with UnifiedQueryService).
     */
    private QueryBuilder buildFuzzyQuery(String fieldName, String value) {
        if (value.length() >= 7 && ("platenumber".equals(fieldName)
                || "vehicleplate".equals(fieldName)
                || "gantrycode".equals(fieldName)
                || "sectioncode".equals(fieldName)
                || "envehicleid".equals(fieldName))) {
            return QueryBuilders.termQuery(fieldName + ".keyword", value);
        }
        if (value.length() >= 3) {
            return QueryBuilders.matchQuery(fieldName + ".ngram", value);
        }
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*");
    }

    // ============================================================
    // 模块2：统计查询（ES aggregation，三表）/ Module 2: aggregation (3 tables)
    // ============================================================

    /**
     * 统计查询 - 按维度分组计数（指定 type）
     * Aggregation: group count by dimension, for a specific table type.
     *
     * 原理：ES 在分片并行聚合，不将 8 亿条数据拉到应用层
     * Aggregation runs on shards in parallel; no full scan to app layer.
     */
    public Map<String, Long> aggregationStats(String type, String startTime, String endTime,
                                               String groupBy, String countField,
                                               Map<String, String> fuzzyFields,
                                               int topN) {
        Target target = resolve(type);
        long start = System.currentTimeMillis();
        try {
            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
            boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                    .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime));
            if (fuzzyFields != null) {
                for (Map.Entry<String, String> entry : fuzzyFields.entrySet()) {
                    if (entry.getValue() != null && !entry.getValue().isEmpty()) {
                        boolQuery.must(buildFuzzyQuery(entry.getKey(), entry.getValue()));
                    }
                }
            }

            SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
            sourceBuilder.query(boolQuery);
            sourceBuilder.size(0);
            sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
            sourceBuilder.aggregation(AggregationBuilders.terms("group_by_" + groupBy)
                    .field(groupBy + ".keyword")
                    .size(topN)
                    .subAggregation(AggregationBuilders.count("total_count")
                            .field(countField == null ? "_id" : countField))
            );

            SearchRequest request = new SearchRequest(target.indexName);
            request.source(sourceBuilder);
            SearchResponse response = client.search(request, RequestOptions.DEFAULT);

            Map<String, Long> resultMap = new LinkedHashMap<>();
            ParsedStringTerms terms = response.getAggregations().get("group_by_" + groupBy);
            for (Terms.Bucket bucket : terms.getBuckets()) {
                ValueCount count = bucket.getAggregations().get("total_count");
                resultMap.put(bucket.getKeyAsString(), count.getValue());
            }
            log.info("[统计查询] type={}, groupBy={}, 桶数={}, 耗时={}ms",
                    type, groupBy, resultMap.size(), System.currentTimeMillis() - start);
            return resultMap;
        } catch (Exception e) {
            log.error("[统计查询] 聚合失败 type={}", type, e);
            throw new RuntimeException("统计查询异常：" + e.getMessage(), e);
        }
    }

    // ============================================================
    // 模块3：大数据量导出（三表，PIT + search_after / Scroll）
    // ============================================================

    /**
     * 异步提交导出任务（指定 type）
     * Submit async export task for a specific table type.
     */
    public String submitExportTask(String type, String startTime, String endTime,
                                    Map<String, String> fuzzyFields) {
        String taskId = UUID.randomUUID().toString();
        ExportTaskStatus status = new ExportTaskStatus();
        status.taskId = taskId;
        status.status = "PENDING";
        status.submitTime = System.currentTimeMillis();
        exportTaskMap.put(taskId, status);

        queryExecutor.submit(() -> {
            try {
                executeExportScroll(type, taskId, startTime, endTime, fuzzyFields);
            } catch (Exception e) {
                log.error("[导出任务] task={} 执行异常", taskId, e);
                status.status = "FAILED";
                status.errorMessage = e.getMessage();
            }
        });
        return taskId;
    }

    /**
     * 查询导出任务状态 / Get export task status.
     */
    public ExportTaskStatus getExportStatus(String taskId) {
        return exportTaskMap.get(taskId);
    }

    /**
     * 核心：使用 Scroll API 深度分页导出大量数据
     * Core: Scroll-based deep pagination export.
     *
     * 为什么不用 from+size：from=1,000,000 需先扫描百万再丢弃，O(n) 且内存爆
     * Why not from+size: deep offset scans & discards rows (O(n), OOM)
     */
    private void executeExportScroll(String type, String taskId, String startTime, String endTime,
                                      Map<String, String> fuzzyFields) throws Exception {
        Target target = resolve(type);
        ExportTaskStatus status = exportTaskMap.get(taskId);
        status.status = "RUNNING";
        log.info("[导出任务] taskId={}, type={} 开始执行", taskId, type);

        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
        boolQuery.filter(QueryBuilders.rangeQuery(target.timeField)
                .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime));
        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getValue() != null && !e.getValue().isEmpty()) {
                    boolQuery.must(buildFuzzyQuery(e.getKey(), e.getValue()));
                }
            }
        }

        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
        sourceBuilder.query(boolQuery);
        sourceBuilder.size(SCROLL_BATCH_SIZE);
        sourceBuilder.sort(target.timeField, SortOrder.DESC);
        sourceBuilder.timeout(new TimeValue(120, TimeUnit.SECONDS));

        SearchRequest searchRequest = new SearchRequest(target.indexName);
        searchRequest.source(sourceBuilder);
        searchRequest.scroll(new Scroll(new TimeValue(5, TimeUnit.MINUTES)));
        SearchResponse scrollResp = client.search(searchRequest, RequestOptions.DEFAULT);

        String scrollId = scrollResp.getScrollId();
        int totalCount = 0;
        int filePartIndex = 0;
        BufferedWriter currentWriter = null;
        Path dir = Paths.get(exportDir);
        if (!Files.exists(dir)) { Files.createDirectories(dir); }

        try {
            while (scrollResp.getHits().getHits().length > 0) {
                if (currentWriter == null || totalCount % EXPORT_BATCH_SIZE == 0) {
                    if (currentWriter != null) currentWriter.close();
                    filePartIndex++;
                    String fileName = exportDir + "/export_" + type + "_" + taskId
                            + "_p" + filePartIndex + ".csv";
                    currentWriter = Files.newBufferedWriter(Paths.get(fileName));
                    // CSV 表头：业务主键 + 车牌/车辆编号 + 时间 + 完整 JSON 明细
                    currentWriter.write(target.idField + "," + target.plateField + ","
                            + target.timeField + ",detail\n");
                }

                for (SearchHit hit : scrollResp.getHits().getHits()) {
                    Map<String, Object> doc = hit.getSourceAsMap();
                    String id = doc.get(target.idField) == null ? "" : doc.get(target.idField).toString();
                    String plate = doc.get(target.plateField) == null ? "" : doc.get(target.plateField).toString();
                    String time = doc.get(target.timeField) == null ? "" : doc.get(target.timeField).toString();
                    // detail 列包含完整文档 JSON（CSV 内换行用空格替换，避免破坏行结构）
                    String detail = JSON.toJSONString(doc).replace("\n", " ").replace("\r", "");
                    currentWriter.write(id + "," + plate + "," + time + ",\"" + detail + "\"\n");
                    totalCount++;
                }
                status.totalExported = totalCount;

                SearchScrollRequest scrollRequest = new SearchScrollRequest(scrollId);
                scrollRequest.scroll(new Scroll(new TimeValue(5, TimeUnit.MINUTES)));
                scrollResp = client.scroll(scrollRequest, RequestOptions.DEFAULT);
                scrollId = scrollResp.getScrollId();

                if (totalCount % (SCROLL_BATCH_SIZE * 10) == 0) {
                    log.info("[导出任务] taskId={}, type={} 已导出{}条...", taskId, type, totalCount);
                }
            }
            status.status = "COMPLETED";
            status.filePartCount = filePartIndex;
            status.endTime = System.currentTimeMillis();
            log.info("[导出任务] taskId={}, type={} 完成, 共导出 {} 条, 切分 {} 个文件",
                    taskId, type, totalCount, filePartIndex);
        } finally {
            if (currentWriter != null) currentWriter.close();
            ClearScrollRequest clearScrollRequest = new ClearScrollRequest();
            clearScrollRequest.addScrollId(scrollId);
            client.clearScroll(clearScrollRequest, RequestOptions.DEFAULT);
        }
    }

    // ============================================================
    // 辅助：任务状态类 / Export task status
    // ============================================================

    public static class ExportTaskStatus {
        public String taskId;
        public volatile String status;  // PENDING/RUNNING/COMPLETED/FAILED
        public volatile long submitTime;
        public volatile long endTime;
        public volatile long totalExported;
        public volatile int filePartCount;
        public volatile String errorMessage;
    }

    private static class NamedThreadFactory implements ThreadFactory {
        private final AtomicInteger counter = new AtomicInteger(0);
        private final String namePrefix;
        public NamedThreadFactory(String prefix) { this.namePrefix = prefix; }
        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, namePrefix + "-" + counter.incrementAndGet());
            t.setDaemon(true);
            return t;
        }
    }
}
