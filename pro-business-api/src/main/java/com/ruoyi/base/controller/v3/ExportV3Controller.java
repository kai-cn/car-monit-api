package com.ruoyi.base.controller.v3;

import com.ruoyi.base.service.v3.export.ExportRequest;
import com.ruoyi.base.service.v3.export.ExportTask;
import com.ruoyi.base.service.v3.export.ExportTaskService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * V3 导出接口骨架。
 *
 * <p>POST /api/v3/export/display：展示字段（ES PIT）；
 * POST /api/v3/export/full：全字段（GaussDB 游标）。均异步返回 taskId，
 * 前端轮询 /status/{taskId}。对象存储/签名下载在后续阶段接入。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v3/export")
public class ExportV3Controller {

    private final ExportTaskService exportTaskService;

    public ExportV3Controller(ExportTaskService exportTaskService) {
        this.exportTaskService = exportTaskService;
    }

    /**
     * 导出能力探测：返回模式、各表可过滤维度、展示字段白名单与多值支持，
     * backend 据此放开全字段维度过滤/plate_color_name，不再硬编码判断。
     */
    @GetMapping("/capabilities")
    public Map<String, Object> capabilities() {
        return exportTaskService.capabilities();
    }

    @PostMapping("/display")
    public Map<String, Object> submitDisplay(@RequestBody ExportRequest request) {
        return submit(request, true);
    }

    @PostMapping("/full")
    public Map<String, Object> submitFull(@RequestBody ExportRequest request) {
        return submit(request, false);
    }

    private Map<String, Object> submit(ExportRequest request, boolean display) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            ExportTask task = display
                    ? exportTaskService.submitDisplay(request)
                    : exportTaskService.submitFull(request);
            result.put("code", 200);
            result.put("message", "导出任务已提交");
            result.put("data", task);
        } catch (Exception e) {
            log.error("[V3导出] 提交失败", e);
            result.put("code", 400);
            result.put("message", e.getMessage());
        }
        return result;
    }

    @GetMapping("/status/{taskId}")
    public Map<String, Object> status(@PathVariable String taskId) {
        Map<String, Object> result = new LinkedHashMap<>();
        ExportTask task = exportTaskService.get(taskId);
        if (task == null) {
            result.put("code", 404);
            result.put("message", "task not found");
            return result;
        }
        result.put("code", 200);
        result.put("data", task);
        return result;
    }

    @PostMapping("/cancel/{taskId}")
    public Map<String, Object> cancel(@PathVariable String taskId) {
        Map<String, Object> result = new LinkedHashMap<>();
        boolean ok = exportTaskService.cancel(taskId);
        result.put("code", ok ? 200 : 404);
        result.put("message", ok ? "已请求取消" : "task not found");
        return result;
    }
}
