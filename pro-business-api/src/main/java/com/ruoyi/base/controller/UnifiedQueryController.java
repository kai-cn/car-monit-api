package com.ruoyi.base.controller;

import com.ruoyi.base.service.optimization.UnifiedExportService;
import com.ruoyi.base.service.optimization.UnifiedQueryService;
import com.ruoyi.base.service.optimization.UnifiedQueryService.DataSource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 统一大表查询/导出 Controller
 *
 * =================================================================
 * 设计目标：
 *   为 3 张 8 亿级大表（门架抓拍 / 收费流水 / 车辆轨迹）提供
 *   一致的"全字段模糊 + 时间范围 + 分页 / 异步导出"HTTP 入口。
 *
 * 路由异常时由 UnifiedQueryService 自动降级到 MySQL，
 * 调用方无需关注底层是 ES 还是 DB。
 *
 * 接口规范：
 *   GET  /api/v1/unified/{ds}/list       分页列表查询
 *   POST /api/v1/unified/{ds}/export/submit   提交异步导出任务
 *   GET  /api/v1/unified/export/status/{taskId}  查询导出状态
 *
 * {ds} 取值：
 *   snapshot  -> 门架抓拍流水 (ods_rt_szdn_snapshot_flow_addcode)
 *   fee       -> 收费流水 (ods_lwzxsfsj_fee_records_01)
 *   trail     -> 车辆历史轨迹 (zdata_trail_fitting)
 *
 * 模糊查询参数格式：
 *   GET  /api/v1/unified/snapshot/list?startTime=2026-05-01 00:00:00
 *                                      &endTime=2026-05-31 23:59:59
 *                                      &fuzzyFields.platenumber=赣A1
 *                                      &fuzzyFields.gantryname=长安
 *                                      &pageNum=1&pageSize=20
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/unified")
public class UnifiedQueryController {

    @Autowired
    private UnifiedQueryService queryService;

    @Autowired
    private UnifiedExportService exportService;

    // ================================================================
    // 模块1：分页列表查询
    // ================================================================

    /**
     * 通用大表分页查询接口
     *
     * 注意：
     *   1. fuzzyFields.* 是 Spring 自动注入的多值参数，需手动提取过滤
     *   2. 若 from + size 超过 ES max_result_window，会抛异常引导使用导出接口
     */
    @GetMapping("/{ds}/list")
    public Map<String, Object> list(
            @PathVariable String ds,
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(required = false) Map<String, String> fuzzyFields,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {

        Map<String, Object> result = new LinkedHashMap<>();
        try {
            DataSource source = parseDataSource(ds);
            Map<String, String> fields = extractFuzzyFields(fuzzyFields);

            List<?> data = queryService.query(source, startTime, endTime, fields, pageNum, pageSize);

            result.put("code", 200);
            result.put("message", "ok");
            result.put("dataSource", ds);
            result.put("pageNum", pageNum);
            result.put("pageSize", pageSize);
            result.put("data", data);
        } catch (IllegalArgumentException e) {
            result.put("code", 400);
            result.put("message", e.getMessage());
        } catch (Exception e) {
            log.error("[统一查询] 异常 ds={}", ds, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    // ================================================================
    // 模块2：大数据量异步导出
    // ================================================================

    /**
     * 提交异步导出任务（解决单次导出 >100 万条 OOM 问题）
     *
     * 调用方：
     *   1. POST 提交获取 taskId
     *   2. 前端轮询 GET /api/v1/unified/export/status/{taskId}
     *   3. 完成后从 status.filePaths 拿到可下载的 CSV 文件列表
     *
     * Body 形式（JSON）：
     *   { "platenumber": "赣A", "gantryname": "长安" }
     */
    @PostMapping("/{ds}/export/submit")
    public Map<String, Object> submitExport(
            @PathVariable String ds,
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestBody(required = false) Map<String, String> fuzzyFields) {

        Map<String, Object> result = new LinkedHashMap<>();
        try {
            DataSource source = parseDataSource(ds);
            String taskId = exportService.submitExportTask(source, startTime, endTime, fuzzyFields);

            result.put("code", 200);
            result.put("message", "导出任务已提交, 请用 taskId 轮询状态");
            result.put("taskId", taskId);
        } catch (IllegalArgumentException e) {
            result.put("code", 400);
            result.put("message", e.getMessage());
        } catch (Exception e) {
            log.error("[统一导出] 提交异常 ds={}", ds, e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 查询导出任务状态
     */
    @GetMapping("/export/status/{taskId}")
    public Map<String, Object> getExportStatus(@PathVariable String taskId) {
        Map<String, Object> result = new LinkedHashMap<>();
        UnifiedExportService.ExportTaskStatus status = exportService.getExportStatus(taskId);
        if (status == null) {
            result.put("code", 404);
            result.put("message", "task not found");
            return result;
        }
        result.put("code", 200);
        result.put("status", status.status);
        result.put("totalExported", status.totalExported);
        result.put("filePartCount", status.filePartCount);
        result.put("submitTime", status.submitTime);
        if ("COMPLETED".equals(status.status)) {
            result.put("endTime", status.finishTime);
            result.put("filePaths", status.filePaths);
            long costSec = (status.finishTime - status.submitTime) / 1000;
            result.put("costSeconds", costSec);
        } else if ("FAILED".equals(status.status)) {
            result.put("errorMessage", status.errorMessage);
        }
        return result;
    }

    // ================================================================
    // 私有辅助
    // ================================================================

    /** 字符串 -> DataSource 枚举，校验非法输入 */
    private DataSource parseDataSource(String ds) {
        if (ds == null) throw new IllegalArgumentException("数据源 {ds} 不能为空");
        switch (ds.toLowerCase()) {
            case "snapshot": return DataSource.SNAPSHOT;
            case "fee":      return DataSource.FEE;
            case "trail":    return DataSource.TRAIL;
            default: throw new IllegalArgumentException("未知数据源: " + ds
                    + ", 合法取值: snapshot / fee / trail");
        }
    }

    /** 从 Spring 注入的 Map 中提取 fuzzyFields.* 前缀的参数 */
    private Map<String, String> extractFuzzyFields(Map<String, String> raw) {
        Map<String, String> result = new HashMap<>();
        if (raw == null) return result;
        for (Map.Entry<String, String> e : raw.entrySet()) {
            String key = e.getKey();
            String value = e.getValue();
            if (key.startsWith("fuzzyFields.") && value != null && !value.isEmpty()) {
                result.put(key.substring("fuzzyFields.".length()), value);
            }
        }
        return result;
    }
}
