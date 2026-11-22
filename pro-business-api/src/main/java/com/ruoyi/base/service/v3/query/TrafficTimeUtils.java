package com.ruoyi.base.service.v3.query;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.List;

/**
 * V3 查询时间解析：统一 Asia/Shanghai，兼容旧接口的 yyyy-MM-dd HH:mm:ss。
 */
public final class TrafficTimeUtils {

    public static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");

    private static final List<DateTimeFormatter> DATE_TIME_FORMATS = Arrays.asList(
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss"),
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"),
            DateTimeFormatter.ISO_LOCAL_DATE_TIME
    );

    private TrafficTimeUtils() {
    }

    /**
     * 解析时间字符串为 epoch millis。
     *
     * @param value    时间字符串；纯数字按 epoch millis
     * @param endOfDay 仅日期格式时是否取当天 23:59:59.999
     */
    public static Long parse(String value, boolean endOfDay) {
        if (value == null || value.trim().isEmpty()) {
            return null;
        }
        String s = value.trim();
        try {
            if (s.matches("\\d{10,13}")) {
                long v = Long.parseLong(s);
                return s.length() == 10 ? v * 1000L : v;
            }
            for (DateTimeFormatter f : DATE_TIME_FORMATS) {
                try {
                    LocalDateTime dt = LocalDateTime.parse(s, f);
                    return dt.atZone(ZONE).toInstant().toEpochMilli();
                } catch (Exception ignored) {
                    // 尝试下一个格式
                }
            }
            LocalDate date = LocalDate.parse(s);
            LocalDateTime dt = endOfDay
                    ? date.atTime(23, 59, 59, 999_000_000)
                    : date.atStartOfDay();
            return dt.atZone(ZONE).toInstant().toEpochMilli();
        } catch (Exception e) {
            throw TrafficQueryException.badRequest("无法解析时间: " + value
                    + "，支持 yyyy-MM-dd HH:mm:ss / yyyy-MM-dd / epoch millis");
        }
    }

    public static String format(long millis) {
        return LocalDateTime.ofInstant(Instant.ofEpochMilli(millis), ZONE)
                .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }

    /**
     * epoch millis -> JDBC timestamp（显式按 Asia/Shanghai 解释）。
     *
     * <p>{@code new Timestamp(millis)} 依赖 JVM 默认时区；容器默认 UTC 时，
     * 绑定到 GaussDB {@code timestamp without time zone} 会整体偏 8 小时。
     * 这里先把毫秒解释成上海本地时间，再交给驱动，保证时间窗与查询侧口径一致。</p>
     */
    public static java.sql.Timestamp toDbTimestamp(long millis) {
        return java.sql.Timestamp.valueOf(
                LocalDateTime.ofInstant(Instant.ofEpochMilli(millis), ZONE));
    }

    /** epoch millis -> java.sql.Date（按 Asia/Shanghai 的日历日）。 */
    public static java.sql.Date toDbDate(long millis) {
        return java.sql.Date.valueOf(Instant.ofEpochMilli(millis).atZone(ZONE).toLocalDate());
    }

    /**
     * 解析数据库返回的时间字符串为 epoch millis（显式 Asia/Shanghai）。
     * 支持 {@code yyyy-MM-dd HH:mm:ss[.SSSSSS]}、ISO 与纯数字 epoch。
     */
    public static Long parseDbTimestamp(String value) {
        if (value == null || value.trim().isEmpty()) {
            return null;
        }
        String s = value.trim();
        if (s.matches("\\d{10,13}")) {
            long v = Long.parseLong(s);
            return s.length() == 10 ? v * 1000L : v;
        }
        try {
            if (s.length() >= 11 && s.charAt(10) == 'T') {
                return OffsetDateTime.parse(s).toInstant().toEpochMilli();
            }
            for (DateTimeFormatter f : DATE_TIME_FORMATS) {
                try {
                    return LocalDateTime.parse(s, f).atZone(ZONE).toInstant().toEpochMilli();
                } catch (Exception ignored) {
                    // 尝试下一个格式
                }
            }
            // 通过 Timestamp.valueOf 兜底（分秒与纳秒分隔符差异）
            return java.sql.Timestamp.valueOf(s).toLocalDateTime()
                    .atZone(ZONE).toInstant().toEpochMilli();
        } catch (Exception e) {
            return null;
        }
    }
}
