package com.ruoyi.base.agent.tools;

import com.ruoyi.base.agent.config.AgentProperties;
import com.ruoyi.base.agent.core.AgentConfirmationService;
import com.ruoyi.base.agent.core.AgentErrorCode;
import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.KnowledgeBase;
import com.ruoyi.base.domain.TrailBo;
import com.ruoyi.base.service.ISysUtilService;
import com.ruoyi.base.service.impl.DataLossDetectionService;
import com.ruoyi.base.service.v3.bigscreen.BigScreenStatVo;
import com.ruoyi.base.service.v3.bigscreen.BigScreenStatsService;
import com.ruoyi.base.service.v3.export.ExportRequest;
import com.ruoyi.base.service.v3.export.ExportTask;
import com.ruoyi.base.service.v3.export.ExportTaskService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficSearchRequest;
import com.ruoyi.base.service.v3.query.TrafficSearchResult;
import com.ruoyi.base.service.v3.query.TrafficSearchService;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import com.ruoyi.base.service.v3.query.TrailPointLoader;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 工具执行层：把模型意图落到既有 Service 上。
 *
 * <p>所有方法返回结构化 Map（ok/errorCode/message/data），不向模型抛异常堆栈；
 * 所有入参在这里二次校验，框架适配层只负责协议转换。</p>
 */
@Slf4j
@Service
public class AgentToolService {

    private static final Duration QUERY_MAX_WINDOW = Duration.ofDays(31);
    private static final Duration QUERY_DEFAULT_WINDOW = Duration.ofDays(7);
    private static final Duration TRACK_MAX_WINDOW = Duration.ofHours(24);
    private static final Duration TRACK_DEFAULT_WINDOW = Duration.ofHours(6);
    private static final Duration QUALITY_MAX_WINDOW = Duration.ofHours(24);
    private static final int MAX_ROWS_TO_MODEL = 20;

    private final TrafficSearchService trafficSearchService;
    private final TrailPointLoader trailPointLoader;
    private final BigScreenStatsService bigScreenStatsService;
    private final ExportTaskService exportTaskService;
    private final DataLossDetectionService dataLossDetectionService;
    private final ISysUtilService sysUtilService;
    private final KnowledgeBase knowledgeBase;
    private final AgentConfirmationService confirmationService;
    private final AgentProperties properties;

    public AgentToolService(TrafficSearchService trafficSearchService,
                            TrailPointLoader trailPointLoader,
                            BigScreenStatsService bigScreenStatsService,
                            ExportTaskService exportTaskService,
                            DataLossDetectionService dataLossDetectionService,
                            ISysUtilService sysUtilService,
                            KnowledgeBase knowledgeBase,
                            AgentConfirmationService confirmationService,
                            AgentProperties properties) {
        this.trafficSearchService = trafficSearchService;
        this.trailPointLoader = trailPointLoader;
        this.bigScreenStatsService = bigScreenStatsService;
        this.exportTaskService = exportTaskService;
        this.dataLossDetectionService = dataLossDetectionService;
        this.sysUtilService = sysUtilService;
        this.knowledgeBase = knowledgeBase;
        this.confirmationService = confirmationService;
        this.properties = properties;
    }

    // ------------------------------------------------------------------
    // query_traffic_records
    // ------------------------------------------------------------------
    public Map<String, Object> queryTraffic(AgentPrincipal principal, Map<String, Object> args) {
        try {
            TrafficTable table = TrafficTable.fromParam(str(args, "table", "snapshot"));
            long end = orNow(parse(args, "end_time", true));
            long start = orDefault(parse(args, "start_time", false), end - QUERY_DEFAULT_WINDOW.toMillis());
            ToolSupport.validateWindow(start, end, QUERY_MAX_WINDOW, "查询");

            String plate = str(args, "plate", null);
            if (plate != null && plate.length() < 2) {
                return ToolSupport.error("BAD_PLATE", "车牌至少 2 个字符");
            }

            TrafficSearchRequest req = new TrafficSearchRequest();
            req.setTable(table);
            req.setStartMillis(start);
            req.setEndMillis(end);
            req.setPlate(plate);
            req.setColorCode(str(args, "color_code", null));
            req.setPageSize(ToolSupport.clamp(intArg(args, "page_size", 20), 1, 50));
            req.setPageNum(ToolSupport.clamp(intArg(args, "page_num", 1), 1, 10));
            req.setNeedTotal(true);
            putCodes(req, "orgcode", args, "org_codes");
            putCodes(req, "sectioncode", args, "section_codes");
            putCodes(req, "roadcode", args, "road_codes");
            putCodes(req, "gantrycode", args, "gantry_codes");
            putCodes(req, "tollcode", args, "toll_codes");

            TrafficSearchResult result = trafficSearchService.search(req);
            List<Map<String, Object>> masked = new ArrayList<>();
            for (Map<String, Object> row : result.getRows()) {
                masked.add(ToolSupport.maskRow(row, principal.canSeeFullPlate()));
            }
            boolean truncated = masked.size() > MAX_ROWS_TO_MODEL;
            if (truncated) {
                masked = new ArrayList<>(masked.subList(0, MAX_ROWS_TO_MODEL));
            }

            Map<String, Object> data = ToolSupport.ok();
            data.put("queryId", UUID.randomUUID().toString().replace("-", ""));
            data.put("table", table.getParamName());
            data.put("startTime", TrafficTimeUtils.format(start));
            data.put("endTime", TrafficTimeUtils.format(end));
            data.put("total", result.getTotal());
            data.put("hasMore", result.isHasMore());
            data.put("tookMs", result.getTookMs());
            data.put("rowCountReturned", masked.size());
            data.put("truncated", truncated);
            data.put("rows", masked);
            if (truncated) {
                data.put("note", "仅返回前 " + MAX_ROWS_TO_MODEL + " 行；更多数据请提示用户缩小时间范围或使用页面/导出");
            }
            return data;
        } catch (AgentException e) {
            return ToolSupport.error(e.getCode().name(), e.getMessage());
        } catch (TrafficQueryException e) {
            return ToolSupport.error("TRAFFIC_QUERY_" + e.getCode(), e.getMessage());
        } catch (IllegalArgumentException e) {
            return ToolSupport.error("BAD_ARGUMENT", e.getMessage());
        } catch (Exception e) {
            log.error("[Agent工具] 通行记录查询失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "查询失败，请稍后重试或联系值班人员");
        }
    }

    // ------------------------------------------------------------------
    // get_vehicle_track
    // ------------------------------------------------------------------
    public Map<String, Object> vehicleTrack(AgentPrincipal principal, Map<String, Object> args) {
        try {
            if (!principal.canSeeFullPlate()) {
                return ToolSupport.error("FORBIDDEN", "当前角色无权回放车辆轨迹");
            }
            String plate = str(args, "plate", null);
            if (plate == null || plate.length() < 2) {
                return ToolSupport.error("BAD_PLATE", "请提供至少 2 个字符的车牌");
            }
            long end = orNow(parse(args, "end_time", true));
            long start = orDefault(parse(args, "start_time", false), end - TRACK_DEFAULT_WINDOW.toMillis());
            ToolSupport.validateWindow(start, end, TRACK_MAX_WINDOW, "轨迹回放");
            int maxPoints = ToolSupport.clamp(intArg(args, "max_points", 200), 20, 200);

            TrafficSearchRequest req = new TrafficSearchRequest();
            req.setTable(TrafficTable.TRAIL);
            req.setStartMillis(start);
            req.setEndMillis(end);
            req.setPlate(plate);
            req.setPageSize(20);
            req.setPageNum(1);
            req.setNeedTotal(false);
            TrafficSearchResult result = trafficSearchService.search(req);

            List<String> cids = new ArrayList<>();
            for (Map<String, Object> row : result.getRows()) {
                Object cid = row.get("cid");
                if (cid == null) {
                    cid = row.get("big_id");
                }
                if (cid != null && !String.valueOf(cid).isBlank()) {
                    cids.add(String.valueOf(cid));
                }
            }
            if (cids.isEmpty()) {
                Map<String, Object> empty = ToolSupport.ok();
                empty.put("plate", ToolSupport.maskPlate(plate, principal.canSeeFullPlate()));
                empty.put("startTime", TrafficTimeUtils.format(start));
                empty.put("endTime", TrafficTimeUtils.format(end));
                empty.put("pointCount", 0);
                empty.put("points", List.of());
                empty.put("note", "该时间段内未找到轨迹元数据");
                return empty;
            }

            Map<String, String> rawPoints = trailPointLoader.load(cids, start, end);
            List<Map<String, Object>> points = new ArrayList<>();
            for (Map.Entry<String, String> entry : rawPoints.entrySet()) {
                List<TrailBo> bos = sysUtilService.getTrailBoList(entry.getValue());
                for (TrailBo bo : bos) {
                    Map<String, Object> point = toPoint(bo);
                    if (point != null) {
                        points.add(point);
                    }
                }
            }
            points.sort(Comparator.comparing(p -> String.valueOf(p.get("time"))));
            int totalPoints = points.size();
            List<Map<String, Object>> sampled = downsample(points, maxPoints);

            Map<String, Object> data = ToolSupport.ok();
            data.put("plate", ToolSupport.maskPlate(plate, principal.canSeeFullPlate()));
            data.put("startTime", TrafficTimeUtils.format(start));
            data.put("endTime", TrafficTimeUtils.format(end));
            data.put("trackCount", cids.size());
            data.put("pointCount", totalPoints);
            data.put("returnedPoints", sampled.size());
            data.put("truncated", totalPoints > sampled.size());
            data.put("points", sampled);
            return data;
        } catch (AgentException e) {
            return ToolSupport.error(e.getCode().name(), e.getMessage());
        } catch (TrafficQueryException e) {
            return ToolSupport.error("TRAFFIC_QUERY_" + e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("[Agent工具] 轨迹回放失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "轨迹回放失败");
        }
    }

    private Map<String, Object> toPoint(TrailBo bo) {
        if (bo == null) {
            return null;
        }
        Object lon = bo.getLon() != null ? bo.getLon() : bo.getLongitude();
        Object lat = bo.getLat() != null ? bo.getLat() : bo.getLatitude();
        if (lon == null || lat == null) {
            return null;
        }
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("time", bo.getCaptureTime());
        p.put("lon", lon);
        p.put("lat", lat);
        p.put("stateType", bo.getStateType());
        p.put("locationId", bo.getLocationId());
        p.put("sectionCode", bo.getSectionCode());
        p.put("orgCode", bo.getOrgCode());
        p.put("pileNo", bo.getPileno());
        return p;
    }

    private static List<Map<String, Object>> downsample(List<Map<String, Object>> points, int max) {
        if (points.size() <= max) {
            return points;
        }
        List<Map<String, Object>> out = new ArrayList<>(max);
        double step = (double) (points.size() - 1) / (max - 1);
        for (int i = 0; i < max; i++) {
            out.add(points.get((int) Math.round(i * step)));
        }
        return out;
    }

    // ------------------------------------------------------------------
    // get_bigscreen_metric
    // ------------------------------------------------------------------
    public Map<String, Object> bigScreen(AgentPrincipal principal, Map<String, Object> args) {
        try {
            String metric = str(args, "metric", null);
            if (metric == null) {
                return ToolSupport.error("BAD_ARGUMENT", "metric 必填");
            }
            String startDate = str(args, "start_date", null);
            String endDate = str(args, "end_date", null);
            Map<String, Object> data = ToolSupport.ok();
            data.put("metric", metric);
            switch (metric) {
                case "escape" -> data.put("rows", bigScreenStatsService.escape(
                        startDate, endDate, str(args, "org_id", null), str(args, "escaped_type", null)));
                case "audit" -> data.put("summary", bigScreenStatsService.audit(startDate, endDate));
                case "income" -> data.put("rows", bigScreenStatsService.income(
                        str(args, "query_date_type", "day"), startDate,
                        str(args, "apply_time1", startDate), str(args, "apply_time2", endDate)));
                case "warning_top" -> data.put("rows", bigScreenStatsService.warningTop(
                        str(args, "start_time", startDate), str(args, "end_time", endDate),
                        ToolSupport.clamp(intArg(args, "top_n", 10), 1, 50)));
                default -> {
                    return ToolSupport.error("BAD_ARGUMENT", "未知 metric: " + metric);
                }
            }
            return data;
        } catch (Exception e) {
            log.error("[Agent工具] 大屏指标查询失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "指标查询失败：" + e.getMessage());
        }
    }

    // ------------------------------------------------------------------
    // search_knowledge
    // ------------------------------------------------------------------
    public Map<String, Object> searchKnowledge(Map<String, Object> args) {
        String query = str(args, "query", null);
        if (query == null || query.isBlank()) {
            return ToolSupport.error("BAD_ARGUMENT", "query 必填");
        }
        int topK = ToolSupport.clamp(intArg(args, "top_k", 3), 1, 5);
        List<KnowledgeBase.KnowledgeHit> hits = knowledgeBase.search(query, topK);
        Map<String, Object> data = ToolSupport.ok();
        data.put("query", query);
        data.put("count", hits.size());
        List<Map<String, Object>> items = new ArrayList<>();
        for (KnowledgeBase.KnowledgeHit hit : hits) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("title", hit.title());
            item.put("source", hit.source());
            item.put("content", ToolSupport.truncate(hit.content(), 700));
            item.put("score", hit.score());
            items.add(item);
        }
        data.put("items", items);
        if (items.isEmpty()) {
            data.put("note", "知识库未命中；请改用数据查询工具，或提示用户联系数据管理员");
        }
        return data;
    }

    // ------------------------------------------------------------------
    // submit_export / get_export_status
    // ------------------------------------------------------------------
    public Map<String, Object> submitExport(AgentPrincipal principal, String sessionId,
                                            String confirmToken, Map<String, Object> args) {
        try {
            if (!properties.isAllowExport()) {
                return ToolSupport.error("EXPORT_DISABLED", "导出能力未开启，请联系管理员");
            }
            if (!principal.canExport()) {
                return ToolSupport.error("FORBIDDEN", "仅管理员可提交导出任务");
            }
            if (!confirmationService.consume(principal, sessionId, "export", confirmToken)) {
                return ToolSupport.error("CONFIRM_REQUIRED",
                        "导出需要用户在界面二次确认；请先让用户确认导出范围，再由客户端携带 confirmToken 重试");
            }
            TrafficTable table = TrafficTable.fromParam(str(args, "table", "snapshot"));
            long end = orNow(parse(args, "end_time", true));
            long start = orDefault(parse(args, "start_time", false), end - QUERY_DEFAULT_WINDOW.toMillis());
            ToolSupport.validateWindow(start, end, QUERY_MAX_WINDOW, "导出");
            String purpose = str(args, "purpose", null);
            if (purpose == null || purpose.isBlank()) {
                return ToolSupport.error("BAD_ARGUMENT", "purpose 必填（导出用途会写入审计）");
            }

            ExportRequest request = new ExportRequest();
            request.setTable(table.getParamName());
            request.setStartTime(TrafficTimeUtils.format(start));
            request.setEndTime(TrafficTimeUtils.format(end));
            request.setPlate(str(args, "plate", null));
            request.setPurpose(ToolSupport.truncate(purpose, 200));
            request.setRequestedBy(principal.userId());
            Object fields = args.get("fields");
            if (fields instanceof List<?> list) {
                List<String> fs = new ArrayList<>();
                for (Object f : list) {
                    if (f != null) {
                        fs.add(String.valueOf(f));
                    }
                }
                request.setFields(fs);
            }

            boolean full = "full".equalsIgnoreCase(str(args, "mode", "display"));
            ExportTask task = full ? exportTaskService.submitFull(request) : exportTaskService.submitDisplay(request);
            Map<String, Object> data = ToolSupport.ok();
            data.put("taskId", task.getTaskId());
            data.put("status", task.getStatus());
            data.put("mode", task.getMode());
            data.put("table", task.getTable().getParamName());
            data.put("estimatedRows", task.getTotalRows());
            data.put("downloadPath", "/api/v1/agent/export/" + task.getTaskId() + "/download");
            data.put("note", "导出为异步任务，请轮询 get_export_status 或调用任务状态接口");
            return data;
        } catch (AgentException e) {
            return ToolSupport.error(e.getCode().name(), e.getMessage());
        } catch (TrafficQueryException e) {
            return ToolSupport.error("TRAFFIC_QUERY_" + e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("[Agent工具] 导出提交失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "导出提交失败");
        }
    }

    public Map<String, Object> exportStatus(AgentPrincipal principal, Map<String, Object> args) {
        try {
            String taskId = str(args, "task_id", null);
            if (taskId == null || taskId.isBlank()) {
                return ToolSupport.error("BAD_ARGUMENT", "task_id 必填");
            }
            ExportTask task = exportTaskService.get(taskId);
            if (task == null) {
                return ToolSupport.error("NOT_FOUND", "任务不存在或已过期");
            }
            if (!principal.hasRole("admin") && task.getRequestedBy() != null
                    && !task.getRequestedBy().equals(principal.userId())) {
                return ToolSupport.error("FORBIDDEN", "只能查询本人提交的导出任务");
            }
            Map<String, Object> data = ToolSupport.ok();
            data.put("taskId", task.getTaskId());
            data.put("status", task.getStatus());
            data.put("mode", task.getMode());
            data.put("table", task.getTable() == null ? null : task.getTable().getParamName());
            data.put("totalRows", task.getTotalRows());
            data.put("exportedRows", task.getExportedRows());
            data.put("error", task.getError());
            data.put("createdAt", task.getCreatedAt());
            data.put("finishedAt", task.getFinishedAt());
            return data;
        } catch (Exception e) {
            log.error("[Agent工具] 导出状态查询失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "任务状态查询失败");
        }
    }

    // ------------------------------------------------------------------
    // get_data_quality
    // ------------------------------------------------------------------
    public Map<String, Object> dataQuality(AgentPrincipal principal, Map<String, Object> args) {
        try {
            Long start = parse(args, "start_time", false);
            Long end = parse(args, "end_time", true);
            if (start == null || end == null) {
                return ToolSupport.error("BAD_ARGUMENT", "start_time 与 end_time 必填");
            }
            ToolSupport.validateWindow(start, end, QUALITY_MAX_WINDOW, "数据质量诊断");
            DataLossDetectionService.DetectionResult result =
                    dataLossDetectionService.detectDataLoss(new Date(start), new Date(end));
            Map<String, Object> data = ToolSupport.ok();
            data.put("startTime", TrafficTimeUtils.format(start));
            data.put("endTime", TrafficTimeUtils.format(end));
            data.put("reportedCount", result.getReportedCount());
            data.put("storedCount", result.getStoredCount());
            data.put("lostCount", result.getLostCount());
            data.put("lossRate", result.getLossRate());
            data.put("duplicateCount", result.getDuplicateCount());
            data.put("passed", result.isPassed());
            data.put("lostMessageIds", ToolSupport.limitList(
                    result.getLostMessageIds() == null ? List.of() : new ArrayList<>(result.getLostMessageIds()), 20));
            return data;
        } catch (AgentException e) {
            return ToolSupport.error(e.getCode().name(), e.getMessage());
        } catch (Exception e) {
            log.error("[Agent工具] 数据质量诊断失败", e);
            return ToolSupport.error("TOOL_INTERNAL", "数据质量诊断失败");
        }
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------
    private static void putCodes(TrafficSearchRequest req, String field, Map<String, Object> args, String key) {
        Object value = args.get(key);
        if (value instanceof List<?> list) {
            List<String> codes = new ArrayList<>();
            for (Object o : list) {
                if (o != null && !String.valueOf(o).isBlank()) {
                    codes.add(String.valueOf(o));
                }
            }
            req.addCodes(field, codes);
        }
    }

    private static Long parse(Map<String, Object> args, String key, boolean endOfDay) {
        Object v = args.get(key);
        if (v == null || String.valueOf(v).isBlank()) {
            return null;
        }
        return ToolSupport.parseTime(String.valueOf(v), endOfDay);
    }

    private static long orNow(Long value) {
        return value == null ? System.currentTimeMillis() : value;
    }

    private static long orDefault(Long value, long fallback) {
        return value == null ? fallback : value;
    }

    private static String str(Map<String, Object> args, String key, String fallback) {
        Object v = args.get(key);
        if (v == null) {
            return fallback;
        }
        String s = String.valueOf(v).trim();
        return s.isEmpty() ? fallback : s;
    }

    private static int intArg(Map<String, Object> args, String key, int fallback) {
        Object v = args.get(key);
        if (v instanceof Number n) {
            return n.intValue();
        }
        if (v != null) {
            try {
                return Integer.parseInt(String.valueOf(v).trim());
            } catch (NumberFormatException ignored) {
                return fallback;
            }
        }
        return fallback;
    }
}
