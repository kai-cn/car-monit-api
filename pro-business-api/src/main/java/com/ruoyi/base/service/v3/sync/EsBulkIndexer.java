package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficDocumentBuilder;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
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
        long eventTime = event.getEventTime() == null ? System.currentTimeMillis() : event.getEventTime();
        String id = event.getPk();
        if (id == null || id.isEmpty()) {
            log.warn("[V3同步] 事件缺少主键，丢弃: {}", event.getEventId());
            return false;
        }

        Exception lastError = null;
        for (int attempt = 1; attempt <= properties.getSync().getMaxRetry(); attempt++) {
            try {
                String index = indexService.ensureIndexForEventTime(table, eventTime);
                if ("D".equalsIgnoreCase(event.getOp())) {
                    esClient.delete(new DeleteRequest(index, id), RequestOptions.DEFAULT);
                } else {
                    Map<String, Object> doc = event.getPayload();
                    if (doc == null || doc.isEmpty()) {
                        log.warn("[V3同步] 事件 payload 为空，跳过: eventId={}", event.getEventId());
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
                log.warn("[V3同步] 确保月索引失败 table={}, time={}: {}", table, eventTime, e.getMessage());
                continue;
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
                if (response.hasFailures()) {
                    for (BulkItemResponse item : response.getItems()) {
                        if (item.isFailed()) {
                            log.warn("[V3同步] bulk 单条失败 index={}, id={}: {}",
                                    entry.getKey(), item.getId(), item.getFailureMessage());
                        } else {
                            success++;
                        }
                    }
                } else {
                    success += entry.getValue().size();
                }
            } catch (Exception e) {
                log.error("[V3同步] bulk 失败 index={}, size={}", entry.getKey(), entry.getValue().size(), e);
            }
        }
        return success;
    }

    private void toDlq(SearchSyncEvent event, Exception error) {
        try {
            jdbc.update("INSERT INTO jl_data01.search_sync_dlq "
                            + "(event_id, table_name, pk, op, event_time, payload, error_message, retry_count) "
                            + "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    event.getEventId(), event.getTable(), event.getPk(), event.getOp(),
                    event.getEventTime() == null ? null : new Timestamp(event.getEventTime()),
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
