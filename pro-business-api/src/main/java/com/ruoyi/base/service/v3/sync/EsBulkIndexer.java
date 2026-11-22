package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficDocumentBuilder;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.bulk.BulkItemResponse;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.delete.DeleteRequest;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * ES 幂等写入器。
 *
 * <p>抓拍/收费 {@code _id=big_id}，轨迹 {@code _id=cid}；重复事件覆盖而非新增。
 * 单条写入失败重试 {@code traffic.sync.max-retry} 次后落 {@code search_sync_dlq}。</p>
 */
@Slf4j
@Service
public class EsBulkIndexer {

    private final RestHighLevelClient esClient;
    private final TrafficEsIndexService indexService;
    private final TrafficDocumentBuilder documentBuilder;
    private final TrafficV3Properties properties;
    private final JdbcTemplate jdbc;

    public EsBulkIndexer(RestHighLevelClient esClient,
                         TrafficEsIndexService indexService,
                         TrafficDocumentBuilder documentBuilder,
                         TrafficV3Properties properties,
                         DataSource dataSource) {
        this.esClient = esClient;
        this.indexService = indexService;
        this.documentBuilder = documentBuilder;
        this.properties = properties;
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(10);
    }

    /**
     * 写入/删除单条同步事件。
     */
    public boolean indexOne(SearchSyncEvent event) {
        TrafficTable table = TrafficTable.fromSourceTableOrParam(event.getTable());
        String id = event.getPk();
        if (id == null || id.isEmpty()) {
            log.warn("[V3同步] 事件缺少主键，丢弃: {}", event.getEventId());
            return false;
        }

        // P1-5：按月路由使用业务时间（transtime/snapshottime/extime），
        // 而不是 outbox 的 event_time；删除事件无 payload 时才回退 event_time。
        long routingTime = routingTime(table, event);

        Exception lastError = null;
        for (int attempt = 1; attempt <= properties.getSync().getMaxRetry(); attempt++) {
            try {
                String index = indexService.ensureIndexForEventTime(table, routingTime);
                if ("D".equalsIgnoreCase(event.getOp())) {
                    // P1-6：删除事件即使 payload 为空也生成 tombstone（按 _id 删除）
                    esClient.delete(new DeleteRequest(index, id), RequestOptions.DEFAULT);
                } else {
                    Map<String, Object> payload = event.getPayload();
                    if (payload == null || payload.isEmpty()) {
                        log.warn("[V3同步] 事件 payload 为空，跳过: eventId={}", event.getEventId());
                        return false;
                    }
                    // 统一过文档构建器：只保留 mapping 白名单字段并归一化日期，
                    // 避免 Outbox payload/回查原始行在 dynamic:strict 下被 ES 拒绝。
                    Map<String, Object> doc = documentBuilder.build(table, payload);
                    if (doc.isEmpty()) {
                        log.warn("[V3同步] 事件 payload 无有效字段，跳过: eventId={}", event.getEventId());
                        return false;
                    }
                    IndexRequest request = new IndexRequest(index).id(id)
                            .source(JSON.toJSONString(doc), XContentType.JSON);
                    esClient.index(request, RequestOptions.DEFAULT);
                }
                return true;
            } catch (Exception e) {
                lastError = e;
                sleepBackoff(attempt);
            }
        }
        toDlq(event, lastError);
        return false;
    }

    /** 业务时间优先；payload 缺时间列时回退 event_time。 */
    private long routingTime(TrafficTable table, SearchSyncEvent event) {
        Map<String, Object> payload = event.getPayload();
        if (payload != null) {
            Long millis = toMillis(payload.get(table.getTimeField()));
            if (millis != null) {
                return millis;
            }
        }
        return event.getEventTime() == null ? System.currentTimeMillis() : event.getEventTime();
    }

    private Long toMillis(Object value) {
        if (value instanceof java.util.Date) {
            return ((java.util.Date) value).getTime();
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        if (value instanceof CharSequence) {
            return TrafficTimeUtils.parseDbTimestamp(value.toString());
        }
        return null;
    }

    /**
     * 批量写入（回灌/对账补偿使用）。按 (eventTime) 分月索引，一次 bulk 请求。
     */
    public int bulkIndex(List<IndexDoc> docs) {
        if (docs == null || docs.isEmpty()) {
            return 0;
        }
        Map<String, List<IndexDoc>> byIndex = new LinkedHashMap<>();
        for (IndexDoc doc : docs) {
            TrafficTable table = doc.table;
            long eventTime = doc.eventTime == null ? System.currentTimeMillis() : doc.eventTime;
            String index;
            try {
                index = indexService.ensureIndexForEventTime(table, eventTime);
            } catch (Exception e) {
                // 不能静默跳过：跳过后回灌游标仍会前进，这批数据永久不进 ES
                throw new IllegalStateException("确保月索引失败 table=" + table + ", time=" + eventTime, e);
            }
            byIndex.computeIfAbsent(index, k -> new ArrayList<>()).add(doc);
        }

        int success = 0;
        for (Map.Entry<String, List<IndexDoc>> entry : byIndex.entrySet()) {
            BulkRequest bulk = new BulkRequest();
            for (IndexDoc doc : entry.getValue()) {
                bulk.add(new IndexRequest(entry.getKey()).id(doc.id)
                        .source(JSON.toJSONString(doc.doc), XContentType.JSON));
            }
            try {
                BulkResponse response = esClient.bulk(bulk, RequestOptions.DEFAULT);
                int ok = entry.getValue().size();
                if (response.hasFailures()) {
                    ok = 0;
                    String firstFailure = null;
                    for (BulkItemResponse item : response.getItems()) {
                        if (item.isFailed()) {
                            log.warn("[V3同步] bulk 单条失败 index={}, id={}: {}",
                                    entry.getKey(), item.getId(), item.getFailureMessage());
                            if (firstFailure == null) {
                                firstFailure = item.getId() + ":" + item.getFailureMessage();
                            }
                        } else {
                            ok++;
                        }
                    }
                    if (ok != entry.getValue().size()) {
                        throw new IllegalStateException("ES bulk 部分失败 index=" + entry.getKey()
                                + " ok=" + ok + "/" + entry.getValue().size() + " first=" + firstFailure);
                    }
                }
                success += ok;
            } catch (IllegalStateException e) {
                // 保留上面拼好的失败明细（含首个失败 id + 原因），供回灌任务状态查询
                throw e;
            } catch (Exception e) {
                log.error("[V3同步] bulk 失败 index={}, size={}", entry.getKey(), entry.getValue().size(), e);
                // 抛出异常让回灌任务置 FAILED，而不是 DONE + 游标推进后永久丢数据
                throw new IllegalStateException("ES bulk 失败 index=" + entry.getKey()
                        + " size=" + entry.getValue().size(), e);
            }
        }
        return success;
    }

    /** 写入 DLQ（car-warning 等非三表索引的消费者共用）。 */
    public void toDlq(SearchSyncEvent event, Exception error) {
        try {
            jdbc.update("INSERT INTO jl_data01.search_sync_dlq "
                            + "(event_id, table_name, pk, op, event_time, payload, error_message, retry_count) "
                            + "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    event.getEventId(), event.getTable(), event.getPk(), event.getOp(),
                    event.getEventTime() == null ? null : TrafficTimeUtils.toDbTimestamp(event.getEventTime()),
                    event.getPayload() == null ? null : JSON.toJSONString(event.getPayload()),
                    error == null ? "unknown" : String.valueOf(error.getMessage()).substring(
                            0, Math.min(1000, String.valueOf(error.getMessage()).length())),
                    properties.getSync().getMaxRetry());
        } catch (Exception e) {
            log.error("[V3同步] 写 DLQ 失败（表可能未创建，请执行 004_sync_tables.sql）: {}", e.getMessage());
        }
    }

    private void sleepBackoff(int attempt) {
        try {
            TimeUnit.MILLISECONDS.sleep(Math.min(5000L, 200L * attempt));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    /** 待写入文档 */
    public static class IndexDoc {
        private final TrafficTable table;
        private final String id;
        private final Map<String, Object> doc;
        private final Long eventTime;

        public IndexDoc(TrafficTable table, String id, Map<String, Object> doc, Long eventTime) {
            this.table = table;
            this.id = id;
            this.doc = doc;
            this.eventTime = eventTime;
        }
    }
}
