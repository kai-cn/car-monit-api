package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Outbox Relay：轮询 {@code search_sync_outbox}，发送到 Kafka {@code search-sync}。
 *
 * <p>设计 §5.6.2：业务事实行与 outbox 行同事务写入；relay 只读 outbox，
 * 不反向写业务表，也不在业务代码中双写 ES。若 payload 为空，消费者按 pk 回查。</p>
 *
 * <p>默认关闭（{@code traffic.sync.enabled=false}），避免本地误连 Kafka。</p>
 */
@Slf4j
@Service
public class OutboxRelayService {

    private final JdbcTemplate jdbc;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final TrafficV3Properties properties;
    private final TrafficDocumentLoader documentLoader;
    private final AtomicBoolean running = new AtomicBoolean(false);

    public OutboxRelayService(DataSource dataSource,
                              KafkaTemplate<String, Object> kafkaTemplate,
                              TrafficV3Properties properties,
                              TrafficDocumentLoader documentLoader) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(10);
        this.kafkaTemplate = kafkaTemplate;
        this.properties = properties;
        this.documentLoader = documentLoader;
    }

    @Scheduled(fixedDelayString = "${traffic.sync.poll-interval-ms:5000}")
    public void relay() {
        if (!properties.getSync().isEnabled()) {
            return;
        }
        if (!running.compareAndSet(false, true)) {
            return;
        }
        try {
            List<Map<String, Object>> rows = jdbc.queryForList(
                    "SELECT id, event_id, table_name, pk, op, event_time, payload, schema_version "
                            + "FROM jl_data01.search_sync_outbox "
                            + "WHERE status = 'PENDING' ORDER BY id LIMIT ?",
                    properties.getSync().getBatchSize());
            for (Map<String, Object> row : rows) {
                handle(row);
            }
        } catch (Exception e) {
            log.warn("[V3 Outbox] 轮询失败（表可能未创建，请执行 004_sync_tables.sql）: {}", e.getMessage());
        } finally {
            running.set(false);
        }
    }

    private void handle(Map<String, Object> row) {
        long id = ((Number) row.get("id")).longValue();
        String tableName = String.valueOf(row.get("table_name"));
        String pk = String.valueOf(row.get("pk"));
        String op = row.get("op") == null ? "I" : String.valueOf(row.get("op"));
        Timestamp eventTime = (Timestamp) row.get("event_time");
        long millis = eventTime == null ? System.currentTimeMillis() : eventTime.getTime();

        SearchSyncEvent event = new SearchSyncEvent();
        event.setEventId(String.valueOf(row.get("event_id")));
        event.setTable(tableName);
        event.setPk(pk);
        event.setOp(op);
        event.setEventTime(millis);
        event.setSchemaVersion(row.get("schema_version") == null
                ? 1 : ((Number) row.get("schema_version")).intValue());

        String payload = row.get("payload") == null ? null : String.valueOf(row.get("payload"));
        if (payload != null && !payload.trim().isEmpty()) {
            try {
                event.setPayload(JSON.parseObject(payload, Map.class));
            } catch (Exception e) {
                log.warn("[V3 Outbox] payload 不是 JSON，改为按主键回查: id={}", id);
            }
        }
        if (event.getPayload() == null) {
            TrafficTable table = TrafficTable.fromSourceTableOrParam(tableName);
            event.setPayload(documentLoader.loadByPk(table, pk, millis));
        }
        if (event.getPayload() == null) {
            markFailed(id, "payload 为空且回查无数据");
            return;
        }

        try {
            kafkaTemplate.send(properties.getSync().getTopic(), event.getEventId(), event)
                    .get(10, TimeUnit.SECONDS);
            jdbc.update("UPDATE jl_data01.search_sync_outbox "
                    + "SET status='SENT', sent_at=now(), retry_count=0, last_error=NULL WHERE id=?", id);
        } catch (Exception e) {
            int retry = incrementRetry(id, e.getMessage());
            if (retry >= properties.getSync().getMaxRetry()) {
                markFailed(id, e.getMessage());
            }
            log.warn("[V3 Outbox] 发送失败 id={}, retry={}: {}", id, retry, e.getMessage());
        }
    }

    private int incrementRetry(long id, String error) {
        try {
            jdbc.update("UPDATE jl_data01.search_sync_outbox "
                            + "SET retry_count = retry_count + 1, last_error = ? WHERE id = ?",
                    truncate(error), id);
            Integer retry = jdbc.queryForObject(
                    "SELECT retry_count FROM jl_data01.search_sync_outbox WHERE id = ?",
                    Integer.class, id);
            return retry == null ? 1 : retry;
        } catch (Exception e) {
            log.debug("[V3 Outbox] 更新重试次数失败: {}", e.getMessage());
            return 1;
        }
    }

    private void markFailed(long id, String error) {
        try {
            jdbc.update("UPDATE jl_data01.search_sync_outbox "
                    + "SET status='FAILED', last_error=? WHERE id=?", truncate(error), id);
            jdbc.update("INSERT INTO jl_data01.search_sync_dlq "
                            + "(event_id, table_name, pk, op, event_time, payload, error_message, retry_count) "
                            + "SELECT event_id, table_name, pk, op, event_time, payload, ?, retry_count "
                            + "FROM jl_data01.search_sync_outbox WHERE id = ?",
                    truncate(error), id);
        } catch (Exception e) {
            log.debug("[V3 Outbox] 标记失败状态/落 DLQ 异常: {}", e.getMessage());
        }
    }

    private String truncate(String value) {
        String s = value == null ? "unknown" : value;
        return s.length() > 500 ? s.substring(0, 500) : s;
    }
}
