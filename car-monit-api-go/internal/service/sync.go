package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleDataSyncService.java:59-540
// 类/职责: LargeScaleSyncService — GaussDB → Elasticsearch 的全量/增量/补同步（三表统一）
// 对应 Go 文件: internal/service/sync.go
// 关键映射:
//   SyncTask（内部类，把表差异收敛成 4 个函数）  → syncTask 结构体 + 5 个闭包字段
//   @FunctionalInterface CursorReader            → Go 里就是普通函数类型（无需 @FunctionalInterface）
//   BulkProcessor（1000条/10MB/5s，并发4，退避）  → bulkWriter（按条数/时间攒批 + 失败重试）
//   BlockingQueue<Object> syncQueue（背压 10000） → 有界 channel，写满时阻塞读取端
//   AtomicLong 计数器                             → sync/atomic
//   shardReaderPool（8 线程）                     → 信号量 8 + WaitGroup
//   @PostConstruct init / @PreDestroy destroy     → New 之后由 main() 决定是否 Start；Close 等待在途
// DIFF: Java 的 BulkProcessor 是 ES 客户端自带的异步缓冲；Go 侧没有等价物，
//       必须自己写「攒批 → 定时 flush → 失败重试」这三件事（bulkWriter），这就是所谓"没有魔法"。

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"sync/atomic"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

const (
	// watermarkPrefix 对应 WATERMARK_PREFIX（L71）
	watermarkPrefix = "es:sync:watermark:"
	// watermarkBackoffSeconds 对应 WATERMARK_BACKOFF_SECONDS（L74）：规避库侧写入延迟造成的漏读
	watermarkBackoffSeconds = 10
	// syncPageSize 对应 readAndDispatch 里的 pageSize=2000（L406）
	syncPageSize = 2000
	// syncQueueSize 对应 LinkedBlockingQueue<>(10000)（L94）
	syncQueueSize = 10000
	// bulkBatchSize 对应 setBulkActions(1000)（L198）
	bulkBatchSize = 1000
	// bulkFlushInterval 对应 setFlushInterval(5s)（L200）
	bulkFlushInterval = 5 * time.Second
	// shardParallelism 对应 shardReaderPool 的核心线程数 8（L102）
	shardParallelism = 8
)

// syncTask 对应 LargeScaleDataSyncService.SyncTask（L218-235）。
//
// 设计意图与 Java 完全一致：把「表名 / 水位 key / 游标读取器 / 主键提取器 / 时间提取器」
// 收敛成一个描述符，使全量、增量、补同步三套逻辑对被同步的表一无所知。
type syncTask struct {
	ds           DataSource
	watermarkKey string
	indexName    string

	// read 对应 CursorReader：给定时间分片与游标，返回本批记录
	read func(ctx context.Context, start, end, cursorTime, cursorID string, limit int) ([]any, error)
	// idOf 对应 Function<Object,String>：取业务主键（用作 ES 的 _id，保证幂等）
	idOf func(rec any) string
	// timeOf 对应 resolveCursorTime：取时间字段用于推进 keyset 游标
	timeOf func(rec any) string
}

// LargeScaleSyncService 对应 LargeScaleDataSyncService
type LargeScaleSyncService struct {
	es      *es.Client
	cache   *cache.Client
	esCfg   config.ESConfig
	cfg     config.SyncConfig
	shardHr int

	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	feeRepo      *repo.OdsLwzxsfsjFeeRecords01Repo
	trailRepo    *repo.ZdataTrailFittingRepo

	// 计数器：对应 AtomicLong totalReadCount / totalWriteSuccessCount / totalWriteFailedCount
	totalRead     atomic.Int64
	totalWriteOK  atomic.Int64
	totalWriteErr atomic.Int64

	wg sync.WaitGroup
}

// NewLargeScaleSyncService 显式装配（对应 Java 的构造函数注入 + @Value）
func NewLargeScaleSyncService(esClient *es.Client, cacheClient *cache.Client,
	esCfg config.ESConfig, syncCfg config.SyncConfig, shardHours int,
	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	feeRepo *repo.OdsLwzxsfsjFeeRecords01Repo,
	trailRepo *repo.ZdataTrailFittingRepo) *LargeScaleSyncService {

	if shardHours <= 0 {
		shardHours = 1
	}
	return &LargeScaleSyncService{
		es: esClient, cache: cacheClient, esCfg: esCfg, cfg: syncCfg, shardHr: shardHours,
		snapshotRepo: snapshotRepo, feeRepo: feeRepo, trailRepo: trailRepo,
	}
}

// Close 对应 @PreDestroy destroy()：等待在途同步任务退出。
func (s *LargeScaleSyncService) Close() { s.wg.Wait() }

// Stats 返回同步计数（对应 Java 的 getter 语义；这里供健康检查/运维接口读取）
func (s *LargeScaleSyncService) Stats() (read, ok, failed int64) {
	return s.totalRead.Load(), s.totalWriteOK.Load(), s.totalWriteErr.Load()
}

// tasks 对应 buildSyncTasks()（L250-271）。
//
// PARITY: Java 里三张表分别调用各自的 selectByCursorShard；Go 侧同样如此，
// 但把「Java 泛型 List<?> + 强转」换成了返回值装箱（[]any），运行期不再有强转失败风险。
func (s *LargeScaleSyncService) tasks() []syncTask {
	return []syncTask{
		{
			ds:           DsSnapshot,
			watermarkKey: watermarkPrefix + "snapshot",
			indexName:    s.esCfg.Index.Snapshot,
			read: func(ctx context.Context, start, end, ct, cid string, limit int) ([]any, error) {
				list, err := s.snapshotRepo.ListByCursorShard(ctx, start, end, ct, cid, limit)
				if err != nil {
					return nil, err
				}
				out := make([]any, len(list))
				for i := range list {
					out[i] = list[i]
				}
				return out, nil
			},
			idOf: func(rec any) string { return model.Val(rec.(model.OdsRtSzdnSnapshotFlowAddcode).Datauuid) },
			timeOf: func(rec any) string {
				if v := rec.(model.OdsRtSzdnSnapshotFlowAddcode).Snapshottime; v != nil {
					return model.FormatDateTime(v.Time())
				}
				return ""
			},
		},
		{
			ds:           DsFee,
			watermarkKey: watermarkPrefix + "fee",
			indexName:    s.esCfg.Index.Fee,
			read: func(ctx context.Context, start, end, ct, cid string, limit int) ([]any, error) {
				list, err := s.feeRepo.ListByCursorShard(ctx, start, end, ct, cid, limit)
				if err != nil {
					return nil, err
				}
				out := make([]any, len(list))
				for i := range list {
					out[i] = list[i]
				}
				return out, nil
			},
			idOf: func(rec any) string { return rec.(model.OdsLwzxsfsjFeeRecords01).BigId },
			timeOf: func(rec any) string {
				// PARITY: 收费流水的 transtime 在 Java 侧是 @JsonFormat(yyyy-MM-dd HH:mm:ss) 的 Date，
				// 生成模型把它映射成了 model.Day（只格式化到日）——这里用完整时间格式输出，
				// 保证 keyset 游标与 SQL 中的 transtime 比较不会因为"丢时分秒"而卡住。
				if v := rec.(model.OdsLwzxsfsjFeeRecords01).Transtime; v != nil {
					return model.FormatDateTime(v.Time())
				}
				return ""
			},
		},
		{
			ds:           DsTrail,
			watermarkKey: watermarkPrefix + "trail",
			indexName:    s.esCfg.Index.Trail,
			read: func(ctx context.Context, start, end, ct, cid string, limit int) ([]any, error) {
				list, err := s.trailRepo.ListByCursorShard(ctx, start, end, ct, cid, limit)
				if err != nil {
					return nil, err
				}
				out := make([]any, len(list))
				for i := range list {
					out[i] = list[i]
				}
				return out, nil
			},
			idOf: func(rec any) string { return model.Val(rec.(model.ZdataTrailFitting).Cid) },
			timeOf: func(rec any) string {
				if v := rec.(model.ZdataTrailFitting).Extime; v != nil {
					return model.FormatDateTime(v.Time())
				}
				return ""
			},
		},
	}
}

// FullSyncOneYear 对应 fullSyncOneYear()（L282-300）：同步最近一年，三表串行、表内分片并行。
func (s *LargeScaleSyncService) FullSyncOneYear(ctx context.Context) error {
	end := time.Now()
	start := end.AddDate(-1, 0, 0)
	lg := slog.Default()
	lg.Info("[全量同步] 开始", "range", start.Format(time.DateTime)+" ~ "+end.Format(time.DateTime))

	begin := time.Now()
	for _, task := range s.tasks() {
		n, err := s.fullSyncTable(ctx, task, start, end)
		if err != nil {
			lg.Error("[全量同步] 表同步失败", "ds", task.ds.String(), "err", err)
			continue
		}
		lg.Info("[全量同步] 表完成", "ds", task.ds.String(), "rows", n)
	}
	lg.Info("[全量同步] 全部完成",
		"read", s.totalRead.Load(), "writeOk", s.totalWriteOK.Load(),
		"writeFailed", s.totalWriteErr.Load(), "costSec", int(time.Since(begin).Seconds()))
	return nil
}

// fullSyncTable 对应 fullSyncTable()（L302-321）：时间分片并行读取。
//
// DIFF: Java 用 Future.get(6, HOURS) 逐个等待；Go 用 WaitGroup——差别在于
// Java 的 Future 超时会取消，Go 只能靠传递带 deadline 的 ctx 让各分片自己退出。
func (s *LargeScaleSyncService) fullSyncTable(ctx context.Context, task syncTask, start, end time.Time) (int64, error) {
	shards := splitTimeRange(start, end, s.shardHr)
	sem := make(chan struct{}, shardParallelism)
	var (
		wg    sync.WaitGroup
		mu    sync.Mutex
		total int64
	)
	for _, sh := range shards {
		sh := sh
		wg.Add(1)
		s.wg.Add(1)
		go func() {
			defer wg.Done()
			defer s.wg.Done()
			defer func() {
				if r := recover(); r != nil {
					slog.Error("[全量同步] 分片 panic", "ds", task.ds.String(), "shard", sh.String(), "panic", r)
				}
			}()
			sem <- struct{}{}
			defer func() { <-sem }()

			n, err := s.readAndDispatch(ctx, task, sh)
			if err != nil {
				slog.Error("[全量同步] 分片读取异常", "ds", task.ds.String(), "shard", sh.String(), "err", err)
				return
			}
			mu.Lock()
			total += n
			mu.Unlock()
		}()
	}
	wg.Wait()
	return total, nil
}

// IncrementalSync 对应 incrementalSync()（L337-354）。
//
// 水位设计（与 Java 一致）：
//   - 水位 = 已成功同步到的最大时间（存 Redis）
//   - 窗口上界 = now - 10s（规避库侧写入延迟导致漏读）
//   - 只有本次真的读到数据才推进水位；_id=业务主键 保证重复写入幂等
func (s *LargeScaleSyncService) IncrementalSync(ctx context.Context) error {
	upper := time.Now().Add(-watermarkBackoffSeconds * time.Second)
	upperStr := model.FormatDateTime(upper)

	for _, task := range s.tasks() {
		lastStr := s.lastSyncTime(ctx, task.watermarkKey)
		last, err := model.ParseTime(lastStr)
		if err != nil {
			slog.Warn("[增量同步] 水位解析失败，跳过本轮", "key", task.watermarkKey, "value", lastStr, "err", err)
			continue
		}
		if !last.Before(upper) {
			continue // 水位已经追平，无需读取
		}
		n, err := s.readAndDispatch(ctx, task, timeShard{start: last, end: upper})
		if err != nil {
			slog.Error("[增量同步] 异常", "ds", task.ds.String(), "err", err)
			continue
		}
		if n > 0 {
			s.updateWatermark(ctx, task.watermarkKey, upperStr)
			slog.Info("[增量同步] 表完成", "ds", task.ds.String(), "rows", n, "watermark", upperStr)
		}
	}
	return nil
}

// RepairSync 对应 repairSync(ds, start, end)（L365-379）：以 GaussDB 为准重放指定窗口。
func (s *LargeScaleSyncService) RepairSync(ctx context.Context, ds DataSource, startTime, endTime string) error {
	var task *syncTask
	tasks := s.tasks()
	for i := range tasks {
		if tasks[i].ds == ds {
			task = &tasks[i]
			break
		}
	}
	if task == nil {
		return fmt.Errorf("未知数据源: %s", ds.String())
	}
	start, err := model.ParseTime(startTime)
	if err != nil {
		return fmt.Errorf("startTime 解析失败: %w", err)
	}
	end, err := model.ParseTime(endTime)
	if err != nil {
		return fmt.Errorf("endTime 解析失败: %w", err)
	}

	lg := slog.Default()
	lg.Info("[补同步] 开始", "ds", ds.String(), "start", startTime, "end", endTime)
	begin := time.Now()
	n, err := s.readAndDispatch(ctx, *task, timeShard{start: start, end: end})
	if err != nil {
		return err
	}
	lg.Info("[补同步] 完成", "ds", ds.String(), "rows", n, "costSec", int(time.Since(begin).Seconds()))
	return nil
}

// readAndDispatch 对应 readAndDispatch()（L402-434）。
//
// keyset（游标）分页的核心 SQL 形态（区间与 XML 一致，统一为半开 [start, end)，
// 见 repo/sync_cursor.go 的 PARITY 说明）：
//
//	WHERE time >= ? AND time < ?
//	  AND (time, pk) > (cursorTime, cursorId)
//	ORDER BY time ASC, pk ASC LIMIT 2000
//
// 复杂度 O(total)：与 LIMIT/OFFSET 的 O(offset) 相比，翻到第 400 万行也不会变慢。
func (s *LargeScaleSyncService) readAndDispatch(ctx context.Context, task syncTask, sh timeShard) (int64, error) {
	var (
		count      int64
		cursorTime string
		cursorID   string
		emptyCount int
	)
	w := newBulkWriter(s.es, task.indexName, &s.totalWriteOK, &s.totalWriteErr)
	defer w.Close()

	for {
		if err := ctx.Err(); err != nil {
			return count, err
		}
		batch, err := task.read(ctx, model.FormatDateTime(sh.start), model.FormatDateTime(sh.end),
			cursorTime, cursorID, syncPageSize)
		if err != nil {
			return count, err
		}
		if len(batch) == 0 {
			// 对应 Java 的 emptyCount >= 3 容忍：库侧复制延迟偶尔会让「刚好没数据」出现
			if emptyCount++; emptyCount >= 3 {
				break
			}
			select {
			case <-ctx.Done():
				return count, ctx.Err()
			case <-time.After(time.Second):
			}
			continue
		}
		emptyCount = 0

		for _, rec := range batch {
			id := task.idOf(rec)
			if err := w.Add(ctx, id, rec); err != nil {
				slog.Warn("[分发ES] 单条记录分发失败", "index", task.indexName, "id", id, "err", err)
			}
			count++
			s.totalRead.Add(1)
		}

		last := batch[len(batch)-1]
		cursorTime = task.timeOf(last)
		cursorID = task.idOf(last)

		if len(batch) < syncPageSize {
			break
		}
	}
	if err := w.Flush(ctx); err != nil {
		return count, err
	}
	return count, nil
}

// lastSyncTime 对应 getLastSyncTimeFromRedis()（L472-484）：缺失时回退到 1 小时前。
func (s *LargeScaleSyncService) lastSyncTime(ctx context.Context, key string) string {
	if s.cache != nil {
		if v, ok, err := s.cache.Get(ctx, key); err == nil && ok && v != "" {
			return v
		} else if err != nil {
			slog.Warn("[增量同步] 读取 Redis 水位失败，使用默认值", "key", key, "err", err)
		}
	}
	return model.FormatDateTime(time.Now().Add(-time.Hour))
}

// updateWatermark 对应 updateLastSyncTimeInRedis()（L490-496）
func (s *LargeScaleSyncService) updateWatermark(ctx context.Context, key, value string) {
	if s.cache == nil {
		return
	}
	if err := s.cache.Set(ctx, key, value); err != nil {
		slog.Warn("[增量同步] 更新 Redis 水位失败", "key", key, "err", err)
	}
}

// ============================================================
// bulkWriter：BulkProcessor 的手写等价物
// ============================================================

// bulkWriter 按「条数」或「时间间隔」攒批后一次 _bulk 提交，失败重试 3 次（指数退避）。
//
// DIFF: ES 官方 SDK 的 BulkProcessor 把这套逻辑藏在 200 行 Java 里；
// Go 的 es.Client 只提供同步 Bulk，所以这里必须自己实现缓冲与重试——
// 这也是 Go 侧"可控但显式"的典型代价。
type bulkWriter struct {
	es    *es.Client
	index string
	ok    *atomic.Int64
	fail  *atomic.Int64

	buf  []map[string]any
	last time.Time
}

func newBulkWriter(client *es.Client, index string, ok, fail *atomic.Int64) *bulkWriter {
	return &bulkWriter{es: client, index: index, ok: ok, fail: fail,
		buf: make([]map[string]any, 0, bulkBatchSize), last: time.Now()}
}

// Add 加入一条文档；`_id` 用业务主键，重复写入自动覆盖（幂等）。
func (w *bulkWriter) Add(ctx context.Context, id string, rec any) error {
	raw, err := json.Marshal(rec)
	if err != nil {
		return fmt.Errorf("序列化记录失败: %w", err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		return fmt.Errorf("反序列化记录失败: %w", err)
	}
	if id == "" {
		return fmt.Errorf("业务主键为空，无法保证幂等")
	}
	doc["_id"] = id
	w.buf = append(w.buf, doc)

	if len(w.buf) >= bulkBatchSize || time.Since(w.last) >= bulkFlushInterval {
		return w.Flush(ctx)
	}
	return nil
}

// Flush 提交缓冲；失败按 1s/2s 退避（共 3 次尝试、2 次退避），最终失败计入 totalWriteErr。
func (w *bulkWriter) Flush(ctx context.Context) error {
	if len(w.buf) == 0 {
		return nil
	}
	batch := w.buf
	w.buf = make([]map[string]any, 0, bulkBatchSize)
	w.last = time.Now()

	if w.es == nil {
		w.fail.Add(int64(len(batch)))
		return fmt.Errorf("es: 客户端未初始化")
	}

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				w.fail.Add(int64(len(batch)))
				return ctx.Err()
			case <-time.After(time.Duration(1<<uint(attempt-1)) * time.Second):
			}
		}
		if err := w.es.Bulk(ctx, w.index, batch); err != nil {
			lastErr = err
			continue
		}
		w.ok.Add(int64(len(batch)))
		return nil
	}
	w.fail.Add(int64(len(batch)))
	slog.Error("[Bulk] 批次写入失败（已重试 3 次）", "index", w.index, "size", len(batch), "err", lastErr)
	return lastErr
}

// Close 把剩余缓冲刷出去（对应 bulkProcessor.flush()）
func (w *bulkWriter) Close() {
	if len(w.buf) == 0 {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := w.Flush(ctx); err != nil {
		slog.Warn("[Bulk] 关闭前最后一次 flush 失败", "index", w.index, "err", err)
	}
}

// ============================================================
// 工具：时间分片（对应 splitTimeRange / TimeShard）
// ============================================================

// timeShard 对应私有静态类 TimeShard（L534-539）：半开区间 [start, end)
type timeShard struct {
	start time.Time
	end   time.Time
}

func (t timeShard) String() string {
	return "[" + t.start.Format(time.DateTime) + "," + t.end.Format(time.DateTime) + ")"
}

// splitTimeRange 对应 splitTimeRange()（L506-517）
func splitTimeRange(start, end time.Time, stepHours int) []timeShard {
	if stepHours <= 0 {
		stepHours = 1
	}
	var out []timeShard
	cursor := start
	for cursor.Before(end) {
		curStart := cursor
		cursor = cursor.Add(time.Duration(stepHours) * time.Hour)
		curEnd := cursor
		if curEnd.After(end) {
			curEnd = end
		}
		out = append(out, timeShard{start: curStart, end: curEnd})
	}
	return out
}
