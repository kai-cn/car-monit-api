package com.ruoyi.base.service.optimization;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.domain.ZdataTrailFitting;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.mapper.ZdataTrailFittingMapper;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.core.TimeValue;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.index.query.RangeQueryBuilder;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 统一查询路由服务（3 大表共用）
 *
 * =================================================================
 * 设计目标：
 *   面向"日增 70W、单表 8 亿、最近一年查询 + 任意字段全模糊"场景，
 *   提供一致的查询入口，屏蔢单表差异：
 *     1. 自动路由到 Elasticsearch（默认），不可用时降级到 MySQL
 *     2. 任意模糊字段统一按 ngram match 走倒排索引
 *     3. 分页使用 from+size（窗口内）+ search_after（深分页可选扩展）
 *
 * 路由策略：
 *   if (存在模糊查询字段 || 时间范围超过 30 天) {
 *       优先走 ES；
 *   } else if (主键精确查询) {
 *       走 MySQL；
 *   } else {
 *       可走 MySQL（小范围精确，结合分区裁剪）；
 *   }
 *   ES 异常时自动降级 MySQL。
 *
 * 数据源抽象（DataSource Meta）：
 *   ┌─────────────┬──────────────────────────────────────┬──────────────┐
 *   │ 业务表      │ ES 索引                              │ 时间范围字段 │
 *   ├─────────────┼──────────────────────────────────────┼──────────────┤
 *   │ 门架抓拍    │ snapshot_flow                        │ snapshottime │
 *   │ 收费流水    │ fee_records                          │ transtime    │
 *   │ 车辆轨迹    │ trail_fitting                        │ extime       │
 *   └─────────────┴──────────────────────────────────────┴──────────────┘
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class UnifiedQueryService {

    /** 三种业务数据源类型 */
    public enum DataSource {
        SNAPSHOT,
        FEE,
        TRAIL
    }

    @Autowired
    private RestHighLevelClient esClient;

    @Autowired
    private EsIndexManageService indexManageService;

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotMapper;

    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper feeMapper;

    @Autowired
    private ZdataTrailFittingMapper trailMapper;

    /** 单次 ES 查询超时（秒） */
    @Value("${optimization.query.timeout-ms:30000}")
    private long queryTimeoutMs;

    /** from + size 单次最大返回文档数（ES 默认 max_result_window = 10000） */
    @Value("${optimization.query.max-window:10000}")
    private int maxWindow;

    /** 时间范围超过多少天时强制走 ES */
    @Value("${optimization.query.es-force-days:30}")
    private int esForceDays;

    // ============================================================
    // 公共入口
    // ============================================================

    /**
     * 统一查询接口
     *
     * @param ds         数据源类型
     * @param startTime  开始时间 (yyyy-MM-dd HH:mm:ss)
     * @param endTime    结束时间
     * @param fuzzyFields 通用全模糊字段（key=字段名，value=模糊内容）
     *                    支持字段：platenumber/orgname/sectionname/roadname/gantryname/tollname
     * @param pageNum    页码 (1-based)
     * @param pageSize   每页条数
     * @return 查询结果列表（已根据数据源反向化为对应 domain）
     */
    public List<?> query(DataSource ds, String startTime, String endTime,
                         Map<String, String> fuzzyFields,
                         int pageNum, int pageSize) {
        // 1. 路由决策
        boolean useEs = shouldRouteToEs(startTime, endTime, fuzzyFields, ds);
        long t0 = System.currentTimeMillis();

        try {
            if (useEs) {
                return queryFromEs(ds, startTime, endTime, fuzzyFields, pageNum, pageSize);
            } else {
                return queryFromMysql(ds, startTime, endTime, fuzzyFields, pageNum, pageSize);
            }
        } catch (Exception e) {
            log.error("[统一查询] 查询失败 ds={}, useEs={}, 耗时={}ms", ds, useEs,
                    System.currentTimeMillis() - t0, e);
            // ES 查询失败 -> 降级 MySQL
            if (useEs) {
                log.warn("[统一查询] ES 查询失败，尝试降级到 MySQL, ds={}", ds);
                try {
                    return queryFromMysql(ds, startTime, endTime, fuzzyFields, pageNum, pageSize);
                } catch (Exception ex) {
                    log.error("[统一查询] 降级 MySQL 也失败, ds={}", ds, ex);
                    return Collections.emptyList();
                }
            }
            return Collections.emptyList();
        } finally {
            long cost = System.currentTimeMillis() - t0;
            log.info("[统一查询] ds={}, useEs={}, cost={}ms, page={}/{}",
                    ds, useEs, cost, pageNum, pageSize);
        }
    }

    // ============================================================
    // 路由策略
    // ============================================================

    /**
     * 是否应该路由到 ES
     *
     * 触发 ES 的条件（满足任一）：
     *   1. 存在任意模糊查询字段（MySQL like '%xxx%' 走不了索引）
     *   2. 时间范围超过 esForceDays 天
     *   3. 数据源是收费流水或轨迹（这两张表分区裁剪效果较难保证）
     *
     * 不触发时：
     *   - 小范围精确查询：MySQL + 分区裁剪 + B-tree 索引效率更好
     *   - 例如最近 1 周 + 单个门架代码 + 完整车牌
     */
    private boolean shouldRouteToEs(String startTime, String endTime,
                                     Map<String, String> fuzzyFields, DataSource ds) {
        // 条件 1：任意模糊字段非空
        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getValue() != null && !e.getValue().isEmpty()) {
                    return true;
                }
            }
        }
        // 条件 2：时间跨度 > esForceDays（粗略判断，避免误差不影响路由选择）
        try {
            long start = parseToMillis(startTime);
            long end   = parseToMillis(endTime);
            if (end - start > (long) esForceDays * 24 * 3600 * 1000L) {
                return true;
            }
        } catch (Exception ignored) {
            // 时间格式异常时保守走 ES（ES 对时间格式更宽容）
            return true;
        }
        // 条件 3：轨迹数据和收费流水默认走 ES（场景复杂、字段更多）
        return ds == DataSource.FEE || ds == DataSource.TRAIL;
    }

    private long parseToMillis(String time) {
        if (time == null || time.isEmpty()) return 0;
        return java.sql.Timestamp.valueOf(time).getTime();
    }

    // ============================================================
    // ES 查询实现（3 表统一）
    // ============================================================

    private List<?> queryFromEs(DataSource ds, String startTime, String endTime,
                                 Map<String, String> fuzzyFields,
                                 int pageNum, int pageSize) throws Exception {
        String indexName = resolveIndexName(ds);
        String timeField = resolveTimeField(ds);
        Class<?> targetClass = resolveDomainClass(ds);

        // 1. 构建查询
        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();

        // 时间范围（必填，过滤到最近一年）
        RangeQueryBuilder timeRange = QueryBuilders.rangeQuery(timeField)
                .format("yyyy-MM-dd HH:mm:ss")
                .gte(startTime)
                .lte(endTime);
        boolQuery.filter(timeRange);

        // 通用全模糊字段（统一走 ngram 倒排索引）
        // 先翻译逻辑字段名 -> 物理字段名（如 FEE 的 platenumber -> vehicleplate），对调用方透明
        // Translate logical field -> physical field (e.g. FEE platenumber -> vehicleplate) before querying.
        Map<String, String> translation = buildFieldTranslation(ds);
        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getValue() == null || e.getValue().isEmpty()) continue;
                String physicalField = translation.getOrDefault(e.getKey(), e.getKey());
                boolQuery.must(buildFuzzyQuery(physicalField, e.getValue()));
            }
        }

        // 2. 分页参数（long 运算避免深分页溢出）
        long from = com.ruoyi.common.utils.PageUtils.safeFrom(pageNum, pageSize);
        int size = Math.min(pageSize, maxWindow);
        if (from + size > maxWindow) {
            throw new IllegalStateException(
                    "浅分页超过 max_result_window=" + maxWindow + "，请使用 export 接口或 search_after");
        }

        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
                .query(boolQuery)
                .from((int) from)
                .size(size)
                .sort(timeField, SortOrder.DESC)
                .timeout(new TimeValue(queryTimeoutMs, TimeUnit.MILLISECONDS));

        SearchRequest request = new SearchRequest(indexName);
        request.source(sourceBuilder);

        // 3. 执行查询
        SearchResponse response = esClient.search(request, RequestOptions.DEFAULT);

        // 4. 解析结果 -> 反向化为 domain 对象
        List<Object> results = new ArrayList<>(response.getHits().getHits().length);
        for (SearchHit hit : response.getHits().getHits()) {
            Object obj = JSON.parseObject(hit.getSourceAsString(), targetClass);
            results.add(obj);
        }

        log.debug("[统一查询-ES] ds={}, index={}, timeField={}, totalHits={}, returned={}",
                ds, indexName, timeField,
                response.getHits().getTotalHits().value, results.size());
        return results;
    }

    /**
     * 智能构建全模糊查询条件
     *
     * 字段长度策略：
     *   - 长度>=7 且为编号/车牌类字段：直接 term 精确匹配（最高性能）
     *   - 长度 3-6：ngram match 走倒排索引（核心路径）
     *   - 长度 1-2：wildcard 通配符兜底（语义正确但性能较低，避免高频使用）
     *
     * 注意：所有模糊字段都必须在 ES Mapping 中已定义 ".ngram" 子字段，
     *      否则 match 会报错。索引管理服务已确保 mapping 完整。
     */
    private QueryBuilder buildFuzzyQuery(String fieldName, String value) {
        // 完整编号类（>= 7 字符）：精确匹配
        if (value.length() >= 7 && (fieldName.equals("platenumber")
                || fieldName.equals("gantrycode")
                || fieldName.equals("sectioncode"))) {
            return QueryBuilders.termQuery(fieldName + ".keyword", value);
        }
        // 3-6 字符：ngram match（核心路径）
        if (value.length() >= 3) {
            return QueryBuilders.matchQuery(fieldName + ".ngram", value);
        }
        // 1-2 字符：wildcard 兜底
        return QueryBuilders.wildcardQuery(fieldName + ".keyword", "*" + value + "*");
    }

    // ============================================================
    // MySQL 降级查询实现
    // ============================================================

    /**
     * ES 不可用 / 未启用时的降级查询路径（兜底，非主路径）
     * Fallback query path when ES is unavailable (best-effort, not the main path).
     *
     * 说明 / Notes:
     *   - 依赖 GaussDB 月度分区裁剪 + pg_trgm GIN 索引保证基本可用
     *     Relies on monthly partition pruning + pg_trgm GIN for basic usability
     *   - MySQL 的 like '%xxx%' 走不了 B-tree 索引，8 亿级数据下性能差，仅作兜底
     *     like '%xxx%' cannot use B-tree; only a safety net, keep ES healthy in production
     *   - 时间范围 + 模糊字段翻译后，使用 MyBatis-Plus QueryWrapper 构建，最后内存分页
     *     Build with QueryWrapper after field translation, then paginate in memory
     */
    private List<?> queryFromMysql(DataSource ds, String startTime, String endTime,
                                    Map<String, String> fuzzyFields,
                                    int pageNum, int pageSize) {
        String timeField = resolveTimeField(ds);
        Map<String, String> translation = buildFieldTranslation(ds);

        // 使用裸类型 QueryWrapper 以兼容三张表的不同实体类型（运行期安全，编译期 unchecked）
        // Raw QueryWrapper to share logic across 3 entity types (runtime-safe, compile unchecked).
        com.baomidou.mybatisplus.core.conditions.query.QueryWrapper qw =
                new com.baomidou.mybatisplus.core.conditions.query.QueryWrapper();
        // 时间范围（分区裁剪核心）
        if (startTime != null && !startTime.isEmpty()) {
            qw.ge(timeField, new java.sql.Timestamp(parseToMillis(startTime)));
        }
        if (endTime != null && !endTime.isEmpty()) {
            qw.le(timeField, new java.sql.Timestamp(parseToMillis(endTime)));
        }
        // 模糊字段（翻译为物理字段后走 like）
        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getValue() == null || e.getValue().isEmpty()) continue;
                String physical = translation.getOrDefault(e.getKey(), e.getKey());
                qw.like(physical, e.getValue());
            }
        }
        qw.last("LIMIT 1000"); // 降级路径限量，防止全表拉爆内存

        List<?> all;
        switch (ds) {
            case SNAPSHOT: all = snapshotMapper.selectList(qw); break;
            case FEE:      all = feeMapper.selectList(qw); break;
            case TRAIL:    all = trailMapper.selectList(qw); break;
            default:       return Collections.emptyList();
        }
        // 内存分页（降级场景，结果集已 LIMIT 1000）
        int from = Math.max(0, (pageNum - 1) * pageSize);
        int to = Math.min(all.size(), from + pageSize);
        return from >= all.size() ? Collections.emptyList() : new ArrayList<>(all.subList(from, to));
    }

    /**
     * 逻辑字段 -> 物理字段翻译表（对调用方透明）
     * Logical field -> physical field translation (transparent to callers).
     *
     * 说明：收费流水表的车牌物理字段为 vehicleplate，轨迹表的车辆编号物理字段为 envehicleid，
     * 对外统一以 platenumber 作为通用查询入参，在此翻译为对应物理字段。
     */
    private static Map<String, String> buildFieldTranslation(DataSource ds) {
        Map<String, String> m = new java.util.HashMap<>();
        m.put("orgname", "orgname");
        m.put("sectionname", "sectionname");
        m.put("roadname", "roadname");
        m.put("gantryname", "gantryname");
        m.put("tollname", "tollname");
        switch (ds) {
            case SNAPSHOT:
                m.put("platenumber", "platenumber");
                break;
            case FEE:
                m.put("platenumber", "vehicleplate");
                break;
            case TRAIL:
                // 轨迹表仅支持 platenumber，物理字段为入口车辆编号
                m.put("platenumber", "envehicleid");
                break;
            default:
                break;
        }
        return m;
    }

    // ============================================================
    // 元数据映射
    // ============================================================

    private String resolveIndexName(DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return indexManageService.getSnapshotIndex();
            case FEE:      return indexManageService.getFeeIndex();
            case TRAIL:    return indexManageService.getTrailIndex();
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    private String resolveTimeField(DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return "snapshottime";
            case FEE:      return "transtime";
            case TRAIL:    return "extime";
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    private Class<?> resolveDomainClass(DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return OdsRtSzdnSnapshotFlowAddcode.class;
            case FEE:      return OdsLwzxsfsjFeeRecords01.class;
            case TRAIL:    return ZdataTrailFitting.class;
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }
}
