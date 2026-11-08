package com.ruoyi.base.service.v3.query;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
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
}
