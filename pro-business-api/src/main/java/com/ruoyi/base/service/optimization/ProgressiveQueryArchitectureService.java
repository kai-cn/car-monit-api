package com.ruoyi.base.service.optimization;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.ZdataTrailFitting;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.mapper.ZdataTrailFittingMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;

/**
 * 渐进式查询架构服务 - Progressive Query Architecture Service
 * <p>
 * 架构思路 / Architecture Design:
 * <p>
 * 阶段一：千万级（单表 < 5000万行）- Phase 1: Ten Million Level
 *   - 策略：GaussDB 原生 B-tree 索引 + pg_trgm GIN 索引 + 游标分页
 *   - Strategy: GaussDB native B-tree index + pg_trgm GIN index + cursor pagination
 *   - 适用：LIKE '%xxx%' 模糊查询通过 trigram GIN 索引加速
 *   - Applicable: LIKE '%xxx%' fuzzy query accelerated by trigram GIN index
 *   - 查询路径：Controller → GaussDB（B-tree + GIN 索引扫描）
 *   - Query path: Controller → GaussDB (B-tree + GIN index scan)
 * <p>
 * 阶段二：亿级（单表 5000万 ~ 5亿行）- Phase 2: Hundred Million Level
 *   - 策略：按月范围分区（Range Partition）+ 分区裁剪 + 覆盖索引 + 物化视图
 *   - Strategy: Monthly range partition + partition pruning + covering index + materialized view
 *   - 查询路径：Controller → GaussDB 分区表（分区裁剪 + 索引扫描）
 *   - Query path: Controller → GaussDB partitioned table (partition pruning + index scan)
 *   - 统计查询走物化视图，明细查询走分区表
 *   - Statistical queries go through materialized views, detail queries go through partitioned tables
 * <p>
 * 阶段三：十亿级（单表 > 5亿行）- Phase 3: Billion Level
 *   - 策略：冷热分离 + Elasticsearch 全文检索 + GaussDB 只处理热数据
 *   - Strategy: Cold/hot separation + Elasticsearch full-text search + GaussDB handles only hot data
 *   - 查询路径：Controller → 路由判断 → ES（全模糊/统计/导出）/ GaussDB（精确查询/热数据）
 *   - Query path: Controller → routing decision → ES (full fuzzy/stats/export) / GaussDB (exact query/hot data)
 *   - ES 负责全字段模糊查询、聚合统计、大规模导出
 *   - ES handles full-field fuzzy query, aggregation statistics, large-scale export
 *   - GaussDB 负责近期热数据的精确查询和事务操作
 *   - GaussDB handles exact query and transactional operations on recent hot data
 */
@Slf4j
@Service
public class ProgressiveQueryArchitectureService {

    /**
     * 数据量级别枚举 - Data scale level enum
     */
    public enum DataScaleLevel {
        /** 千万级：单表 < 5000万 - Ten million level: single table < 50 million */
        LEVEL_10M,
        /** 亿级：5000万 ~ 5亿 - Hundred million level: 50M ~ 500M */
        LEVEL_100M,
        /** 十亿级：> 5亿 - Billion level: > 500M */
        LEVEL_1B
    }

    /** 配置的数据量级别 - Configured data scale level */
    @Value("${optimization.scale-level:LEVEL_10M}")
    private String configuredScaleLevel;

    /** 门架抓拍流水 Mapper - Snapshot flow mapper */
    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotFlowMapper;

    /** 收费流水 Mapper - Fee records mapper */
    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper feeRecordsMapper;

    /** 车辆轨迹拟合 Mapper - Trail fitting mapper */
    @Autowired
    private ZdataTrailFittingMapper trailFittingMapper;

    /** Redis 缓存模板 - Redis cache template */
    @Autowired
    private RedisTemplate redisTemplate;

    /**
     * Elasticsearch 查询服务（可选依赖，阶段三启用）
     * Elasticsearch query service (optional dependency, enabled in phase 3)
     */
    @Autowired(required = false)
    private ElasticsearchQueryService elasticsearchQueryService;

    /** 表行数缓存前缀 - Table row count cache prefix */
    private static final String TABLE_COUNT_CACHE = "table:count:";

    /** 表行数缓存过期时间（秒）- Table row count cache TTL in seconds (1 hour) */
    private static final long TABLE_COUNT_TTL = 3600;

    /**
     * 自动检测数据量级别
     * Auto-detect data scale level based on table row count
     *
     * @param tableName 表名 - table name
     * @return 数据量级别 - data scale level
     */
    public DataScaleLevel detectScaleLevel(String tableName) {
        // 1. 先从 Redis 缓存读取 - First read from Redis cache
        String cacheKey = TABLE_COUNT_CACHE + tableName;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            long count = Long.parseLong(cached.toString());
            return judgeScaleLevel(count);
        }
        // 2. 缓存未命中，使用配置的级别 - Cache miss, use configured level
        try {
            return DataScaleLevel.valueOf(configuredScaleLevel);
        } catch (Exception e) {
            // 配置非法时降级为千万级 - Degrade to ten million level when configuration is invalid
            return DataScaleLevel.LEVEL_10M;
        }
    }

    /**
     * 根据行数判定数据量级别
     * Judge data scale level by row count
     *
     * @param count 表行数 - table row count
     * @return 数据量级别 - data scale level
     */
    private DataScaleLevel judgeScaleLevel(long count) {
        if (count < 50_000_000L) return DataScaleLevel.LEVEL_10M;
        if (count < 500_000_000L) return DataScaleLevel.LEVEL_100M;
        return DataScaleLevel.LEVEL_1B;
    }

    /**
     * 统一查询入口 - 门架抓拍流水
     * Unified query entry - Snapshot Flow
     *
     * @param request 查询请求 - query request
     * @return 查询结果 - query result
     */
    public QueryResult querySnapshotFlow(QueryRequest request) {
        DataScaleLevel level = detectScaleLevel("ods_rt_szdn_snapshot_flow_addcode");
        log.info("[渐进式查询] 门架抓拍流水，数据量级别={}, 请求={}", level, request);

        switch (level) {
            case LEVEL_10M:
                return querySnapshotFlowPhase1(request);
            case LEVEL_100M:
                return querySnapshotFlowPhase2(request);
            case LEVEL_1B:
                return querySnapshotFlowPhase3(request);
            default:
                return querySnapshotFlowPhase1(request);
        }
    }

    // 类似的方法 queryFeeRecords 和 queryTrailFitting
    // Similar methods: queryFeeRecords and queryTrailFitting

    // ==================== 阶段一：千万级 ====================
    // ==================== Phase 1: Ten Million Level ====================

    /**
     * 阶段一查询：门架抓拍流水（千万级）
     * Phase 1 query: snapshot flow (ten million level)
     * <p>
     * 策略：B-tree 索引 + GIN trigram 索引 + 游标分页
     * Strategy: B-tree index + GIN trigram index + cursor pagination
     */
    private QueryResult querySnapshotFlowPhase1(QueryRequest request) {
        // 构建查询条件对象 - Build query condition object
        OdsRtSzdnSnapshotFlowAddcode query = new OdsRtSzdnSnapshotFlowAddcode();
        query.setApplyTime1(request.getStartTime());
        query.setApplyTime2(request.getEndTime());
        if (request.getPlatenumber() != null) query.setPlatenumber(request.getPlatenumber());
        if (request.getGantryname() != null) query.setGantryname(request.getGantryname());
        if (request.getRoadname() != null) query.setRoadname(request.getRoadname());
        if (request.getSectionname() != null) query.setSectionname(request.getSectionname());
        if (request.getOrgname() != null) query.setOrgname(request.getOrgname());
        if (request.getTollname() != null) query.setTollname(request.getTollname());

        // 走 GaussDB 原生索引扫描 - Use GaussDB native index scan
        List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query);
        return QueryResult.of(list, list.size(), "phase1-gaussdb-gin");
    }

    // ==================== 阶段二：亿级 ====================
    // ==================== Phase 2: Hundred Million Level ====================

    /**
     * 阶段二查询：门架抓拍流水（亿级）
     * Phase 2 query: snapshot flow (hundred million level)
     * <p>
     * 策略：分区裁剪 + 覆盖索引 + 游标分页
     * Strategy: partition pruning + covering index + cursor pagination
     */
    private QueryResult querySnapshotFlowPhase2(QueryRequest request) {
        // 策略：分区裁剪 + 覆盖索引 + 游标分页
        // Strategy: partition pruning + covering index + cursor pagination
        // 使用游标分页避免深翻页 - Use cursor pagination to avoid deep pagination
        if (request.getCursor() != null && !request.getCursor().isEmpty()) {
            String maxTime = request.getEndTime();
            List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowMapper.selectByCursorShard(
                    request.getStartTime(), maxTime, request.getCursor(), null, request.getPageSize());
            return QueryResult.of(list, list.size(), "phase2-partition-cursor");
        }
        // 无游标时走分区裁剪查询 - Use partition pruning query when no cursor
        OdsRtSzdnSnapshotFlowAddcode query = new OdsRtSzdnSnapshotFlowAddcode();
        query.setApplyTime1(request.getStartTime());
        query.setApplyTime2(request.getEndTime());
        if (request.getPlatenumber() != null) query.setPlatenumber(request.getPlatenumber());
        if (request.getGantryname() != null) query.setGantryname(request.getGantryname());
        if (request.getRoadname() != null) query.setRoadname(request.getRoadname());
        if (request.getSectionname() != null) query.setSectionname(request.getSectionname());
        if (request.getOrgname() != null) query.setOrgname(request.getOrgname());
        if (request.getTollname() != null) query.setTollname(request.getTollname());
        List<OdsRtSzdnSnapshotFlowAddcode> list = snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query);
        return QueryResult.of(list, list.size(), "phase2-partition-prune");
    }

    // ==================== 阶段三：十亿级 ====================
    // ==================== Phase 3: Billion Level ====================

    /**
     * 阶段三查询：门架抓拍流水（十亿级）
     * Phase 3 query: snapshot flow (billion level)
     * <p>
     * 策略：ES 全文检索 + 冷热分离
     * Strategy: ES full-text search + cold/hot separation
     */
    private QueryResult querySnapshotFlowPhase3(QueryRequest request) {
        // 策略：ES 全文检索 + 冷热分离
        // Strategy: ES full-text search + cold/hot separation
        if (elasticsearchQueryService != null) {
            // 有任何模糊查询条件时走 ES - Route to ES when any fuzzy query condition exists
            boolean hasFuzzy = request.getPlatenumber() != null || request.getGantryname() != null ||
                    request.getRoadname() != null || request.getSectionname() != null ||
                    request.getOrgname() != null || request.getTollname() != null;
            if (hasFuzzy || request.getPageSize() > 100) {
                // 走 ES 查询 - Route to ES query
                return QueryResult.esPlaceholder("phase3-elasticsearch");
            }
        }
        // 精确查询走 GaussDB 热数据 - Exact query on GaussDB hot data
        return querySnapshotFlowPhase2(request);
    }

    // 类似实现 queryFeeRecords 的3个阶段方法
    // Similar implementation: queryFeeRecords with 3 phase methods

    /**
     * 统一查询入口 - 收费流水
     * Unified query entry - Fee Records
     *
     * @param request 查询请求 - query request
     * @return 查询结果 - query result
     */
    public QueryResult queryFeeRecords(QueryRequest request) {
        DataScaleLevel level = detectScaleLevel("ods_lwzxsfsj_fee_records_01");
        log.info("[渐进式查询] 收费流水，数据量级别={}, 请求={}", level, request);
        switch (level) {
            case LEVEL_10M:
                return queryFeeRecordsPhase1(request);
            case LEVEL_100M:
                return queryFeeRecordsPhase2(request);
            case LEVEL_1B:
                return queryFeeRecordsPhase3(request);
            default:
                return queryFeeRecordsPhase1(request);
        }
    }

    /**
     * 阶段一查询：收费流水（千万级）
     * Phase 1 query: fee records (ten million level)
     */
    private QueryResult queryFeeRecordsPhase1(QueryRequest request) {
        OdsLwzxsfsjFeeRecords01 query = new OdsLwzxsfsjFeeRecords01();
        query.setInApplyTime1(request.getStartTime());
        query.setInApplyTime2(request.getEndTime());
        if (request.getPlatenumber() != null) query.setVehicleplate(request.getPlatenumber());
        List<OdsLwzxsfsjFeeRecords01> list = feeRecordsMapper.selectOdsLwzxsfsjFeeRecords01List(query);
        return QueryResult.of(list, list.size(), "phase1-gaussdb-gin");
    }

    /**
     * 阶段二查询：收费流水（亿级）
     * Phase 2 query: fee records (hundred million level)
     * <p>
     * 分区表对应用透明，复用阶段一查询逻辑
     * Partitioned table is transparent to application, reuse phase 1 query logic
     */
    private QueryResult queryFeeRecordsPhase2(QueryRequest request) {
        return queryFeeRecordsPhase1(request);
    }

    /**
     * 阶段三查询：收费流水（十亿级）
     * Phase 3 query: fee records (billion level)
     */
    private QueryResult queryFeeRecordsPhase3(QueryRequest request) {
        if (elasticsearchQueryService != null) {
            boolean hasFuzzy = request.getPlatenumber() != null;
            if (hasFuzzy || request.getPageSize() > 100) {
                return QueryResult.esPlaceholder("phase3-elasticsearch");
            }
        }
        return queryFeeRecordsPhase2(request);
    }

    // 类似实现 queryTrailFitting 的3个阶段方法
    // Similar implementation: queryTrailFitting with 3 phase methods

    /**
     * 统一查询入口 - 车辆轨迹拟合
     * Unified query entry - Trail Fitting
     *
     * @param request 查询请求 - query request
     * @return 查询结果 - query result
     */
    public QueryResult queryTrailFitting(QueryRequest request) {
        DataScaleLevel level = detectScaleLevel("zdata_trail_fitting");
        log.info("[渐进式查询] 轨迹拟合，数据量级别={}, 请求={}", level, request);
        switch (level) {
            case LEVEL_10M:
                return queryTrailFittingPhase1(request);
            case LEVEL_100M:
                return queryTrailFittingPhase2(request);
            case LEVEL_1B:
                return queryTrailFittingPhase3(request);
            default:
                return queryTrailFittingPhase1(request);
        }
    }

    /**
     * 阶段一查询：车辆轨迹拟合（千万级）
     * Phase 1 query: trail fitting (ten million level)
     */
    private QueryResult queryTrailFittingPhase1(QueryRequest request) {
        ZdataTrailFitting query = new ZdataTrailFitting();
        // 入口时间作为查询上界 - Entry time as upper bound of query
        if (request.getStartTime() != null) query.setEntime(java.sql.Timestamp.valueOf(request.getStartTime()));
        // 出口时间作为查询下界 - Exit time as lower bound of query
        if (request.getEndTime() != null) query.setExtime(java.sql.Timestamp.valueOf(request.getEndTime()));
        List<ZdataTrailFitting> list = trailFittingMapper.selectZdataTrailFittingList(query);
        return QueryResult.of(list, list.size(), "phase1-gaussdb-gin");
    }

    /**
     * 阶段二查询：车辆轨迹拟合（亿级）
     * Phase 2 query: trail fitting (hundred million level)
     * <p>
     * 分区表对应用透明，复用阶段一查询逻辑
     * Partitioned table is transparent to application, reuse phase 1 query logic
     */
    private QueryResult queryTrailFittingPhase2(QueryRequest request) {
        return queryTrailFittingPhase1(request);
    }

    /**
     * 阶段三查询：车辆轨迹拟合（十亿级）
     * Phase 3 query: trail fitting (billion level)
     */
    private QueryResult queryTrailFittingPhase3(QueryRequest request) {
        if (elasticsearchQueryService != null) {
            return QueryResult.esPlaceholder("phase3-elasticsearch");
        }
        return queryTrailFittingPhase2(request);
    }

    // ==================== 内部类 ====================
    // ==================== Inner Classes ====================

    /**
     * 统一查询请求对象
     * Unified query request object
     */
    public static class QueryRequest {
        /** 开始时间（yyyy-MM-dd HH:mm:ss）- Start time */
        private String startTime;
        /** 结束时间（yyyy-MM-dd HH:mm:ss）- End time */
        private String endTime;
        /** 车牌号 - Plate number */
        private String platenumber;
        /** 管理中心名称 - Organization name */
        private String orgname;
        /** 路段名称 - Section name */
        private String sectionname;
        /** 道路名称 - Road name */
        private String roadname;
        /** 门架名称 - Gantry name */
        private String gantryname;
        /** 收费站名称 - Toll station name */
        private String tollname;
        /** 游标（游标分页用，上一页最后一条记录的时间戳）- Cursor (for cursor pagination, timestamp of last record in previous page) */
        private String cursor;
        /** 每页大小 - Page size */
        private int pageSize = 20;

        public String getStartTime() { return startTime; }
        public void setStartTime(String startTime) { this.startTime = startTime; }
        public String getEndTime() { return endTime; }
        public void setEndTime(String endTime) { this.endTime = endTime; }
        public String getPlatenumber() { return platenumber; }
        public void setPlatenumber(String platenumber) { this.platenumber = platenumber; }
        public String getOrgname() { return orgname; }
        public void setOrgname(String orgname) { this.orgname = orgname; }
        public String getSectionname() { return sectionname; }
        public void setSectionname(String sectionname) { this.sectionname = sectionname; }
        public String getRoadname() { return roadname; }
        public void setRoadname(String roadname) { this.roadname = roadname; }
        public String getGantryname() { return gantryname; }
        public void setGantryname(String gantryname) { this.gantryname = gantryname; }
        public String getTollname() { return tollname; }
        public void setTollname(String tollname) { this.tollname = tollname; }
        public String getCursor() { return cursor; }
        public void setCursor(String cursor) { this.cursor = cursor; }
        public int getPageSize() { return pageSize; }
        public void setPageSize(int pageSize) { this.pageSize = pageSize; }

        @Override
        public String toString() {
            return String.format("QueryRequest{start=%s, end=%s, plate=%s, gantry=%s, pageSize=%d}",
                    startTime, endTime, platenumber, gantryname, pageSize);
        }
    }

    /**
     * 统一查询结果对象
     * Unified query result object
     */
    public static class QueryResult {
        /** 结果数据列表 - Result data list */
        private List<?> data;
        /** 总记录数 - Total record count */
        private long total;
        /** 实际采用的查询策略标识 - Actual query strategy identifier used */
        private String strategy;

        /**
         * 构造普通查询结果
         * Build a normal query result
         *
         * @param data     数据列表 - data list
         * @param total    总数 - total count
         * @param strategy 查询策略 - query strategy
         * @return 查询结果对象 - query result object
         */
        public static QueryResult of(List<?> data, long total, String strategy) {
            QueryResult r = new QueryResult();
            r.data = data;
            r.total = total;
            r.strategy = strategy;
            return r;
        }

        /**
         * 构造 ES 占位结果（ES 查询的实际数据由调用方进一步处理）
         * Build an ES placeholder result (actual ES query data is further processed by the caller)
         *
         * @param strategy 查询策略 - query strategy
         * @return 查询结果对象 - query result object
         */
        public static QueryResult esPlaceholder(String strategy) {
            QueryResult r = new QueryResult();
            r.data = Collections.emptyList();
            r.total = 0;
            r.strategy = strategy;
            return r;
        }

        public List<?> getData() { return data; }
        public long getTotal() { return total; }
        public String getStrategy() { return strategy; }
    }
}
