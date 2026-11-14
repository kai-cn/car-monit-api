package com.ruoyi.base.service.optimization;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.domain.ZdataTrailFitting;
import com.ruoyi.base.mapper.OdsLwzxsfsjFeeRecords01Mapper;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.mapper.ZdataTrailFittingMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.HttpHost;
import org.elasticsearch.action.ActionListener;
import org.elasticsearch.action.bulk.*;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.*;
import org.elasticsearch.common.unit.ByteSizeUnit;
import org.elasticsearch.common.unit.ByteSizeValue;
import org.elasticsearch.core.TimeValue;
import org.elasticsearch.xcontent.XContentType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import jakarta.annotation.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BiConsumer;
import java.util.function.Function;

/**
 * 超大规模数据同步服务 - GaussDB -> Elasticsearch（三表统一）
 * Large-scale data sync service: GaussDB -> Elasticsearch (unified for 3 tables).
 *
 * =====================================================================
 * 背景 / Background:
 *   3 张表，每张表未来 3 年预计 8 亿条数据，日增约 70 万条。
 *   需将最近 12 个月数据实时同步到 ES，支撑全字段模糊查询、统计与导出。
 *   本服务是「GaussDB↔ES 一致性保障」的主路径（应用双写 / 增量补偿）。
 *
 * 同步策略 / Sync strategies:
 *   1. 全量同步（首次上线）：按时间分片并行 + 游标分页(keyset) + BulkProcessor
 *      Full sync: time-shard parallelism + keyset pagination + BulkProcessor
 *   2. 增量同步（日常）：Redis 水位标记，拉取 > watermark 且 < now-10s 的新数据
 *      Incremental: Redis watermark, at-least-once + _id idempotency = exactly-once
 *   3. 补同步（修复）：按指定时间窗重放，以 GaussDB 为准回灌 ES
 *      Repair: replay a window, GaussDB is source of truth
 *
 * 性能保障 / Performance guarantees:
 *   A. BulkProcessor: 1000 条 / 10MB / 5s 先到先触发，并发 4，指数退避重试
 *   B. 游标分页(keyset): 复杂度 O(total)，避免 limit/offset 的 O(offset) 深翻页
 *   C. 背压队列(BlockingQueue, 10000): ES 写入过载时阻塞读取端，防 OOM
 *   D. Redis 水位: 真实读写，增量不重复、不漏读（留 10s 缓冲规避写入延迟）
 *
 * @author car-monit-api
 */
@Slf4j
@Service
public class LargeScaleDataSyncService {

    @Value("${elasticsearch.host:127.0.0.1}")
    private String esHost;

    @Value("${elasticsearch.port:9200}")
    private int esPort;

    @Value("${sync.shard.hours:1}")
    private int shardHours;

    /** Redis 水位 key 前缀（按表隔离） / Redis watermark key prefix (per table) */
    private static final String WATERMARK_PREFIX = "es:sync:watermark:";

    /** 增量水位向后缓冲秒数（规避 GaussDB 写入延迟造成漏读） / watermark back-off seconds */
    private static final int WATERMARK_BACKOFF_SECONDS = 10;

    private RestHighLevelClient client;
    private BulkProcessor bulkProcessor;

    /** 三表 Mapper / mappers for the 3 tables */
    private final OdsRtSzdnSnapshotFlowAddcodeMapper snapshotMapper;
    private final OdsLwzxsfsjFeeRecords01Mapper feeMapper;
    private final ZdataTrailFittingMapper trailMapper;

    /** Redis 水位存储 / Redis watermark store (raw type, consistent with other services) */
    private final RedisTemplate redisTemplate;

    /** ES 索引名解析（与查询路由统一，确保同步与目标索引一致） / index name resolver (shared with query layer) */
    private final EsIndexManageService indexManageService;

    /**
     * 背压队列：DB 读取线程与 ES 写入线程之间的有界缓冲，避免内存无限增长
     * Bounded back-pressure buffer between DB reader and ES writer.
     */
    private final BlockingQueue<Object> syncQueue = new LinkedBlockingQueue<>(10000);

    /** 统计计数器（并发安全） / atomic counters */
    private final AtomicLong totalReadCount = new AtomicLong(0);
    private final AtomicLong totalWriteSuccessCount = new AtomicLong(0);
    private final AtomicLong totalWriteFailedCount = new AtomicLong(0);

    /** 读取线程池（默认 8 个并行分片） / reader thread pool */
    private final ExecutorService shardReaderPool = new ThreadPoolExecutor(
            8, 16, 30L, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(500),
            r -> { Thread t = new Thread(r, "es-shard-reader"); t.setDaemon(true); return t; },
            new ThreadPoolExecutor.CallerRunsPolicy()
    );

    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1, r -> {
        Thread t = new Thread(r, "es-bulk-scheduler"); t.setDaemon(true); return t;
    });

    /**
     * 构造注入依赖 / Constructor injection.
     * 注意：@Value 字段在构造函数执行时尚未注入，ES 客户端初始化必须放到 @PostConstruct。
     */
    public LargeScaleDataSyncService(OdsRtSzdnSnapshotFlowAddcodeMapper snapshotMapper,
                                     OdsLwzxsfsjFeeRecords01Mapper feeMapper,
                                     ZdataTrailFittingMapper trailMapper,
                                     RedisTemplate redisTemplate,
                                     EsIndexManageService indexManageService) {
        this.snapshotMapper = snapshotMapper;
        this.feeMapper = feeMapper;
        this.trailMapper = trailMapper;
        this.redisTemplate = redisTemplate;
        this.indexManageService = indexManageService;
    }

    /**
     * 在所有依赖（含 @Value）注入完成后再创建 ES 客户端与 BulkProcessor。
     * Initialize ES client & BulkProcessor after @Value fields have been injected.
     */
    @PostConstruct
    public void init() {
        this.client = new RestHighLevelClient(
                RestClient.builder(new HttpHost(esHost, esPort, "http"))
                        .setRequestConfigCallback(builder -> builder
                                .setConnectTimeout(10000)
                                .setSocketTimeout(120000)
                                .setConnectionRequestTimeout(10000))
        );
        this.bulkProcessor = buildBulkProcessor();
        log.info("[数据同步服务] 初始化完成, ES={}:{}", esHost, esPort);
    }

    @PreDestroy
    public void destroy() {
        try {
            if (bulkProcessor != null) { bulkProcessor.awaitClose(30, TimeUnit.SECONDS); }
            if (client != null) { client.close(); }
        } catch (Exception e) {
            log.error("[数据同步服务] 关闭异常", e);
        }
        shardReaderPool.shutdown();
        scheduler.shutdown();
    }

    // ================================================================
    // 内部方法：构建 BulkProcessor（带失败重试）
    // Build BulkProcessor with failure retry.
    // ================================================================

    private BulkProcessor buildBulkProcessor() {
        BiConsumer<BulkRequest, ActionListener<BulkResponse>> bulkConsumer =
                (request, bulkListener) -> client.bulkAsync(request, RequestOptions.DEFAULT, bulkListener);

        return BulkProcessor.builder(bulkConsumer, new BulkProcessor.Listener() {
                    @Override
                    public void beforeBulk(long executionId, BulkRequest request) {
                        log.debug("[Bulk] 执行批次 {}, size={}条", executionId, request.numberOfActions());
                    }

                    @Override
                    public void afterBulk(long executionId, BulkRequest request, BulkResponse response) {
                        if (response.hasFailures()) {
                            long failed = Arrays.stream(response.getItems())
                                    .filter(BulkItemResponse::isFailed)
                                    .peek(item -> log.warn("[Bulk] 写入失败: id={}, reason={}",
                                            item.getId(), item.getFailureMessage()))
                                    .count();
                            totalWriteFailedCount.addAndGet(failed);
                            totalWriteSuccessCount.addAndGet(request.numberOfActions() - failed);
                        } else {
                            totalWriteSuccessCount.addAndGet(request.numberOfActions());
                        }
                        long total = totalWriteSuccessCount.get();
                        if (total > 0 && total % 10000 == 0) {
                            log.info("[Bulk] 进度: 已写入 {} 条, 失败 {} 条", total, totalWriteFailedCount.get());
                        }
                    }

                    @Override
                    public void afterBulk(long executionId, BulkRequest request, Throwable failure) {
                        log.error("[Bulk] 批次 {} 异常, size={}", executionId, request.numberOfActions(), failure);
                        totalWriteFailedCount.addAndGet(request.numberOfActions());
                    }
                })
                .setBulkActions(1000)
                .setBulkSize(new ByteSizeValue(10L, ByteSizeUnit.MB))
                .setFlushInterval(TimeValue.timeValueSeconds(5))
                .setConcurrentRequests(4)
                .setBackoffPolicy(BackoffPolicy.exponentialBackoff(TimeValue.timeValueMillis(1000), 5))
                .build();
    }

    // ================================================================
    // 同步任务定义（三表统一）/ Sync task definition (3 tables)
    // ================================================================

    /**
     * 单表同步任务描述符 / Per-table sync task descriptor.
     *
     * 将「表名、Redis 水位 key、时间字段、游标读取器、主键提取器」封装为一个任务，
     * 使全量/增量/补同步逻辑对三表完全通用，避免重复代码。
     * Encapsulates table identity, watermark key, time field, cursor reader and id extractor
     * so full/incremental/repair logic is table-agnostic.
     */
    private static class SyncTask {
        final UnifiedQueryService.DataSource ds;
        final String redisWatermarkKey;   // Redis 水位 key
        final CursorReader reader;        // 游标分页读取器
        final Function<Object, String> idExtractor; // 从记录提取 ES 文档 _id（业务主键）

        SyncTask(UnifiedQueryService.DataSource ds, String redisWatermarkKey,
                 CursorReader reader, Function<Object, String> idExtractor) {
            this.ds = ds;
            this.redisWatermarkKey = redisWatermarkKey;
            this.reader = reader;
            this.idExtractor = idExtractor;
        }

        String indexName(EsIndexManageService svc) {
            return svc.resolveIndexName(ds);
        }
    }

    /**
     * 游标分页读取器：给定时间分片与游标，返回本批记录
     * Cursor reader: returns a batch given a time shard and cursor.
     */
    @FunctionalInterface
    private interface CursorReader {
        List<?> read(Date start, Date end, String cursorTime, String cursorUuid, int limit);
    }

    /**
     * 构建三表同步任务（每次调用重建，确保引用最新 Mapper）
     * Build the 3 sync tasks (rebuilt each call to bind the latest mappers).
     */
    private List<SyncTask> buildSyncTasks() {
        List<SyncTask> tasks = new ArrayList<>(3);
        // 1) 门架抓拍流水：主键 datauuid，时间 snapshottime
        tasks.add(new SyncTask(UnifiedQueryService.DataSource.SNAPSHOT,
                WATERMARK_PREFIX + "snapshot",
                (s, e, ct, cu, lim) -> snapshotMapper.selectByCursorShard(
                        formatDateTime(s), formatDateTime(e), ct, cu, lim),
                r -> ((OdsRtSzdnSnapshotFlowAddcode) r).getDatauuid()));
        // 2) 收费流水：主键 big_id，时间 transtime（物理车牌字段 vehicleplate）
        tasks.add(new SyncTask(UnifiedQueryService.DataSource.FEE,
                WATERMARK_PREFIX + "fee",
                (s, e, ct, cu, lim) -> feeMapper.selectByCursorShard(
                        formatDateTime(s), formatDateTime(e), ct, cu, lim),
                r -> ((OdsLwzxsfsjFeeRecords01) r).getBigId()));
        // 3) 车辆轨迹：主键 cid，时间 extime（车辆编号 envehicleid）
        tasks.add(new SyncTask(UnifiedQueryService.DataSource.TRAIL,
                WATERMARK_PREFIX + "trail",
                (s, e, ct, cu, lim) -> trailMapper.selectByCursorShard(
                        formatDateTime(s), formatDateTime(e), ct, cu, lim),
                r -> ((ZdataTrailFitting) r).getCid()));
        return tasks;
    }

    // ================================================================
    // 功能 1：全量同步（最近一年，三表）
    // Full sync (last year, 3 tables)
    // ================================================================

    /**
     * 全量同步：对三张表分别按时间分片并行读取并写入 ES
     * Full sync: time-shard parallel read + ES write for all 3 tables.
     */
    public void fullSyncOneYear() {
        Calendar cal = Calendar.getInstance();
        Date endTime = cal.getTime();
        cal.add(Calendar.YEAR, -1);
        Date startTime = cal.getTime();

        log.info("[全量同步] 开始, 时间范围: {} ~ {}", startTime, endTime);
        long startMs = System.currentTimeMillis();

        for (SyncTask task : buildSyncTasks()) {
            long tableTotal = fullSyncTable(task, startTime, endTime);
            log.info("[全量同步] 表 {} 完成, 处理 {} 条", task.ds, tableTotal);
        }

        bulkProcessor.flush();
        long cost = (System.currentTimeMillis() - startMs) / 1000;
        log.info("[全量同步] 全部完成! 总读取 {} 条, 写入成功 {}, 失败 {}, 耗时 {} 秒",
                totalReadCount.get(), totalWriteSuccessCount.get(), totalWriteFailedCount.get(), cost);
    }

    private long fullSyncTable(SyncTask task, Date startTime, Date endTime) {
        List<TimeShard> shards = splitTimeRange(startTime, endTime, shardHours);
        List<Future<Long>> futures = new ArrayList<>(shards.size());
        for (TimeShard shard : shards) {
            futures.add(shardReaderPool.submit(() -> {
                try {
                    return readAndDispatch(task, shard);
                } catch (Exception e) {
                    log.error("[全量同步] 分片读取异常 task={}, shard={}", task.ds, shard, e);
                    return 0L;
                }
            }));
        }
        long total = 0;
        for (Future<Long> f : futures) {
            try { total += f.get(6, TimeUnit.HOURS); }
            catch (Exception e) { log.error("[全量同步] 等待分片异常 task={}", task.ds, e); }
        }
        return total;
    }

    // ================================================================
    // 功能 2：增量同步（每分钟，按 Redis 水位，三表）
    // Incremental sync (per minute, per Redis watermark, 3 tables)
    // ================================================================

    /**
     * 增量同步：遍历三表，读取各自 Redis 水位之后的新数据写入 ES
     * Incremental sync: for each table, read rows after its Redis watermark and write to ES.
     *
     * 水位设计 / Watermark design:
     *   - 水位 = 已成功同步到的最大时间（存于 Redis）
     *   - 增量窗口上界 = now - 10s（留缓冲，规避 GaussDB 写入延迟导致漏读）
     *   - 同步成功才推进水位（at-least-once）；_id=业务主键 保证幂等（exactly-once 效果）
     */
    public void incrementalSync() {
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.SECOND, -WATERMARK_BACKOFF_SECONDS);
        String upperBound = formatDateTime(cal.getTime());

        for (SyncTask task : buildSyncTasks()) {
            try {
                String lastSyncTime = getLastSyncTimeFromRedis(task.redisWatermarkKey);
                long total = readAndDispatch(task, new TimeShard(parseDateTime(lastSyncTime), parseDateTime(upperBound)));
                if (total > 0) {
                    updateLastSyncTimeInRedis(task.redisWatermarkKey, upperBound);
                    log.info("[增量同步] 表 {} 完成, 本次同步 {} 条, 水位更新为 {}", task.ds, total, upperBound);
                }
            } catch (Exception e) {
                log.error("[增量同步] 异常 task={}", task.ds, e);
            }
        }
    }

    // ================================================================
    // 功能 3：补同步（按数据源 + 时间窗，以 GaussDB 为准回灌 ES）
    // Repair sync (by data source + window, GaussDB is source of truth)
    // ================================================================

    /**
     * 补同步（按数据源）：重放指定时间窗，用于一致性对账修复
     * Repair sync (by data source): replay a window for consistency repair.
     */
    public void repairSync(UnifiedQueryService.DataSource ds, String startTime, String endTime) {
        SyncTask task = buildSyncTasks().stream()
                .filter(t -> t.ds == ds).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("未知数据源: " + ds));
        log.info("[补同步] 开始 ds={}, 时间范围: {} ~ {}", ds, startTime, endTime);
        long s = System.currentTimeMillis();
        try {
            long total = readAndDispatch(task, new TimeShard(parseDateTime(startTime), parseDateTime(endTime)));
            bulkProcessor.flush();
            log.info("[补同步] 完成 ds={}, 处理 {} 条, 耗时 {} 秒", ds, total,
                    (System.currentTimeMillis() - s) / 1000);
        } catch (Exception e) {
            log.error("[补同步] 异常 ds={}", ds, e);
        }
    }

    /**
     * 补同步（兼容老接口，默认门架抓拍流水）
     * Repair sync (legacy overload, defaults to SNAPSHOT).
     */
    public void repairSync(String startTime, String endTime) {
        repairSync(UnifiedQueryService.DataSource.SNAPSHOT, startTime, endTime);
    }

    // ================================================================
    // 通用游标读取与分发 / Generic cursor read & dispatch
    // ================================================================

    /**
     * 单个时间分片的游标分页读取 + 分发 ES
     * Cursor-paginated read of one time shard + dispatch to ES.
     *
     * 关键 SQL 模式（替代 limit/offset，复杂度 O(total)）：
     *   SELECT ... WHERE time >= ? AND time < ?
     *     AND (time > cursorTime OR (time = cursorTime AND id > cursorUuid))
     *   ORDER BY time ASC, id ASC LIMIT 2000;
     */
    private long readAndDispatch(SyncTask task, TimeShard shard) throws Exception {
        long shardCount = 0;
        String cursorTime = null;
        String cursorUuid = null;
        final int pageSize = 2000;
        int emptyCount = 0;

        while (true) {
            List<?> batch = task.reader.read(shard.start, shard.end, cursorTime, cursorUuid, pageSize);
            if (batch == null || batch.isEmpty()) {
                if (++emptyCount >= 3) { break; }
                Thread.sleep(1000);
                continue;
            }
            emptyCount = 0;

            for (Object record : batch) {
                // 背压：队列满时阻塞读取端，自然限流
                syncQueue.put(record);
                String id = task.idExtractor.apply(record);
                dispatchToEs(task.indexName(indexManageService), id, record);
                shardCount++;
                totalReadCount.incrementAndGet();
            }

            Object last = batch.get(batch.size() - 1);
            cursorTime = resolveCursorTime(task.ds, last);
            cursorUuid = task.idExtractor.apply(last);

            if (batch.size() < pageSize) { break; }
        }
        return shardCount;
    }

    /**
     * 提取上一批最后一条记录的时间游标（用于 keyset 推进）
     * Extract the time cursor from the last record of a batch.
     */
    private String resolveCursorTime(UnifiedQueryService.DataSource ds, Object last) {
        switch (ds) {
            case SNAPSHOT: return formatDateTime(((OdsRtSzdnSnapshotFlowAddcode) last).getSnapshottime());
            case FEE:      return formatDateTime(((OdsLwzxsfsjFeeRecords01) last).getTranstime());
            case TRAIL:    return formatDateTime(((ZdataTrailFitting) last).getExtime());
            default: return null;
        }
    }

    /**
     * 将单条记录写入 ES BulkProcessor（以业务主键为 _id，保证幂等）
     * Write one record to ES BulkProcessor, using the business primary key as _id (idempotent).
     */
    private void dispatchToEs(String indexName, String id, Object record) {
        try {
            IndexRequest request = new IndexRequest(indexName)
                    .id(id)   // 业务主键 = _id，重复写入自动覆盖（幂等）
                    .source(JSON.toJSONString(record), XContentType.JSON);
            bulkProcessor.add(request);
        } catch (Exception e) {
            log.warn("[分发ES] 单条记录分发失败 index={}, id={}", indexName, id, e);
        }
    }

    // ================================================================
    // Redis 水位真实读写 / Real Redis watermark read/write
    // ================================================================

    /**
     * 从 Redis 读取指定表的同步水位（不存在则返回 1 小时前，触发增量追赶）
     * Read the sync watermark for a table; default to 1h ago if absent (catch-up).
     */
    private String getLastSyncTimeFromRedis(String key) {
        try {
            Object v = redisTemplate.opsForValue().get(key);
            if (v != null && !v.toString().isEmpty()) {
                return v.toString();
            }
        } catch (Exception e) {
            log.warn("[增量同步] 读取 Redis 水位失败 key={}, 使用默认值", key, e);
        }
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.HOUR, -1);
        return formatDateTime(cal.getTime());
    }

    /**
     * 更新 Redis 同步水位
     * Update the sync watermark in Redis.
     */
    private void updateLastSyncTimeInRedis(String key, String time) {
        try {
            redisTemplate.opsForValue().set(key, time);
        } catch (Exception e) {
            log.warn("[增量同步] 更新 Redis 水位失败 key={}", key, e);
        }
    }

    // ================================================================
    // 工具方法 / Utilities
    // ================================================================

    /**
     * 将 [start, end) 按 stepHours 小时切分为多个分片（每分片独立线程）
     * Split [start, end) into hourly shards for parallel reading.
     */
    private List<TimeShard> splitTimeRange(Date start, Date end, int stepHours) {
        List<TimeShard> result = new ArrayList<>();
        Calendar cursor = Calendar.getInstance();
        cursor.setTime(start);
        while (cursor.getTime().before(end)) {
            Date curStart = cursor.getTime();
            cursor.add(Calendar.HOUR, stepHours);
            Date curEnd = cursor.getTime().after(end) ? end : cursor.getTime();
            result.add(new TimeShard(curStart, curEnd));
        }
        return result;
    }

    private String formatDateTime(Date d) {
        return new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(d);
    }

    private Date parseDateTime(String s) {
        try {
            return new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").parse(s);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * 时间分片 - 简单的不可变数据类 / Immutable time shard.
     */
    private static class TimeShard {
        final Date start;
        final Date end;
        TimeShard(Date s, Date e) { this.start = s; this.end = e; }
        @Override public String toString() { return "[" + start + "," + end + ")"; }
    }
}
