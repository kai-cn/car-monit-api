package com.ruoyi.base.service.v3.es;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.plate.PlateNumberParser;
import com.ruoyi.base.service.v3.plate.PlateParseResult;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 大屏实时预警列表查询（car-warning ES 索引）。
 *
 * <p>契约：返回与 backend {@code CarWarningInfo} 一致的 camelCase JSON 字段。</p>
 * <ul>
 *   <li>索引存在但无数据 -> 200 + 空列表；</li>
 *   <li>索引缺失 -> 200 + 空列表（WARN，提示先创建模板/索引与回灌）；</li>
 *   <li>ES 不可达/查询异常 -> 503，让 backend 回退 Redis 快照。</li>
 * </ul>
 */
@Slf4j
@Service
public class CarWarningSearchService {

    private static final String INDEX = TrafficEsIndexService.CAR_WARNING_INDEX;

    private static final Set<String> DATE_FIELDS = new HashSet<>(Arrays.asList(
            "in_time", "gantry_time", "next_pass_time", "create_time", "update_time"));

    private final RestHighLevelClient esClient;
    private final TrafficEsIndexService indexService;
    private final PlateNumberParser plateParser;
    private final TrafficV3Properties properties;

    public CarWarningSearchService(RestHighLevelClient esClient,
                                   TrafficEsIndexService indexService,
                                   PlateNumberParser plateParser,
                                   TrafficV3Properties properties) {
        this.esClient = esClient;
        this.indexService = indexService;
        this.plateParser = plateParser;
        this.properties = properties;
    }

    /**
     * 查询实时预警列表。
     *
     * <p>维度参数支持逗号分隔多值（terms）；captureType 支持
     * StationCapture / GantryCapture / ServiceAreaCapture 哨兵。</p>
     *
     * @param limit 上限 100；backend 已做一次 clamp，这里再兜底
     */
    public List<Map<String, Object>> search(String roadCode, String sectionCode, String tollCode,
                                            String gantryCode, String fwqbm, String escapedType,
                                            String carNo, String captureType, int limit) {
        int size = limit <= 0 ? 100 : Math.min(limit, 100);

        if (!indexService.ping()) {
            throw TrafficQueryException.unavailable("car-warning 查询失败：ES 不可达");
        }
        if (!indexService.carWarningIndexExists()) {
            log.warn("[V3预警] car-warning 索引不存在，返回空列表；"
                    + "请先创建模板/索引并回灌（见 docs/decisions-v3.md §6.3）");
            return Collections.emptyList();
        }

        BoolQueryBuilder bool = QueryBuilders.boolQuery();
        addTerms(bool, "road_code", roadCode);
        addTerms(bool, "section_code", sectionCode);
        addTerms(bool, "toll_code", tollCode);
        addTerms(bool, "fwqbm", fwqbm);
        addTerms(bool, "escaped_type", escapedType);
        addTerms(bool, "capture_type", captureType);

        List<String> gantryValues = splitValues(gantryCode);
        if (!gantryValues.isEmpty()) {
            // 兼容 gantry_code 与 gantry_station_id 两种写入口径
            BoolQueryBuilder gantry = QueryBuilders.boolQuery();
            for (String value : gantryValues) {
                gantry.should(QueryBuilders.termQuery("gantry_code", value));
                gantry.should(QueryBuilders.termQuery("gantry_station_id", value));
            }
            gantry.minimumShouldMatch(1);
            bool.filter(gantry);
        }

        List<String> plates = splitValues(carNo);
        if (!plates.isEmpty()) {
            BoolQueryBuilder plateQuery = QueryBuilders.boolQuery();
            int clauses = 0;
            for (String plateValue : plates) {
                PlateParseResult parsed = plateParser.parse(plateValue);
                String core = parsed.getPlateCore();
                if (core == null || core.isEmpty()) {
                    continue;
                }
                if (plateParser.isFullPlate(core)) {
                    plateQuery.should(QueryBuilders.termQuery("car_no", core));
                    clauses++;
                } else if (core.length() >= properties.getQuery().getMinPlateFuzzyLength()) {
                    plateQuery.should(QueryBuilders.matchPhraseQuery("car_no.ngram", core));
                    clauses++;
                }
            }
            if (clauses == 0) {
                return Collections.emptyList();
            }
            plateQuery.minimumShouldMatch(1);
            bool.filter(plateQuery);
        }

        SearchSourceBuilder source = new SearchSourceBuilder()
                .query(bool)
                .size(size)
                .trackTotalHits(false)
                .sort("gantry_time", SortOrder.DESC)
                .sort("id", SortOrder.ASC);

        SearchRequest request = new SearchRequest(INDEX);
        request.source(source);
        try {
            SearchResponse response = esClient.search(request, RequestOptions.DEFAULT);
            List<Map<String, Object>> rows = new ArrayList<>(response.getHits().getHits().length);
            for (SearchHit hit : response.getHits().getHits()) {
                rows.add(toContractMap(hit.getSourceAsMap()));
            }
            return rows;
        } catch (Exception e) {
            throw TrafficQueryException.unavailable("car-warning 查询异常: " + e.getMessage(), e);
        }
    }

    /**
     * snake_case -> backend CamelCase，日期 epoch millis -> yyyy-MM-dd HH:mm:ss。
     */
    private Map<String, Object> toContractMap(Map<String, Object> source) {
        Map<String, Object> row = new LinkedHashMap<>();
        if (source == null) {
            return row;
        }
        for (Map.Entry<String, Object> entry : source.entrySet()) {
            String key = entry.getKey();
            Object value = entry.getValue();
            String camel = toCamel(key);
            if (value instanceof Number && DATE_FIELDS.contains(key)) {
                row.put(camel, TrafficTimeUtils.format(((Number) value).longValue()));
            } else {
                row.put(camel, value);
            }
        }
        return row;
    }

    private String toCamel(String name) {
        StringBuilder sb = new StringBuilder(name.length());
        boolean upper = false;
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            if (c == '_') {
                upper = true;
                continue;
            }
            sb.append(upper ? Character.toUpperCase(c) : c);
            upper = false;
        }
        return sb.toString();
    }

    private void addTerms(BoolQueryBuilder bool, String field, String value) {
        List<String> values = splitValues(value);
        if (!values.isEmpty()) {
            bool.filter(QueryBuilders.termsQuery(field, values));
        }
    }

    /**
     * 逗号分隔多值：去空、去重；出现 "all"（前端"全部"）时取消该维度过滤。
     */
    private List<String> splitValues(String value) {
        if (!notBlank(value)) {
            return Collections.emptyList();
        }
        List<String> values = new ArrayList<>();
        for (String item : value.split(",")) {
            String token = item == null ? "" : item.trim();
            if (token.isEmpty()) {
                continue;
            }
            if ("all".equalsIgnoreCase(token)) {
                return Collections.emptyList();
            }
            if (!values.contains(token)) {
                values.add(token);
            }
        }
        return values;
    }

    private boolean notBlank(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
