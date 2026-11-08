package com.ruoyi.base.service.v3.es;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.plate.PlateNumberParser;
import com.ruoyi.base.service.v3.plate.PlateParseResult;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.sql.Array;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 把 GaussDB 行（JDBC Map / Outbox payload）转换为 ES 文档。
 *
 * <p>严格遵循 mapping（{@code dynamic: strict}）：只输出模板中声明过的字段；
 * 收费车牌拆分为 plate_core/plate_color_code/plate_raw；轨迹不输出 trailpoints，
 * 只输出摘要（point_count/首末时间/路段与门架编码数组）。</p>
 */
@Slf4j
@Component
public class TrafficDocumentBuilder {

    private final PlateNumberParser plateParser;

    public TrafficDocumentBuilder(PlateNumberParser plateParser) {
        this.plateParser = plateParser;
    }

    /** 每张表允许写入 ES 的字段白名单（必须与模板一致） */
    private static final Set<String> SNAPSHOT_FIELDS = new HashSet<>(Arrays.asList(
            "big_id", "datauuid", "snapshottime", "snapshottimeunix", "receivedtime",
            "receivedtimeunix", "loadtime", "orgcode", "sectioncode", "roadcode",
            "gantrycode", "tollcode", "hexcode", "pileno", "deviceid", "deviceip",
            "datasource", "cameratype", "siteid", "laneid", "direction", "lon", "lat",
            "platenumber", "plate_norm", "plate_raw", "platecolor", "platecolorcode",
            "platetype", "platetypecode", "plateconfidence", "carbrand", "carcolor",
            "carcolorcode", "cartype", "cartypecode", "cardirection", "gradelevel",
            "reserve3", "snappicturepath", "orgname", "sectionname", "roadname",
            "gantryname", "tollname"
    ));

    private static final Set<String> FEE_FIELDS = new HashSet<>(Arrays.asList(
            "big_id", "transtime", "lastgantrytime", "entime", "extime", "orgcode",
            "sectioncode", "roadcode", "gantryid", "gantrycode", "tollcode", "cid",
            "passid", "passstate", "gantrytype", "mediatype", "dealstatus", "matchstatus",
            "gantryordernum", "axlecount", "vehiclehight", "envehicleclass", "exvehicleclass",
            "envehicletype", "exvehicletype", "enweight", "exweight", "fee", "payfee",
            "discountfee", "feemileage", "plate_norm", "plate_core", "plate_color_code",
            "plate_color_raw", "plate_parse_status", "plate_raw", "vehicleplate",
            "cpuvehicleplate", "obuvehicleplate", "obumac", "entolllaneid", "extolllaneid",
            "entollstationid", "extollstationid", "entollstationname", "extollstationname",
            "orgname", "sectionname", "roadname", "gantryname", "tollname"
    ));

    private static final Set<String> TRAIL_FIELDS = new HashSet<>(Arrays.asList(
            "cid", "extime", "entime", "first_capture_time", "last_capture_time",
            "plate_norm", "envehicleid", "exvehicleid", "enaxlecount", "envehicleclass",
            "envehicletype", "exvehicleclass", "exvehicletype", "enweight", "exweight",
            "entolllaneid", "extolllaneid", "entollstationid", "extollstationid",
            "entollstationname", "extollstationname", "trailtype", "point_count",
            "route_sections", "route_gantries"
    ));

    private static final Set<String> DATE_FIELDS = new HashSet<>(Arrays.asList(
            "snapshottime", "receivedtime", "loadtime", "transtime", "lastgantrytime",
            "entime", "extime", "first_capture_time", "last_capture_time"
    ));

    /**
     * 构建 ES 文档；返回只包含 mapping 白名单字段的 Map。
     */
    public Map<String, Object> build(TrafficTable table, Map<String, Object> row) {
        if (row == null) {
            return new LinkedHashMap<>();
        }
        switch (table) {
            case SNAPSHOT:
                return buildSnapshot(row);
            case FEE:
                return buildFee(row);
            case TRAIL:
                return buildTrail(row);
            default:
                throw new IllegalArgumentException("未知表: " + table);
        }
    }

    /** 文档 _id：抓拍/收费 big_id，轨迹 cid */
    public String docId(TrafficTable table, Map<String, Object> row) {
        Object id = row.get(table.getPkField());
        return id == null ? null : String.valueOf(id);
    }

    private Map<String, Object> buildSnapshot(Map<String, Object> row) {
        Map<String, Object> doc = copyFields(row, SNAPSHOT_FIELDS);
        String rawPlate = asString(row.get("platenumber"));
        PlateParseResult parsed = plateParser.parse(rawPlate);
        String core = parsed.getPlateCore();
        doc.put("platenumber", rawPlate);
        doc.put("plate_norm", core == null || core.isEmpty() ? plateParser.normalize(rawPlate) : core);
        doc.put("plate_raw", rawPlate);
        return doc;
    }

    private Map<String, Object> buildFee(Map<String, Object> row) {
        Map<String, Object> doc = copyFields(row, FEE_FIELDS);
        String rawPlate = asString(row.get("vehicleplate"));
        PlateParseResult parsed = plateParser.parse(rawPlate);
        String core = parsed.getPlateCore();
        doc.put("vehicleplate", rawPlate);
        doc.put("plate_norm", core == null || core.isEmpty() ? plateParser.normalize(rawPlate) : core);
        doc.put("plate_core", core);
        doc.put("plate_color_code", String.valueOf(parsed.getPlateColorCode()));
        doc.put("plate_color_raw", parsed.getPlateColorRaw());
        doc.put("plate_parse_status", parsed.getPlateParseStatus());
        doc.put("plate_raw", rawPlate);
        return doc;
    }

    private Map<String, Object> buildTrail(Map<String, Object> row) {
        Map<String, Object> doc = copyFields(row, TRAIL_FIELDS);
        String rawPlate = asString(row.get("envehicleid"));
        PlateParseResult parsed = plateParser.parse(rawPlate);
        String core = parsed.getPlateCore();
        doc.put("envehicleid", rawPlate);
        doc.put("plate_norm", core == null || core.isEmpty() ? plateParser.normalize(rawPlate) : core);

        // 轨迹摘要：若上游已提供则不重复解析
        List<String> points = extractPoints(row.get("trailpoints"));
        if (!doc.containsKey("point_count")) {
            doc.put("point_count", points.size());
        }
        if (!doc.containsKey("route_sections") || !doc.containsKey("route_gantries")
                || !doc.containsKey("first_capture_time") || !doc.containsKey("last_capture_time")) {
            TrailSummary summary = summarize(points);
            if (!doc.containsKey("route_sections")) {
                doc.put("route_sections", summary.sections);
            }
            if (!doc.containsKey("route_gantries")) {
                doc.put("route_gantries", summary.gantries);
            }
            if (!doc.containsKey("first_capture_time") && summary.firstMillis != null) {
                doc.put("first_capture_time", summary.firstMillis);
            }
            if (!doc.containsKey("last_capture_time") && summary.lastMillis != null) {
                doc.put("last_capture_time", summary.lastMillis);
            }
        }
        return doc;
    }

    /**
     * 白名单复制 + 日期统一转 epoch millis（ES 模板使用 strict_date_optional_time||epoch_millis）。
     */
    private Map<String, Object> copyFields(Map<String, Object> row, Set<String> allowed) {
        Map<String, Object> doc = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : row.entrySet()) {
            String key = e.getKey();
            if (key == null || !allowed.contains(key)) {
                continue;
            }
            Object value = e.getValue();
            if (value == null) {
                continue;
            }
            if (DATE_FIELDS.contains(key)) {
                Long millis = toEpochMillis(value);
                if (millis != null) {
                    doc.put(key, millis);
                }
                continue;
            }
            if (value instanceof Array || value instanceof Object[] || value instanceof String[]) {
                continue;
            }
            doc.put(key, value);
        }
        return doc;
    }

    private Long toEpochMillis(Object value) {
        if (value instanceof Date) {
            return ((Date) value).getTime();
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        if (value instanceof CharSequence) {
            String s = value.toString().trim();
            if (s.isEmpty()) {
                return null;
            }
            try {
                if (s.length() >= 11 && s.charAt(10) == 'T') {
                    return OffsetDateTime.parse(s).toInstant().toEpochMilli();
                }
                if (s.length() >= 19 && s.charAt(4) == '-' && s.charAt(10) == ' ') {
                    return TrafficTimeUtils.parseDbTimestamp(s);
                }
                return Long.parseLong(s);
            } catch (DateTimeParseException | IllegalArgumentException ignored) {
                return null;
            }
        }
        return null;
    }

    /**
     * 从 JDBC 返回的 text[] 中提取元素。兼容 java.sql.Array、String[]、PG 数组字面量。
     */
    @SuppressWarnings("unchecked")
    private List<String> extractPoints(Object value) {
        List<String> points = new ArrayList<>();
        if (value == null) {
            return points;
        }
        try {
            Object arr = value;
            if (value instanceof Array) {
                arr = ((Array) value).getArray();
            }
            if (arr instanceof String[]) {
                points.addAll(Arrays.asList((String[]) arr));
            } else if (arr instanceof Object[]) {
                for (Object o : (Object[]) arr) {
                    if (o != null) {
                        points.add(String.valueOf(o));
                    }
                }
            } else if (arr instanceof String) {
                points.addAll(parsePgArrayLiteral((String) arr));
            }
        } catch (Exception e) {
            log.debug("[V3文档] trailpoints 解析失败，按空数组处理: {}", e.getMessage());
        }
        return points;
    }

    /**
     * 解析 PostgreSQL 数组字面量：{"{...}","{...}"}，元素内部可能有逗号/引号/转义。
     * 禁止 array_to_string 后再按逗号切分（设计 §5.8.1）。
     */
    private List<String> parsePgArrayLiteral(String literal) {
        List<String> result = new ArrayList<>();
        String s = literal.trim();
        if (s.isEmpty() || s.equals("{}") || s.equals("[]")) {
            return result;
        }
        if (s.startsWith("[")) {
            // 已经是 JSON 数组
            try {
                return JSON.parseArray(s, String.class);
            } catch (Exception ignored) {
                return result;
            }
        }
        if (s.startsWith("{")) {
            s = s.substring(1);
        }
        if (s.endsWith("}")) {
            s = s.substring(0, s.length() - 1);
        }
        StringBuilder current = new StringBuilder();
        boolean inQuote = false;
        boolean escaped = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (escaped) {
                current.append(c);
                escaped = false;
                continue;
            }
            if (c == '\\') {
                escaped = true;
                continue;
            }
            if (c == '"') {
                inQuote = !inQuote;
                continue;
            }
            if (c == ',' && !inQuote) {
                addIfNotBlank(result, current.toString());
                current.setLength(0);
                continue;
            }
            current.append(c);
        }
        addIfNotBlank(result, current.toString());
        return result;
    }

    private void addIfNotBlank(List<String> list, String value) {
        String v = value.trim();
        if (!v.isEmpty()) {
            list.add(v);
        }
    }

    private TrailSummary summarize(List<String> points) {
        TrailSummary summary = new TrailSummary();
        for (String point : points) {
            try {
                JSONObject json = JSON.parseObject(point);
                String sectionCode = json.getString("sectionCode");
                String orgCode = json.getString("orgCode");
                String locationId = json.getString("locationId");
                if (sectionCode != null && !sectionCode.isEmpty()) {
                    summary.sections.add(sectionCode);
                }
                if (locationId != null && !locationId.isEmpty()) {
                    summary.gantries.add(locationId);
                } else if (orgCode != null && !orgCode.isEmpty()) {
                    // 无 locationId 时以 orgCode 兜底，避免丢失组织维度
                    summary.gantries.add(orgCode);
                }
                Long millis = toEpochMillis(json.getString("captureTime"));
                if (millis != null) {
                    if (summary.firstMillis == null || millis < summary.firstMillis) {
                        summary.firstMillis = millis;
                    }
                    if (summary.lastMillis == null || millis > summary.lastMillis) {
                        summary.lastMillis = millis;
                    }
                }
            } catch (Exception ignored) {
                // 单点解析失败不影响整行；详情仍回 GaussDB
            }
        }
        return summary;
    }

    private String asString(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static class TrailSummary {
        private final Set<String> sections = new LinkedHashSet<>();
        private final Set<String> gantries = new LinkedHashSet<>();
        private Long firstMillis;
        private Long lastMillis;
    }
}
