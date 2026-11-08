package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

/**
 * {@code search-sync} 消费者：解析事件 -> 幂等 bulk 写入 ES。
 *
 * <p>消费失败由 {@link EsBulkIndexer} 重试并落 DLQ；offset 提交语义由 Kafka 默认
 * 自动提交控制（至少一次），重复事件由 {@code _id} 覆盖。</p>
 */
@Slf4j
@Service
public class SearchSyncConsumer {

    private final EsBulkIndexer indexer;
    private final CarWarningIndexWriter carWarningIndexWriter;

    public SearchSyncConsumer(EsBulkIndexer indexer,
                              CarWarningIndexWriter carWarningIndexWriter) {
        this.indexer = indexer;
        this.carWarningIndexWriter = carWarningIndexWriter;
    }

    @KafkaListener(
            topics = "${traffic.sync.topic:search-sync}",
            groupId = "${traffic.sync.group-id:search-sync-api}",
            autoStartup = "${traffic.sync.enabled:false}"
    )
    public void onMessage(String message) {
        if (message == null || message.trim().isEmpty()) {
            return;
        }
        try {
            SearchSyncEvent event = JSON.parseObject(message, SearchSyncEvent.class);
            if (event == null) {
                log.warn("[V3同步] 收到空事件，忽略");
                return;
            }
            if (isCarWarning(event.getTable())) {
                carWarningIndexWriter.indexOne(event);
            } else {
                indexer.indexOne(event);
            }
        } catch (Exception e) {
            log.error("[V3同步] 消费失败，消息进入 DLQ 由运维重放: {}", e.getMessage());
            // 抛出让 Kafka 错误处理器处理/重投；配合幂等 _id 不会产生重复文档
            throw new IllegalStateException("search-sync 消费失败", e);
        }
    }

    private boolean isCarWarning(String table) {
        if (table == null) {
            return false;
        }
        String t = table.toLowerCase();
        return t.contains("car_warning") || t.contains("car-warning");
    }
}
