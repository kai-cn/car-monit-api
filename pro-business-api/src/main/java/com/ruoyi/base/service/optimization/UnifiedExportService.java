package com.ruoyi.base.service.optimization;

import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.ClearScrollRequest;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.action.search.SearchScrollRequest;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.core.TimeValue;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.index.query.RangeQueryBuilder;
import org.elasticsearch.search.Scroll;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 统一异步导出服务（3 大表通用）
 *
 * =================================================================
 * 设计目标：
 *   面向"单次导出 >100 万条"场景，避免 OOM 与 HTTP 超时。
 *
 * 实现要点：
 *   1. 异步任务：调用方立即返回 taskId，后台线程池执行
 *   2. ES Scroll API：每次拉取 SCROLL_BATCH_SIZE 条，避免 from+size 深分页性能问题
 *   3. 流式写盘：每 EXPORT_BATCH_SIZE 条切一个 CSV 文件，避免堆内存堆积
 *   4. 进度上报：内存 Map 实时记录状态，前端轮询获取
 *
 * 与 LargeScaleQueryService.submitExportTask 的区别：
 *   - 通用化：3 表共用同一导出路径，按数据源抽象出 time field / index / 列定义
 *   - 独立线程池：避免与查询服务竞争线程
 *   - 可观测：导出完成后保留可下载的文件路径
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class UnifiedExportService {

    @Autowired
    private RestHighLevelClient esClient;

    @Autowired
    private EsIndexManageService indexManageService;

    /** 单次 scroll 拉取的文档数（过大内存压力大，过小IO频繁） */
    @Value("${optimization.export.scroll-batch:2000}")
    private int scrollBatchSize;

    /** 每 EXPORT_BATCH_SIZE 条切一个文件 */
    @Value("${optimization.export.file-batch:100000}")
    private int exportBatchSize;

    /** 导出文件根目录 */
    @Value("${optimization.export.dir:/data/export}")
    private String exportDir;

    /** Scroll 上下文保留时长（分钟） */
    @Value("${optimization.export.scroll-keepalive-min:5}")
    private int scrollKeepaliveMin;

    /** 导出任务线程池 */
    private final ExecutorService exportExecutor = new ThreadPoolExecutor(
            2, 4, 60L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(200),
            new NamedThreadFactory("export-worker"),
            new ThreadPoolExecutor.CallerRunsPolicy()
    );

    /** 任务状态追踪 Map（taskId -> ExportTaskStatus） */
    private final Map<String, ExportTaskStatus> taskStatusMap = new ConcurrentHashMap<>();

    // ============================================================
    // 三种数据源的列定义（导出 CSV 表头）
    // ============================================================
    private static final Map<UnifiedQueryService.DataSource, List<String>> COLUMNS;
    static {
        Map<UnifiedQueryService.DataSource, List<String>> m = new HashMap<>();
        m.put(UnifiedQueryService.DataSource.SNAPSHOT, Arrays.asList(
                "datauuid", "platenumber", "gantrycode", "gantryname",
                "sectioncode", "sectionname", "roadcode", "roadname",
                "orgcode", "orgname", "snapshottime", "platecolor"
        ));
        m.put(UnifiedQueryService.DataSource.FEE, Arrays.asList(
                "big_id", "vehicleplate", "gantryid", "gantryname",
                "sectioncode", "sectionname", "roadname", "tollname",
                "orgname", "transtime", "fee", "axlecount", "passstate"
        ));
        m.put(UnifiedQueryService.DataSource.TRAIL, Arrays.asList(
                "cid", "envehicleid", "exvehicleid",
                "entollstationname", "extollstationname",
                "entime", "extime", "envehicleclass", "exvehicleclass"
        ));
        COLUMNS = Collections.unmodifiableMap(m);
    }

    // ============================================================
    // 公共入口
    // ============================================================

    /**
     * 提交异步导出任务
     *
     * @param ds          数据源类型
     * @param startTime   起始时间 yyyy-MM-dd HH:mm:ss
     * @param endTime     结束时间
     * @param fuzzyFields 模糊字段（key=字段名，value=模糊内容）；可为空
     * @return taskId 调用方凭此轮询状态/下载
     */
    public String submitExportTask(UnifiedQueryService.DataSource ds,
                                     String startTime, String endTime,
                                     Map<String, String> fuzzyFields) {
        String taskId = UUID.randomUUID().toString();
        ExportTaskStatus status = new ExportTaskStatus();
        status.taskId       = taskId;
        status.dataSource   = ds.name();
        status.startTime    = startTime;
        status.endTime      = endTime;
        status.status       = "PENDING";
        status.submitTime   = System.currentTimeMillis();
        taskStatusMap.put(taskId, status);

        exportExecutor.submit(() -> {
            try {
                executeExportScroll(taskId, ds, startTime, endTime, fuzzyFields);
            } catch (Exception e) {
                log.error("[统一导出] task={} 执行失败", taskId, e);
                status.status = "FAILED";
                status.errorMessage = e.getMessage();
                status.finishTime = System.currentTimeMillis();
            }
        });

        log.info("[统一导出] 已提交任务 taskId={}, ds={}, time={}~{}, fuzzyFields={}",
                taskId, ds, startTime, endTime,
                fuzzyFields == null ? 0 : fuzzyFields.size());
        return taskId;
    }

    /**
     * 查询导出任务状态
     */
    public ExportTaskStatus getExportStatus(String taskId) {
        return taskStatusMap.get(taskId);
    }

    /**
     * 清理过期的任务状态（避免内存泄漏）
     *
     * 建议由定时任务每天调用一次，清理超过 7 天的已完成任务
     */
    public void cleanExpiredTasks(long maxAgeMs) {
        long threshold = System.currentTimeMillis() - maxAgeMs;
        taskStatusMap.entrySet().removeIf(e -> {
            ExportTaskStatus s = e.getValue();
            return ("COMPLETED".equals(s.status) || "FAILED".equals(s.status))
                    && s.finishTime > 0 && s.finishTime < threshold;
        });
    }

    @PreDestroy
    public void destroy() {
        exportExecutor.shutdown();
        try {
            exportExecutor.awaitTermination(5, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // ============================================================
    // 核心导出实现：ES Scroll + 流式 CSV
    // ============================================================

    private void executeExportScroll(String taskId,
                                      UnifiedQueryService.DataSource ds,
                                      String startTime, String endTime,
                                      Map<String, String> fuzzyFields) throws Exception {
        ExportTaskStatus status = taskStatusMap.get(taskId);
        status.status = "RUNNING";
        log.info("[统一导出] task={} 开始执行", taskId);

        // 1. 构建查询
        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
        boolQuery.filter(buildTimeRange(ds, startTime, endTime));

        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getValue() == null || e.getValue().isEmpty()) continue;
                // 智能模糊策略（与 UnifiedQueryService 统一）
                boolQuery.must(buildFuzzyQuery(e.getKey(), e.getValue()));
            }
        }

        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
                .query(boolQuery)
                .size(scrollBatchSize)
                .sort(resolveTimeField(ds), SortOrder.DESC)
                .timeout(new TimeValue(120, TimeUnit.SECONDS));
        // 导出时不做 terminate_after 限制，按条件完整导出
        sourceBuilder.fetchSource(COLUMNS.get(ds).toArray(new String[0]), null);

        // 2. 初始化 scroll
        SearchRequest searchRequest = new SearchRequest(resolveIndexName(ds));
        searchRequest.source(sourceBuilder);
        searchRequest.scroll(new Scroll(new TimeValue(scrollKeepaliveMin, TimeUnit.MINUTES)));

        SearchResponse scrollResp = esClient.search(searchRequest, RequestOptions.DEFAULT);
        String scrollId = scrollResp.getScrollId();

        int totalCount = 0;
        int filePartIndex = 0;
        BufferedWriter currentWriter = null;

        try {
            // 3. 循环 scroll 直到无更多数据
            while (scrollResp.getHits().getHits().length > 0) {
                // 3.1 切分文件：每 exportBatchSize 条开一个新 CSV
                if (currentWriter == null || totalCount % exportBatchSize == 0) {
                    if (currentWriter != null) {
                        currentWriter.close();
                    }
                    filePartIndex++;
                    Path filePath = Paths.get(exportDir,
                            "export_" + taskId + "_p" + filePartIndex + ".csv");
                    // 确保目录存在
                    Files.createDirectories(filePath.getParent());
                    currentWriter = Files.newBufferedWriter(filePath, StandardCharsets.UTF_8);
                    // 文件头
                    currentWriter.write(String.join(",", COLUMNS.get(ds)));
                    currentWriter.newLine();
                    status.filePaths.add(filePath.toString());
                    log.info("[统一导出] task={} 切分新文件 part={}", taskId, filePartIndex);
                }

                // 3.2 写入当前批次
                for (SearchHit hit : scrollResp.getHits().getHits()) {
                    Map<String, Object> doc = hit.getSourceAsMap();
                    StringBuilder line = new StringBuilder();
                    for (int i = 0; i < COLUMNS.get(ds).size(); i++) {
                        if (i > 0) line.append(',');
                        Object v = doc.get(COLUMNS.get(ds).get(i));
                        if (v != null) {
                            // CSV 转义：包含逗号/换行/引号时加引号并转义引号
                            String s = v.toString();
                            if (s.contains(",") || s.contains("\n") || s.contains("\"")) {
                                line.append('"').append(s.replace("\"", "\"\"")).append('"');
                            } else {
                                line.append(s);
                            }
                        }
                    }
                    currentWriter.write(line.toString());
                    currentWriter.newLine();
                    totalCount++;
                }
                status.totalExported = totalCount;

                // 3.3 进度日志（每 scrollBatchSize*50 条打一次）
                if (totalCount % (scrollBatchSize * 50) == 0) {
                    log.info("[统一导出] task={} 已导出 {} 条, filePart={}", taskId, totalCount, filePartIndex);
                }

                // 3.4 下一批 scroll
                SearchScrollRequest scrollRequest = new SearchScrollRequest(scrollId);
                scrollRequest.scroll(new Scroll(new TimeValue(scrollKeepaliveMin, TimeUnit.MINUTES)));
                scrollResp = esClient.scroll(scrollRequest, RequestOptions.DEFAULT);
                scrollId = scrollResp.getScrollId();
            }

            // 4. 完成
            if (currentWriter != null) {
                currentWriter.close();
            }
            status.status = "COMPLETED";
            status.filePartCount = filePartIndex;
            status.finishTime = System.currentTimeMillis();
            log.info("[统一导出] task={} 完成, 共导出 {} 条, 切分为 {} 个 CSV 文件",
                    taskId, totalCount, filePartIndex);
        } finally {
            // 关键：清空 scroll 上下文，释放 ES 服务端游标资源
            if (currentWriter != null) {
                try { currentWriter.close(); } catch (IOException ignored) {}
            }
            try {
                ClearScrollRequest clearReq = new ClearScrollRequest();
                clearReq.addScrollId(scrollId);
                esClient.clearScroll(clearReq, RequestOptions.DEFAULT);
            } catch (Exception e) {
                log.warn("[统一导出] task={} 清空 scroll 上下文失败", taskId, e);
            }
        }
    }

    private RangeQueryBuilder buildTimeRange(UnifiedQueryService.DataSource ds,
                                              String startTime, String endTime) {
        return QueryBuilders.rangeQuery(resolveTimeField(ds))
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime);
    }

    /**
     * 智能模糊查询（与 UnifiedQueryService.buildFuzzyQuery 保持一致）
     */
    private QueryBuilder buildFuzzyQuery(String fieldName, String value) {
        if (value.length() >= 7 && (fieldName.equals("platenumber")
                || fieldName.equals("gantrycode")
                || fieldName.equals("sectioncode"))) {
            return QueryBuilders.termQuery(fieldName + ".keyword", value);
        }
        if (value.length() >= 3) {
            return QueryBuilders.matchQuery(fieldName + ".ngram", value);
        }
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*");
    }

    private String resolveIndexName(UnifiedQueryService.DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return indexManageService.getSnapshotIndex();
            case FEE:      return indexManageService.getFeeIndex();
            case TRAIL:    return indexManageService.getTrailIndex();
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    private String resolveTimeField(UnifiedQueryService.DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return "snapshottime";
            case FEE:      return "transtime";
            case TRAIL:    return "extime";
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    // ============================================================
    // 任务状态对象
    // ============================================================
    public static class ExportTaskStatus {
        public String taskId;
        public String dataSource;
        public String startTime;
        public String endTime;
        public volatile String status;        // PENDING / RUNNING / COMPLETED / FAILED
        public volatile long submitTime;
        public volatile long finishTime;
        public volatile long totalExported;
        public volatile int filePartCount;
        public volatile String errorMessage;
        public final List<String> filePaths = Collections.synchronizedList(new ArrayList<>());
    }

    /**
     * 线程工厂
     */
    private static class NamedThreadFactory implements ThreadFactory {
        private final AtomicInteger counter = new AtomicInteger(0);
        private final String namePrefix;

        public NamedThreadFactory(String prefix) {
            this.namePrefix = prefix;
        }

        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, namePrefix + "-" + counter.incrementAndGet());
            t.setDaemon(true);
            return t;
        }
    }
}
