package com.ruoyi.base.service.optimization;

import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.mapper.ZdataTrailFittingMapper;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.index.query.RangeQueryBuilder;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.concurrent.atomic.AtomicLong;

/**
 * GaussDB ↔ Elasticsearch 一致性对账与修复服务
 * GaussDB ↔ Elasticsearch consistency reconciliation & repair service.
 *
 * =================================================================================
 * 背景 / Background:
 *   异步线程消费 Kafka 写 ES 与 GaussDB 之间天然存在时序漂移（写 DB 成功但写 ES 失败、
 *   写入延迟、消息重复/丢失）。本服务是「四层一致性保障」的最后一层（兜底中的兜底）：
 *   There is an inherent timing drift between async Kafka->ES writes and GaussDB.
 *   This service is the last (and ultimate) layer of the 4-layer consistency guarantee.
 *
 * 四层保障 / 4-layer guarantee:
 *   1) 应用双写 (Async Dual-Write)      —— 主路径，_id=业务主键 保证幂等
 *   2) Redis 水位增量同步                —— 日常补偿，at-least-once + 幂等 = exactly-once
 *   3) Debezium CDC 兜底                 —— 捕获型补偿，覆盖双写缺失窗口
 *   4) 本服务：定时对账 + 修复            —— 低频全量校验，以 GaussDB 为准回灌 ES
 *
 * 对账思路 / Reconciliation approach:
 *   按「月分区」对 GaussDB 与 ES 在相同时间窗内做 COUNT 比对；条数不一致即视为漂移，
 *   触发 repairSync 以 GaussDB 为准重跑该时间窗，回灌 ES（_id 幂等覆盖）。
 *   Compare row counts per monthly partition; drift triggers a repair that re-syncs the window.
 *
 * @author car-monit-api-optimization
 */
@Slf4j
@Service
public class GaussEsConsistencyService {

    @Autowired
    private RestHighLevelClient esClient;

    @Autowired
    private EsIndexManageService indexManageService;

    @Autowired
    private LargeScaleDataSyncService dataSyncService;

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper snapshotMapper;

    @Autowired
    private OdsLwzxsfsjFeeRecords01Mapper feeMapper;

    @Autowired
    private ZdataTrailFittingMapper trailMapper;

    /** 是否开启定时对账任务 / enable scheduled reconciliation */
    @Value("${consistency.reconcile.enabled:false}")
    private boolean reconcileEnabled;

    /** 对账回看月份数（仅校验最近 N 个月，控制成本）/ look-back months for reconciliation */
    @Value("${consistency.reconcile.lookback-months:3}")
    private int lookbackMonths;

    /** 漂移告警阈值：ES 与 GaussDB 条数差异超过该比例视为漂移 / drift ratio threshold */
    @Value("${consistency.reconcile.drift-ratio:0.01}")
    private double driftRatio;

    private static final SimpleDateFormat SDF = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    /** 累计修复次数（监控用）/ cumulative repair counter for monitoring */
    private final AtomicLong repairCounter = new AtomicLong(0);

    /**
     * 一致性对账报告 / Consistency reconciliation report.
     */
    public static class ConsistencyReport {
        public UnifiedQueryService.DataSource dataSource;
        public String startTime;
        public String endTime;
        public long gaussDbCount;
        public long esCount;
        public long diff;
        public String status;   // CONSISTENT / DRIFT
        public String suggestion;

        @Override
        public String toString() {
            return "ConsistencyReport{ds=" + dataSource + ", range=[" + startTime + "," + endTime + ")"
                    + ", gaussDb=" + gaussDbCount + ", es=" + esCount
                    + ", diff=" + diff + ", status=" + status + ", suggestion=" + suggestion + "}";
        }
    }

    /**
     * 对指定数据源在指定时间窗内做一致性对账
     * Reconcile a given data source within the time window.
     *
     * @param ds        数据源 / data source
     * @param startTime 起始时间 yyyy-MM-dd HH:mm:ss
     * @param endTime   结束时间
     * @return 对账报告 / reconciliation report
     */
    public ConsistencyReport reconcile(UnifiedQueryService.DataSource ds,
                                       String startTime, String endTime) {
        ConsistencyReport report = new ConsistencyReport();
        report.dataSource = ds;
        report.startTime = startTime;
        report.endTime = endTime;

        try {
            // 1) GaussDB 侧条数（依赖分区裁剪，按月分区下很快）
            report.gaussDbCount = countInGaussDb(ds, startTime, endTime);
            // 2) ES 侧条数（Count API，倒排索引聚合）
            report.esCount = countInEs(ds, startTime, endTime);
            // 3) 计算差异与状态
            report.diff = Math.abs(report.gaussDbCount - report.esCount);
            double ratio = report.gaussDbCount == 0 ? (report.esCount == 0 ? 0 : 1)
                    : (double) report.diff / report.gaussDbCount;
            if (report.diff == 0 || ratio <= driftRatio) {
                report.status = "CONSISTENT";
                report.suggestion = "OK";
            } else {
                report.status = "DRIFT";
                report.suggestion = "建议触发 repairSync 以 GaussDB 为准回灌 ES";
            }
            log.info("[一致性对账] {}", report);
        } catch (Exception e) {
            log.error("[一致性对账] 对账失败 ds={}, range=[{},{}]", ds, startTime, endTime, e);
            report.status = "ERROR";
            report.suggestion = e.getMessage();
        }
        return report;
    }

    /**
     * 依据对账差异触发指定时间窗的补同步（以 GaussDB 为准回灌 ES）
     * Trigger a repair sync for the drifted window (GaussDB is source of truth).
     *
     * @param ds        数据源 / data source
     * @param startTime 起始时间
     * @param endTime   结束时间
     */
    public void triggerRepair(UnifiedQueryService.DataSource ds,
                              String startTime, String endTime) {
        log.info("[一致性修复] 触发补同步 ds={}, range=[{},{}]", ds, startTime, endTime);
        try {
            dataSyncService.repairSync(ds, startTime, endTime);
            repairCounter.incrementAndGet();
        } catch (Exception e) {
            log.error("[一致性修复] 补同步失败 ds={}, range=[{},{}]", ds, startTime, endTime, e);
        }
    }

    /**
     * 定时对账任务（默认关闭，生产环境通过 consistency.reconcile.enabled=true 开启）
     * Scheduled reconciliation (disabled by default; enable via config).
     *
     * 设计思路 / Design:
     *   - 每天凌晨 02:30 执行一次（cron 可在 application.yml 覆盖）
     *   - 遍历三张表、最近 lookback-months 个月，逐月对账
     *   - 仅当漂移超过阈值时异步触发 repairSync，避免风暴
     *   - 逐月而非整年一次性，控制单次 COUNT/Count 的资源占用
     */
    @Scheduled(cron = "${consistency.reconcile.cron:0 30 2 * * ?}")
    public void scheduledReconcile() {
        if (!reconcileEnabled) {
            return;
        }
        log.info("[一致性对账] 定时任务启动, lookback-months={}", lookbackMonths);
        UnifiedQueryService.DataSource[] all = UnifiedQueryService.DataSource.values();
        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.DAY_OF_MONTH, 1);
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);

        for (int i = 0; i < lookbackMonths; i++) {
            Date monthEnd = cal.getTime();
            // 回到月初
            cal.add(Calendar.MONTH, -1);
            Date monthStart = cal.getTime();
            String start = SDF.format(monthStart);
            String end = SDF.format(monthEnd);
            for (UnifiedQueryService.DataSource ds : all) {
                try {
                    ConsistencyReport report = reconcile(ds, start, end);
                    if ("DRIFT".equals(report.status)) {
                        // 异步触发修复，避免阻塞对账主流程
                        final UnifiedQueryService.DataSource fds = ds;
                        new Thread(() -> triggerRepair(fds, start, end),
                                "consistency-repair-" + ds).start();
                    }
                } catch (Exception e) {
                    log.error("[一致性对账] 月度对账异常 ds={}, range=[{},{}]", ds, start, end, e);
                }
            }
        }
        log.info("[一致性对账] 定时任务完成, 累计修复次数={}", repairCounter.get());
    }

    /**
     * GaussDB 侧条数统计 / Count rows in GaussDB within the window.
     */
    private long countInGaussDb(UnifiedQueryService.DataSource ds, String startTime, String endTime) {
        Date start = parse(startTime);
        Date end = parse(endTime);
        // 注意：必须显式指定 QueryWrapper 的泛型（链式 .between() 会破坏菱形推断）
        // Note: explicit generic required; chained .between() defeats diamond inference.
        switch (ds) {
            case SNAPSHOT:
                return snapshotMapper.selectCount(
                        new com.baomidou.mybatisplus.core.conditions.query.QueryWrapper<com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode>()
                                .between("snapshottime", start, end));
            case FEE:
                return feeMapper.selectCount(
                        new com.baomidou.mybatisplus.core.conditions.query.QueryWrapper<com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01>()
                                .between("transtime", start, end));
            case TRAIL:
                return trailMapper.selectCount(
                        new com.baomidou.mybatisplus.core.conditions.query.QueryWrapper<com.ruoyi.base.domain.ZdataTrailFitting>()
                                .between("extime", start, end));
            default:
                return 0L;
        }
    }

    /**
     * ES 侧条数统计 / Count docs in ES within the window (Count API).
     */
    private long countInEs(UnifiedQueryService.DataSource ds, String startTime, String endTime) throws Exception {
        String indexName = resolveIndexName(ds);
        String timeField = resolveTimeField(ds);

        // 使用 SearchRequest(size=0 + track_total_hits) 获取精确文档数，
        // 避免依赖可能不存在的 Count API 类（ES 版本差异）。
        // Use SearchRequest(size=0 + track_total_hits) for an accurate doc count,
        // avoiding version-specific Count API classes.
        RangeQueryBuilder range = QueryBuilders.rangeQuery(timeField)
                .format("yyyy-MM-dd HH:mm:ss").gte(startTime).lte(endTime);
        SearchSourceBuilder ssb = new SearchSourceBuilder().query(range).size(0).trackTotalHits(true);
        SearchRequest searchRequest = new SearchRequest(indexName);
        searchRequest.source(ssb);

        SearchResponse response = esClient.search(searchRequest, RequestOptions.DEFAULT);
        return response.getHits().getTotalHits().value;
    }

    private String resolveIndexName(UnifiedQueryService.DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return indexManageService.getSnapshotIndex();
            case FEE:      return indexManageService.getFeeIndex();
            case TRAIL:    return indexManageService.getTrailIndex();
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    private String resolveTimeField(UnifiedQueryService.DataSource ds) {
        switch (ds) {
            case SNAPSHOT: return "snapshottime";
            case FEE:      return "transtime";
            case TRAIL:    return "extime";
            default: throw new IllegalArgumentException("未知数据源: " + ds);
        }
    }

    private Date parse(String s) {
        try {
            return SDF.parse(s);
        } catch (Exception e) {
            throw new RuntimeException("时间解析失败: " + s, e);
        }
    }
}
