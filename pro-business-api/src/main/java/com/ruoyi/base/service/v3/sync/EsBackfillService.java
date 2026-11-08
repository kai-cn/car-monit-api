package com.ruoyi.base.service.v3.sync;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficDocumentBuilder;
import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import javax.annotation.PreDestroy;
import javax.sql.DataSource;
import java.sql.ResultSetMetaData;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * GaussDB -> ES 受控回灌（索引重建/对账补偿/13 个月初始化）。
 *
 * <p>不是应用双写：回灌只从 SoR 读取，按 (time, pk) keyset 分页 + bulk 幂等写入；
 * 与在线写入隔离，避免全表快照锁库（设计 §5.6.2）。</p>
 */
@Slf4j
@Service
public class EsBackfillService {

    private final JdbcTemplate jdbc;
    private final TrafficDocumentBuilder documentBuilder;
    private final EsBulkIndexer bulkIndexer;
    private final TrafficV3Properties properties;

    private final ExecutorService executor;
    private final Map<String, BackfillTask> tasks = new ConcurrentHashMap<>();

    public EsBackfillService(DataSource dataSource,
                             TrafficDocumentBuilder documentBuilder,
                             EsBulkIndexer bulkIndexer,
                             TrafficV3Properties properties) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.jdbc.setQueryTimeout(60);
        this.documentBuilder = documentBuilder;
        this.bulkIndexer = bulkIndexer;
        this.properties = properties;
        AtomicInteger seq = new AtomicInteger();
        this.executor = Executors.newFixedThreadPool(2, r -> {
            Thread t = new Thread(r, "v3-backfill-" + seq.incrementAndGet());
            t.setDaemon(true);
            return t;
        });
    }

    /**
     * 提交回灌任务（异步，最多 2 并发）。
     */
    public BackfillTask submit(TrafficTable table, long startMillis, long endMillis) {
        BackfillTask task = new BackfillTask();
        task.setTaskId(UUID.randomUUID().toString().replace("-", ""));
        task.setTable(table);
        task.setStartMillis(startMillis);
        task.setEndMillis(endMillis);
        tasks.put(task.getTaskId(), task);
        executor.submit(() -> run(task));
        log.info("[V3回灌] 任务已提交: id={}, table={}, {} ~ {}",
                task.getTaskId(), table, new Date(startMillis), new Date(endMillis));
        return task;
    }

    public BackfillTask get(String taskId) {
        return tasks.get(taskId);
    }

    private void run(BackfillTask task) {
        try {
            TrafficTable table = task.getTable();
            long start = task.getStartMillis();
            long end = task.getEndMillis();
            long cursorTime = start - 1000L;
            String cursorPk = "";
            int batch = Math.max(100, properties.getSync().getBulkSize());

            while (!Thread.currentThread().isInterrupted() && task.getStatus().equals("RUNNING")) {
                List<Map<String, Object>> rows = queryChunk(
                        table, start, end, cursorTime, cursorPk, batch);
                if (rows.isEmpty()) {
                    break;
                }

                List<EsBulkIndexer.IndexDoc> docs = new ArrayList<>(rows.size());
                for (Map<String, Object> row : rows) {
                    String id = documentBuilder.docId(table, row);
                    if (id == null || id.isEmpty()) {
                        continue;
                    }
                    long eventTime = eventTime(table, row);
                    Map<String, Object> doc = documentBuilder.build(table, row);
                    docs.add(new EsBulkIndexer.IndexDoc(table, id, doc, eventTime));
                }
                int indexed = bulkIndexer.bulkIndex(docs);
                task.setRowsIndexed(task.getRowsIndexed() + indexed);

                Map<String, Object> last = rows.get(rows.size() - 1);
                cursorTime = eventTime(table, last);
                Object pk = last.get(table.getPkField());
                cursorPk = pk == null ? "" : String.valueOf(pk);
                task.setLastEventTime(new Date(cursorTime));

                if (rows.size() < batch) {
                    break;
                }
                log.info("[V3回灌] {} 进度: rows={}, cursor={}/{}",
                        task.getTaskId(), task.getRowsIndexed(), cursorTime, cursorPk);
            }
            task.setStatus("DONE");
            task.setFinishedAt(new Date());
            log.info("[V3回灌] 完成: id={}, rows={}", task.getTaskId(), task.getRowsIndexed());
        } catch (Exception e) {
            task.setStatus("FAILED");
            task.setError(e.getMessage());
            task.setFinishedAt(new Date());
            log.error("[V3回灌] 失败: id={}", task.getTaskId(), e);
        }
    }

    private List<Map<String, Object>> queryChunk(TrafficTable table, long start, long end,
                                                 long cursorTime, String cursorPk, int limit) {
        String time = table.getTimeField();
        String pk = table.getPkField();
        String sql;
        switch (table) {
            case SNAPSHOT:
                sql = "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode t "
                        + "WHERE t." + time + " >= ? AND t." + time + " < ? "
                        + "AND (t." + time + " > ? OR (t." + time + " = ? AND t." + pk + " > ?)) "
                        + "ORDER BY t." + time + ", t." + pk + " LIMIT ?";
                break;
            case FEE:
                sql = "SELECT t.*, g.gantry_name AS gantryname, g.section_code AS sectioncode "
                        + "FROM jl_data01.ods_lwzxsfsj_fee_records_01 t "
                        + "LEFT JOIN jl_data01.ods_szdn_gantry g ON t.gantryid = g.gantry_code "
                        + "WHERE t." + time + " >= ? AND t." + time + " < ? "
                        + "AND (t." + time + " > ? OR (t." + time + " = ? AND t." + pk + " > ?)) "
                        + "ORDER BY t." + time + ", t." + pk + " LIMIT ?";
                break;
            case TRAIL:
                sql = "SELECT cid, envehicleid, exvehicleid, entime, extime, enaxlecount, "
                        + "envehicleclass, envehicletype, exvehicleclass, exvehicletype, "
                        + "enweight, exweight, entolllaneid, extolllaneid, entollstationid, "
                        + "extollstationid, entollstationname, extollstationname, trailtype, trailpoints "
                        + "FROM jl_data01.zdata_trail_fitting t "
                        + "WHERE t." + time + " >= ? AND t." + time + " < ? "
                        + "AND (t." + time + " > ? OR (t." + time + " = ? AND t." + pk + " > ?)) "
                        + "ORDER BY t." + time + ", t." + pk + " LIMIT ?";
                break;
            default:
                return new ArrayList<>();
        }
        Object[] args = new Object[]{
                new Timestamp(start), new Timestamp(end),
                new Timestamp(cursorTime), new Timestamp(cursorTime), cursorPk, limit
        };
        RowMapper<Map<String, Object>> mapper = (rs, rowNum) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            ResultSetMetaData meta = rs.getMetaData();
            for (int i = 1; i <= meta.getColumnCount(); i++) {
                String label = meta.getColumnLabel(i);
                row.put(label, rs.getObject(i));
            }
            return row;
        };
        return jdbc.query(sql, args, mapper);
    }

    private long eventTime(TrafficTable table, Map<String, Object> row) {
        Object value = row.get(table.getTimeField());
        if (value instanceof Date) {
            return ((Date) value).getTime();
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        if (value instanceof CharSequence) {
            try {
                return Timestamp.valueOf(value.toString()).getTime();
            } catch (Exception ignored) {
                return System.currentTimeMillis();
            }
        }
        return System.currentTimeMillis();
    }

    @PreDestroy
    public void shutdown() {
        executor.shutdownNow();
    }
}
