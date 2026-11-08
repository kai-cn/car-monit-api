package com.ruoyi.base.service.v3.export;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.plate.PlateColorDictionary;
import com.ruoyi.base.service.v3.plate.PlateNumberParser;
import com.ruoyi.base.service.v3.plate.PlateParseResult;
import com.ruoyi.base.service.v3.query.TrafficSearchRequest;
import com.ruoyi.base.service.v3.query.TrafficSearchResult;
import com.ruoyi.base.service.v3.query.TrafficSearchService;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import javax.annotation.PreDestroy;
import javax.sql.DataSource;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.sql.Array;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.GZIPOutputStream;

/**
 * 导出任务服务（设计 §5.5 双路径）。
 *
 * <ul>
 *   <li>DISPLAY：ES PIT + search_after 拉展示字段，CSV/GZIP；</li>
 *   <li>FULL：GaussDB 服务端游标（setFetchSize）流式输出全字段，CSV/GZIP；</li>
 *   <li>全局固定 2 个 worker；任务可取消；文件先落本地目录，对象存储/签名 URL 预留。</li>
 * </ul>
 */
@Slf4j
@Service
public class ExportTaskService {

    private static final List<String> SNAPSHOT_COLUMNS = Arrays.asList(
            "big_id", "snapshottime", "platenumber", "platecolor", "platecolorcode",
            "plate_color_name",
            "orgcode", "orgname", "sectioncode", "sectionname", "roadcode", "roadname",
            "gantrycode", "gantryname", "tollcode", "tollname", "direction", "pileno",
            "lon", "lat", "cartype", "cartypecode", "carcolor", "snappicturepath");

    private static final List<String> FEE_COLUMNS = Arrays.asList(
            "big_id", "vehicleplate", "plate_core", "plate_color_code", "plate_color_raw",
            "plate_color_name", "plate_parse_status", "transtime", "gantryid", "gantryname",
            "sectioncode", "fee", "payfee", "axlecount",
            "passstate", "entollstationid", "extollstationid");

    private static final List<String> TRAIL_COLUMNS = Arrays.asList(
            "cid", "envehicleid", "entime", "extime", "entollstationid", "entollstationname",
            "extollstationid", "extollstationname", "trailtype", "point_count",
            "route_sections", "route_gantries");

    /** 日期字段：导出时把 epoch millis 格式化为 yyyy-MM-dd HH:mm:ss */
    private static final Set<String> DATE_FIELDS = new HashSet<>(Arrays.asList(
            "snapshottime", "receivedtime", "loadtime", "transtime", "lastgantrytime",
            "entime", "extime", "first_capture_time", "last_capture_time"));

    private final TrafficV3Properties properties;
    private final TrafficSearchService searchService;
    private final PlateNumberParser plateParser;
    private final PlateColorDictionary colorDictionary;
    private final JdbcTemplate jdbc;

    private final ExecutorService executor;
    private final Map<String, ExportTask> tasks = new ConcurrentHashMap<>();
    private final Map<String, PreparedStatement> runningStatements = new ConcurrentHashMap<>();

    public ExportTaskService(TrafficV3Properties properties,
                             TrafficSearchService searchService,
                             PlateNumberParser plateParser,
                             PlateColorDictionary colorDictionary,
                             DataSource dataSource) {
        this.properties = properties;
        this.searchService = searchService;
        this.plateParser = plateParser;
        this.colorDictionary = colorDictionary;
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(3600);
        AtomicInteger seq = new AtomicInteger();
        int workers = Math.max(1, properties.getExport().getWorkers());
        this.executor = Executors.newFixedThreadPool(workers, r -> {
            Thread t = new Thread(r, "v3-export-" + seq.incrementAndGet());
            t.setDaemon(true);
            return t;
        });
    }

    public ExportTask submitDisplay(ExportRequest request) {
        return submit("DISPLAY", request);
    }

    public ExportTask submitFull(ExportRequest request) {
        return submit("FULL", request);
    }

    private ExportTask submit(String mode, ExportRequest request) {
        TrafficTable table = TrafficTable.fromParam(request.getTable());
        if ("DISPLAY".equals(mode)) {
            validateDisplayFields(table, request);
        }
        validateDimensionCodes(table, request);
        long now = System.currentTimeMillis();
        Long start = TrafficTimeUtils.parse(request.getStartTime(), false);
        Long end = TrafficTimeUtils.parse(request.getEndTime(), true);
        if (start == null) {
            start = now - java.util.concurrent.TimeUnit.DAYS.toMillis(
                    properties.getQuery().getDefaultDays());
        }
        if (end == null) {
            end = now;
        }
        if (start > end) {
            throw new IllegalArgumentException("startTime 必须早于 endTime");
        }
        if (end - start > java.util.concurrent.TimeUnit.DAYS.toMillis(
                properties.getQuery().getMaxDays())) {
            throw new IllegalArgumentException("导出时间范围超过 " + properties.getQuery().getMaxDays() + " 天");
        }

        ExportTask task = new ExportTask();
        task.setTaskId(UUID.randomUUID().toString().replace("-", ""));
        task.setTable(table);
        task.setMode(mode);
        task.setStartMillis(start);
        task.setEndMillis(end);
        task.setRequestedBy(request.getRequestedBy());
        task.setPurpose(request.getPurpose());
        task.setFilePath(buildFilePath(task.getTaskId()));
        tasks.put(task.getTaskId(), task);

        executor.submit(() -> {
            task.setStatus("running");
            task.setStartedAt(new Date());
            try {
                if ("DISPLAY".equals(mode)) {
                    runDisplay(task, request);
                } else {
                    runFull(task, request);
                }
                if (task.isCancelRequested()) {
                    task.setStatus("canceled");
                } else {
                    task.setStatus("done");
                }
            } catch (Exception e) {
                task.setStatus("failed");
                task.setError(e.getMessage());
                log.error("[V3导出] 失败 taskId={}", task.getTaskId(), e);
            } finally {
                task.setFinishedAt(new Date());
                runningStatements.remove(task.getTaskId());
            }
        });
        return task;
    }

    public ExportTask get(String taskId) {
        return tasks.get(taskId);
    }

    /**
     * api 重启后内存任务丢失时，按 taskId 探测已完成文件，避免下载 404。
     */
    public File resolveFinishedFile(String taskId) {
        if (taskId == null || !taskId.matches("[A-Za-z0-9_-]{1,64}")) {
            return null;
        }
        File file = new File(buildFilePath(taskId));
        return file.exists() && file.isFile() ? file : null;
    }

    public boolean cancel(String taskId) {
        ExportTask task = tasks.get(taskId);
        if (task == null) {
            return false;
        }
        task.setCancelRequested(true);
        PreparedStatement ps = runningStatements.get(taskId);
        if (ps != null) {
            try {
                ps.cancel();
            } catch (Exception ignored) {
                // 已结束
            }
        }
        return true;
    }

    // ============================================================
    // 路径 A：展示字段（ES PIT + search_after）
    // ============================================================

    private void runDisplay(ExportTask task, ExportRequest request) throws Exception {
        TrafficSearchRequest req = new TrafficSearchRequest();
        req.setTable(task.getTable());
        req.setStartMillis(task.getStartMillis());
        req.setEndMillis(task.getEndMillis());
        req.setPlate(request.getPlate());
        req.setColorCode(request.getColorCode());
        if (request.getDimensionCodes() != null) {
            req.getDimensionCodes().putAll(request.getDimensionCodes());
        }
        req.setPageSize(properties.getQuery().getMaxPageSize());
        req.setPageNum(1);
        req.setNeedTotal(true);
        req.setKeepPit(true);

        String pitId = null;
        List<Object> searchAfter = new ArrayList<>();
        long exported = 0;
        List<DisplayColumn> columns = resolveColumns(task.getTable(), request.getFields());

        try (Writer writer = openGzipWriter(task.getFilePath());
             CsvWriter csv = new CsvWriter(writer)) {
            List<String> headers = new ArrayList<>(columns.size());
            for (DisplayColumn column : columns) {
                headers.add(column.header);
            }
            csv.writeRow(headers);
            while (!task.isCancelRequested()) {
                req.setPitId(pitId);
                req.setSearchAfter(searchAfter);
                req.setNeedTotal(pitId == null);
                TrafficSearchResult result = searchService.searchForExport(
                        req, properties.getExport().getPageSize());
                if (pitId == null) {
                    pitId = result.getPitId();
                    task.setTotalRows(result.getTotal());
                }
                if (result.isEmpty()) {
                    break;
                }
                for (Map<String, Object> row : result.getRows()) {
                    List<String> values = new ArrayList<>(columns.size());
                    for (DisplayColumn column : columns) {
                        values.add(displayValue(task.getTable(), column, row));
                    }
                    csv.writeRow(values);
                }
                exported += result.getRows().size();
                task.setExportedRows(exported);
                searchAfter = result.getSearchAfter() == null
                        ? new ArrayList<>() : new ArrayList<>(result.getSearchAfter());
                if (!result.isHasMore() || searchAfter.isEmpty()) {
                    break;
                }
            }
        } finally {
            if (pitId != null) {
                searchService.closePit(pitId);
            }
        }
        log.info("[V3导出] 展示字段完成 taskId={}, rows={}", task.getTaskId(), exported);
    }

    // ============================================================
    // 路径 B：全字段（GaussDB 游标）
    // ============================================================

    private void runFull(ExportTask task, ExportRequest request) throws Exception {
        TrafficTable table = task.getTable();
        StringBuilder sql = new StringBuilder("SELECT t.* FROM ")
                .append(table.getSourceTable()).append(" t");
        if (table == TrafficTable.FEE) {
            sql.append(" LEFT JOIN jl_data01.ods_szdn_gantry g")
                    .append(" ON t.gantryid = g.gantry_code");
        }
        sql.append(" WHERE t.").append(table.getTimeField()).append(" >= ? AND t.")
                .append(table.getTimeField()).append(" < ?");
        List<Object> args = new ArrayList<>();
        args.add(TrafficTimeUtils.toDbTimestamp(task.getStartMillis()));
        args.add(TrafficTimeUtils.toDbTimestamp(task.getEndMillis()));

        // 车牌过滤：与展示路径（ES plate_norm.ngram 包含匹配）保持同一语义。
        // 完整车牌：收费按“核心+颜色后缀”前缀，抓拍/轨迹按核心等值（与原行为一致）；
        // 片段车牌：三表统一为包含匹配，避免 display 命中而 full 导出漏数据。
        if (request.getPlate() != null && !request.getPlate().trim().isEmpty()) {
            PlateParseResult parsed = plateParser.parse(request.getPlate());
            String core = parsed.getPlateCore();
            if (core != null && !core.isEmpty()) {
                if (!plateParser.isFullPlate(core)) {
                    String column;
                    if (table == TrafficTable.FEE) {
                        column = "t.vehicleplate";
                    } else if (table == TrafficTable.TRAIL) {
                        column = "t.envehicleid";
                    } else {
                        column = "t.platenumber";
                    }
                    sql.append(" AND ").append(column).append(" LIKE ? ESCAPE '\\'");
                    args.add("%" + escapeLike(core) + "%");
                } else if (table == TrafficTable.FEE) {
                    sql.append(" AND t.vehicleplate LIKE ?");
                    args.add(core + "%");
                } else if (table == TrafficTable.TRAIL) {
                    sql.append(" AND t.envehicleid = ?");
                    args.add(core);
                } else {
                    sql.append(" AND t.platenumber = ?");
                    args.add(core);
                }
            }
        }
        if (table == TrafficTable.FEE && request.getColorCode() != null
                && !request.getColorCode().trim().isEmpty()) {
            sql.append(" AND t.vehicleplate LIKE ?");
            args.add("%_" + request.getColorCode().trim());
        }

        // 维度过滤：多值 IN 下推；名称已在入口解析为编码
        if (request.getDimensionCodes() != null && table != TrafficTable.TRAIL) {
            for (Map.Entry<String, List<String>> e : request.getDimensionCodes().entrySet()) {
                List<String> values = e.getValue();
                if (values == null || values.isEmpty()) {
                    continue;
                }
                String column = fullExportDimColumn(table, e.getKey());
                if (column == null) {
                    continue;
                }
                List<String> cleaned = new ArrayList<>();
                for (String v : values) {
                    if (v != null && !v.trim().isEmpty()) {
                        cleaned.add(v.trim());
                    }
                }
                if (cleaned.isEmpty()) {
                    continue;
                }
                sql.append(" AND ").append(column).append(" IN (");
                for (int i = 0; i < cleaned.size(); i++) {
                    if (i > 0) {
                        sql.append(',');
                    }
                    sql.append('?');
                    args.add(cleaned.get(i));
                }
                sql.append(')');
            }
        }

        long exported = 0;
        try (Writer writer = openGzipWriter(task.getFilePath())) {
            final long[] count = {0};
            jdbc.execute((ConnectionCallback<Void>) conn -> {
                conn.setAutoCommit(false);
                try (PreparedStatement ps = conn.prepareStatement(
                        sql.toString(), ResultSet.TYPE_FORWARD_ONLY, ResultSet.CONCUR_READ_ONLY)) {
                    ps.setFetchSize(5000);
                    ps.setQueryTimeout(3600);
                    for (int i = 0; i < args.size(); i++) {
                        ps.setObject(i + 1, args.get(i));
                    }
                    runningStatements.put(task.getTaskId(), ps);
                    try (ResultSet rs = ps.executeQuery()) {
                        CsvWriter csv = new CsvWriter(writer);
                        ResultSetMetaData meta = rs.getMetaData();
                        int columnCount = meta.getColumnCount();
                        List<String> header = new ArrayList<>(columnCount);
                        boolean addColorName = table == TrafficTable.FEE;
                        for (int i = 1; i <= columnCount; i++) {
                            header.add(meta.getColumnLabel(i));
                        }
                        if (addColorName) {
                            header.add("plate_color_name");
                        }
                        csv.writeRow(header);
                        while (rs.next() && !task.isCancelRequested()) {
                            List<String> values = new ArrayList<>(columnCount + (addColorName ? 1 : 0));
                            for (int i = 1; i <= columnCount; i++) {
                                values.add(displayValue(meta.getColumnLabel(i), rs.getObject(i)));
                            }
                            if (addColorName) {
                                PlateParseResult parsed = plateParser.parse(
                                        String.valueOf(rs.getObject("vehicleplate")));
                                values.add(colorDictionary.displayName(
                                        parsed.getPlateColorCode(), parsed.getPlateColorRaw()));
                            }
                            csv.writeRow(values);
                            count[0]++;
                        }
                    }
                } finally {
                    runningStatements.remove(task.getTaskId());
                    conn.rollback();
                }
                return null;
            });
            exported = count[0];
            task.setExportedRows(exported);
        }
        log.info("[V3导出] 全字段完成 taskId={}, rows={}", task.getTaskId(), exported);
    }

    // ============================================================
    // Helpers
    // ============================================================

    /**
     * 全字段导出维度 -> SQL 列。抓拍直接列；收费经 gantry join；轨迹无维度。
     */
    private String fullExportDimColumn(TrafficTable table, String field) {
        if (field == null) {
            return null;
        }
        String key = field.trim().toLowerCase();
        if (table == TrafficTable.SNAPSHOT) {
            switch (key) {
                case "orgcode":
                case "sectioncode":
                case "roadcode":
                case "tollcode":
                    return "t." + key;
                case "gantrycode":
                case "gantryid":
                    return "t.gantrycode";
                default:
                    return null;
            }
        }
        if (table == TrafficTable.FEE) {
            switch (key) {
                case "orgcode":
                    return "g.org_code";
                case "sectioncode":
                    return "g.section_code";
                case "roadcode":
                    return "g.road_code";
                case "tollcode":
                    return "g.toll_code";
                case "gantrycode":
                case "gantryid":
                    return "t.gantryid";
                default:
                    return null;
            }
        }
        return null;
    }

    /** 展示字段白名单（含 fee 派生列 plate_color_name） */
    public List<String> displayColumnsFor(TrafficTable table) {
        return new ArrayList<>(displayColumns(table));
    }

    /** 全字段导出支持的维度过滤字段（trail 无维度） */
    public List<String> fullDimensionFieldsFor(TrafficTable table) {
        List<String> fields = new ArrayList<>();
        if (table == TrafficTable.SNAPSHOT || table == TrafficTable.FEE) {
            fields.add("orgcode");
            fields.add("sectioncode");
            fields.add("roadcode");
            fields.add("tollcode");
            fields.add("gantrycode");
        }
        return fields;
    }

    /** 导出能力元数据：backend 据此放开过滤/字段，不再硬编码探测。 */
    public Map<String, Object> capabilities() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("modes", Arrays.asList("display", "full"));
        result.put("tables", Arrays.asList("snapshot", "fee", "trail"));
        result.put("fullDimensionFilters", true);
        result.put("multiValueDimensionFilters", true);
        result.put("plateColorName", true);
        result.put("plateColorNameField", "plate_color_name");
        Map<String, Object> plateColorNameByTable = new LinkedHashMap<>();
        plateColorNameByTable.put("snapshot", true);
        plateColorNameByTable.put("fee", true);
        plateColorNameByTable.put("trail", false);
        result.put("plateColorNameByTable", plateColorNameByTable);
        Map<String, Object> unsupportedFields = new LinkedHashMap<>();
        unsupportedFields.put("trail", Arrays.asList("plate_color_name"));
        result.put("unsupportedDisplayFields", unsupportedFields);
        result.put("nameFilters", Arrays.asList(
                "orgname", "sectionname", "roadname", "gantryname", "tollname"));
        Map<String, Object> dimensionFilters = new LinkedHashMap<>();
        Map<String, Object> displayFields = new LinkedHashMap<>();
        for (TrafficTable table : TrafficTable.values()) {
            dimensionFilters.put(table.getParamName(), fullDimensionFieldsFor(table));
            displayFields.put(table.getParamName(), displayColumnsFor(table));
        }
        result.put("dimensionFilters", dimensionFilters);
        result.put("displayFields", displayFields);
        result.put("displayAliases", new LinkedHashMap<>(DISPLAY_ALIASES));
        result.put("fullFields", "all_columns");
        return result;
    }

    private List<String> displayColumns(TrafficTable table) {
        switch (table) {
            case SNAPSHOT:
                return SNAPSHOT_COLUMNS;
            case FEE:
                return FEE_COLUMNS;
            case TRAIL:
                return TRAIL_COLUMNS;
            default:
                return SNAPSHOT_COLUMNS;
        }
    }

    /** backend 逻辑字段名 -> ES 文档字段名 */
    private static final Map<String, String> DISPLAY_ALIASES = new LinkedHashMap<>();

    static {
        DISPLAY_ALIASES.put("bigId", "big_id");
        DISPLAY_ALIASES.put("plateColor", "plate_color_raw");
        DISPLAY_ALIASES.put("plateColorName", "plate_color_name");
        DISPLAY_ALIASES.put("lane", "laneid");
        DISPLAY_ALIASES.put("speed", "speed");
        DISPLAY_ALIASES.put("feevehicletype", "envehicleclass");
        DISPLAY_ALIASES.put("vehicleclass", "envehicleclass");
        DISPLAY_ALIASES.put("uuid", "cid");
        DISPLAY_ALIASES.put("plateKey", "envehicleid");
        DISPLAY_ALIASES.put("enterTime", "entime");
        DISPLAY_ALIASES.put("exitTime", "extime");
        DISPLAY_ALIASES.put("pointCount", "point_count");
        DISPLAY_ALIASES.put("enterLocationcode", "entollstationid");
        DISPLAY_ALIASES.put("exitLocationcode", "extollstationid");
        DISPLAY_ALIASES.put("fentollstationname", "entollstationname");
    }

    /**
     * 同步校验展示字段：不支持的表/字段直接拒绝并返回 400，而不是异步任务静默失败。
     * 收费表 ES 文档没有 orgcode/orgname/sectionname 等列，已从白名单移除，
     * 继续请求这些字段会显式报错，避免“声明支持却永远输出空列”。
     */
    private void validateDisplayFields(TrafficTable table, ExportRequest request) {
        if (request.getFields() == null || request.getFields().isEmpty()) {
            return;
        }
        List<String> supported = displayColumns(table);
        for (String alias : request.getFields()) {
            String field = resolveDisplayField(alias);
            if ("plate_color_name".equals(field)) {
                if (table == TrafficTable.TRAIL) {
                    throw new IllegalArgumentException("表 trail 不支持展示字段 plate_color_name");
                }
                continue;
            }
            if (field == null || !supported.contains(field)) {
                throw new IllegalArgumentException("表 " + table.getParamName()
                        + " 不支持展示字段: " + alias);
            }
        }
    }

    /** 导出维度键白名单：未知键直接 400，避免 SQL/ES 侧静默忽略。 */
    private void validateDimensionCodes(TrafficTable table, ExportRequest request) {
        if (request.getDimensionCodes() == null || request.getDimensionCodes().isEmpty()) {
            return;
        }
        java.util.Set<String> allowed = new java.util.HashSet<>(fullDimensionFieldsFor(table));
        for (String key : request.getDimensionCodes().keySet()) {
            String normalized = key == null ? "" : key.trim().toLowerCase();
            if (!allowed.contains(normalized)) {
                throw new IllegalArgumentException("表 " + table.getParamName()
                        + " 不支持维度过滤: " + key + "，允许值: " + allowed);
            }
        }
    }

    private List<DisplayColumn> resolveColumns(TrafficTable table, List<String> requested) {
        List<DisplayColumn> columns = new ArrayList<>();
        if (requested == null || requested.isEmpty()) {
            for (String field : displayColumns(table)) {
                columns.add(new DisplayColumn(field, field));
            }
            return columns;
        }
        for (String alias : requested) {
            String field = resolveDisplayField(alias);
            // 不支持的表显式拒绝，避免“请求成功但字段被忽略”
            if ("plate_color_name".equals(field) && table == TrafficTable.TRAIL) {
                throw new IllegalArgumentException("表 trail 不支持展示字段 plate_color_name");
            }
            columns.add(new DisplayColumn(alias, field));
        }
        // 抓拍/收费展示字段固定补齐 plate_color_name：旧同步 Excel 有该列，backend 字段清单可能未包含
        if (table == TrafficTable.FEE || table == TrafficTable.SNAPSHOT) {
            boolean present = false;
            for (DisplayColumn column : columns) {
                if ("plate_color_name".equals(column.field)) {
                    present = true;
                    break;
                }
            }
            if (!present) {
                columns.add(new DisplayColumn("plate_color_name", "plate_color_name"));
            }
        }
        return columns;
    }

    private String resolveDisplayField(String alias) {
        if (alias == null) {
            return null;
        }
        String mapped = DISPLAY_ALIASES.get(alias);
        return mapped != null ? mapped : toSnake(alias);
    }

    private String toSnake(String name) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            if (Character.isUpperCase(c) && i > 0) {
                sb.append('_');
            }
            sb.append(Character.toLowerCase(c));
        }
        return sb.toString();
    }

    /** LIKE 通配符转义（配合 ESCAPE '\\'），防止片段车牌里的 %/_ 扩大匹配范围。 */
    private String escapeLike(String value) {
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }

    private static class DisplayColumn {
        private final String header;
        private final String field;

        private DisplayColumn(String header, String field) {
            this.header = header;
            this.field = field;
        }
    }

    private Writer openGzipWriter(String path) throws Exception {
        File dir = new File(properties.getExport().getDir());
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IllegalStateException("无法创建导出目录: " + dir.getAbsolutePath());
        }
        return new BufferedWriter(new OutputStreamWriter(
                new GZIPOutputStream(new FileOutputStream(path)), StandardCharsets.UTF_8));
    }

    private String buildFilePath(String taskId) {
        return properties.getExport().getDir() + File.separator + taskId + ".csv.gz";
    }

    @SuppressWarnings("unchecked")
    private String displayValue(TrafficTable table, DisplayColumn column, Map<String, Object> row) {
        if ("plate_color_name".equals(column.field)) {
            Object existing = row.get("plate_color_name");
            if (existing != null) {
                return String.valueOf(existing);
            }
            if (table == TrafficTable.SNAPSHOT) {
                return snapshotColorName(row);
            }
            Object code = row.get("plate_color_code");
            Object raw = row.get("plate_color_raw");
            int c = -1;
            if (code != null) {
                try {
                    c = Integer.parseInt(String.valueOf(code).trim());
                } catch (NumberFormatException ignored) {
                    c = -1;
                }
            }
            return colorDictionary.displayName(c, raw == null ? null : String.valueOf(raw));
        }
        return displayValue(column.field, column.field == null ? null : row.get(column.field));
    }

    /**
     * 抓拍表颜色：platecolor 是可直接展示的文本（如“黄色”“渐变绿底黑字”），
     * 其 platecolorcode 与收费表字典码不同源，不能直接套用；这里用文本回查字典做规范化，
     * 文本无法匹配时原样展示，空值展示“未知”。
     */
    private String snapshotColorName(Map<String, Object> row) {
        Object raw = row.get("platecolor");
        if (raw == null || String.valueOf(raw).trim().isEmpty()) {
            return "未知";
        }
        String text = String.valueOf(raw).trim();
        int code = colorDictionary.codeForWord(text);
        return code >= 0 ? colorDictionary.displayName(code) : text;
    }

    @SuppressWarnings("unchecked")
    private String displayValue(String field, Object value) {
        if (value instanceof Number && field != null && DATE_FIELDS.contains(field)) {
            return TrafficTimeUtils.format(((Number) value).longValue());
        }
        return displayValue(value);
    }

    @SuppressWarnings("unchecked")
    private String displayValue(Object value) {
        if (value == null) {
            return "";
        }
        if (value instanceof Array) {
            try {
                value = ((Array) value).getArray();
            } catch (Exception ignored) {
                return String.valueOf(value);
            }
        }
        if (value instanceof Object[]) {
            List<String> parts = new ArrayList<>();
            for (Object o : (Object[]) value) {
                if (o != null) {
                    parts.add(String.valueOf(o));
                }
            }
            return String.join("|", parts);
        }
        if (value instanceof List) {
            List<String> parts = new ArrayList<>();
            for (Object o : (List<Object>) value) {
                if (o != null) {
                    parts.add(String.valueOf(o));
                }
            }
            return String.join("|", parts);
        }
        if (value instanceof Date) {
            return TrafficTimeUtils.format(((Date) value).getTime());
        }
        return String.valueOf(value);
    }

    /**
     * 简单 CSV 写入器（UTF-8、逗号分隔、引号转义）。
     */
    private static class CsvWriter implements AutoCloseable {
        private final Writer writer;

        private CsvWriter(Writer writer) {
            this.writer = writer;
        }

        private void writeRow(List<String> values) {
            try {
                StringBuilder line = new StringBuilder();
                for (int i = 0; i < values.size(); i++) {
                    if (i > 0) {
                        line.append(',');
                    }
                    line.append(escape(values.get(i)));
                }
                line.append('\n');
                writer.write(line.toString());
            } catch (Exception e) {
                throw new IllegalStateException("写 CSV 失败: " + e.getMessage(), e);
            }
        }

        private String escape(String value) {
            if (value == null) {
                return "";
            }
            boolean needQuote = value.indexOf(',') >= 0 || value.indexOf('"') >= 0
                    || value.indexOf('\n') >= 0 || value.indexOf('\r') >= 0;
            String v = value.replace("\"", "\"\"");
            return needQuote ? "\"" + v + "\"" : v;
        }

        @Override
        public void close() throws Exception {
            writer.flush();
            writer.close();
        }
    }

    @PreDestroy
    public void shutdown() {
        executor.shutdownNow();
    }
}
