package com.ruoyi.base.service.optimization;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.ZdataTrailFitting;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.mapper.ZdataTrailFittingMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;

/**
 * 亿级数据量查询优化服务 - Hundred Million Level Query Optimization Service
 * <p>
 * 适用场景 / Applicable Scenario:
 *   单表数据量 5000万 ~ 5亿行，月增 2000万条
 *   Single table with 50M - 500M rows, monthly growth of 20M records
 * <p>
 * 核心策略 / Core Strategies:
 *   1. 分区裁剪：按月分区表，查询时自动裁剪不需要的分区
 *      Partition pruning: Monthly partitioned tables, auto-prune unused partitions
 *   2. 游标分页（Keyset Pagination）：替代 OFFSET 分页，避免深翻页性能问题
 *      Keyset pagination: Replace OFFSET pagination, avoid deep pagination performance issues
 *   3. 物化视图：预计算统计聚合结果，加速统计类查询
 *      Materialized views: Pre-compute aggregation results for statistics queries
 *   4. 覆盖索引（Covering Index）：索引包含查询所需所有字段，避免回表
 *      Covering index: Include all needed columns in index, avoid table lookup
 *   5. 并行分片查询：将大时间范围拆分为多个小分片，并行查询后合并
 *      Parallel shard query: Split large time range into small shards, query in parallel, merge results
 */
@Slf4j
@Service
public class HundredMillionLevelQueryService {

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotFlowMapper;
    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper feeRecordsMapper;
    @Autowired
    private ZdataTrailFittingMapper trailFittingMapper;
    @Autowired
    private RedisTemplate redisTemplate;
    @Autowired(required = false)
    private JdbcTemplate jdbcTemplate;

    /** 游标分页默认每页大小 / Default page size for cursor pagination */
    private static final int DEFAULT_PAGE_SIZE = 50;
    /** 并行查询线程池大小 / Thread pool size for parallel queries */
    private static final int PARALLEL_POOL_SIZE = 4;
    /** 物化视图缓存前缀 / Cache prefix for materialized view results */
    private static final String MV_CACHE_PREFIX = "mv:cache:";
    /** 物化视图缓存TTL（秒） / Cache TTL for materialized view results (seconds) */
    private static final long MV_CACHE_TTL = 300L;

    /**
     * 门架抓拍流水 - 游标分页查询
     * Snapshot flow - Cursor pagination query
     */
    public List<OdsRtSzdnSnapshotFlowAddcode> querySnapshotFlowByCursor(
            String startTime, String endTime,
            String cursor, String cursorUuid, int pageSize) {
        log.info("[亿级查询] 门架抓拍流水游标分页: start={}, end={}, cursor={}, pageSize={}",
                startTime, endTime, cursor, pageSize);
        return snapshotFlowMapper.selectByCursorShard(startTime, endTime, cursor, cursorUuid, pageSize);
    }

    /**
     * 门架抓拍流水 - 并行分片查询
     * Snapshot flow - Parallel shard query
     */
    public List<OdsRtSzdnSnapshotFlowAddcode> querySnapshotFlowParallel(
            String startTime, String endTime) {
        log.info("[亿级查询] 门架抓拍流水并行分片: start={}, end={}", startTime, endTime);
        List<String[]> shards = splitDateRangeByDay(startTime, endTime);
        log.info("[亿级查询] 拆分为 {} 个分片", shards.size());
        ExecutorService executor = Executors.newFixedThreadPool(
                Math.min(shards.size(), PARALLEL_POOL_SIZE));
        List<Future<List<OdsRtSzdnSnapshotFlowAddcode>>> futures = new ArrayList<>();
        for (String[] shard : shards) {
            futures.add(executor.submit(() -> {
                OdsRtSzdnSnapshotFlowAddcode query = new OdsRtSzdnSnapshotFlowAddcode();
                query.setApplyTime1(shard[0]);
                query.setApplyTime2(shard[1]);
                return snapshotFlowMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(query);
            }));
        }
        List<OdsRtSzdnSnapshotFlowAddcode> merged = new ArrayList<>();
        for (Future<List<OdsRtSzdnSnapshotFlowAddcode>> future : futures) {
            try {
                merged.addAll(future.get(60, TimeUnit.SECONDS));
            } catch (Exception e) {
                log.error("[亿级查询] 分片查询失败", e);
            }
        }
        executor.shutdown();
        merged.sort((a, b) -> {
            if (a.getSnapshottime() == null && b.getSnapshottime() == null) return 0;
            if (a.getSnapshottime() == null) return 1;
            if (b.getSnapshottime() == null) return -1;
            return b.getSnapshottime().compareTo(a.getSnapshottime());
        });
        log.info("[亿级查询] 并行查询完成，合并结果 {} 条", merged.size());
        return merged;
    }

    public List<OdsLwzxsfsjFeeRecords01> queryFeeRecordsByCursor(
            String startTime, String endTime,
            String cursor, int pageSize) {
        log.info("[亿级查询] 收费流水游标分页: start={}, end={}, cursor={}, pageSize={}",
                startTime, endTime, cursor, pageSize);
        OdsLwzxsfsjFeeRecords01 query = new OdsLwzxsfsjFeeRecords01();
        query.setInApplyTime1(startTime);
        query.setInApplyTime2(endTime);
        return feeRecordsMapper.selectOdsLwzxsfsjFeeRecords01List(query);
    }

    public List<ZdataTrailFitting> queryTrailFittingByCursor(
            String startTime, String endTime, int pageSize) {
        log.info("[亿级查询] 轨迹拟合查询: start={}, end={}, pageSize={}",
                startTime, endTime, pageSize);
        ZdataTrailFitting query = new ZdataTrailFitting();
        if (startTime != null) query.setEntime(java.sql.Timestamp.valueOf(startTime));
        if (endTime != null) query.setExtime(java.sql.Timestamp.valueOf(endTime));
        return trailFittingMapper.selectZdataTrailFittingList(query);
    }

    public List<Map<String, Object>> getSnapshotDailyStats(String startDate, String endDate) {
        String cacheKey = MV_CACHE_PREFIX + "snapshot_daily:" + startDate + ":" + endDate;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            log.info("[亿级查询] 物化视图统计命中缓存: {}", cacheKey);
            return (List<Map<String, Object>>) cached;
        }
        if (jdbcTemplate == null) {
            log.warn("[亿级查询] JdbcTemplate 未注入，返回空列表");
            return Collections.emptyList();
        }
        String sql = "SELECT snapshot_date, sectioncode, sectionname, record_count, vehicle_count " +
                     "FROM jl_data01.mv_snapshot_daily_section " +
                     "WHERE snapshot_date >= ? AND snapshot_date <= ? " +
                     "ORDER BY snapshot_date DESC";
        List<Map<String, Object>> result = jdbcTemplate.queryForList(sql, startDate, endDate);
        redisTemplate.opsForValue().set(cacheKey, result, MV_CACHE_TTL, TimeUnit.SECONDS);
        log.info("[亿级查询] 物化视图统计查询完成，{} 条记录已缓存", result.size());
        return result;
    }

    public List<Map<String, Object>> getFeeMonthlyStats(String startMonth, String endMonth) {
        String cacheKey = MV_CACHE_PREFIX + "fee_monthly:" + startMonth + ":" + endMonth;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            return (List<Map<String, Object>>) cached;
        }
        if (jdbcTemplate == null) {
            return Collections.emptyList();
        }
        String sql = "SELECT trans_month, gantryid, record_count, total_fee, vehicle_count " +
                     "FROM jl_data01.mv_fee_monthly " +
                     "WHERE trans_month >= ? AND trans_month <= ? " +
                     "ORDER BY trans_month DESC";
        List<Map<String, Object>> result = jdbcTemplate.queryForList(sql, startMonth, endMonth);
        redisTemplate.opsForValue().set(cacheKey, result, MV_CACHE_TTL, TimeUnit.SECONDS);
        return result;
    }

    private List<String[]> splitDateRangeByDay(String startTime, String endTime) {
        List<String[]> result = new ArrayList<>();
        try {
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
            Date start = sdf.parse(startTime);
            Date end = endTime != null ? sdf.parse(endTime) : new Date();
            Calendar cal = Calendar.getInstance();
            cal.setTime(start);
            cal.set(Calendar.HOUR_OF_DAY, 0);
            cal.set(Calendar.MINUTE, 0);
            cal.set(Calendar.SECOND, 0);
            while (cal.getTime().before(end)) {
                String dayStart = sdf.format(cal.getTime());
                cal.add(Calendar.DAY_OF_MONTH, 1);
                String dayEnd = cal.getTime().before(end) ?
                        sdf.format(cal.getTime()) : sdf.format(end);
                result.add(new String[]{dayStart, dayEnd});
            }
        } catch (Exception e) {
            log.error("[亿级查询] 时间拆分失败", e);
            result.add(new String[]{startTime, endTime});
        }
        return result;
    }

    public void refreshMaterializedViews() {
        if (jdbcTemplate == null) return;
        try {
            log.info("[亿级查询] 开始刷新物化视图");
            jdbcTemplate.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_snapshot_daily_section");
            jdbcTemplate.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY jl_data01.mv_fee_monthly");
            Set<String> keys = redisTemplate.keys(MV_CACHE_PREFIX + "*");
            if (keys != null && !keys.isEmpty()) {
                redisTemplate.delete(keys);
            }
            log.info("[亿级查询] 物化视图刷新完成");
        } catch (Exception e) {
            log.error("[亿级查询] 物化视图刷新失败", e);
        }
    }
}
