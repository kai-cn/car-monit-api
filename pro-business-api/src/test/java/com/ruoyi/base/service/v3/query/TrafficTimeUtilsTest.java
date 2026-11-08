package com.ruoyi.base.service.v3.query;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.TimeZone;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * P2-1 自证：JDBC 时间窗不依赖 JVM 默认时区。
 * 在 JVM 默认 UTC（容器常见配置）下，绑定值仍必须是上海本地墙钟。
 */
class TrafficTimeUtilsTest {

    @Test
    void dbTimestampKeepsShanghaiWallClockWhenJvmDefaultIsUtc() {
        TimeZone original = TimeZone.getDefault();
        TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
        try {
            long millis = TrafficTimeUtils.parse("2026-01-01 00:00:00", false);
            LocalDateTime bound = TrafficTimeUtils.toDbTimestamp(millis).toLocalDateTime();
            assertEquals(LocalDateTime.of(2026, 1, 1, 0, 0), bound);
            assertEquals("2026-01-01", TrafficTimeUtils.toDbDate(millis).toString());
            assertEquals(millis, TrafficTimeUtils.parseDbTimestamp("2026-01-01 00:00:00"));
        } finally {
            TimeZone.setDefault(original);
        }
    }
}
