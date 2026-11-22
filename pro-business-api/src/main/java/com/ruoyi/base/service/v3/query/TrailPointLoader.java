package com.ruoyi.base.service.v3.query;

import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 轨迹详情回查：ES 只返回元数据，{@code trailpoints} 按 (cid, extime) 回 GaussDB 取。
 * 对应设计 §5.8.4：详情/全字段导出回 SoR，不在线 UNNEST。
 */
@Slf4j
@Service
public class TrailPointLoader {

    private final JdbcTemplate jdbc;

    public TrailPointLoader(DataSource dataSource) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(30);
    }

    /**
     * 批量加载轨迹点原文（PG text[] 字面量）。
     *
     * @param cids cid 列表（单页最多 100）
     * @return cid -> trailpoints::text
     */
    public Map<String, String> load(List<String> cids, Long startMillis, Long endMillis) {
        if (cids == null || cids.isEmpty()) {
            return Collections.emptyMap();
        }
        long now = System.currentTimeMillis();
        long start = startMillis == null ? now - TimeUnit.DAYS.toMillis(180) : startMillis;
        long end = endMillis == null ? now : endMillis;

        StringBuilder sql = new StringBuilder()
                .append("SELECT cid, trailpoints::text AS trail_points ")
                .append("FROM jl_data01.zdata_trail_fitting ")
                .append("WHERE extime >= ? AND extime <= ? AND cid IN (");
        for (int i = 0; i < cids.size(); i++) {
            if (i > 0) {
                sql.append(',');
            }
            sql.append('?');
        }
        sql.append(')');

        Object[] args = new Object[cids.size() + 2];
        args[0] = TrafficTimeUtils.toDbTimestamp(start);
        args[1] = TrafficTimeUtils.toDbTimestamp(end);
        for (int i = 0; i < cids.size(); i++) {
            args[i + 2] = cids.get(i);
        }

        Map<String, String> result = new LinkedHashMap<>();
        try {
            jdbc.query(sql.toString(), args, rs -> {
                result.put(rs.getString("cid"), rs.getString("trail_points"));
            });
        } catch (Exception e) {
            log.warn("[V3轨迹] 批量加载轨迹点失败，返回空轨迹: {}", e.getMessage());
        }
        return result;
    }

    /** 便捷：单条 */
    public String loadOne(String cid, Long startMillis, Long endMillis) {
        return load(Arrays.asList(cid), startMillis, endMillis).get(cid);
    }
}
