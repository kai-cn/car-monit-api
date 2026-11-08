package com.ruoyi.base.service.v3.sync;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.delete.DeleteRequest;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.client.core.CountRequest;
import org.elasticsearch.client.core.CountResponse;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortBuilders;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * GaussDB ↔ ES 分钟桶对账与按桶补偿（设计 §5.6.3）。
 *
 * <p>默认关闭。开启后按 {@code traffic.reconcile.cron} 执行：</p>
 * <ul>
 *   <li>GaussDB 按分钟桶 count(*)，ES 对读别名做 range count；</li>
 *   <li>偏差超过阈值写 {@code search_sync_reconcile} 并告警日志；</li>
 *   <li>对 DRIFT 桶提交回灌任务（以 GaussDB 为准覆盖 ES）。</li>
 * </ul>
 */
@Slf4j
@Service
public class TrafficReconciliationService {

    private final JdbcTemplate jdbc;
    private final RestHighLevelClient esClient;
    private final EsBackfillService backfillService;
    private final TrafficV3Properties properties;
    private final AtomicBoolean running = new AtomicBoolean(false);

    public TrafficReconciliationService(DataSource dataSource,
                                        RestHighLevelClient esClient,
                                        EsBackfillService backfillService,
                                        TrafficV3Properties properties) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(30);
        this.esClient = esClient;
        this.backfillService = backfillService;
        this.properties = properties;
    }

    @Scheduled(cron = "${traffic.reconcile.cron:0 30 2 * * ?}")
    public void scheduledReconcile() {
        if (!properties.getReconcile().isEnabled()) {
            return;
        }
        if (!running.compareAndSet(false, true)) {
            return;
        }
        try {
            reconcileLastWindow();
        } catch (Exception e) {
            log.error("[V3对账] 执行失败", e);
        } finally {
            running.set(false);
        }
    }

    public java.util.Map<String, Object> reconcileLastWindow() {
        int bucketMinutes = Math.max(1, properties.getReconcile().getBucketMinutes());
        long bucketMs = TimeUnit.MINUTES.toMillis(bucketMinutes);
        long now = alignDown(System.currentTimeMillis(), bucketMs);
        long start = alignDown(now - TimeUnit.MINUTES.toMillis(
                Math.max(1, properties.getReconcile().getLookbackMinutes())), bucketMs);
        return reconcileRange(start, now, bucketMinutes);
    }

    /** 使用配置的桶大小对指定范围对账。 */
    public java.util.Map<String, Object> reconcileRange(long start, long end) {
        return reconcileRange(start, end,
                Math.max(1, properties.getReconcile().getBucketMinutes()));
    }

    /**
     * 对指定时间范围做分钟桶对账；返回窗口、桶数与漂移/补偿统计。
     */
    public java.util.Map<String, Object> reconcileRange(long start, long end, int bucketMinutes) {
        long bucketMs = TimeUnit.MINUTES.toMillis(Math.max(1, bucketMinutes));
        long alignedStart = alignDown(start, bucketMs);
        long alignedEnd = alignDown(end, bucketMs);
        if (alignedEnd <= alignedStart) {
            throw new IllegalArgumentException("对账时间范围为空（需至少一个桶）");
        }

        int repairs = 0;
        int driftBuckets = 0;
        int totalBuckets = 0;
        int orphansDeleted = 0;
        for (TrafficTable table : TrafficTable.values()) {
            long bucketStart = alignedStart;
            while (bucketStart < alignedEnd) {
                long bucketEnd = Math.min(bucketStart + bucketMs, alignedEnd);
                ReconcileResult result = reconcileBucket(table, bucketStart, bucketEnd);
                boolean wasDrift = alreadyDrift(table, bucketStart);
                writeResult(table, bucketStart, bucketEnd, result);
                totalBuckets++;
                if (result.drift) {
                    driftBuckets++;
                    if (repairs < properties.getReconcile().getMaxRepairBuckets() && !wasDrift) {
                        backfillService.submit(table, bucketStart, bucketEnd);
                        repairs++;
                        log.warn("[V3对账] {} 桶存在漂移，已提交回灌: {} ~ {}",
                                table, TrafficTimeUtils.toDbTimestamp(bucketStart),
                                TrafficTimeUtils.toDbTimestamp(bucketEnd));
                    }
                    // P1-7：只回灌无法删除“GaussDB 不存在但 ES 仍存在”的孤儿文档，
                    // 漂移会长期存在。这里同步清理孤儿文档（单桶有 maxDocs 上限）。
                    if (properties.getReconcile().isDeleteOrphans()) {
                        orphansDeleted += sweepOrphanDocs(table, bucketStart, bucketEnd);
                    }
                }
                bucketStart = bucketEnd;
            }
        }
        log.info("[V3对账] 完成，窗口 {} ~ {}，桶数 {}，漂移 {}，触发回灌 {}，清理孤儿 {}",
                TrafficTimeUtils.toDbTimestamp(alignedStart), TrafficTimeUtils.toDbTimestamp(alignedEnd),
                totalBuckets, driftBuckets, repairs, orphansDeleted);

        java.util.Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("start", TrafficTimeUtils.toDbTimestamp(alignedStart));
        summary.put("end", TrafficTimeUtils.toDbTimestamp(alignedEnd));
        summary.put("bucketMinutes", bucketMinutes);
        summary.put("totalBuckets", totalBuckets);
        summary.put("driftBuckets", driftBuckets);
        summary.put("repairBuckets", repairs);
        summary.put("orphansDeleted", orphansDeleted);
        return summary;
    }

    /**
     * P1-7：删除指定桶内“ES 存在但 GaussDB 不存在”的孤儿文档。
     *
     * <p>只回灌（GaussDB→ES）无法收敛 ES 多出来的文档，漂移会一直存在。
     * 这里按业务主键排序 + search_after 拉取 ES _id，再分批回查 GaussDB 做差集，
     * 最后 bulk delete。单次最多扫描 {@code traffic.reconcile.orphan-sweep-max-docs} 条。</p>
     */
    public int sweepOrphanDocs(TrafficTable table, long start, long end) {
        int maxDocs = Math.max(1, properties.getReconcile().getOrphanSweepMaxDocs());
        String pk = table.getPkField();
        String time = table.getTimeField();

        List<String> esIds = new ArrayList<>();
        List<Object> searchAfter = new ArrayList<>();
        try {
            while (esIds.size() < maxDocs) {
                int size = Math.min(1000, maxDocs - esIds.size());
                SearchSourceBuilder source = new SearchSourceBuilder()
                        .query(QueryBuilders.rangeQuery(time)
                                .format("epoch_millis").gte(start).lt(end))
                        .size(size)
                        .fetchSource(false)
                        .sort(SortBuilders.fieldSort(pk).order(SortOrder.ASC).missing("_last"));
                if (!searchAfter.isEmpty()) {
                    source.searchAfter(searchAfter.toArray());
                }
                SearchRequest request = new SearchRequest(table.readAlias()).source(source);
                SearchResponse response = esClient.search(request, RequestOptions.DEFAULT);
                SearchHit[] hits = response.getHits().getHits();
                if (hits.length == 0) {
                    break;
                }
                for (SearchHit hit : hits) {
                    esIds.add(hit.getId());
                }
                if (hits.length < size || hits[hits.length - 1].getSortValues() == null) {
                    break;
                }
                searchAfter = Arrays.asList(hits[hits.length - 1].getSortValues());
            }
        } catch (Exception e) {
            log.warn("[V3对账] 孤儿扫描失败 table={}: {}", table, e.getMessage());
            return 0;
        }
        if (esIds.isEmpty()) {
            return 0;
        }

        Set<String> existing = new HashSet<>();
        for (int i = 0; i < esIds.size(); i += 1000) {
            List<String> chunk = esIds.subList(i, Math.min(i + 1000, esIds.size()));
            String sql = "SELECT " + pk + " FROM " + table.getSourceTable()
                    + " WHERE " + time + " >= ? AND " + time + " < ? AND " + pk + " IN ("
                    + placeholders(chunk.size()) + ")";
            Object[] args = new Object[chunk.size() + 2];
            args[0] = TrafficTimeUtils.toDbTimestamp(start);
            args[1] = TrafficTimeUtils.toDbTimestamp(end);
            for (int j = 0; j < chunk.size(); j++) {
                args[j + 2] = chunk.get(j);
            }
            try {
                existing.addAll(jdbc.queryForList(sql, String.class, args));
            } catch (Exception e) {
                log.warn("[V3对账] 孤儿回查 GaussDB 失败 table={}: {}", table, e.getMessage());
                return 0;
            }
        }

        List<String> orphans = new ArrayList<>();
        for (String id : esIds) {
            if (!existing.contains(id)) {
                orphans.add(id);
            }
        }
        if (orphans.isEmpty()) {
            return 0;
        }
        return deleteFromEs(table, orphans);
    }

    private String placeholders(int count) {
        StringBuilder sb = new StringBuilder(count * 2);
        for (int i = 0; i < count; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append('?');
        }
        return sb.toString();
    }

    private int deleteFromEs(TrafficTable table, List<String> ids) {
        int deleted = 0;
        try {
            BulkRequest bulk = new BulkRequest();
            for (String id : ids) {
                bulk.add(new DeleteRequest(table.readAlias(), id));
            }
            BulkResponse response = esClient.bulk(bulk, RequestOptions.DEFAULT);
            for (org.elasticsearch.action.bulk.BulkItemResponse item : response.getItems()) {
                if (!item.isFailed()) {
                    deleted++;
                }
            }
            if (response.hasFailures()) {
                log.warn("[V3对账] 孤儿删除部分失败 table={}: {}", table, response.buildFailureMessage());
            }
            log.warn("[V3对账] 已删除孤儿文档 table={}, count={}", table, deleted);
        } catch (Exception e) {
            log.warn("[V3对账] 孤儿删除失败 table={}: {}", table, e.getMessage());
            return 0;
        }
        return deleted;
    }

    private ReconcileResult reconcileBucket(TrafficTable table, long bucketStart, long bucketEnd) {
        ReconcileResult result = new ReconcileResult();
        try {
            Long gauss = jdbc.queryForObject(
                    "SELECT count(*) FROM " + table.getSourceTable()
                            + " WHERE " + table.getTimeField() + " >= ? AND "
                            + table.getTimeField() + " < ?",
                    Long.class, TrafficTimeUtils.toDbTimestamp(bucketStart), TrafficTimeUtils.toDbTimestamp(bucketEnd));
            result.gaussCount = gauss == null ? 0 : gauss;
        } catch (Exception e) {
            result.error = e.getMessage();
            result.status = "ERROR";
            return result;
        }

        try {
            CountRequest request = new CountRequest(table.readAlias());
            request.query(QueryBuilders.rangeQuery(table.getTimeField())
                    .format("epoch_millis")
                    .gte(bucketStart)
                    .lt(bucketEnd));
            CountResponse response = esClient.count(request, RequestOptions.DEFAULT);
            result.esCount = response.getCount();
        } catch (Exception e) {
            result.error = e.getMessage();
            result.status = "ERROR";
            return result;
        }

        long base = Math.max(result.gaussCount, 1L);
        result.diffRatio = Math.abs(result.gaussCount - result.esCount) / (double) base;
        result.drift = result.diffRatio > properties.getReconcile().getDriftRatio();
        result.status = result.drift ? "DRIFT" : "OK";
        return result;
    }

    private void writeResult(TrafficTable table, long bucketStart, long bucketEnd,
                             ReconcileResult result) {
        try {
            // openGauss 3.0 不支持 ON CONFLICT：先 UPDATE，未命中再 INSERT
            int updated = jdbc.update("UPDATE jl_data01.search_sync_reconcile SET "
                            + "bucket_end = ?, gauss_count = ?, es_count = ?, diff_ratio = ?, "
                            + "status = ?, detail = ?, created_at = now() "
                            + "WHERE table_name = ? AND bucket_start = ?",
                    TrafficTimeUtils.toDbTimestamp(bucketEnd), result.gaussCount, result.esCount, result.diffRatio,
                    result.status, result.error == null ? null : truncate(result.error),
                    table.getIndexBase(), TrafficTimeUtils.toDbTimestamp(bucketStart));
            if (updated == 0) {
                jdbc.update("INSERT INTO jl_data01.search_sync_reconcile "
                                + "(table_name, bucket_start, bucket_end, gauss_count, es_count, "
                                + "diff_ratio, status, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        table.getIndexBase(), TrafficTimeUtils.toDbTimestamp(bucketStart), TrafficTimeUtils.toDbTimestamp(bucketEnd),
                        result.gaussCount, result.esCount, result.diffRatio, result.status,
                        result.error == null ? null : truncate(result.error));
            }
        } catch (Exception e) {
            log.debug("[V3对账] 结果落库失败（表可能未创建）: {}", e.getMessage());
        }
        if (result.drift) {
            log.warn("[V3对账] 漂移 {}: gauss={}, es={}, ratio={}",
                    table, result.gaussCount, result.esCount, result.diffRatio);
        }
    }

    private boolean alreadyDrift(TrafficTable table, long bucketStart) {
        try {
            Integer count = jdbc.queryForObject(
                    "SELECT count(*) FROM jl_data01.search_sync_reconcile "
                            + "WHERE table_name = ? AND bucket_start = ? AND status IN ('DRIFT','REPAIRED')",
                    Integer.class, table.getIndexBase(), TrafficTimeUtils.toDbTimestamp(bucketStart));
            return count != null && count > 0;
        } catch (Exception e) {
            return false;
        }
    }

    private long alignDown(long millis, long bucketMs) {
        return millis - (millis % bucketMs);
    }

    private String truncate(String value) {
        return value.length() > 500 ? value.substring(0, 500) : value;
    }

    private static class ReconcileResult {
        private long gaussCount;
        private long esCount;
        private double diffRatio;
        private boolean drift;
        private String status = "OK";
        private String error;
    }
}
