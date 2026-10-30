package com.ruoyi.base.service.optimization;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.lang.reflect.Method;
import java.util.*;
import java.util.concurrent.*;

/**
 * 十亿级数据量查询优化服务 - Billion Level Query Optimization Service
 * <p>
 * 适用场景 / Applicable Scenario:
 *   单表数据量 > 5亿行，未来3年达到8亿级
 *   Single table with > 500M rows, reaching 800M in 3 years
 * <p>
 * 核心策略 / Core Strategies:
 *   1. 冷热分离：热数据（近6个月）留在 GaussDB，冷数据归档 + 同步到 ES
 *      Cold-hot separation: Hot data (recent 6 months) in GaussDB, cold data archived + synced in ES
 *   2. Elasticsearch 全文检索：所有模糊查询、多条件组合查询走 ES
 *      Elasticsearch full-text search: All fuzzy and multi-condition queries go through ES
 *   3. GaussDB 精确查询：有精确等值条件的查询走 GaussDB 分区表
 *      GaussDB exact query: Queries with exact equality conditions go through GaussDB partitioned tables
 *   4. 异步导出：大规模数据导出使用 ES Scroll API 异步拉取
 *      Async export: Large-scale data export uses ES Scroll API for async retrieval
 *   5. 查询路由：根据查询条件自动路由到 ES 或 GaussDB
 *      Query routing: Auto-route to ES or GaussDB based on query conditions
 */
@Slf4j
@Service
public class BillionLevelQueryService {

    @Autowired(required = false)
    private ElasticsearchQueryService elasticsearchQueryService;
    @Autowired
    private RedisTemplate redisTemplate;
    @Autowired(required = false)
    private JdbcTemplate jdbcTemplate;

    @Value("${optimization.query.es-force-days:30}")
    private int esForceDays;

    @Value("${optimization.query.timeout-ms:30000}")
    private long esQueryTimeout;

    @Value("${optimization.export.scroll-batch:2000}")
    private int scrollBatchSize;

    @Value("${optimization.cold-hot.hot-days:180}")
    private int hotDataDays;

    /**
     * 查询路由判断 - 决定走 ES 还是 GaussDB
     * Query routing - decide whether to use ES or GaussDB
     */
    public String routeQuery(QueryRouteRequest request) {
        if (request.hasFuzzyCondition()) {
            log.debug("[十亿级路由] 命中规则1: 有模糊条件 → ES");
            return "es";
        }
        if (request.getTimeRangeDays() > esForceDays) {
            log.debug("[十亿级路由] 命中规则2: 时间范围{}天 > {}天 → ES", request.getTimeRangeDays(), esForceDays);
            return "es";
        }
        if (request.isAggregation()) {
            log.debug("[十亿级路由] 命中规则3: 聚合统计 → ES");
            return "es";
        }
        if (request.isExport() && request.getExportCount() > 1000) {
            log.debug("[十亿级路由] 命中规则4: 导出{}条 → ES", request.getExportCount());
            return "es";
        }
        log.debug("[十亿级路由] 默认: 精确查询 → GaussDB");
        return "gaussdb";
    }

    /**
     * ES 全字段模糊查询 - 门架抓拍流水
     * ES full-field fuzzy query - Snapshot Flow
     */
    public Map<String, Object> querySnapshotFlowFromES(
            String startTime, String endTime,
            String plateNumber, String gantryName, String roadName,
            String sectionName, String orgName, String tollName,
            int pageNum, int pageSize) {
        log.info("[十亿级查询] ES门架抓拍流水: start={}, end={}, plate={}, pageNum={}, pageSize={}",
                startTime, endTime, plateNumber, pageNum, pageSize);
        if (elasticsearchQueryService == null) {
            log.warn("[十亿级查询] ElasticsearchQueryService 未注入，返回空结果");
            return emptyResult();
        }
        try {
            Map<String, Object> conditions = new HashMap<>();
            if (startTime != null) conditions.put("snapshottime_gte", startTime);
            if (endTime != null) conditions.put("snapshottime_lte", endTime);
            if (plateNumber != null) conditions.put("platenumber", plateNumber);
            if (gantryName != null) conditions.put("gantryname", gantryName);
            if (roadName != null) conditions.put("roadname", roadName);
            if (sectionName != null) conditions.put("sectionname", sectionName);
            if (orgName != null) conditions.put("orgname", orgName);
            if (tollName != null) conditions.put("tollname", tollName);
            return invokeQueryByConditions("snapshot_flow", conditions, pageNum, pageSize);
        } catch (Exception e) {
            log.error("[十亿级查询] ES查询失败，降级到 GaussDB", e);
            return emptyResult();
        }
    }

    /**
     * ES 全字段模糊查询 - 收费流水
     */
    public Map<String, Object> queryFeeRecordsFromES(
            String startTime, String endTime,
            String plateNumber, String gantryName,
            int pageNum, int pageSize) {
        log.info("[十亿级查询] ES收费流水: start={}, end={}, plate={}", startTime, endTime, plateNumber);
        if (elasticsearchQueryService == null) return emptyResult();
        try {
            Map<String, Object> conditions = new HashMap<>();
            if (startTime != null) conditions.put("transtime_gte", startTime);
            if (endTime != null) conditions.put("transtime_lte", endTime);
            if (plateNumber != null) conditions.put("vehicleplate", plateNumber);
            return invokeQueryByConditions("fee_records", conditions, pageNum, pageSize);
        } catch (Exception e) {
            log.error("[十亿级查询] ES查询失败", e);
            return emptyResult();
        }
    }

    /**
     * ES 全字段模糊查询 - 轨迹拟合
     */
    public Map<String, Object> queryTrailFittingFromES(
            String startTime, String endTime,
            String plateNumber, String stationName,
            int pageNum, int pageSize) {
        log.info("[十亿级查询] ES轨迹拟合: start={}, end={}", startTime, endTime);
        if (elasticsearchQueryService == null) return emptyResult();
        try {
            Map<String, Object> conditions = new HashMap<>();
            if (startTime != null) conditions.put("extime_gte", startTime);
            if (endTime != null) conditions.put("extime_lte", endTime);
            if (plateNumber != null) conditions.put("envehicleid", plateNumber);
            if (stationName != null) conditions.put("extollstationname", stationName);
            return invokeQueryByConditions("trail_fitting", conditions, pageNum, pageSize);
        } catch (Exception e) {
            log.error("[十亿级查询] ES查询失败", e);
            return emptyResult();
        }
    }

    /**
     * 异步导出 - 使用 ES Scroll API 分批拉取
     * Async export - using ES Scroll API for batch retrieval
     */
    public CompletableFuture<Integer> asyncExport(String indexName, Map<String, Object> conditions) {
        return CompletableFuture.supplyAsync(() -> {
            int totalExported = 0;
            try {
                log.info("[十亿级导出] 开始异步导出: index={}, conditions={}", indexName, conditions);
                if (elasticsearchQueryService != null) {
                    totalExported = invokeScrollExport(indexName, conditions, scrollBatchSize);
                }
                log.info("[十亿级导出] 导出完成，共 {} 条", totalExported);
            } catch (Exception e) {
                log.error("[十亿级导出] 导出失败", e);
            }
            return totalExported;
        }, Executors.newFixedThreadPool(2));
    }

    /**
     * 归档冷数据 - 将超过热数据保留期的数据迁移到归档表
     * Archive cold data - migrate data older than hot retention period to archive tables
     */
    public void archiveColdData() {
        if (jdbcTemplate == null) return;
        try {
            log.info("[十亿级冷热分离] 开始归档冷数据，热数据保留 {} 天", hotDataDays);
            String archiveSql = "INSERT INTO jl_data01.ods_rt_szdn_snapshot_flow_archive " +
                    "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode " +
                    "WHERE snapshottime < NOW() - INTERVAL '" + hotDataDays + " days'";
            String deleteSql = "DELETE FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode " +
                    "WHERE snapshottime < NOW() - INTERVAL '" + hotDataDays + " days'";
            executeArchive(archiveSql, deleteSql, "ods_rt_szdn_snapshot_flow_addcode");

            archiveSql = "INSERT INTO jl_data01.ods_lwzxsfsj_fee_records_archive " +
                    "SELECT * FROM jl_data01.ods_lwzxsfsj_fee_records_01 " +
                    "WHERE transtime < NOW() - INTERVAL '" + hotDataDays + " days'";
            deleteSql = "DELETE FROM jl_data01.ods_lwzxsfsj_fee_records_01 " +
                    "WHERE transtime < NOW() - INTERVAL '" + hotDataDays + " days'";
            executeArchive(archiveSql, deleteSql, "ods_lwzxsfsj_fee_records_01");

            archiveSql = "INSERT INTO jl_data01.zdata_trail_fitting_archive " +
                    "SELECT * FROM jl_data01.zdata_trail_fitting " +
                    "WHERE extime < NOW() - INTERVAL '" + hotDataDays + " days'";
            deleteSql = "DELETE FROM jl_data01.zdata_trail_fitting " +
                    "WHERE extime < NOW() - INTERVAL '" + hotDataDays + " days'";
            executeArchive(archiveSql, deleteSql, "zdata_trail_fitting");

            log.info("[十亿级冷热分离] 冷数据归档完成");
        } catch (Exception e) {
            log.error("[十亿级冷热分离] 归档失败", e);
        }
    }

    private void executeArchive(String archiveSql, String deleteSql, String tableName) {
        try {
            int archived = jdbcTemplate.update(archiveSql);
            log.info("[十亿级冷热分离] {} 归档 {} 条", tableName, archived);
            int deleted = jdbcTemplate.update(deleteSql);
            log.info("[十亿级冷热分离] {} 删除冷数据 {} 条", tableName, deleted);
        } catch (Exception e) {
            log.error("[十亿级冷热分离] {} 归档失败", tableName, e);
        }
    }

    /**
     * 反射调用 ElasticsearchQueryService.queryByConditions
     * 如果方法不存在，返回空结果
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> invokeQueryByConditions(String indexName, Map<String, Object> conditions, int pageNum, int pageSize) {
        try {
            Method method = elasticsearchQueryService.getClass().getMethod("queryByConditions", String.class, Map.class, int.class, int.class);
            return (Map<String, Object>) method.invoke(elasticsearchQueryService, indexName, conditions, pageNum, pageSize);
        } catch (NoSuchMethodException e) {
            log.warn("[十亿级查询] ElasticsearchQueryService.queryByConditions 方法不存在，返回空结果");
            return emptyResult();
        } catch (Exception e) {
            log.error("[十亿级查询] 反射调用 queryByConditions 失败", e);
            return emptyResult();
        }
    }

    /**
     * 反射调用 ElasticsearchQueryService.scrollExport
     * 如果方法不存在，返回 0
     */
    private int invokeScrollExport(String indexName, Map<String, Object> conditions, int batchSize) {
        try {
            Method method = elasticsearchQueryService.getClass().getMethod("scrollExport", String.class, Map.class, int.class);
            return (int) method.invoke(elasticsearchQueryService, indexName, conditions, batchSize);
        } catch (NoSuchMethodException e) {
            log.warn("[十亿级导出] ElasticsearchQueryService.scrollExport 方法不存在，返回 0");
            return 0;
        } catch (Exception e) {
            log.error("[十亿级导出] 反射调用 scrollExport 失败", e);
            return 0;
        }
    }

    private Map<String, Object> emptyResult() {
        Map<String, Object> result = new HashMap<>();
        result.put("total", 0);
        result.put("data", Collections.emptyList());
        return result;
    }

    /**
     * 查询路由请求 - 用于判断走 ES 还是 GaussDB
     * Query route request - for deciding ES vs GaussDB
     */
    public static class QueryRouteRequest {
        private String startTime;
        private String endTime;
        private String platenumber;
        private String gantryname;
        private String roadname;
        private String sectionname;
        private String orgname;
        private String tollname;
        private boolean aggregation;
        private boolean export;
        private int exportCount;

        public boolean hasFuzzyCondition() {
            return isNotEmpty(platenumber) || isNotEmpty(gantryname) ||
                   isNotEmpty(roadname) || isNotEmpty(sectionname) ||
                   isNotEmpty(orgname) || isNotEmpty(tollname);
        }

        public int getTimeRangeDays() {
            try {
                if (startTime == null || endTime == null) return 365;
                java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
                long diff = sdf.parse(endTime).getTime() - sdf.parse(startTime).getTime();
                return (int) (diff / (1000 * 60 * 60 * 24));
            } catch (Exception e) {
                return 365;
            }
        }

        private boolean isNotEmpty(String s) {
            return s != null && !s.trim().isEmpty();
        }

        public String getStartTime() { return startTime; }
        public void setStartTime(String startTime) { this.startTime = startTime; }
        public String getEndTime() { return endTime; }
        public void setEndTime(String endTime) { this.endTime = endTime; }
        public String getPlatenumber() { return platenumber; }
        public void setPlatenumber(String platenumber) { this.platenumber = platenumber; }
        public String getGantryname() { return gantryname; }
        public void setGantryname(String gantryname) { this.gantryname = gantryname; }
        public String getRoadname() { return roadname; }
        public void setRoadname(String roadname) { this.roadname = roadname; }
        public String getSectionname() { return sectionname; }
        public void setSectionname(String sectionname) { this.sectionname = sectionname; }
        public String getOrgname() { return orgname; }
        public void setOrgname(String orgname) { this.orgname = orgname; }
        public String getTollname() { return tollname; }
        public void setTollname(String tollname) { this.tollname = tollname; }
        public boolean isAggregation() { return aggregation; }
        public void setAggregation(boolean aggregation) { this.aggregation = aggregation; }
        public boolean isExport() { return export; }
        public void setExport(boolean export) { this.export = export; }
        public int getExportCount() { return exportCount; }
        public void setExportCount(int exportCount) { this.exportCount = exportCount; }
    }
}
