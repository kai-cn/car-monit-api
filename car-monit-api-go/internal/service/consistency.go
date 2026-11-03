package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/GaussEsConsistencyService.java:50-288
// 类/职责: GaussEsConsistencyService — GaussDB ↔ Elasticsearch 一致性对账与修复（四层保障的最后一层）
// 对应 Go 文件: internal/service/consistency.go
// 关键映射:
//   ConsistencyReport（静态内部类）           → ConsistencyReport 结构体
//   reconcile(ds, start, end)                → Reconcile
//   triggerRepair(ds, start, end)            → TriggerRepair
//   @Scheduled(cron = "0 30 2 * * ?")        → scheduler 里的 robfig/cron "30 2 * * *"（见 scheduler）
//   countInGaussDb / countInEs               → countInGaussDB / countInES
//   new Thread(...).start()                  → go func()（对账主流程不阻塞）
// DIFF: Java 的 @Scheduled 注解由 Spring 扫描注册；Go 没有注解扫描，
//       必须由 scheduler 包显式登记（"看不见的魔法"变成"看得见的一行注册"）。

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sync/atomic"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

// 对账状态常量（对应 Java 里的 "CONSISTENT"/"DRIFT"/"ERROR" 字符串）
const (
	ConsistencyOK    = "CONSISTENT"
	ConsistencyDrift = "DRIFT"
	ConsistencyError = "ERROR"
)

// ConsistencyReport 对应 ConsistencyReport（L90-106）。
// 字段名与 Java 保持一致，运维接口的响应因此不需要改字段名。
type ConsistencyReport struct {
	DataSource DataSource `json:"dataSource"`
	StartTime  string     `json:"startTime"`
	EndTime    string     `json:"endTime"`
	GaussDBCnt int64      `json:"gaussDbCount"`
	ESCount    int64      `json:"esCount"`
	Diff       int64      `json:"diff"`
	Status     string     `json:"status"`
	Suggestion string     `json:"suggestion"`
}

func (r ConsistencyReport) String() string {
	return fmt.Sprintf("ConsistencyReport{ds=%s, range=[%s,%s), gaussDb=%d, es=%d, diff=%d, status=%s, suggestion=%s}",
		r.DataSource.String(), r.StartTime, r.EndTime, r.GaussDBCnt, r.ESCount, r.Diff, r.Status, r.Suggestion)
}

// GaussEsConsistencyService 对应 GaussEsConsistencyService.java
type GaussEsConsistencyService struct {
	es    *es.Client
	sync  *LargeScaleSyncService
	query *UnifiedQueryService
	cfg   config.ConsistencyConfig

	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	feeRepo      *repo.OdsLwzxsfsjFeeRecords01Repo
	trailRepo    *repo.ZdataTrailFittingRepo

	// repairCounter 对应 AtomicLong repairCounter（L85）
	repairCounter atomic.Int64
}

// NewGaussEsConsistencyService 构造
func NewGaussEsConsistencyService(esClient *es.Client, syncSvc *LargeScaleSyncService,
	query *UnifiedQueryService, cfg config.ConsistencyConfig,
	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	feeRepo *repo.OdsLwzxsfsjFeeRecords01Repo,
	trailRepo *repo.ZdataTrailFittingRepo) *GaussEsConsistencyService {

	return &GaussEsConsistencyService{
		es: esClient, sync: syncSvc, query: query, cfg: cfg,
		snapshotRepo: snapshotRepo, feeRepo: feeRepo, trailRepo: trailRepo,
	}
}

// Repairs 返回累计修复次数（对应 repairCounter.get()）
func (s *GaussEsConsistencyService) Repairs() int64 { return s.repairCounter.Load() }

// Reconcile 对应 reconcile()（L117-147）：同窗口内比对两侧条数。
func (s *GaussEsConsistencyService) Reconcile(ctx context.Context, ds DataSource,
	startTime, endTime string) ConsistencyReport {

	report := ConsistencyReport{DataSource: ds, StartTime: startTime, EndTime: endTime}

	// 1) GaussDB 侧条数（依赖分区裁剪，按月分区下很快）
	dbCount, err := s.countInGaussDB(ctx, ds, startTime, endTime)
	if err != nil {
		report.Status = ConsistencyError
		report.Suggestion = err.Error()
		slog.Error("[一致性对账] GaussDB 计数失败", "ds", ds.String(), "err", err)
		return report
	}
	// 2) ES 侧条数（_count，走倒排索引）
	esCount, err := s.countInES(ctx, ds, startTime, endTime)
	if err != nil {
		report.Status = ConsistencyError
		report.Suggestion = err.Error()
		slog.Error("[一致性对账] ES 计数失败", "ds", ds.String(), "err", err)
		return report
	}

	// 3) 差异与状态（比例口径与 Java 完全一致，含除零处理）
	report.GaussDBCnt = dbCount
	report.ESCount = esCount
	report.Diff = int64(math.Abs(float64(dbCount - esCount)))
	var ratio float64
	switch {
	case dbCount == 0 && esCount == 0:
		ratio = 0
	case dbCount == 0:
		ratio = 1
	default:
		ratio = float64(report.Diff) / float64(dbCount)
	}
	if report.Diff == 0 || ratio <= s.cfg.Reconcile.DriftRatio {
		report.Status = ConsistencyOK
		report.Suggestion = "OK"
	} else {
		report.Status = ConsistencyDrift
		report.Suggestion = "建议触发 repairSync 以 GaussDB 为准回灌 ES"
	}
	slog.Info("[一致性对账]", "report", report.String())
	return report
}

// TriggerRepair 对应 triggerRepair()（L157-166）。
func (s *GaussEsConsistencyService) TriggerRepair(ctx context.Context, ds DataSource,
	startTime, endTime string) error {

	slog.Info("[一致性修复] 触发补同步", "ds", ds.String(), "start", startTime, "end", endTime)
	if err := s.sync.RepairSync(ctx, ds, startTime, endTime); err != nil {
		slog.Error("[一致性修复] 补同步失败", "ds", ds.String(), "err", err)
		return err
	}
	s.repairCounter.Add(1)
	return nil
}

// ScheduledReconcile 对应 scheduledReconcile()（L179-214）。
//
// 由 scheduler 按 cron 调用（application.yml 的 consistency.reconcile.cron 原样透传）。
// 设计（与 Java 一致）：
//   - 关闭开关时直接返回
//   - 逐月回看 lookback-months 个月，避免一次性 COUNT 整年
//   - 仅当漂移超阈值才异步补同步，避免修复风暴
func (s *GaussEsConsistencyService) ScheduledReconcile(ctx context.Context) {
	if !s.cfg.Reconcile.Enabled {
		return
	}
	lookback := s.cfg.Reconcile.LookbackMonth
	if lookback <= 0 {
		lookback = 3
	}
	slog.Info("[一致性对账] 定时任务启动", "lookbackMonths", lookback)

	// 从「当月 1 号 00:00:00」开始往前推
	monthEnd := time.Date(time.Now().Year(), time.Now().Month(), 1, 0, 0, 0, 0, time.Local)
	for i := 0; i < lookback; i++ {
		monthStart := monthEnd.AddDate(0, -1, 0)
		start := model.FormatDateTime(monthStart)
		end := model.FormatDateTime(monthEnd)

		for _, ds := range []DataSource{DsSnapshot, DsFee, DsTrail} {
			report := s.Reconcile(ctx, ds, start, end)
			if report.Status == ConsistencyDrift {
				// 异步触发修复，避免阻塞对账主流程（对应 Java 的 new Thread(...).start()）
				fds, fs, fe := ds, start, end
				go func() {
					defer func() {
						if r := recover(); r != nil {
							slog.Error("[一致性对账] 修复协程 panic", "ds", fds.String(), "panic", r)
						}
					}()
					if err := s.TriggerRepair(context.WithoutCancel(ctx), fds, fs, fe); err != nil {
						slog.Warn("[一致性对账] 自动修复失败", "ds", fds.String(), "err", err)
					}
				}()
			}
		}
		monthEnd = monthStart
	}
	slog.Info("[一致性对账] 定时任务完成", "repairs", s.repairCounter.Load())
}

// countInGaussDB 对应 countInGaussDb()（L219-240）
func (s *GaussEsConsistencyService) countInGaussDB(ctx context.Context, ds DataSource,
	start, end string) (int64, error) {

	switch ds {
	case DsSnapshot:
		return s.snapshotRepo.CountBetween(ctx, start, end)
	case DsFee:
		return s.feeRepo.CountBetween(ctx, start, end)
	case DsTrail:
		return s.trailRepo.CountBetween(ctx, start, end)
	}
	return 0, fmt.Errorf("未知数据源: %s", ds.String())
}

// countInES 对应 countInEs()（L245-261）。
//
// DIFF: Java 注释里提到"用 SearchRequest(size=0 + track_total_hits) 而非 Count API 以规避版本差异"；
// Go 侧我们自己的客户端就是 HTTP，直接打 _count 更省一次文档扫描，语义等价。
func (s *GaussEsConsistencyService) countInES(ctx context.Context, ds DataSource,
	start, end string) (int64, error) {

	if s.es == nil {
		return 0, fmt.Errorf("Elasticsearch 未启用")
	}
	meta := s.query.Meta(ds)
	body := map[string]any{
		"query": map[string]any{
			"range": map[string]any{meta.TimeField: map[string]any{
				"format": "yyyy-MM-dd HH:mm:ss", "gte": start, "lte": end,
			}},
		},
	}
	return s.es.Count(ctx, meta.Index, body)
}
