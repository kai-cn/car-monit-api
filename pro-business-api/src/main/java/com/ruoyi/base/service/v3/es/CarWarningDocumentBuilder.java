package com.ruoyi.base.service.v3.es;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.util.Arrays;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * car_warning_info 行 -> car-warning ES 文档。
 *
 * <p>严格遵循 car-warning 模板：只输出模板声明字段；track_josn 不入索引/不写 source；
 * 日期统一转 epoch millis。</p>
 */
@Slf4j
@Component
public class CarWarningDocumentBuilder {

    private static final Set<String> ALLOWED_FIELDS = new HashSet<>(Arrays.asList(
            "id", "car_id", "car_no", "car_type", "car_vehicle", "car_num",
            "in_station_id", "in_station", "in_time", "gantry_station_id", "gantryt_station",
            "gantry_code", "gantry_time", "file_ids", "next_pass_time", "next_pass_type",
            "next_pass_address", "next_pass_longitude", "next_pass_latitude",
            "road_code", "road_name", "section_code", "section_name", "toll_code", "fwqbm",
            "track_id", "track_names", "back_col1", "back_col2", "status",
            "escaped_type", "escaped_amount", "plate_color", "create_time", "update_time", "del_flag"
    ));

    private static final Set<String> DATE_FIELDS = new HashSet<>(Arrays.asList(
            "in_time", "gantry_time", "next_pass_time", "create_time", "update_time"));

    private static final Set<String> CAPTURE_TYPES = new HashSet<>(Arrays.asList(
            "StationCapture", "GantryCapture", "ServiceAreaCapture"));

    public Map<String, Object> build(Map<String, Object> row) {
        Map<String, Object> doc = new LinkedHashMap<>();
        if (row == null) {
            return doc;
        }
        for (Map.Entry<String, Object> entry : row.entrySet()) {
            String key = entry.getKey();
            if (!ALLOWED_FIELDS.contains(key)) {
                continue;
            }
            Object value = entry.getValue();
            if (value == null) {
                continue;
            }
            if (DATE_FIELDS.contains(key)) {
                Long millis = toMillis(value);
                if (millis != null) {
                    doc.put(key, millis);
                }
                continue;
            }
            doc.put(key, value);
        }
        // 派生抓拍类型：car-warning 索引没有独立列，需要可从 track_names 前缀或维度列推断
        String captureType = deriveCaptureType(row);
        if (captureType != null) {
            doc.put("capture_type", captureType);
        }
        return doc;
    }

    /**
     * 抓拍类型：优先 track_names 的首段 "Type:code"；否则按维度列推断。
     */
    private String deriveCaptureType(Map<String, Object> row) {
        Object trackNames = row.get("track_names");
        if (trackNames != null) {
            String text = String.valueOf(trackNames).trim();
            if (!text.isEmpty()) {
                int colon = text.indexOf(':');
                int comma = text.indexOf(',');
                if (colon > 0 && (comma < 0 || colon < comma)) {
                    String type = text.substring(0, colon).trim();
                    if (CAPTURE_TYPES.contains(type)) {
                        return type;
                    }
                }
            }
        }
        if (hasText(row.get("in_station_id"))) {
            return "StationCapture";
        }
        if (hasText(row.get("gantry_station_id")) || hasText(row.get("gantry_code"))) {
            return "GantryCapture";
        }
        if (hasText(row.get("fwqbm"))) {
            return "ServiceAreaCapture";
        }
        return null;
    }

    private boolean hasText(Object value) {
        return value != null && !String.valueOf(value).trim().isEmpty();
    }

    public String docId(Map<String, Object> row) {
        Object id = row == null ? null : row.get("id");
        return id == null ? null : String.valueOf(id);
    }

    private Long toMillis(Object value) {
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
                if (s.length() >= 19 && s.charAt(4) == '-' && s.charAt(10) == ' ') {
                    return Timestamp.valueOf(s).getTime();
                }
                return Long.parseLong(s);
            } catch (Exception e) {
                log.debug("[V3预警] 日期解析失败: {}", value);
                return null;
            }
        }
        return null;
    }
}
