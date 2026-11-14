package com.ruoyi.base.service.v3.query;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.plate.PlateNumberParser;
import com.ruoyi.base.service.v3.plate.PlateParseResult;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.util.EntityUtils;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.core.TimeValue;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.PointInTimeBuilder;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.FieldSortBuilder;
import org.elasticsearch.search.sort.SortBuilders;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 三表组合查询（ES 主路径）。
 *
 * <p>实现设计 §4.3/§5.3.5：</p>
 * <ul>
 *   <li>时间范围必填（默认 7 天、最大 365 天）；</li>
 *   <li>维度过滤走编码 term（名称由码表解析后下推）；</li>
 *   <li>车牌完整走 term，部分走 {@code plate_norm.ngram} 的 match_phrase；</li>
 *   <li>深分页 PIT + search_after；</li>
 *   <li><b>任何模糊条件在 ES 故障时都不回退 GaussDB</b>，直接抛出 503。</li>
 * </ul>
 */
@Slf4j
@Service
public class TrafficSearchService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final RestHighLevelClient esClient;
    private final TrafficEsIndexService indexService;
    private final PlateNumberParser plateParser;
    private final TrafficV3Properties properties;
    private final DimensionCodeResolver dimensionResolver;

    public TrafficSearchService(RestHighLevelClient esClient,
                                TrafficEsIndexService indexService,
                                PlateNumberParser plateParser,
                                TrafficV3Properties properties,
                                DimensionCodeResolver dimensionResolver) {
        this.esClient = esClient;
        this.indexService = indexService;
        this.plateParser = plateParser;
        this.properties = properties;
        this.dimensionResolver = dimensionResolver;
    }

    /**
     * 统一入口：按 pageNum 或 searchAfter 查询。
     */
    public TrafficSearchResult search(TrafficSearchRequest req) {
        validateAndNormalize(req);
        return searchInternal(req);
    }

    /**
     * 展示字段导出/回灌内部使用：允许更大的 size（上限 1000）。
     */
    public TrafficSearchResult searchForExport(TrafficSearchRequest req, int maxSize) {
        int desired = Math.min(Math.max(1, req.getPageSize()), Math.max(1, maxSize));
        // 在线查询的 pageSize≤100 只约束交互式分页；导出是内部 PIT+search_after，
        // 允许更大页。校验时临时钳到在线上限，校验后恢复导出页大小。
        req.setPageSize(Math.min(desired, properties.getQuery().getMaxPageSize()));
        validateAndNormalize(req);
        req.setPageSize(desired);
        req.setPageNum(1);
        // 导出必须使用 search_after 深翻页
        return searchInternal(req);
    }

    private TrafficSearchResult searchInternal(TrafficSearchRequest req) {
        TrafficTable table = req.getTable();
        String timeField = table.getTimeField();
        String pkField = table.getPkField();
        int size = req.getPageSize();

        // P2：未知维度键显式 400，避免拼到不存在的字段后静默命中 0 条
        validateDimensionKeys(table, req.getDimensionCodes());
        // P1-1/P1-2：收费表无 org/road/toll 物理列，翻译为门架编码集合再过滤
        if (table == TrafficTable.FEE
                && !dimensionResolver.translateFeeDimensions(req.getDimensionCodes())) {
            return emptyResult();
        }

        BoolQueryBuilder bool = QueryBuilders.boolQuery();
        bool.filter(QueryBuilders.rangeQuery(timeField)
                .format("epoch_millis")
                .gte(req.getStartMillis())
                .lte(req.getEndMillis()));

        // 维度编码 term 过滤（名称→编码已在入口解析，此处只做低基数精确过滤）
        if (req.getDimensionCodes() != null) {
            for (Map.Entry<String, List<String>> e : req.getDimensionCodes().entrySet()) {
                List<String> values = e.getValue();
                if (values == null || values.isEmpty()) {
                    continue;
                }
                String field = resolveDimensionField(table, e.getKey());
                bool.filter(QueryBuilders.termsQuery(field, values));
            }
        }

        // 车牌过滤：完整 term / 部分 ngram match_phrase；颜色独立 term
        PlateParseResult parsed = null;
        String plateCore = null;
        if (req.getPlate() != null && !req.getPlate().trim().isEmpty()) {
            parsed = plateParser.parse(req.getPlate());
            plateCore = parsed.getPlateCore();
            if (plateCore == null || plateCore.isEmpty()) {
                throw TrafficQueryException.badRequest("车牌无法解析: " + req.getPlate());
            }
            if (!plateParser.isFullPlate(plateCore)) {
                if (plateCore.length() < properties.getQuery().getMinPlateFuzzyLength()) {
                    throw TrafficQueryException.badRequest("车牌模糊查询至少需要 "
                            + properties.getQuery().getMinPlateFuzzyLength() + " 个字符");
                }
                bool.filter(QueryBuilders.matchPhraseQuery(
                        table.plateNormField() + ".ngram", plateCore));
            } else {
                bool.filter(QueryBuilders.termQuery(table.plateNormField(), plateCore));
            }
        }

        // 收费颜色过滤：颜色不进入 ngram（设计 §5.1.6）
        if (table == TrafficTable.FEE) {
            String color = req.getColorCode();
            if (color == null || color.trim().isEmpty()) {
                if (parsed != null && parsed.getPlateColorCode() >= 0) {
                    color = String.valueOf(parsed.getPlateColorCode());
                }
            }
            if (color != null && !color.trim().isEmpty()) {
                bool.filter(QueryBuilders.termQuery("plate_color_code", color.trim()));
            }
        }

        boolean useSearchAfter = req.getSearchAfter() != null && !req.getSearchAfter().isEmpty();
        String pitId = req.getPitId();
        // 普通 from/size 分页不创建 PIT：每次多两次 ES 往返并占用 2 分钟搜索上下文，
        // 高并发或 keepPit=true 的滥用会打满 max_open_scroll_context。
        boolean openPit = (pitId == null || pitId.isEmpty())
                && (useSearchAfter || req.isKeepPit());
        String readAlias = table.readAlias();
        boolean completed = false;

        try {
            if (openPit) {
                pitId = openPit(readAlias);
            }

            SearchSourceBuilder source = new SearchSourceBuilder()
                    .query(bool)
                    .size(size)
                    .timeout(new TimeValue(30000, TimeUnit.MILLISECONDS));
            if (req.isNeedTotal()) {
                source.trackTotalHitsUpTo(properties.getQuery().getTotalHitsCap());
            } else {
                source.trackTotalHits(false);
            }

            FieldSortBuilder timeSort = SortBuilders.fieldSort(timeField)
                    .order(SortOrder.DESC).missing("_last");
            FieldSortBuilder pkSort = SortBuilders.fieldSort(pkField)
                    .order(SortOrder.DESC).missing("_last");
            source.sort(timeSort);
            source.sort(pkSort);

            if (useSearchAfter) {
                source.searchAfter(req.getSearchAfter().toArray());
            } else {
                int from = Math.max(0, (req.getPageNum() - 1) * size);
                source.from(from);
            }

            if (pitId != null && !pitId.isEmpty()) {
                source.pointInTimeBuilder(new PointInTimeBuilder(pitId)
                        .setKeepAlive(new TimeValue(2, TimeUnit.MINUTES)));
            }

            SearchRequest searchRequest = pitId != null && !pitId.isEmpty()
                    ? new SearchRequest()
                    : new SearchRequest(readAlias);
            searchRequest.source(source);

            long t0 = System.currentTimeMillis();
            SearchResponse response = esClient.search(searchRequest, RequestOptions.DEFAULT);
            TrafficSearchResult result = parseResponse(response, req, plateCore, size);
            result.setTookMs(System.currentTimeMillis() - t0);
            result.setPitId(req.isKeepPit() ? pitId : null);
            completed = true;
            return result;
        } catch (IOException e) {
            throw TrafficQueryException.unavailable(
                    "ES 查询失败（模糊查询禁止回退 GaussDB）：" + e.getMessage(), e);
        } catch (TrafficQueryException e) {
            throw e;
        } catch (Exception e) {
            throw TrafficQueryException.unavailable(
                    "ES 查询异常（模糊查询禁止回退 GaussDB）：" + e.getMessage(), e);
        } finally {
            // 请求失败时即便调用方要求保留 PIT，也必须关闭本次新建的上下文，
            // 否则异常路径持续泄漏搜索上下文。
            if (openPit && pitId != null && !pitId.isEmpty()
                    && (!completed || !req.isKeepPit())) {
                closePitQuietly(pitId);
            }
        }
    }

    private TrafficSearchResult parseResponse(SearchResponse response,
                                              TrafficSearchRequest req,
                                              String plateCore,
                                              int size) {
        TrafficSearchResult result = new TrafficSearchResult();
        long total = 0;
        if (response.getHits().getTotalHits() != null) {
            total = response.getHits().getTotalHits().value;
        }
        result.setTotal(total);

        SearchHit[] hits = response.getHits().getHits();
        List<Map<String, Object>> rows = new ArrayList<>(hits.length);
        List<Object> lastSort = new ArrayList<>();
        for (SearchHit hit : hits) {
            if (hit.getSortValues() != null && hit.getSortValues().length > 0) {
                lastSort = Arrays.asList(hit.getSortValues());
            }
            Map<String, Object> source = hit.getSourceAsMap();
            // ngram 假阳性复核（设计 §5.1.5：返回页内应用层 contains 复核）
            if (plateCore != null && !plateCore.isEmpty()) {
                Object plateNorm = source.get("plate_norm");
                if (plateNorm != null
                        && !String.valueOf(plateNorm).toUpperCase().contains(plateCore.toUpperCase())) {
                    continue;
                }
            }
            rows.add(source);
        }
        result.setRows(rows);
        result.setSearchAfter(lastSort);
        result.setHasMore(hits.length >= size);
        return result;
    }

    private void validateAndNormalize(TrafficSearchRequest req) {
        if (req.getTable() == null) {
            throw TrafficQueryException.badRequest("table 不能为空");
        }
        long now = System.currentTimeMillis();
        if (req.getStartMillis() == null) {
            req.setStartMillis(now - TimeUnit.DAYS.toMillis(properties.getQuery().getDefaultDays()));
        }
        if (req.getEndMillis() == null) {
            req.setEndMillis(now);
        }
        if (req.getStartMillis() > req.getEndMillis()) {
            throw TrafficQueryException.badRequest("startTime 必须早于 endTime");
        }
        long maxMillis = TimeUnit.DAYS.toMillis(properties.getQuery().getMaxDays());
        if (req.getEndMillis() - req.getStartMillis() > maxMillis) {
            throw TrafficQueryException.badRequest("时间范围超过 " + properties.getQuery().getMaxDays() + " 天");
        }

        int maxPageSize = properties.getQuery().getMaxPageSize();
        if (req.getPageSize() <= 0) {
            req.setPageSize(20);
        }
        if (req.getPageSize() > maxPageSize) {
            throw TrafficQueryException.badRequest("pageSize 不能超过 " + maxPageSize);
        }
        if (req.getPageNum() < 1) {
            req.setPageNum(1);
        }

        boolean useSearchAfter = req.getSearchAfter() != null && !req.getSearchAfter().isEmpty();
        if (useSearchAfter && (req.getPitId() == null || req.getPitId().isEmpty())) {
            throw TrafficQueryException.badRequest("searchAfter 必须与 pitId 一起使用");
        }
        if (!useSearchAfter) {
            int from = (req.getPageNum() - 1) * req.getPageSize();
            int maxWindow = properties.getQuery().getMaxWindow();
            if (from + req.getPageSize() > maxWindow) {
                throw TrafficQueryException.badRequest(
                        "from+size 超过 " + maxWindow + "，请使用 /api/v3/traffic/searchAfter 接口");
            }
        }
    }

    private String resolveDimensionField(TrafficTable table, String logicalField) {
        if ("gantrycode".equals(logicalField) && table == TrafficTable.FEE) {
            return "gantryid";
        }
        return logicalField;
    }

    /**
     * 维度键白名单：未知键直接 400，不再“拼字段名后静默命中 0 条”。
     * 收费表允许 org/road/toll（由 translateFeeDimensions 翻译），轨迹表无维度。
     */
    private void validateDimensionKeys(TrafficTable table, Map<String, List<String>> codes) {
        if (codes == null || codes.isEmpty()) {
            return;
        }
        java.util.Set<String> allowed;
        if (table == TrafficTable.TRAIL) {
            allowed = java.util.Collections.emptySet();
        } else {
            allowed = new java.util.HashSet<>(Arrays.asList(
                    "orgcode", "sectioncode", "roadcode", "gantrycode", "tollcode"));
        }
        Map<String, List<String>> normalized = new java.util.LinkedHashMap<>();
        for (Map.Entry<String, List<String>> entry : codes.entrySet()) {
            String key = entry.getKey() == null ? "" : entry.getKey().trim().toLowerCase();
            if (!allowed.contains(key)) {
                throw TrafficQueryException.badRequest("不支持的维度字段: " + entry.getKey()
                        + "，允许值: " + allowed);
            }
            List<String> values = normalized.get(key);
            if (values == null) {
                values = new ArrayList<>();
                normalized.put(key, values);
            }
            if (entry.getValue() != null) {
                values.addAll(entry.getValue());
            }
        }
        codes.clear();
        codes.putAll(normalized);
    }

    private TrafficSearchResult emptyResult() {
        TrafficSearchResult result = new TrafficSearchResult();
        result.setTotal(0);
        result.setHasMore(false);
        result.setRows(new ArrayList<>());
        return result;
    }

    private String openPit(String indexOrAlias) throws IOException {
        Request request = new Request("POST", "/" + indexOrAlias + "/_pit");
        request.addParameter("keep_alive", properties.getEs().getPitKeepAlive());
        Response response = esClient.getLowLevelClient().performRequest(request);
        String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
        JsonNode node = MAPPER.readTree(body);
        if (!node.has("id")) {
            throw new IOException("开启 PIT 失败: " + body);
        }
        return node.get("id").asText();
    }

    private void closePitQuietly(String pitId) {
        try {
            Request request = new Request("DELETE", "/_pit");
            request.setJsonEntity("{\"id\":\"" + pitId + "\"}");
            esClient.getLowLevelClient().performRequest(request);
        } catch (Exception e) {
            log.debug("[V3查询] 关闭 PIT 失败: {}", e.getMessage());
        }
    }

    /** 供健康检查使用 */
    public boolean esAvailable() {
        return indexService.ping();
    }

    /** 显式关闭 PIT（导出/深分页结束时调用） */
    public void closePit(String pitId) {
        closePitQuietly(pitId);
    }
}
