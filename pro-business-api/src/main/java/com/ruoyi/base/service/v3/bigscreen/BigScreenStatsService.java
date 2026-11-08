package com.ruoyi.base.service.v3.bigscreen;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 大屏预聚合查询（读 dws_*，不直连 backend 业务表）。
 *
 * <p>契约：返回裸 JSON（不带 code/data 包装），字段名与 backend VO 一致；
 * 未启用/表缺失时抛 503，由 backend hybrid 模式回退 legacy。</p>
 *
 * <p>口径说明：dws_* 由 Flink/ETL 从业务表派生；`car_cnt` 为按日去重近似值，
 * 跨日求和不是精确 distinct（设计允许 HLL/近似，误差 1–2%）。</p>
 */
@Slf4j
@Service
public class BigScreenStatsService {

    private static final Map<String, String> ESCAPED_TYPE_NAMES = new LinkedHashMap<>();

    static {
        ESCAPED_TYPE_NAMES.put("10", "入口少轴");
        ESCAPED_TYPE_NAMES.put("20", "屏蔽通行介质");
        ESCAPED_TYPE_NAMES.put("30", "货车客标");
        ESCAPED_TYPE_NAMES.put("40", "有入无出");
        ESCAPED_TYPE_NAMES.put("50", "大车小标");
        ESCAPED_TYPE_NAMES.put("60", "假冒其他优免车");
    }

    private static final int MAX_RANGE_DAYS = 365;

    private final JdbcTemplate jdbc;
    private final TrafficV3Properties properties;

    public BigScreenStatsService(DataSource dataSource, TrafficV3Properties properties) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(Math.max(1, properties.getBigscreen().getQueryTimeoutMs() / 1000));
        this.properties = properties;
    }

    /**
     * 逃费类型统计（对应 backend CarStatisticsVO）。
     */
    public List<BigScreenStatVo.Escape> escape(String startDate, String endDate,
                                              String orgId, String escapedType) {
        assertEnabled();
        LocalDate[] range = dateRange(startDate, endDate, 7);

        StringBuilder sql = new StringBuilder()
                .append("SELECT escaped_type, coalesce(sum(amount), 0) amount, ")
                .append("coalesce(sum(car_cnt), 0) car_cnt ")
                .append("FROM jl_data01.dws_escape_daily ")
                .append("WHERE stat_date >= ? AND stat_date < ?");
        List<Object> args = new ArrayList<>();
        args.add(range[0]);
        args.add(range[1]);
        if (notBlank(orgId)) {
            sql.append(" AND org_id = ?");
            args.add(orgId.trim());
        }
        if (notBlank(escapedType)) {
            sql.append(" AND escaped_type = ?");
            args.add(escapedType.trim());
        }
        sql.append(" GROUP BY escaped_type");

        Map<String, BigScreenStatVo.Escape> rows = new LinkedHashMap<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList(sql.toString(), args.toArray())) {
                String type = String.valueOf(row.get("escaped_type"));
                BigScreenStatVo.Escape vo = new BigScreenStatVo.Escape();
                vo.setEscapedType(type);
                vo.setEscapedTypeName(ESCAPED_TYPE_NAMES.getOrDefault(type, type));
                vo.setNumber(toInt(row.get("car_cnt")));
                vo.setEscapedAmount(toBigDecimal(row.get("amount")));
                rows.put(type, vo);
            }
        } catch (Exception e) {
            throw unavailable("逃费统计", e);
        }

        // 与 legacy 口径对齐：即使某类型无数据也返回 0，按固定字典顺序输出
        List<BigScreenStatVo.Escape> result = new ArrayList<>();
        for (Map.Entry<String, String> entry : ESCAPED_TYPE_NAMES.entrySet()) {
            BigScreenStatVo.Escape vo = rows.get(entry.getKey());
            if (vo == null) {
                vo = new BigScreenStatVo.Escape();
                vo.setEscapedType(entry.getKey());
                vo.setEscapedTypeName(entry.getValue());
            }
            result.add(vo);
        }
        for (Map.Entry<String, BigScreenStatVo.Escape> entry : rows.entrySet()) {
            if (!ESCAPED_TYPE_NAMES.containsKey(entry.getKey())) {
                result.add(entry.getValue());
            }
        }
        return result;
    }

    /**
     * 追缴统计（对应 backend CarAuditVO）。
     *
     * <p>total = dws_escape_daily（应追缴口径）；finished = dws_income_daily（已完成/已补缴口径）。
     * 精确 distinct 车牌数需上游 HLL/精确去重；此处按日 car_cnt 求和，属近似值。</p>
     */
    public BigScreenStatVo.Audit audit(String startDate, String endDate) {
        assertEnabled();
        LocalDate[] range = dateRange(startDate, endDate, 7);
        BigScreenStatVo.Audit vo = new BigScreenStatVo.Audit();
        try {
            Map<String, Object> total = querySum("dws_escape_daily", "amount", "car_cnt", range);
            vo.setTotalAmount(toBigDecimal(total.get("amount")));
            vo.setTotalCount(toInt(total.get("car_cnt")));

            Map<String, Object> finished = querySum("dws_income_daily", "amount", "car_cnt", range);
            vo.setFinishedAmount(toBigDecimal(finished.get("amount")));
            vo.setFinishedCount(toInt(finished.get("car_cnt")));
        } catch (Exception e) {
            throw unavailable("追缴统计", e);
        }
        return vo;
    }

    /**
     * 堵漏增收（对应 backend incomeStatisticVO）。
     */
    public List<BigScreenStatVo.Income> income(String queryDateType, String startDate,
                                              String applyTime1, String applyTime2) {
        assertEnabled();
        String type = notBlank(queryDateType) ? queryDateType.trim() : "suo";
        LocalDate[] range = incomeRange(startDate, applyTime1, applyTime2);

        List<Object> args = new ArrayList<>();
        args.add(range[0]);
        args.add(range[1]);
        args.add(type);

        List<Map<String, Object>> rows;
        try {
            rows = jdbc.queryForList("SELECT coalesce(i.org_name, i.org_id) org_name, "
                            + "coalesce(sum(i.amount), 0) amount, coalesce(sum(i.car_cnt), 0) car_num "
                            + "FROM jl_data01.dws_income_daily i "
                            + "WHERE i.stat_date >= ? AND i.stat_date < ? AND i.query_type = ? "
                            + "GROUP BY coalesce(i.org_name, i.org_id) ORDER BY amount DESC",
                    args.toArray());
        } catch (Exception e) {
            throw unavailable("堵漏增收", e);
        }

        List<BigScreenStatVo.Income> result = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            BigScreenStatVo.Income vo = new BigScreenStatVo.Income();
            vo.setOrgName(row.get("org_name") == null ? "" : String.valueOf(row.get("org_name")));
            vo.setAmount(toBigDecimal(row.get("amount")));
            vo.setCarNum(toInt(row.get("car_num")));
            result.add(vo);
        }
        return result;
    }

    /**
     * 路段预警 Top-N（对应 backend TopTenVO）。
     */
    public List<BigScreenStatVo.WarningTop> warningTop(String startTime, String endTime, int topN) {
        assertEnabled();
        LocalDate[] range = dateRange(startTime, endTime, 7);
        int limit = topN <= 0 ? 10 : Math.min(topN, 100);

        String sql = "SELECT coalesce(s.road_code, w.road_code) road_code, "
                + "coalesce(s.section_name, w.section_code) section_name, "
                + "coalesce(sum(w.warning_cnt), 0) car_num "
                + "FROM jl_data01.dws_warning_section_daily w "
                + "LEFT JOIN jl_data01.ods_szdn_section s ON s.section_code = w.section_code "
                + "WHERE w.stat_date >= ? AND w.stat_date < ? "
                + "GROUP BY coalesce(s.road_code, w.road_code), coalesce(s.section_name, w.section_code) "
                + "ORDER BY car_num DESC LIMIT ?";

        List<Map<String, Object>> rows;
        try {
            rows = jdbc.queryForList(sql, range[0], range[1], limit);
        } catch (Exception e) {
            throw unavailable("路段预警 Top-N", e);
        }

        List<BigScreenStatVo.WarningTop> result = new ArrayList<>();
        Integer topOne = null;
        int index = 1;
        for (Map<String, Object> row : rows) {
            BigScreenStatVo.WarningTop vo = new BigScreenStatVo.WarningTop();
            String roadCode = row.get("road_code") == null ? "" : String.valueOf(row.get("road_code"));
            String sectionName = row.get("section_name") == null ? "" : String.valueOf(row.get("section_name"));
            vo.setRoadCode(roadCode);
            // legacy 会在名称前拼接路线编码，保持响应展示一致
            vo.setSectionName(roadCode + " " + sectionName);
            vo.setCarNum(toInt(row.get("car_num")));
            vo.setRank(index);
            if (index == 1) {
                vo.setRate("100");
                topOne = vo.getCarNum();
            } else if (topOne != null && topOne != 0) {
                vo.setRate(String.valueOf((int) (vo.getCarNum() * 100.0 / topOne)));
            } else {
                vo.setRate("0");
            }
            result.add(vo);
            index++;
        }
        return result;
    }

    // ============================================================
    // 内部工具
    // ============================================================

    private Map<String, Object> querySum(String table, String amountCol, String carCol,
                                         LocalDate[] range) {
        String sql = "SELECT coalesce(sum(" + amountCol + "), 0) amount, "
                + "coalesce(sum(" + carCol + "), 0) car_cnt "
                + "FROM jl_data01." + table + " WHERE stat_date >= ? AND stat_date < ?";
        List<Map<String, Object>> rows = jdbc.queryForList(sql, range[0], range[1]);
        return rows.isEmpty() ? Collections.<String, Object>emptyMap() : rows.get(0);
    }

    private void assertEnabled() {
        if (!properties.getBigscreen().isStatsEnabled()) {
            throw TrafficQueryException.unavailable(
                    "大屏预聚合未启用（traffic.bigscreen.stats-enabled=false），请走 backend legacy");
        }
    }

    private TrafficQueryException unavailable(String scene, Exception e) {
        log.warn("[V3大屏] {} 查询失败: {}", scene, e.getMessage());
        return TrafficQueryException.unavailable(scene + "预聚合查询不可用: " + e.getMessage(), e);
    }

    /**
     * 日期范围：startDate/endDate 支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss；end 为闭区间，内部转半开。
     */
    private LocalDate[] dateRange(String startDate, String endDate, int defaultDays) {
        LocalDate now = LocalDate.now(TrafficTimeUtils.ZONE);
        LocalDate start = parseDate(startDate, now.minusDays(defaultDays));
        LocalDate end = parseDate(endDate, now);
        if (start.isAfter(end)) {
            throw TrafficQueryException.badRequest("开始时间不能晚于结束时间");
        }
        if (ChronoUnit.DAYS.between(start, end) > MAX_RANGE_DAYS) {
            throw TrafficQueryException.badRequest("时间范围不能超过 " + MAX_RANGE_DAYS + " 天");
        }
        return new LocalDate[]{start, end.plusDays(1)};
    }

    private LocalDate[] incomeRange(String startDate, String applyTime1, String applyTime2) {
        if (notBlank(applyTime1) || notBlank(applyTime2)) {
            return dateRange(applyTime1, applyTime2, 7);
        }
        if (notBlank(startDate)) {
            LocalDate start = parseDate(startDate, LocalDate.now(TrafficTimeUtils.ZONE));
            LocalDate monthStart = start.withDayOfMonth(1);
            LocalDate endExclusive = monthStart.plusMonths(1);
            if (ChronoUnit.DAYS.between(monthStart, endExclusive.minusDays(1)) > MAX_RANGE_DAYS) {
                throw TrafficQueryException.badRequest("时间范围不能超过 " + MAX_RANGE_DAYS + " 天");
            }
            return new LocalDate[]{monthStart, endExclusive};
        }
        return dateRange(null, null, 7);
    }

    private LocalDate parseDate(String value, LocalDate defaultValue) {
        if (!notBlank(value)) {
            return defaultValue;
        }
        String v = value.trim();
        if (v.length() >= 10) {
            v = v.substring(0, 10);
        }
        try {
            return LocalDate.parse(v);
        } catch (Exception e) {
            throw TrafficQueryException.badRequest("时间格式非法: " + value
                    + "，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss");
        }
    }

    private boolean notBlank(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private BigDecimal toBigDecimal(Object value) {
        if (value == null) {
            return BigDecimal.ZERO;
        }
        if (value instanceof BigDecimal) {
            return (BigDecimal) value;
        }
        try {
            return new BigDecimal(String.valueOf(value));
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    private Integer toInt(Object value) {
        if (value == null) {
            return 0;
        }
        if (value instanceof Number) {
            long v = ((Number) value).longValue();
            return v > Integer.MAX_VALUE ? Integer.MAX_VALUE : (int) v;
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception e) {
            return 0;
        }
    }
}
