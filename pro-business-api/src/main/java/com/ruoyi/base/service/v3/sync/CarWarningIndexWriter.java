package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.CarWarningDocumentBuilder;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.delete.DeleteRequest;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * car-warning Outbox 消费者写入器：按 _id=id 幂等写/删 car-warning。
 */
@Slf4j
@Service
public class CarWarningIndexWriter {

    private final RestHighLevelClient esClient;
    private final CarWarningDocumentBuilder documentBuilder;
    private final TrafficV3Properties properties;

    public CarWarningIndexWriter(RestHighLevelClient esClient,
                                 CarWarningDocumentBuilder documentBuilder,
                                 TrafficV3Properties properties) {
        this.esClient = esClient;
        this.documentBuilder = documentBuilder;
        this.properties = properties;
    }

    public boolean indexOne(SearchSyncEvent event) {
        String id = event.getPk();
        if (id == null || id.isEmpty()) {
            log.warn("[V3预警同步] 事件缺少主键，丢弃: {}", event.getEventId());
            return false;
        }
        Exception last = null;
        for (int attempt = 1; attempt <= Math.max(3, properties.getSync().getMaxRetry()); attempt++) {
            try {
                if ("D".equalsIgnoreCase(event.getOp())) {
                    esClient.delete(new DeleteRequest(TrafficEsIndexService.CAR_WARNING_INDEX, id),
                            RequestOptions.DEFAULT);
                } else {
                    Map<String, Object> doc = event.getPayload();
                    if (doc == null || doc.isEmpty()) {
                        log.warn("[V3预警同步] payload 为空，跳过: id={}", id);
                        return false;
                    }
                    IndexRequest request = new IndexRequest(TrafficEsIndexService.CAR_WARNING_INDEX)
                            .id(id)
                            .source(JSON.toJSONString(documentBuilder.build(doc)), XContentType.JSON);
                    esClient.index(request, RequestOptions.DEFAULT);
                }
                return true;
            } catch (Exception e) {
                last = e;
                try {
                    Thread.sleep(200L * attempt);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        log.error("[V3预警同步] 写入失败 id={}: {}", id, last == null ? "unknown" : last.getMessage());
        return false;
    }
}
