package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SnapshotFlowSyncService.java:22-176
// 类/职责: SnapshotFlowSyncService — 把快照流水「全量续传 + 增量拉取」推进 Kafka
// 对应 Go 文件: internal/service/snapshot_sync.go
// 关键映射:
//   LAST_SYNC_ID_KEY / LAST_SYNC_TIME_KEY      → lastSyncIDKey / lastSyncTimeKey
//   @PostConstruct init() + Executors(2)       → Start(ctx) 起两个 goroutine
//   fullSync()：big_id keyset 翻页              → FullSync
//   incrementalSync()：snapshottime 窗口轮询    → IncrementalSync + incrementalSyncOnce
//   @Value("${sync.batch-size:1000}")          → config.SyncConfig.BatchSize
//   @Value("${sync.full-sync-enabled:true}")   → config.SyncConfig.FullSyncEnabled
//   @Value("${sync.incremental-sync-interval:60000}") → config.SyncConfig.IncrementalSyncInterval
//
// DIFF: Java 的 Thread.sleep(100) / Thread.sleep(interval) 不可中断；
// Go 用 select{stopCh, timer}，Close() 立即退出，容器滚动发布时不会留下写一半的同步协程。
//
// PARITY: 断点续传的两个 Redis key 沿用 Java 的名字，但**存储格式不同**——
// Java 用 RedisTemplate 的 JDK 序列化（二进制），Go 存毫秒时间戳字符串。
// 因此不能与旧版本共用同一个 Redis 实例的这两个 key；首次切换请先 DEL（README「升级注意」）。

import (
	"context"
	"log/slog"
	"strconv"
	"sync"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
	"github.com/ruoyi/car-monit-api-go/internal/utils"
)

const (
	lastSyncTimeKey = "snapshot_flow:last_sync_time"
	lastSyncIDKey   = "snapshot_flow:last_sync_id"

	fullSyncPause = 100 * time.Millisecond // 对应 Thread.sleep(100)，避免打满数据库
)

// SnapshotFlowSyncService 对应 SnapshotFlowSyncService.java
type SnapshotFlowSyncService struct {
	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	producer     *KafkaProducerService
	cache        *cache.Client
	cfg          config.SyncConfig

	stopCh   chan struct{}
	stopOnce sync.Once
	wg       sync.WaitGroup
}

// NewSnapshotFlowSyncService 构造
func NewSnapshotFlowSyncService(snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	producer *KafkaProducerService, cacheClient *cache.Client,
	cfg config.SyncConfig) *SnapshotFlowSyncService {

	return &SnapshotFlowSyncService{
		snapshotRepo: snapshotRepo, producer: producer, cache: cacheClient, cfg: cfg,
		stopCh: make(chan struct{}),
	}
}

// Start 对应 @PostConstruct init()（L47-56）：
// 固定 2 线程池 → 两个 goroutine（全量可选、增量常驻）。
func (s *SnapshotFlowSyncService) Start(ctx context.Context) {
	if s.cfg.FullSyncEnabled {
		s.wg.Add(1)
		go func() {
			defer s.wg.Done()
			// PARITY/规范：常驻协程必须自带 recover —— repo 层的 panic 若逃逸会直接杀掉进程，
			// 而 Java 侧 @PostConstruct 线程池里的异常只终止该任务。此处与仓库内其他后台协程一致。
			defer func() {
				if r := recover(); r != nil {
					slog.Error("[快照同步] 全量同步协程 panic 退出", "panic", r)
				}
			}()
			if err := s.FullSync(ctx); err != nil {
				slog.Error("[快照同步] 全量同步异常", "err", err)
			}
		}()
	}
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		defer func() {
			if r := recover(); r != nil {
				slog.Error("[快照同步] 增量同步协程 panic 退出", "panic", r)
			}
		}()
		s.IncrementalSync(ctx)
	}()
	slog.Info("[快照同步] 已启动", "fullSyncEnabled", s.cfg.FullSyncEnabled,
		"batchSize", s.cfg.BatchSize, "incrementalIntervalMs", s.cfg.IncrementalSyncInterval)
}

// Close 停止两个同步协程（Java 侧没有这个钩子，见文件头 DIFF）。
func (s *SnapshotFlowSyncService) Close() {
	s.stopOnce.Do(func() { close(s.stopCh) })
	s.wg.Wait()
}

// FullSync 对应 fullSync()（L63-111）：按 big_id keyset 翻页，进度写 Redis，可断点续传。
//
// 要点：
//  1. 每批取 cfg.BatchSize 条，big_id 严格递增 → 天然无重复、无深翻页；
//  2. 每批结束后才更新 Redis 游标（崩溃最多重放一批，不会跳数据）；
//  3. 空批即完成，方法返回（对应 Java 的 break）。
func (s *SnapshotFlowSyncService) FullSync(ctx context.Context) error {
	batchSize := s.cfg.BatchSize
	if batchSize <= 0 {
		batchSize = 1000
	}
	slog.Info("[快照同步] 开始全量同步数据")

	lastSyncID := s.getStr(ctx, lastSyncIDKey)
	total := 0
	for {
		if s.stopped() {
			slog.Info("[快照同步] 全量同步被取消", "synced", total)
			return nil
		}

		list, err := s.snapshotRepo.ListByBigIDAfter(ctx, lastSyncID, batchSize)
		if err != nil {
			return err
		}
		if len(list) == 0 {
			slog.Info("[快照同步] 全量同步完成", "synced", total)
			return nil
		}

		for i := range list {
			data := &list[i]
			// 消息 key 用 bigId，保证同一主键进同一分区（顺序性）
			if _, err := s.producer.SendSnapshotFlowData(ctx, data, model.Val(data.BigId)); err != nil {
				// PARITY: Java 不检查返回值也不中断——单条失败靠可靠性服务后面补偿，整批继续
				slog.Error("[快照同步] 单条发送失败", "bigId", model.Val(data.BigId), "err", err)
			}
			lastSyncID = model.Val(data.BigId)
			total++
		}

		s.setStr(ctx, lastSyncIDKey, lastSyncID)
		slog.Info("[快照同步] 已同步一批", "batch", len(list), "total", total, "cursor", lastSyncID)

		if !s.sleep(fullSyncPause) {
			slog.Info("[快照同步] 全量同步被取消", "synced", total)
			return nil
		}
	}
}

// IncrementalSync 对应 incrementalSync()（L118-175）：常驻轮询。
//
// 每轮：上次同步时间（缺省 now-1 天）→ 取 (last, now] 的一批 → 逐条发 → 推进游标 → 睡 interval。
func (s *SnapshotFlowSyncService) IncrementalSync(ctx context.Context) {
	interval := time.Duration(s.cfg.IncrementalSyncInterval) * time.Millisecond
	if interval <= 0 {
		interval = 60 * time.Second
	}
	slog.Info("[快照同步] 开始增量同步数据", "intervalMs", interval.Milliseconds())

	for {
		if s.stopped() {
			slog.Info("[快照同步] 增量同步退出")
			return
		}
		if err := s.incrementalSyncOnce(ctx); err != nil {
			slog.Error("[快照同步] 增量同步异常", "err", err)
		}
		if !s.sleep(interval) {
			slog.Info("[快照同步] 增量同步退出")
			return
		}
	}
}

// incrementalSyncOnce 抽出一轮增量逻辑（Java 把整轮写在 while 里，抽出来才能单测）。
func (s *SnapshotFlowSyncService) incrementalSyncOnce(ctx context.Context) error {
	batchSize := s.cfg.BatchSize
	if batchSize <= 0 {
		batchSize = 1000
	}

	currentTime := time.Now()
	lastSyncTime, ok := s.getTime(ctx, lastSyncTimeKey)
	if !ok {
		// 首次增量：从 1 天前开始，防止切换期漏数据
		lastSyncTime = utils.AddDays(currentTime, -1)
	}

	list, err := s.snapshotRepo.ListIncrementalBySnapshotTime(ctx, lastSyncTime, currentTime, batchSize)
	if err != nil {
		return err
	}
	if len(list) == 0 {
		return nil
	}

	for i := range list {
		data := &list[i]
		if _, err := s.producer.SendSnapshotFlowData(ctx, data, model.Val(data.BigId)); err != nil {
			slog.Error("[快照同步] 增量单条发送失败", "bigId", model.Val(data.BigId), "err", err)
		}
		if data.Snapshottime != nil {
			lastSyncTime = data.Snapshottime.Time()
		}
	}
	s.setTime(ctx, lastSyncTimeKey, lastSyncTime)
	slog.Info("[快照同步] 增量同步完成", "count", len(list), "syncTime", lastSyncTime)
	return nil
}

// ---- 游标读写（Redis）----

func (s *SnapshotFlowSyncService) getStr(ctx context.Context, key string) string {
	if s.cache == nil {
		return ""
	}
	v, ok, err := s.cache.Get(ctx, key)
	if err != nil || !ok {
		return ""
	}
	return v
}

func (s *SnapshotFlowSyncService) setStr(ctx context.Context, key, val string) {
	if s.cache == nil {
		return
	}
	if err := s.cache.Set(ctx, key, val); err != nil {
		slog.Warn("[快照同步] 写游标失败", "key", key, "err", err)
	}
}

func (s *SnapshotFlowSyncService) getTime(ctx context.Context, key string) (time.Time, bool) {
	raw := s.getStr(ctx, key)
	if raw == "" {
		return time.Time{}, false
	}
	ms, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || ms <= 0 {
		slog.Warn("[快照同步] 游标格式非法，按首次同步处理", "key", key, "value", raw)
		return time.Time{}, false
	}
	return time.UnixMilli(ms), true
}

func (s *SnapshotFlowSyncService) setTime(ctx context.Context, key string, t time.Time) {
	s.setStr(ctx, key, strconv.FormatInt(t.UnixMilli(), 10))
}

// stopped 非阻塞检查退出信号
func (s *SnapshotFlowSyncService) stopped() bool {
	select {
	case <-s.stopCh:
		return true
	default:
		return false
	}
}

// sleep 可被 Close() 打断的等待；返回 false 表示应退出循环
func (s *SnapshotFlowSyncService) sleep(d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-s.stopCh:
		return false
	case <-timer.C:
		return true
	}
}
