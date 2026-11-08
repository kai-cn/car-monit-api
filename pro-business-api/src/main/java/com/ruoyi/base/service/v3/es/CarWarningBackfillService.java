package com.ruoyi.base.service.v3.es;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
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

/**
 * car-warning 索引回灌（阶段一运维/初始化用）。
 *
 * <p>数据源为 backend 业务表 {@code car_warning_info}（可选 join {@code car_info} 取
 * escaped_type/escaped_amount/plate_color）。API 运行时不直连该表，仅提供受控回灌入口；
 * 生产首选写入方案见 docs/decisions-v3.md §6.3（CDC/Outbox -> Kafka car-warning-sync -> bulk）。</p>
 */
@Slf4j
@Service
public class CarWarningBackfillService {

    private static final int BULK_SIZE = 500;

    private final JdbcTemplate jdbc;
    private final RestHighLevelClient esClient;
    private final TrafficEsIndexService indexService;
    private final CarWarningDocumentBuilder documentBuilder;

    public CarWarningBackfillService(DataSource dataSource,
                                     RestHighLevelClient esClient,
                                     TrafficEsIndexService indexService,
                                     CarWarningDocumentBuilder documentBuilder) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(60);
        this.esClient = esClient;
        this.indexService = indexService;
        this.documentBuilder = documentBuilder;
    }

    /**
     * 按 gantry_time 范围回灌，单次最多 10000 行（避免误触发全表）。
     *
     * @return {indexed, fetched, source}
     */
    public Map<String, Object> backfill(String startTime, String endTime, int limit) {
        long end = endTime == null || endTime.trim().isEmpty()
                ? System.currentTimeMillis() : parseTime(endTime);
        long start = startTime == null || startTime.trim().isEmpty()
                ? end - 7L * 24 * 3600 * 1000 : parseTime(startTime);
        if (start > end) {
            throw new IllegalArgumentException("startTime 必须早于 endTime");
        }
        int fetchLimit = limit <= 0 ? 1000 : Math.min(limit, 10000);

        try {
            indexService.ensureCarWarningIndex();
        } catch (Exception e) {
            throw new IllegalStateException("创建 car-warning 索引失败: " + e.getMessage(), e);
        }

        List<Map<String, Object>> rows;
        String source;
        rows = null;
        source = null;
        String[] schemas = {"carmonitdb", "jl_data01", ""};
        Exception lastError = null;
        for (String schema : schemas) {
            try {
                rows = jdbc.queryForList(joinSql(schema),
                        TrafficTimeUtils.toDbTimestamp(start), TrafficTimeUtils.toDbTimestamp(end),
                        fetchLimit);
                source = (schema.isEmpty() ? "" : schema + ".") + "car_warning_info + car_info";
                break;
            } catch (Exception joinError) {
                lastError = joinError;
                try {
                    rows = jdbc.queryForList(simpleSql(schema),
                            TrafficTimeUtils.toDbTimestamp(start), TrafficTimeUtils.toDbTimestamp(end),
                            fetchLimit);
                    source = (schema.isEmpty() ? "" : schema + ".") + "car_warning_info";
                    break;
                } catch (Exception simpleError) {
                    lastError = simpleError;
                }
            }
        }
        if (rows == null) {
            throw new IllegalStateException("car_warning_info 不可用，无法回灌: "
                    + (lastError == null ? "unknown" : lastError.getMessage()));
        }

        long indexed = 0;
        List<IndexRequest> requests = new ArrayList<>(BULK_SIZE);
        for (Map<String, Object> row : rows) {
            String id = documentBuilder.docId(row);
            if (id == null || id.isEmpty()) {
                continue;
            }
            requests.add(new IndexRequest(TrafficEsIndexService.CAR_WARNING_INDEX)
                    .id(id)
                    .source(JSON.toJSONString(documentBuilder.build(row)), XContentType.JSON));
            if (requests.size() >= BULK_SIZE) {
                indexed += flush(requests);
            }
        }
        indexed += flush(requests);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("fetched", rows.size());
        result.put("indexed", indexed);
        result.put("source", source);
        result.put("index", TrafficEsIndexService.CAR_WARNING_INDEX);
        log.info("[V3预警回灌] 完成: fetched={}, indexed={}, source={}", rows.size(), indexed, source);
        return result;
    }

    private int flush(List<IndexRequest> requests) {
        if (requests.isEmpty()) {
            return 0;
        }
        BulkRequest bulk = new BulkRequest();
        for (IndexRequest request : requests) {
            bulk.add(request);
        }
        int count = requests.size();
        requests.clear();
        try {
            BulkResponse response = esClient.bulk(bulk, RequestOptions.DEFAULT);
            if (response.hasFailures()) {
                log.warn("[V3预警回灌] bulk 部分失败: {}", response.buildFailureMessage());
            }
            return count;
        } catch (Exception e) {
            throw new IllegalStateException("car-warning bulk 写入失败: " + e.getMessage(), e);
        }
    }

    private String joinSql(String schema) {
        String prefix = schema == null || schema.isEmpty() ? "" : schema + ".";
        return "SELECT t.*, c.plate_color AS plate_color, c.escaped_type AS escaped_type, "
                + "c.escaped_amount AS escaped_amount "
                + "FROM " + prefix + "car_warning_info t "
                + "LEFT JOIN " + prefix + "car_info c ON c.id = t.car_id AND c.del_flag = '0' "
                + "WHERE t.del_flag = '0' AND t.gantry_time >= ? AND t.gantry_time < ? "
                + "ORDER BY t.gantry_time, t.id LIMIT ?";
    }

    private String simpleSql(String schema) {
        String prefix = schema == null || schema.isEmpty() ? "" : schema + ".";
        return "SELECT t.* FROM " + prefix + "car_warning_info t "
                + "WHERE t.del_flag = '0' AND t.gantry_time >= ? AND t.gantry_time < ? "
                + "ORDER BY t.gantry_time, t.id LIMIT ?";
    }

    private long parseTime(String value) {
        try {
            Long millis = TrafficTimeUtils.parseDbTimestamp(value);
            if (millis != null) {
                return millis;
            }
            throw new IllegalArgumentException("时间格式非法: " + value);
        } catch (Exception e) {
            throw new IllegalArgumentException("时间格式非法: " + value
                    + "，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss");
        }
    }
}
