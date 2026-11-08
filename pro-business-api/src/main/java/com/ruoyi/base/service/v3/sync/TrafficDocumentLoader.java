package com.ruoyi.base.service.v3.sync;

import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 按主键回查 GaussDB 行，供“Outbox payload 为空”的同步事件兜底。
 * 查询窗口限制在事件时间 ±1 天，保证分区裁剪。
 */
@Slf4j
@Service
public class TrafficDocumentLoader {

    private final JdbcTemplate jdbc;

    public TrafficDocumentLoader(DataSource dataSource) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(10);
    }

    public Map<String, Object> loadByPk(TrafficTable table, String pk, Long eventTime) {
        if (pk == null || pk.trim().isEmpty() || eventTime == null) {
            return null;
        }
        long from = eventTime - TimeUnit.DAYS.toMillis(1);
        long to = eventTime + TimeUnit.DAYS.toMillis(1);
        String sql;
        switch (table) {
            case SNAPSHOT:
                sql = "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode "
                        + "WHERE big_id = ? AND snapshottime >= ? AND snapshottime < ? LIMIT 1";
                break;
            case FEE:
                sql = "SELECT t.*, g.gantry_name AS gantryname, g.section_code AS sectioncode "
                        + "FROM jl_data01.ods_lwzxsfsj_fee_records_01 t "
                        + "LEFT JOIN jl_data01.ods_szdn_gantry g ON t.gantryid = g.gantry_code "
                        + "WHERE t.big_id = ? AND t.transtime >= ? AND t.transtime < ? LIMIT 1";
                break;
            case TRAIL:
                sql = "SELECT cid, envehicleid, exvehicleid, entime, extime, "
                        + "entolllaneid, extolllaneid, entollstationid, extollstationid, "
                        + "entollstationname, extollstationname, enaxlecount, envehicleclass, "
                        + "envehicletype, exvehicleclass, exvehicletype, enweight, exweight, "
                        + "trailtype, trailpoints "
                        + "FROM jl_data01.zdata_trail_fitting "
                        + "WHERE cid = ? AND extime >= ? AND extime < ? LIMIT 1";
                break;
            default:
                return null;
        }
        try {
            return jdbc.queryForMap(sql, pk, new Timestamp(from), new Timestamp(to));
        } catch (EmptyResultDataAccessException e) {
            return null;
        } catch (Exception e) {
            log.warn("[V3同步] 回查失败 table={}, pk={}: {}", table, pk, e.getMessage());
            return null;
        }
    }
}
