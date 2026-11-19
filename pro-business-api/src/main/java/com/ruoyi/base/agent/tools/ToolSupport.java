package com.ruoyi.base.agent.tools;

import com.ruoyi.base.agent.core.AgentException;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 工具层通用约束：时间窗、分页上限、车牌脱敏、结果截断。
 *
 * <p>这些约束必须由服务端执行，不能依赖提示词；模型可以“请求”，但不能“决定”越界。</p>
 */
public final class ToolSupport {

    private ToolSupport() {
    }

    public static Long parseTime(String value, boolean endOfDay) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return TrafficTimeUtils.parse(value, endOfDay);
    }

    public static long resolveStart(Long start, long end, Duration defaultWindow) {
        return start != null ? start : end - defaultWindow.toMillis();
    }

    public static void validateWindow(long start, long end, Duration maxWindow, String label) {
        if (end <= start) {
            throw AgentException.badRequest("结束时间必须晚于开始时间");
        }
        if (end - start > maxWindow.toMillis()) {
            throw AgentException.badRequest(label + "时间范围不能超过 " + human(maxWindow));
        }
    }

    public static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    /**
     * 车牌脱敏：保留前 2 位与后 2 位。稽查/管理员角色可看全量（由调用方决定）。
     */
    public static String maskPlate(String plate, boolean allowFull) {
        if (plate == null || plate.isBlank() || allowFull) {
            return plate;
        }
        String v = plate.trim();
        if (v.length() <= 4) {
            return v.charAt(0) + "***";
        }
        return v.substring(0, 2) + "***" + v.substring(v.length() - 2);
    }

    /** 对行内车牌类字段做脱敏，字段名覆盖三张表的车牌口径。 */
    public static Map<String, Object> maskRow(Map<String, Object> row, boolean allowFull) {
        if (row == null || allowFull) {
            return row;
        }
        Map<String, Object> copy = new LinkedHashMap<>(row);
        for (Map.Entry<String, Object> e : copy.entrySet()) {
            String key = e.getKey().toLowerCase();
            if ((key.contains("plate") || key.equals("envehicleid") || key.equals("exvehicleid"))
                    && e.getValue() instanceof String s && !s.isBlank()) {
                e.setValue(maskPlate(s, false));
            }
        }
        return copy;
    }

    public static String truncate(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max) + "...(truncated)";
    }

    public static Map<String, Object> ok() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ok", true);
        return m;
    }

    public static Map<String, Object> error(String code, String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ok", false);
        m.put("errorCode", code);
        m.put("message", message);
        return m;
    }

    public static Map<String, Object> limitList(List<?> list, int max) {
        Map<String, Object> m = new LinkedHashMap<>();
        int size = list == null ? 0 : list.size();
        m.put("count", size);
        m.put("truncated", size > max);
        m.put("items", list == null ? new ArrayList<>() : new ArrayList<>(list.subList(0, Math.min(size, max))));
        return m;
    }

    public static String human(Duration d) {
        long minutes = d.toMinutes();
        if (minutes % 1440 == 0) {
            return (minutes / 1440) + " 天";
        }
        if (minutes % 60 == 0) {
            return (minutes / 60) + " 小时";
        }
        return minutes + " 分钟";
    }
}
