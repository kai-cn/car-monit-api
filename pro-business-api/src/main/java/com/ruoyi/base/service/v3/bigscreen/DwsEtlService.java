package com.ruoyi.base.service.v3.bigscreen;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import javax.sql.DataSource;
import java.sql.Date;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 阶段一大屏预聚合 ETL：MySQL carmonitdb -> GaussDB jl_data01.dws_*。
 *
 * <p>设计最终由 Flink 承担；本服务用于初始化/对账补偿的批量回填，按 stat_date 整体重算，
 * 幂等可重跑。MySQL 是业务表事实源，GaussDB 是查询侧 DWS。</p>
 */
@Slf4j
@Service
public class DwsEtlService {

    private final JdbcTemplate gaussJdbc;
    private final TransactionTemplate transactionTemplate;
    private final TrafficV3Properties properties;
    private final AtomicBoolean running = new AtomicBoolean(false);

    public DwsEtlService(DataSource dataSource, TrafficV3Properties properties) {
        this.gaussJdbc = new JdbcTemplate(dataSource);
        this.gaussJdbc.setQueryTimeout(60);
        this.transactionTemplate = new TransactionTemplate(new DataSourceTransactionManager(dataSource));
        this.properties = properties;
    }

    @Scheduled(fixedDelayString = "${traffic.bigscreen.etl.interval-ms:600000}")
    public void scheduled() {
        TrafficV3Properties.BigScreen.Etl etl = properties.getBigscreen().getEtl();
        if (etl == null || !etl.isEnabled()) {
            return;
        }
        if (!properties.getBigscreen().isStatsEnabled()) {
            return;
        }
        long end = System.currentTimeMillis();
        long start = end - TimeUnit.DAYS.toMillis(Math.max(1, etl.getLookbackDays()));
        try {
            backfillMillis(start, end);
        } catch (Exception e) {
            log.error("[V3 DWS ETL] 定时回填失败: {}", e.getMessage());
        }
    }

    public Map<String, Object> backfill(String startTime, String endTime) {
        long end = endTime == null || endTime.trim().isEmpty()
                ? System.currentTimeMillis() : TrafficTimeUtils.parse(endTime, true);
        long start = startTime == null || startTime.trim().isEmpty()
                ? end - TimeUnit.DAYS.toMillis(30) : TrafficTimeUtils.parse(startTime, false);
        return backfillMillis(start, end);
    }

    public synchronized Map<String, Object> backfillMillis(long startMillis, long endMillis) {
        if (!running.compareAndSet(false, true)) {
            throw new IllegalStateException("DWS ETL 正在执行，请稍后重试");
        }
        long t0 = System.currentTimeMillis();
        try {
            TrafficV3Properties.BigScreen.Etl etl = properties.getBigscreen().getEtl();
            if (etl == null || !etl.isEnabled()) {
                throw new IllegalStateException("DWS ETL 未启用（traffic.bigscreen.etl.enabled=false）");
            }
            if (startMillis >= endMillis) {
                throw new IllegalArgumentException("startTime 必须早于 endTime");
            }

            DriverManagerDataSource mysql = new DriverManagerDataSource(
                    etl.getMysqlUrl(), etl.getUsername(), etl.getPassword());
            mysql.setDriverClassName("com.mysql.cj.jdbc.Driver");
            JdbcTemplate mysqlJdbc = new JdbcTemplate(mysql);
            mysqlJdbc.setQueryTimeout(30);

            Timestamp startTs = TrafficTimeUtils.toDbTimestamp(startMillis);
            Timestamp endTs = TrafficTimeUtils.toDbTimestamp(endMillis);

            // 1. 逃费日汇总
            List<Map<String, Object>> escapeRows = mysqlJdbc.queryForList(
                    "SELECT DATE(create_time) stat_date, COALESCE(CAST(eps_id AS CHAR), '') org_id, "
                            + "escaped_type, COUNT(*) cnt, COALESCE(SUM(dif_amount), 0) amount, "
                            + "COUNT(DISTINCT car_no) car_cnt "
                            + "FROM car_except_record "
                            + "WHERE del_flag = '0' AND create_time >= ? AND create_time < ? "
                            + "GROUP BY DATE(create_time), COALESCE(CAST(eps_id AS CHAR), ''), escaped_type",
                    startTs, endTs);

            // 2. 堵漏增收日汇总（car_confim_free + car_aduit_free；query_type 阶段一统一 suo）
            List<Map<String, Object>> incomeRows = mysqlJdbc.queryForList(
                    "SELECT DATE(create_time) stat_date, COALESCE(org_id, '') org_id, "
                            + "COALESCE(MAX(org_name), '') org_name, "
                            + "COALESCE(SUM(amount), 0) amount, COUNT(DISTINCT car_no) car_cnt "
                            + "FROM ("
                            + "  SELECT create_time, org_id, org_name, "
                            + "         COALESCE(amount, 0) + COALESCE(aduit_amount, 0) amount, car_no "
                            + "  FROM car_confim_free "
                            + "  WHERE del_flag = '0' AND status = '0' AND create_time >= ? AND create_time < ? "
                            + "  UNION ALL "
                            + "  SELECT create_time, org_id, org_name, COALESCE(amount, 0) amount, car_no "
                            + "  FROM car_aduit_free "
                            + "  WHERE del_flag = '0' AND status = '0' AND create_time >= ? AND create_time < ? "
                            + ") t "
                            + "GROUP BY DATE(create_time), COALESCE(org_id, '')",
                    startTs, endTs, startTs, endTs);

            // 3. 路段预警日汇总
            List<Map<String, Object>> warningRows = mysqlJdbc.queryForList(
                    "SELECT DATE(gantry_time) stat_date, COALESCE(road_code, '') road_code, "
                            + "COALESCE(section_code, '') section_code, COUNT(*) warning_cnt "
                            + "FROM car_warning_info "
                            + "WHERE del_flag = '0' AND gantry_time >= ? AND gantry_time < ? "
                            + "GROUP BY DATE(gantry_time), COALESCE(road_code, ''), COALESCE(section_code, '')",
                    startTs, endTs);

            // 4. 幂等重算：只删本次实际算出的 stat_date，删除+写入放在同一事务。
            //    若源表已归档/查询返回空，不执行任何 DELETE，避免误删 DWS 历史。
            List<Object[]> escapeArgs = new ArrayList<>();
            for (Map<String, Object> row : escapeRows) {
                escapeArgs.add(new Object[]{
                        toDate(row.get("stat_date")), str(row.get("org_id")), str(row.get("escaped_type")),
                        toLong(row.get("cnt")), toDecimal(row.get("amount")), toLong(row.get("car_cnt"))
                });
            }

            List<Object[]> incomeArgs = new ArrayList<>();
            for (Map<String, Object> row : incomeRows) {
                incomeArgs.add(new Object[]{
                        toDate(row.get("stat_date")), str(row.get("org_id")), str(row.get("org_name")),
                        "suo", toDecimal(row.get("amount")), toLong(row.get("car_cnt"))
                });
            }

            List<Object[]> warningArgs = new ArrayList<>();
            for (Map<String, Object> row : warningRows) {
                warningArgs.add(new Object[]{
                        toDate(row.get("stat_date")), str(row.get("road_code")), str(row.get("section_code")),
                        toLong(row.get("warning_cnt"))
                });
            }

            Set<Date> escapeDates = statDates(escapeRows);
            Set<Date> incomeDates = statDates(incomeRows);
            Set<Date> warningDates = statDates(warningRows);

            transactionTemplate.execute(status -> {
                deleteByDates("dws_escape_daily", escapeDates);
                deleteByDates("dws_income_daily", incomeDates);
                deleteByDates("dws_warning_section_daily", warningDates);

                if (!escapeArgs.isEmpty()) {
                    gaussJdbc.batchUpdate("INSERT INTO jl_data01.dws_escape_daily "
                            + "(stat_date, org_id, escaped_type, cnt, amount, car_cnt) VALUES (?, ?, ?, ?, ?, ?)",
                            escapeArgs);
                }
                if (!incomeArgs.isEmpty()) {
                    gaussJdbc.batchUpdate("INSERT INTO jl_data01.dws_income_daily "
                            + "(stat_date, org_id, org_name, query_type, amount, car_cnt) VALUES (?, ?, ?, ?, ?, ?)",
                            incomeArgs);
                }
                if (!warningArgs.isEmpty()) {
                    gaussJdbc.batchUpdate("INSERT INTO jl_data01.dws_warning_section_daily "
                            + "(stat_date, road_code, section_code, warning_cnt) VALUES (?, ?, ?, ?)",
                            warningArgs);
                }
                return null;
            });

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("escapeRows", escapeRows.size());
            result.put("incomeRows", incomeRows.size());
            result.put("warningRows", warningRows.size());
            result.put("costMs", System.currentTimeMillis() - t0);
            log.info("[V3 DWS ETL] 完成: {}", result);
            return result;
        } catch (IllegalArgumentException | IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("DWS ETL 失败: " + e.getMessage(), e);
        } finally {
            running.set(false);
        }
    }

    private Date toDate(Object value) {
        if (value instanceof java.util.Date) {
            return TrafficTimeUtils.toDbDate(((java.util.Date) value).getTime());
        }
        String s = String.valueOf(value);
        if (s.length() >= 10 && s.charAt(4) == '-') {
            // MySQL DATE 以字符串返回时，只取日历日，不做时区换算
            return Date.valueOf(s.substring(0, 10));
        }
        return TrafficTimeUtils.toDbDate(Long.parseLong(s));
    }

    /** 本次实际算出的 stat_date 集合（去重、保持顺序）。 */
    private Set<Date> statDates(List<Map<String, Object>> rows) {
        Set<Date> dates = new LinkedHashSet<>();
        for (Map<String, Object> row : rows) {
            Object value = row.get("stat_date");
            if (value != null) {
                dates.add(toDate(value));
            }
        }
        return dates;
    }

    /** 只删除本次重算覆盖到的日期；空集合不做任何删除。 */
    private void deleteByDates(String table, Set<Date> dates) {
        for (Date date : dates) {
            gaussJdbc.update("DELETE FROM jl_data01." + table + " WHERE stat_date = ?", date);
        }
    }

    private String str(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private Long toLong(Object value) {
        if (value == null) {
            return 0L;
        }
        return ((Number) value).longValue();
    }

    private java.math.BigDecimal toDecimal(Object value) {
        if (value == null) {
            return java.math.BigDecimal.ZERO;
        }
        return value instanceof java.math.BigDecimal
                ? (java.math.BigDecimal) value : new java.math.BigDecimal(String.valueOf(value));
    }
}
