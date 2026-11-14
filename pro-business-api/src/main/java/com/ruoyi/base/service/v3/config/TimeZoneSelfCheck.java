package com.ruoyi.base.service.v3.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.time.Instant;
import java.time.ZoneId;
import java.util.TimeZone;

/**
 * P2-1 时区自检：启动时把 JVM 默认时区对齐到业务时区，并打印实际生效值。
 *
 * <p>查询侧固定 {@code Asia/Shanghai}，但 {@code new Timestamp(millis)} /
 * {@code new java.sql.Date(millis)} 的 JDBC 绑定依赖 JVM 默认时区。
 * 容器基础镜像通常为 UTC，若不显式对齐，导出/回灌/对账的时间窗会整体偏 8 小时。
 * 本类只做“默认时区对齐 + 自检日志”，具体时间窗仍由
 * {@code TrafficTimeUtils.toDbTimestamp/toDbDate} 显式转换。</p>
 */
@Slf4j
@Component
public class TimeZoneSelfCheck {

    private final TrafficV3Properties properties;

    public TimeZoneSelfCheck(TrafficV3Properties properties) {
        this.properties = properties;
    }

    @PostConstruct
    public void init() {
        String configured = properties.getTimezone();
        if (configured == null || configured.trim().isEmpty()) {
            configured = "Asia/Shanghai";
        }
        String before = TimeZone.getDefault().getID();
        try {
            TimeZone.setDefault(TimeZone.getTimeZone(ZoneId.of(configured.trim())));
        } catch (Exception e) {
            log.error("[V3时区] 配置值非法，保留 JVM 默认时区: configured={}, before={}", configured, before);
            return;
        }
        TimeZone now = TimeZone.getDefault();
        log.info("[V3时区] 自检: configured={}, before={}, after={}, user.timezone={}, "
                        + "Asia/Shanghai now={}, UTC now={}",
                configured, before, now.getID(), System.getProperty("user.timezone"),
                java.time.LocalDateTime.ofInstant(Instant.now(), ZoneId.of("Asia/Shanghai")),
                java.time.LocalDateTime.ofInstant(Instant.now(), ZoneId.of("UTC")));
        if (!"Asia/Shanghai".equals(now.getID())) {
            log.warn("[V3时区] JVM 默认时区与查询侧 Asia/Shanghai 不一致（after={}），"
                    + "JDBC 时间窗将走显式转换，请确认数据库会话时区", now.getID());
        }
    }
}
