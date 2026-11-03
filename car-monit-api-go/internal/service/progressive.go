package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/ProgressiveQueryArchitectureService.java:49-478
// 类/职责: ProgressiveQueryService — 按数据量级别自动切换三阶段查询策略
// 对应 Go 文件: internal/service/progressive.go
// 关键映射:
//   enum DataScaleLevel                      → type DataScaleLevel int（Go 枚举）
//   @Value("${optimization.scale-level}")    → cfg.ScaleLevel
//   @Autowired(required = false) ES          → esClient 可为 nil（nil 即"阶段三未启用"）
//   QueryRequest / QueryResult 内部类         → 顶层结构体（Go 不允许嵌套类）
// DIFF: Java 用 switch(enum) 分派到 3 个 private 方法；Go 里保持同样结构，
//       但用 interface{} 返回不同实体类型（Java 用 List<?>，Go 用 any）——泛型化反而会让调用方更啰嗦。

import (
	"context"
	"fmt"
	"log/slog"
	"strconv"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/cache"
	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/model"
	"github.com/ruoyi/car-monit-api-go/internal/repo"
)

// DataScaleLevel 对应 DataScaleLevel 枚举（L56-63）
type DataScaleLevel int

const (
	// Level10M 千万级：单表 < 5000 万
	Level10M DataScaleLevel = iota
	// Level100M 亿级：5000 万 ~ 5 亿
	Level100M
	// Level1B 十亿级：> 5 亿
	Level1B
)

// Name 对应 Java 的 enum.name()（Controller 的 /scale-level 直接回显它）
func (l DataScaleLevel) Name() string {
	switch l {
	case Level100M:
		return "LEVEL_100M"
	case Level1B:
		return "LEVEL_1B"
	default:
		return "LEVEL_10M"
	}
}

// parseScaleLevel 对应 DataScaleLevel.valueOf(configured) + 异常降级（L115-119）
func parseScaleLevel(s string) DataScaleLevel {
	switch s {
	case "LEVEL_100M":
		return Level100M
	case "LEVEL_1B":
		return Level1B
	case "LEVEL_10M":
		return Level10M
	}
	return Level10M // 配置非法时降级为千万级
}

// QueryRequest 对应 ProgressiveQueryArchitectureService.QueryRequest（L380-428）
type QueryRequest struct {
	StartTime   string `form:"startTime" json:"startTime"`
	EndTime     string `form:"endTime" json:"endTime"`
	Platenumber string `form:"platenumber" json:"platenumber"`
	Orgname     string `form:"orgname" json:"orgname"`
	Sectionname string `form:"sectionname" json:"sectionname"`
	Roadname    string `form:"roadname" json:"roadname"`
	Gantryname  string `form:"gantryname" json:"gantryname"`
	Tollname    string `form:"tollname" json:"tollname"`
	Cursor      string `form:"cursor" json:"cursor"`
	PageSize    int    `form:"pageSize" json:"pageSize"`
}

// Normalize 对应 Java 的 `int pageSize = 20` 默认值（@RequestParam defaultValue = "20"）
func (q *QueryRequest) Normalize() {
	if q.PageSize <= 0 {
		q.PageSize = 20
	}
}

// QueryResult 对应 QueryResult（L434-477）
type QueryResult struct {
	Data     any    `json:"data"`
	Total    int64  `json:"total"`
	Strategy string `json:"strategy"`
}

// ProgressiveQueryService 对应 ProgressiveQueryArchitectureService
type ProgressiveQueryService struct {
	configured DataScaleLevel

	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo
	feeRepo      *repo.OdsLwzxsfsjFeeRecords01Repo
	trailRepo    *repo.ZdataTrailFittingRepo
	cache        *cache.Client
	es           *esClientHolder
}

// esClientHolder 用于表达"可选依赖"（对应 @Autowired(required = false)）。
//
// DIFF: Spring 的 required=false 在启动时决定 Bean 是否存在；Go 没有容器，
// 于是用一个可为 nil 的持有者 + Healthy() 判断——差别是"是否启用"在运行期判定，可热切换。
type esClientHolder struct {
	search ESQuerier
}

// ESQuerier 是 ES 查询的最小接口（便于单测替换）
type ESQuerier interface {
	Search(ctx context.Context, index string, body map[string]any) (map[string]any, error)
}

// NewProgressiveQueryService 显式装配
func NewProgressiveQueryService(
	cfg config.OptimizationConfig,
	snapshotRepo *repo.OdsRtSzdnSnapshotFlowAddcodeRepo,
	feeRepo *repo.OdsLwzxsfsjFeeRecords01Repo,
	trailRepo *repo.ZdataTrailFittingRepo,
	cacheClient *cache.Client,
	esQuerier ESQuerier,
) *ProgressiveQueryService {
	svc := &ProgressiveQueryService{
		configured:   parseScaleLevel(cfg.ScaleLevel),
		snapshotRepo: snapshotRepo,
		feeRepo:      feeRepo,
		trailRepo:    trailRepo,
		cache:        cacheClient,
	}
	if esQuerier != nil {
		svc.es = &esClientHolder{search: esQuerier}
	}
	return svc
}

// tableCountCache / tableCountTTL 对应 L93-96
const (
	tableCountCachePrefix = "table:count:"
	tableCountTTL         = time.Hour
)

// DetectScaleLevel 对应 L105-120：Redis 缓存命中则按行数判定，否则用配置值。
func (s *ProgressiveQueryService) DetectScaleLevel(ctx context.Context, tableName string) DataScaleLevel {
	key := tableCountCachePrefix + tableName
	if s.cache != nil {
		if v, ok, err := s.cache.Get(ctx, key); err == nil && ok {
			if n, perr := strconv.ParseInt(v, 10, 64); perr == nil {
				return judgeScaleLevel(n)
			}
		}
	}
	return s.configured
}

// judgeScaleLevel 对应 L129-133
func judgeScaleLevel(count int64) DataScaleLevel {
	if count < 50_000_000 {
		return Level10M
	}
	if count < 500_000_000 {
		return Level100M
	}
	return Level1B
}

// CacheTableCount 供同步任务写入行数（Java 侧由外部写入 Redis）
func (s *ProgressiveQueryService) CacheTableCount(ctx context.Context, tableName string, count int64) error {
	if s.cache == nil {
		return nil
	}
	return s.cache.SetWithTTL(ctx, tableCountCachePrefix+tableName, count, tableCountTTL)
}

// ============================================================
// 门架抓拍流水（对应 L142-247）
// ============================================================

// QuerySnapshotFlow 对应 L142-156
func (s *ProgressiveQueryService) QuerySnapshotFlow(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	req.Normalize()
	level := s.DetectScaleLevel(ctx, "ods_rt_szdn_snapshot_flow_addcode")
	slog.Info("[渐进式查询] 门架抓拍流水", "level", level.Name(), "req", req)

	switch level {
	case Level100M:
		return s.snapshotPhase2(ctx, req)
	case Level1B:
		return s.snapshotPhase3(ctx, req)
	default:
		return s.snapshotPhase1(ctx, req)
	}
}

// snapshotPhase1 对应 L171-186：B-tree + GIN + 全量返回列表
//
// PARITY: limit 必须传 0。Java 的 querySnapshotFlowPhase1(L184) 直接调
// selectOdsRtSzdnSnapshotFlowAddcodeList(query)，全程没调 PageHelper.startPage()，
// 也没拼 LIMIT —— 它把 request.getPageSize() 存进了 QueryRequest 但这一路根本没读。
// Go 之前按直觉把 pageSize 当成 limit 传了下去，结果 Java 返 900 行、Go 返 5 行。
// total 用 list.size()（= Java 的 QueryResult.of(list, list.size(), ...)），不是 COUNT(*)。
func (s *ProgressiveQueryService) snapshotPhase1(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	q := &model.OdsRtSzdnSnapshotFlowAddcode{
		ApplyTime1:  model.Str(req.StartTime),
		ApplyTime2:  model.Str(req.EndTime),
		Platenumber: model.Str(req.Platenumber),
		Gantryname:  model.Str(req.Gantryname),
		Roadname:    model.Str(req.Roadname),
		Sectionname: model.Str(req.Sectionname),
		Orgname:     model.Str(req.Orgname),
		Tollname:    model.Str(req.Tollname),
	}
	list, err := s.snapshotRepo.List(ctx, q, 0)
	if err != nil {
		return nil, err
	}
	return &QueryResult{Data: list, Total: int64(len(list)), Strategy: "phase1-gaussdb-gin"}, nil
}

// snapshotPhase2 对应 L198-220：分区裁剪 + 游标分页
func (s *ProgressiveQueryService) snapshotPhase2(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	if req.Cursor != "" {
		list, err := s.snapshotRepo.ListByCursorShard(ctx, req.StartTime, req.EndTime, req.Cursor, "", req.PageSize)
		if err != nil {
			return nil, err
		}
		return &QueryResult{Data: list, Total: int64(len(list)), Strategy: "phase2-partition-cursor"}, nil
	}
	q := &model.OdsRtSzdnSnapshotFlowAddcode{
		ApplyTime1:  model.Str(req.StartTime),
		ApplyTime2:  model.Str(req.EndTime),
		Platenumber: model.Str(req.Platenumber),
		Gantryname:  model.Str(req.Gantryname),
		Roadname:    model.Str(req.Roadname),
		Sectionname: model.Str(req.Sectionname),
		Orgname:     model.Str(req.Orgname),
		Tollname:    model.Str(req.Tollname),
	}
	// PARITY: Java L218 同样不走 PageHelper（只有带 cursor 的分支用 selectByCursorShard+pageSize），
	// 无 cursor 时全量返回。
	list, err := s.snapshotRepo.List(ctx, q, 0)
	if err != nil {
		return nil, err
	}
	return &QueryResult{Data: list, Total: int64(len(list)), Strategy: "phase2-partition-prune"}, nil
}

// snapshotPhase3 对应 L232-247：ES 全文检索 + 冷热分离
func (s *ProgressiveQueryService) snapshotPhase3(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	if s.es != nil {
		hasFuzzy := req.Platenumber != "" || req.Gantryname != "" || req.Roadname != "" ||
			req.Sectionname != "" || req.Orgname != "" || req.Tollname != ""
		if hasFuzzy || req.PageSize > 100 {
			// 对应 Java 的 QueryResult.esPlaceholder：ES 的实际查询由统一查询服务承担
			return &QueryResult{Data: []any{}, Total: 0, Strategy: "phase3-elasticsearch"}, nil
		}
	}
	return s.snapshotPhase2(ctx, req)
}

// ============================================================
// 收费流水（对应 L259-310）
// ============================================================

// QueryFeeRecords 对应 L259-272
func (s *ProgressiveQueryService) QueryFeeRecords(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	req.Normalize()
	level := s.DetectScaleLevel(ctx, "ods_lwzxsfsj_fee_records_01")
	slog.Info("[渐进式查询] 收费流水", "level", level.Name(), "req", req)
	switch level {
	case Level100M:
		return s.feePhase1(ctx, req) // 分区表对应用透明，复用阶段一
	case Level1B:
		return s.feePhase3(ctx, req)
	default:
		return s.feePhase1(ctx, req)
	}
}

// feePhase1 对应 L278-285
func (s *ProgressiveQueryService) feePhase1(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	q := &model.OdsLwzxsfsjFeeRecords01{
		InApplyTime1: model.Str(req.StartTime),
		InApplyTime2: model.Str(req.EndTime),
		Vehicleplate: model.Str(req.Platenumber),
	}
	// PARITY: Java L283 queryFeeRecordsPhase1 直接 selectOdsLwzxsfsjFeeRecords01List(query)，无 LIMIT。
	list, err := s.feeRepo.List(ctx, q, 0)
	if err != nil {
		return nil, err
	}
	return &QueryResult{Data: list, Total: int64(len(list)), Strategy: "phase1-gaussdb-gin"}, nil
}

// feePhase3 对应 L302-310
func (s *ProgressiveQueryService) feePhase3(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	if s.es != nil && (req.Platenumber != "" || req.PageSize > 100) {
		return &QueryResult{Data: []any{}, Total: 0, Strategy: "phase3-elasticsearch"}, nil
	}
	return s.feePhase1(ctx, req)
}

// ============================================================
// 车辆轨迹（对应 L322-371）
// ============================================================

// QueryTrailFitting 对应 L322-335
func (s *ProgressiveQueryService) QueryTrailFitting(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	req.Normalize()
	level := s.DetectScaleLevel(ctx, "zdata_trail_fitting")
	slog.Info("[渐进式查询] 轨迹拟合", "level", level.Name(), "req", req)
	switch level {
	case Level100M:
		return s.trailPhase1(ctx, req)
	case Level1B:
		if s.es != nil {
			return &QueryResult{Data: []any{}, Total: 0, Strategy: "phase3-elasticsearch"}, nil
		}
		return s.trailPhase1(ctx, req)
	default:
		return s.trailPhase1(ctx, req)
	}
}

// trailPhase1 对应 L341-349
//
// PARITY: Java 这里也没走 PageHelper（L347 直接 selectZdataTrailFittingList），limit 传 0。
//
// PARITY: Java 里是用 `java.sql.Timestamp.valueOf(startTime)` 直接塞进 entime/extime，
//
//	注意它的语义是"入口时间作上界、出口时间作下界"（注释与字段名相反），此处保持原样以对齐行为。
func (s *ProgressiveQueryService) trailPhase1(ctx context.Context, req QueryRequest) (*QueryResult, error) {
	q := &model.ZdataTrailFitting{}
	if req.StartTime != "" {
		t, err := model.ParseTime(req.StartTime)
		if err != nil {
			return nil, fmt.Errorf("startTime 格式错误: %w", err)
		}
		q.Entime = model.NewDay(t)
	}
	if req.EndTime != "" {
		t, err := model.ParseTime(req.EndTime)
		if err != nil {
			return nil, fmt.Errorf("endTime 格式错误: %w", err)
		}
		q.Extime = model.NewTimestamp(t)
	}
	// PARITY: Java L347 queryTrailFittingPhase1 直接 selectZdataTrailFittingList(query)，无 LIMIT。
	list, err := s.trailRepo.List(ctx, q, 0)
	if err != nil {
		return nil, err
	}
	return &QueryResult{Data: list, Total: int64(len(list)), Strategy: "phase1-gaussdb-gin"}, nil
}
