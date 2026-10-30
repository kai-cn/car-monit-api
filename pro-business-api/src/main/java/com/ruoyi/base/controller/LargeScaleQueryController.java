package com.ruoyi.base.controller;

import com.ruoyi.base.service.optimization.LargeScaleDataSyncService;
import com.ruoyi.base.service.optimization.LargeScaleQueryService;
import com.ruoyi.base.service.optimization.UnifiedQueryService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 大规模数据查询与统计接口 - 面向 8 亿条数据场景（三表统一）
 * Large-scale query & stats controller for the 800M-row scenario (3 tables unified).
 *
 * =================================================================
 * 统一路由架构 / Unified routing architecture:
 *   【前端】--HTTP-->【本 Controller】--统一路由--> UnifiedQueryService
 *                                                  |-- 模糊/统计/超30天/FEE/TRAIL --> Elasticsearch
 *                                                  |-- 小范围精确 -------------------> GaussDB
 *   数据同步：GaussDB --> LargeScaleDataSyncService --> Elasticsearch（双写/增量/补同步）
 *   一致性：GaussEsConsistencyService 定时对账 GaussDB 与 ES 并触发修复
 *
 * 三表接口 / Three tables:
 *   - /snapshot         门架抓拍流水   ods_rt_szdn_snapshot_flow_addcode   时间字段 snapshottime
 *   - /fee              收费流水       ods_lwzxsfsj_fee_records_01        时间字段 transtime
 *   - /trail            车辆轨迹       zdata_trail_fitting                时间字段 extime
 *   - /carTrackQueryByCarNo  按车牌查历史轨迹（platenumber -> envehicleid）
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/large")
public class LargeScaleQueryController {

    @Autowired
    private UnifiedQueryService unifiedQueryService;

    @Autowired
    private LargeScaleQueryService largeScaleQueryService;

    @Autowired
    private LargeScaleDataSyncService syncService;

    // ================================================================
    // 模块1：三表全字段模糊查询 / Module 1: fuzzy query for 3 tables
    // ================================================================

    /**
     * 门架抓拍流水 - 全字段模糊查询（默认路由到 ES）
     * Snapshot flow fuzzy query (routed to ES by default).
     */
    @GetMapping("/snapshot")
    public Map<String, Object> querySnapshotFlow(
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(required = false) Map<String, String> fuzzyFields,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return queryByDs(UnifiedQueryService.DataSource.SNAPSHOT, startTime, endTime, fuzzyFields, pageNum, pageSize);
    }

    /**
     * 收费流水 - 全字段模糊查询（真实接入，路由到 ES）
     * Fee records fuzzy query (wired to ES via unified routing).
     */
    @GetMapping("/fee")
    public Map<String, Object> queryFeeRecords(
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(required = false) Map<String, String> fuzzyFields,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return queryByDs(UnifiedQueryService.DataSource.FEE, startTime, endTime, fuzzyFields, pageNum, pageSize);
    }

    /**
     * 车辆历史轨迹 - 全字段模糊查询（真实接入，路由到 ES）
     * Vehicle trail fuzzy query (wired to ES via unified routing).
     */
    @GetMapping("/trail")
    public Map<String, Object> queryTrail(
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(required = false) Map<String, String> fuzzyFields,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return queryByDs(UnifiedQueryService.DataSource.TRAIL, startTime, endTime, fuzzyFields, pageNum, pageSize);
    }

    /**
     * 按车牌号查询车辆历史轨迹（需求接口 /carTrackQueryByCarNo）
     * Query vehicle trail by plate number (required API /carTrackQueryByCarNo).
     *
     * 思路：将入参 carNo 映射为逻辑字段 platenumber，由统一路由翻译为轨迹表物理字段 envehicleid
     * Map carNo -> logical platenumber; UnifiedQueryService translates to physical envehicleid.
     */
    @GetMapping("/carTrackQueryByCarNo")
    public Map<String, Object> queryCarTrackByCarNo(
            @RequestParam String carNo,
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {

        Map<String, String> fuzzy = new LinkedHashMap<>();
        if (carNo != null && !carNo.isEmpty()) {
            fuzzy.put("platenumber", carNo);
        }
        return queryByDs(UnifiedQueryService.DataSource.TRAIL, startTime, endTime, fuzzy, pageNum, pageSize);
    }

    /**
     * 统一查询入口封装：抽取 fuzzyFields、调用统一路由、包装返回
     * Shared query entry: extract fuzzy fields, call unified routing, wrap response.
     */
    private Map<String, Object> queryByDs(UnifiedQueryService.DataSource ds,
                                          String startTime, String endTime,
                                          Map<String, String> fuzzyFields,
                                          int pageNum, int pageSize) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            Map<String, String> fields = extractFuzzyFields(fuzzyFields);
            List<?> list = unifiedQueryService.query(ds, startTime, endTime, fields, pageNum, pageSize);
            result.put("code", 200);
            result.put("message", "ok");
            result.put("dataSource", ds.name());
            result.put("pageNum", pageNum);
            result.put("pageSize", pageSize);
            result.put("data", list);
        } catch (Exception e) {
            log.error("[查询接口] 异常 ds={}", ds, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 从 Spring 注入的 Map 中提取 fuzzyFields.xxx 形式的字段
     * Extract fields of the form fuzzyFields.xxx from the injected map.
     */
    private Map<String, String> extractFuzzyFields(Map<String, String> fuzzyFields) {
        Map<String, String> fields = new HashMap<>();
        if (fuzzyFields != null) {
            for (Map.Entry<String, String> e : fuzzyFields.entrySet()) {
                if (e.getKey().startsWith("fuzzyFields.") && e.getValue() != null && !e.getValue().isEmpty()) {
                    fields.put(e.getKey().substring("fuzzyFields.".length()), e.getValue());
                }
            }
        }
        return fields;
    }

    // ================================================================
    // 模块2：统计接口（ES aggregation，三表，type 参数）
    // ================================================================

    /**
     * 按维度分组 Top-N 统计（type: snapshot/fee/trail，默认 snapshot）
     * Group-by Top-N aggregation (type selects table).
     */
    @GetMapping("/stats/group")
    public Map<String, Object> groupByStats(
            @RequestParam(defaultValue = "snapshot") String type,
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam String groupBy,
            @RequestParam(required = false) String countField,
            @RequestParam(required = false) Map<String, String> fuzzyFields,
            @RequestParam(defaultValue = "100") int topN) {

        Map<String, Object> result = new LinkedHashMap<>();
        try {
            Map<String, String> fields = extractFuzzyFields(fuzzyFields);
            Map<String, Long> stats = largeScaleQueryService.aggregationStats(
                    type, startTime, endTime, groupBy, countField, fields, topN);
            result.put("code", 200);
            result.put("message", "ok");
            result.put("type", type);
            result.put("groupBy", groupBy);
            result.put("topN", topN);
            result.put("data", stats);
        } catch (Exception e) {
            log.error("[统计接口] 异常 type={}", type, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    // ================================================================
    // 模块3：大数据导出接口（异步任务，三表，type 参数）
    // ================================================================

    /**
     * 提交导出任务（type: snapshot/fee/trail，默认 snapshot）
     * Submit export task (type selects table).
     */
    @PostMapping("/export/submit")
    public Map<String, Object> submitExport(
            @RequestParam(defaultValue = "snapshot") String type,
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestBody(required = false) Map<String, String> fuzzyFields) {

        Map<String, Object> result = new LinkedHashMap<>();
        try {
            Map<String, String> fields = extractFuzzyFields(fuzzyFields);
            String taskId = largeScaleQueryService.submitExportTask(type, startTime, endTime, fields);
            result.put("code", 200);
            result.put("message", "导出任务已提交");
            result.put("type", type);
            result.put("taskId", taskId);
        } catch (Exception e) {
            log.error("[导出-提交] 异常 type={}", type, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 查询导出任务状态 / Get export task status.
     */
    @GetMapping("/export/status/{taskId}")
    public Map<String, Object> getExportStatus(@PathVariable String taskId) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            LargeScaleQueryService.ExportTaskStatus status = largeScaleQueryService.getExportStatus(taskId);
            if (status == null) {
                result.put("code", 404);
                result.put("message", "task not found");
            } else {
                result.put("code", 200);
                result.put("status", status.status);
                result.put("totalExported", status.totalExported);
                result.put("filePartCount", status.filePartCount);
                result.put("submitTime", status.submitTime);
                result.put("endTime", status.endTime);
            }
        } catch (Exception e) {
            log.error("[导出-查询] 异常", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    // ================================================================
    // 模块4：数据同步运维接口（三表）
    // ================================================================

    /** 触发全量同步（最近一年，三表） / Full sync (3 tables). */
    @PostMapping("/sync/full")
    public Map<String, Object> triggerFullSync() {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            new Thread(() -> syncService.fullSyncOneYear()).start();
            result.put("code", 200);
            result.put("message", "全量同步任务已在后台启动（三表），预计耗时较长");
        } catch (Exception e) {
            log.error("[同步-全量] 异常", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /** 触发增量同步（手动；日常由定时任务执行） / Incremental sync (manual). */
    @PostMapping("/sync/incremental")
    public Map<String, Object> triggerIncrementalSync() {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            syncService.incrementalSync();
            result.put("code", 200);
            result.put("message", "增量同步完成（三表，基于 Redis 水位）");
        } catch (Exception e) {
            log.error("[同步-增量] 异常", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 补同步 - 重放指定数据源与时间窗（以 GaussDB 为准回灌 ES）
     * Repair sync: replay a data source + window (GaussDB is source of truth).
     */
    @PostMapping("/sync/repair")
    public Map<String, Object> triggerRepairSync(
            @RequestParam(defaultValue = "snapshot") String type,
            @RequestParam String startTime,
            @RequestParam String endTime) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            UnifiedQueryService.DataSource ds = resolveDs(type);
            UnifiedQueryService.DataSource finalDs = ds;
            new Thread(() -> syncService.repairSync(finalDs, startTime, endTime)).start();
            result.put("code", 200);
            result.put("message", "补同步任务已在后台启动 type=" + type);
        } catch (Exception e) {
            log.error("[同步-补录] 异常 type={}", type, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /** type 字符串 -> 数据源枚举 / map type string to DataSource enum. */
    private UnifiedQueryService.DataSource resolveDs(String type) {
        if (type == null) return UnifiedQueryService.DataSource.SNAPSHOT;
        switch (type.toLowerCase()) {
            case "fee":   return UnifiedQueryService.DataSource.FEE;
            case "trail": return UnifiedQueryService.DataSource.TRAIL;
            default:      return UnifiedQueryService.DataSource.SNAPSHOT;
        }
    }
}
