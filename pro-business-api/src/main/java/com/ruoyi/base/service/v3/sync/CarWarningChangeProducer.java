package com.ruoyi.base.service.v3.sync;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * car_warning_info 变更采集（生产首选 Debezium CDC；阶段一实现按 update_time 增量扫描，
 * 写入 GaussDB search_sync_outbox，由 OutboxRelay 发 Kafka search-sync，最终由
 * SearchSyncConsumer 路由到 CarWarningIndexWriter）。
 *
 * <p>只扫描 MySQL carmonitdb.car_warning_info，按 update_time 水位推进；del_flag=1 视为删除事件。
 * 不修改源表，不由 API 业务代码双写 ES。</p>
 */
@Slf4j
@Service
public class CarWarningChangeProducer {

    private static final String TABLE_NAME = "carmonitdb.car_warning_info";
    private static final String CHECKPOINT_TABLE = "carmonitdb.car_warning_info";

    private final JdbcTemplate gaussJdbc;
    private final TrafficV3Properties properties;
    private final AtomicBoolean running = new AtomicBoolean(false);

    public CarWarningChangeProducer(DataSource dataSource, TrafficV3Properties properties) {
        this.gaussJdbc = new JdbcTemplate(dataSource);
        this.gaussJdbc.setQueryTimeout(30);
        this.properties = properties;
    }

    @Scheduled(fixedDelayString = "${traffic.sync.car-warning-poll-interval-ms:30000}")
    public void scheduled() {
        TrafficV3Properties.Sync sync = properties.getSync();
        if (!sync.isEnabled() || !sync.isCarWarningEnabled()) {
            return;
        }
        try {
            poll();
        } catch (Exception e) {
            log.error("[V3预警CDC] 定时采集失败: {}", e.getMessage());
        }
    }

    /**
     * 手动/定时触发增量采集，返回新增 outbox 事件数。
     */
    public Map<String, Object> poll() {
        if (!running.compareAndSet(false, true)) {
            throw new IllegalStateException("car-warning 变更采集正在执行");
        }
        long t0 = System.currentTimeMillis();
        try {
            TrafficV3Properties.BigScreen.Etl etl = properties.getBigscreen().getEtl();
            if (etl == null || !etl.isEnabled()) {
                throw new IllegalStateException("MySQL 连接未启用（traffic.bigscreen.etl.enabled=false）");
            }
            DriverManagerDataSource mysql = new DriverManagerDataSource(
                    etl.getMysqlUrl(), etl.getUsername(), etl.getPassword());
            mysql.setDriverClassName("com.mysql.cj.jdbc.Driver");
            JdbcTemplate mysqlJdbc = new JdbcTemplate(mysql);
            mysqlJdbc.setQueryTimeout(30);

            Timestamp watermark = loadWatermark();
            if (watermark == null) {
                watermark = TrafficTimeUtils.toDbTimestamp(System.currentTimeMillis()
                        - TimeUnit.DAYS.toMillis(Math.max(1, properties.getSync().getCarWarningLookbackDays())));
            }
            Timestamp now = TrafficTimeUtils.toDbTimestamp(System.currentTimeMillis());

            List<Map<String, Object>> rows = mysqlJdbc.queryForList(
                    "SELECT t.*, c.plate_color AS plate_color, c.escaped_type AS escaped_type, "
                            + "c.escaped_amount AS escaped_amount "
                            + "FROM car_warning_info t "
                            + "LEFT JOIN car_info c ON c.id = t.car_id AND c.del_flag = '0' "
                            + "WHERE t.update_time >= ? AND t.update_time < ? "
                            + "ORDER BY t.update_time, t.id LIMIT ?",
                    watermark, now, Math.max(1, properties.getSync().getBatchSize()));

            List<Object[]> outboxArgs = new ArrayList<>();
            Timestamp maxTime = watermark;
            for (Map<String, Object> row : rows) {
                Object id = row.get("id");
                if (id == null) {
                    continue;
                }
                Timestamp updateTime = toTimestamp(row.get("update_time"));
                if (updateTime == null) {
                    updateTime = toTimestamp(row.get("gantry_time"));
                }
                if (updateTime == null) {
                    updateTime = now;
                }
                if (updateTime.after(maxTime)) {
                    maxTime = updateTime;
                }
                String op = "1".equals(String.valueOf(row.get("del_flag"))) ? "D" : "I";
                outboxArgs.add(new Object[]{
                        UUID.randomUUID().toString().replace("-", ""),
                        TABLE_NAME,
                        String.valueOf(id),
                        op,
                        updateTime,
                        JSON.toJSONString(row)
                });
            }

            if (!outboxArgs.isEmpty()) {
                gaussJdbc.batchUpdate("INSERT INTO jl_data01.search_sync_outbox "
                        + "(event_id, table_name, pk, op, event_time, payload, status) "
                        + "VALUES (?, ?, ?, ?, ?, ?, 'PENDING')", outboxArgs);
                saveWatermark(maxTime);
            }

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("fetched", rows.size());
            result.put("outboxInserted", outboxArgs.size());
            result.put("watermark", maxTime);
            result.put("costMs", System.currentTimeMillis() - t0);
            log.info("[V3预警CDC] 采集完成: {}", result);
            return result;
        } finally {
            running.set(false);
        }
    }

    private Timestamp loadWatermark() {
        try {
            return gaussJdbc.queryForObject("SELECT last_event_time FROM jl_data01.search_sync_checkpoint "
                    + "WHERE table_name = ?", Timestamp.class, CHECKPOINT_TABLE);
        } catch (Exception e) {
            return null;
        }
    }

    private void saveWatermark(Timestamp time) {
        try {
            // openGauss 3.0 不支持 ON CONFLICT，先 UPDATE 再 INSERT
            int updated = gaussJdbc.update("UPDATE jl_data01.search_sync_checkpoint "
                            + "SET last_event_time = ?, updated_at = now() WHERE table_name = ?",
                    time, CHECKPOINT_TABLE);
            if (updated == 0) {
                gaussJdbc.update("INSERT INTO jl_data01.search_sync_checkpoint "
                                + "(table_name, last_event_id, last_event_time, updated_at) "
                                + "VALUES (?, ?, ?, now())",
                        CHECKPOINT_TABLE, null, time);
            }
        } catch (Exception e) {
            log.warn("[V3预警CDC] 保存水位失败: {}", e.getMessage());
        }
    }

    private Timestamp toTimestamp(Object value) {
        if (value instanceof Timestamp) {
            return (Timestamp) value;
        }
        if (value instanceof java.util.Date) {
            return TrafficTimeUtils.toDbTimestamp(((java.util.Date) value).getTime());
        }
        return null;
    }
}
