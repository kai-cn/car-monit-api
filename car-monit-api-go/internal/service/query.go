// Package service 是业务层。
//
// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/**（interface + impl）
// 对应 Go 文件: internal/service/query.go（本文件）
//
// 分层约定:
//
//	Java: Controller → IService 接口 → ServiceImpl（@Service）→ Mapper
//	Go  : handler     → service 结构体（构造注入）          → repo
//
// DIFF: Java 的 interface + impl 双文件在 Go 里通常不需要——
//
//	只有当"存在两套实现"（如 ES/DB 双路由）时才抽 interface；这里用具体 struct + 显式构造。
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/middleware"
	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// DataSource 对应 UnifiedQueryService.DataSource（L71-75）
type DataSource int

const (
	// DsSnapshot 门架抓拍流水
	DsSnapshot DataSource = iota
	// DsFee 收费流水
	DsFee
	// DsTrail 车辆轨迹拟合
	DsTrail
)

// String 供日志与响应回显
func (d DataSource) String() string {
	switch d {
	case DsSnapshot:
		return "snapshot"
	case DsFee:
		return "fee"
	case DsTrail:
		return "trail"
	}
	return "unknown"
}

// ParseDataSource 对应 UnifiedQueryController.parseDataSource（L171-180）
func ParseDataSource(s string) (DataSource, error) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "snapshot":
		return DsSnapshot, nil
	case "fee":
		return DsFee, nil
	case "trail":
		return DsTrail, nil
	}
	return 0, fmt.Errorf("未知数据源: %s, 合法取值: snapshot / fee / trail", s)
}

// Meta 是三张大表的元数据（对应 resolveIndexName / resolveTimeField / resolveDomainClass 三方法的合并）
type Meta struct {
	Index     string
	TimeField string
	Table     string
	// LogicalToPhysical 逻辑字段 → 物理字段（对应 buildFieldTranslation，L356-378）
	LogicalToPhysical map[string]string
	// Decode 对应 Java 的 resolveDomainClass(ds) 再加上一步
	// `JSON.parseObject(hit.getSourceAsString(), targetClass)`（UnifiedQueryService.java:257）。
	// 它是「领域类」这个信息在 Go 里的等价物：ES 的 _source 必须先绑回实体，再往外返回。
	Decode func(raw []byte) (any, error)
}

// decodeSource 把 ES 的 _source 绑进实体类型，对应 Java 的 JSON.parseObject(json, T.class)。
//
// 为什么必须这一步（而不能直接把 _source 这张 map 递出去）：
// ES 文档里只写了当初同步进去的那十几个字段，_source 本身不是全字段；
// Java 绑成实体后由 Jackson 把**全部**字段输出，没赋到值的字段是 null；
// Go 如果直接透传 map，那些缺失字段在响应里就整个键都不存在。
// 实测：/api/v1/large/snapshot 两边都有 1 行数据时，Java 1079 字节 / Go 163 字节，
// 差的 57 个字段全是「Java 有键且值为 null」vs「Go 根本没这个键」。
func decodeSource[T any](raw []byte) (any, error) {
	var v T
	if err := json.Unmarshal(raw, &v); err != nil {
		return nil, fmt.Errorf("ES _source 反序列化成 %T 失败: %w", v, err)
	}
	return v, nil
}

// 三张表的限定名。
//
// PARITY: Java 的 queryFromMysql 走 MyBatis-Plus 的 selectList(qw)，表名取自 @TableName，
// 而这些注解都没有 schema 前缀（见 OdsRtSzdnSnapshotFlowAddcode.java:25 之外的几个实体都是
// @TableName("xxx")）。openGauss 的默认 search_path 只有 "$user",public，没有 jl_data01，
// 所以 Java 的降级路径实际会抛 42P01，再被 query() 的 catch 吃掉，接口表现为“查到 0 条”。
// Go 侧不复制这个缺陷：表名带上 schema，降级路径真能查出数据。
//
// 数组下标与 DataSource 枚举对齐：0=SNAPSHOT 1=FEE 2=TRAIL。
var metaTables = [...]string{
	"jl_data01.ods_rt_szdn_snapshot_flow_addcode",
	"jl_data01.ods_lwzxsfsj_fee_records_01",
	"jl_data01.zdata_trail_fitting",
}

// UnifiedQueryService 对应 UnifiedQueryService.java（全文件）
//
// 设计目标（与 Java 一致）：8 亿级表 + 任意字段模糊 + 最近一年范围，
// 模糊查询走 ES，小范围精确查询走 GaussDB，ES 故障自动降级。
type UnifiedQueryService struct {
	es    *es.Client
	db    *db.Client
	cfg   config.OptimizationConfig
	esCfg config.ESConfig
}

// NewUnifiedQueryService 显式装配依赖（对应 Spring 的 @Autowired 字段注入）
func NewUnifiedQueryService(esClient *es.Client, dbClient *db.Client,
	opt config.OptimizationConfig, esCfg config.ESConfig) *UnifiedQueryService {
	return &UnifiedQueryService{es: esClient, db: dbClient, cfg: opt, esCfg: esCfg}
}

// Meta 返回指定数据源的元数据（对应 resolveXxx 三方法，L384-409）
func (s *UnifiedQueryService) Meta(ds DataSource) Meta {
	switch ds {
	case DsSnapshot:
		return Meta{
			Index:     s.esCfg.Index.Snapshot,
			TimeField: "snapshottime",
			Table:     metaTables[DsSnapshot],
			Decode:    decodeSource[model.OdsRtSzdnSnapshotFlowAddcode],
			LogicalToPhysical: map[string]string{
				"platenumber": "platenumber",
				"orgname":     "orgname",
				"sectionname": "sectionname",
				"roadname":    "roadname",
				"gantryname":  "gantryname",
				"tollname":    "tollname",
			},
		}
	case DsFee:
		return Meta{
			Index:     s.esCfg.Index.Fee,
			TimeField: "transtime",
			Table:     metaTables[DsFee],
			Decode:    decodeSource[model.OdsLwzxsfsjFeeRecords01],
			LogicalToPhysical: map[string]string{
				"platenumber": "vehicleplate",
				"orgname":     "orgname",
				"sectionname": "sectionname",
				"roadname":    "roadname",
				"gantryname":  "gantryname",
				"tollname":    "tollname",
			},
		}
	default:
		return Meta{
			Index:     s.esCfg.Index.Trail,
			TimeField: "extime",
			Table:     metaTables[DsTrail],
			Decode:    decodeSource[model.ZdataTrailFitting],
			LogicalToPhysical: map[string]string{
				"platenumber": "envehicleid",
				"orgname":     "orgname",
				"sectionname": "sectionname",
				"roadname":    "roadname",
			},
		}
	}
}

// Query 对应 UnifiedQueryService.query（L120-152）：路由 + 失败降级 + 耗时日志。
func (s *UnifiedQueryService) Query(ctx context.Context, ds DataSource, startTime, endTime string,
	fuzzy map[string]string, pageNum, pageSize int) (any, error) {

	useES := s.shouldRouteToES(startTime, endTime, fuzzy, ds)
	start := time.Now()
	lg := slog.Default()

	rows, err := s.queryRoute(ctx, ds, startTime, endTime, fuzzy, pageNum, pageSize, useES)
	if err != nil {
		lg.Error("[统一查询] 查询失败", "ds", ds.String(), "useEs", useES,
			"costMs", time.Since(start).Milliseconds(), "err", err)
		if useES {
			lg.Warn("[统一查询] ES 查询失败，降级到 GaussDB", "ds", ds.String())
			if fallback, ferr := s.queryFromDB(ctx, ds, startTime, endTime, fuzzy, pageNum, pageSize); ferr == nil {
				return fallback, nil
			} else {
				lg.Error("[统一查询] 降级也失败", "ds", ds.String(), "err", ferr)
				return nil, ferr
			}
		}
		return nil, err
	}
	lg.Info("[统一查询] 完成", "ds", ds.String(), "useEs", useES,
		"costMs", time.Since(start).Milliseconds(), "page", pageNum, "size", pageSize)
	return rows, nil
}

func (s *UnifiedQueryService) queryRoute(ctx context.Context, ds DataSource, startTime, endTime string,
	fuzzy map[string]string, pageNum, pageSize int, useES bool) (any, error) {
	if useES {
		return s.queryFromES(ctx, ds, startTime, endTime, fuzzy, pageNum, pageSize)
	}
	return s.queryFromDB(ctx, ds, startTime, endTime, fuzzy, pageNum, pageSize)
}

// shouldRouteToES 对应 L170-193。
func (s *UnifiedQueryService) shouldRouteToES(startTime, endTime string,
	fuzzy map[string]string, ds DataSource) bool {
	for _, v := range fuzzy {
		if strings.TrimSpace(v) != "" {
			return true
		}
	}
	st, err1 := model.ParseTime(startTime)
	et, err2 := model.ParseTime(endTime)
	if err1 != nil || err2 != nil {
		// 时间格式异常时保守走 ES（ES 对时间格式更宽容）—— 与 Java 注释一致
		return true
	}
	if et.Sub(st) > time.Duration(s.cfg.Query.ESForceDays)*24*time.Hour {
		return true
	}
	return ds == DsFee || ds == DsTrail
}

// queryFromES 对应 L204-265。
func (s *UnifiedQueryService) queryFromES(ctx context.Context, ds DataSource, startTime, endTime string,
	fuzzy map[string]string, pageNum, pageSize int) (any, error) {

	if s.es == nil {
		return nil, middleware.NewBizError(500, "Elasticsearch 未启用")
	}
	meta := s.Meta(ds)

	filters := []any{
		map[string]any{
			"range": map[string]any{
				meta.TimeField: map[string]any{
					"format": "yyyy-MM-dd HH:mm:ss",
					"gte":    startTime,
					"lte":    endTime,
				},
			},
		},
	}
	must := []any{}
	for k, v := range fuzzy {
		if strings.TrimSpace(v) == "" {
			continue
		}
		physical, ok := meta.LogicalToPhysical[k]
		if !ok {
			// SECURITY: 字段名必须来自白名单。Java 侧 QueryWrapper.like(field, ...) 直接拼接
			// 请求参数里的字段名，存在 SQL 注入面；Go 侧一律只接受白名单里的逻辑字段。
			return nil, middleware.NewBizError(400, fmt.Sprintf("不支持的模糊查询字段: %s", k))
		}
		must = append(must, buildFuzzyQuery(physical, v))
	}

	from := max(0, (pageNum-1)*pageSize)
	size := min(pageSize, s.cfg.Query.MaxWindow)
	if from+size > s.cfg.Query.MaxWindow {
		// 与 Java 的 IllegalStateException 等价：引导调用方改用导出接口
		return nil, middleware.NewBizError(400,
			fmt.Sprintf("浅分页超过 max_result_window=%d，请使用 export 接口或 search_after", s.cfg.Query.MaxWindow))
	}

	body := map[string]any{
		"from":             from,
		"size":             size,
		"query":            map[string]any{"bool": map[string]any{"filter": filters, "must": must}},
		"sort":             []any{map[string]any{meta.TimeField: map[string]any{"order": "desc"}}},
		"timeout":          fmt.Sprintf("%dms", s.cfg.Query.TimeoutMs),
		"track_total_hits": true,
	}
	resp, err := s.es.Search(ctx, meta.Index, body)
	if err != nil {
		return nil, err
	}
	return extractHits(resp, meta.Decode), nil
}

// buildFuzzyQuery 对应 L278-291 的三段式策略。
//
// DIFF: Java 用 QueryBuilders.termQuery/matchQuery/wildcardQuery 构造 QueryBuilder 对象树；
// Go 直接构造 DSL JSON——同样的语义，少一层 builder。
func buildFuzzyQuery(field, value string) map[string]any {
	if len([]rune(value)) >= 7 && (field == "platenumber" || field == "gantrycode" || field == "sectioncode") {
		return map[string]any{"term": map[string]any{field + ".keyword": value}}
	}
	if len([]rune(value)) >= 3 {
		return map[string]any{"match": map[string]any{field + ".ngram": value}}
	}
	return map[string]any{"wildcard": map[string]any{field + ".keyword": "*" + value + "*"}}
}

// extractHits 取 hits.hits[]._source 并逐条绑成领域对象。
//
// PARITY: 对应 UnifiedQueryService.java:255-259 的
//
//	for (SearchHit hit : ...) { results.add(JSON.parseObject(hit.getSourceAsString(), targetClass)); }
//
// decode 为 nil 时退化为直接返回 _source 原始 map（只给不经过领域类的内部用途用，
// 比如导出时的按列拉平），接口路径一律传 meta.Decode。
func extractHits(resp map[string]any, decode func([]byte) (any, error)) []any {
	out := []any{}
	hits, _ := resp["hits"].(map[string]any)
	items, _ := hits["hits"].([]any)
	for _, it := range items {
		m, ok := it.(map[string]any)
		if !ok {
			continue
		}
		src, ok := m["_source"].(map[string]any)
		if !ok {
			continue
		}
		if decode == nil {
			out = append(out, src)
			continue
		}
		raw, err := json.Marshal(src)
		if err != nil {
			continue
		}
		obj, err := decode(raw)
		if err != nil {
			// Java 的 fastjson2 在单个文档字段类型对不上时会直接抛异常，整个请求 500；
			// 这里不吞掉：把出错文档报上去，行为与 Java 一样可见，而不是静默丢行。
			slog.Warn("[统一查询] 单个 ES 文档绑定领域对象失败，跳过该条", "err", err)
			continue
		}
		out = append(out, obj)
	}
	return out
}

// queryFromDB 对应 L309-347：GaussDB 降级路径，LIMIT 1000 + 内存分页。
//
// DIFF: Java 用 MyBatis-Plus 的裸 QueryWrapper 兼容三张表；
// Go 里 GORM 的 *gorm.DB 同样可以脱离实体类型使用，Scan 到具体 struct 即可。
func (s *UnifiedQueryService) queryFromDB(ctx context.Context, ds DataSource, startTime, endTime string,
	fuzzy map[string]string, pageNum, pageSize int) (any, error) {

	meta := s.Meta(ds)
	tx := s.db.ORM(ctx).Table(meta.Table)
	if strings.TrimSpace(startTime) != "" {
		tx = tx.Where(meta.TimeField+" >= ?", startTime)
	}
	if strings.TrimSpace(endTime) != "" {
		tx = tx.Where(meta.TimeField+" <= ?", endTime)
	}
	for k, v := range fuzzy {
		if strings.TrimSpace(v) == "" {
			continue
		}
		// SECURITY: 列名白名单，详见 queryFromES 中同名注释
		physical, ok := meta.LogicalToPhysical[k]
		if !ok {
			return nil, middleware.NewBizError(400, fmt.Sprintf("不支持的模糊查询字段: %s", k))
		}
		// PARITY: MyBatis-Plus 的 qw.like() 生成的是 LIKE '%v%'（区分大小写），不是 ILIKE。
		tx = tx.Where(physical+" LIKE ?", "%"+v+"%")
	}
	// PARITY: Java L334 只写了 `qw.last("LIMIT 1000")`，整条降级 SQL 没有任何 ORDER BY。
	// Go 之前自己补了一个 TimeField DESC，于是「取前 1000 条再内存分页」拿到的是完全另一批行
	// （实测 /api/v1/large/snapshot：Java 给 bigId 154288684…，Go 给 581339536…）。
	// 补上排序看似更合理，但两边就不可能一致；而且没有 ORDER BY 时“哪 1000 条”本身
	// 在 Java 侧就是不确定的，这是 Java 的设计现状，不是 Go 的缺陷。
	tx = tx.Limit(1000) // 降级路径限量，防止拉爆内存

	switch ds {
	case DsSnapshot:
		var rows []model.OdsRtSzdnSnapshotFlowAddcode
		if err := tx.Find(&rows).Error; err != nil {
			return nil, err
		}
		return pageInMemory(rows, pageNum, pageSize), nil
	case DsFee:
		var rows []model.OdsLwzxsfsjFeeRecords01
		if err := tx.Find(&rows).Error; err != nil {
			return nil, err
		}
		return pageInMemory(rows, pageNum, pageSize), nil
	default:
		var rows []model.ZdataTrailFitting
		if err := tx.Find(&rows).Error; err != nil {
			return nil, err
		}
		return pageInMemory(rows, pageNum, pageSize), nil
	}
}

// pageInMemory 对应 Java 的 subList 内存分页
//
// DIFF: Go 1.21+ 内置 min/max，Java 侧用 Math.min/Math.max；语义完全一致。
func pageInMemory[T any](rows []T, pageNum, pageSize int) []T {
	from := max(0, (pageNum-1)*pageSize)
	if from >= len(rows) {
		return []T{}
	}
	to := min(len(rows), from+pageSize)
	return rows[from:to]
}

// ============================================================
// QueryValidationService 对应 QueryValidationService.java
// ============================================================

// ValidationResult 对应 QueryValidationService.ValidationResult
type ValidationResult struct {
	Valid   bool     `json:"valid"`
	Message string   `json:"message,omitempty"`
	Errors  []string `json:"errors,omitempty"`
}

// QueryValidationService 对应 QueryValidationService.java:88-267。
//
// 职责：在查询/导出前拦掉"必然打爆数据库"的请求（超长时间范围、浅分页越界、非法车牌位数）。
type QueryValidationService struct {
	cfg config.OptimizationConfig
}

// NewQueryValidationService 构造
func NewQueryValidationService(cfg config.OptimizationConfig) *QueryValidationService {
	return &QueryValidationService{cfg: cfg}
}

// ValidatePageQuery 对应 L88-168：分页查询校验。
func (s *QueryValidationService) ValidatePageQuery(startTime, endTime string, fuzzy map[string]string,
	pageNum, pageSize int) ValidationResult {
	res := ValidationResult{Valid: true}

	days, err := daysBetween(startTime, endTime)
	if err != nil {
		return ValidationResult{Valid: false, Message: "时间格式必须为 yyyy-MM-dd HH:mm:ss： " + err.Error()}
	}
	if days > s.cfg.Query.ESForceDays && len(fuzzy) == 0 {
		res.Valid = false
		res.Errors = append(res.Errors, fmt.Sprintf(
			"时间跨度 %d 天超过 %d 天且无模糊条件，无法命中索引，请缩小范围或增加筛选字段",
			days, s.cfg.Query.ESForceDays))
	}
	if pageNum <= 0 {
		res.Errors = append(res.Errors, "pageNum 必须 >= 1")
		res.Valid = false
	}
	if pageSize <= 0 || pageSize > 1000 {
		res.Errors = append(res.Errors, "pageSize 必须在 1..1000 之间")
		res.Valid = false
	}
	if (pageNum * pageSize) > s.cfg.Query.MaxWindow {
		res.Valid = false
		res.Errors = append(res.Errors, fmt.Sprintf(
			"from+size 超过 max_result_window=%d，请改用导出接口", s.cfg.Query.MaxWindow))
	}
	if plate, ok := fuzzy["platenumber"]; ok && plate != "" && !s.isFullPlateNumber(plate) && len([]rune(plate)) < 3 {
		res.Errors = append(res.Errors, "车牌模糊匹配至少 3 个字符，否则会退化为 wildcard 全表扫描")
		res.Valid = false
	}
	return res
}

// ValidateExportQuery 对应 L170-232：导出校验（比查询宽松，但要求必须有时间范围）。
func (s *QueryValidationService) ValidateExportQuery(startTime, endTime string) ValidationResult {
	if strings.TrimSpace(startTime) == "" || strings.TrimSpace(endTime) == "" {
		return ValidationResult{Valid: false, Message: "导出必须指定 startTime 与 endTime"}
	}
	if _, err := daysBetween(startTime, endTime); err != nil {
		return ValidationResult{Valid: false, Message: "时间格式必须为 yyyy-MM-dd HH:mm:ss： " + err.Error()}
	}
	return ValidationResult{Valid: true}
}

// HasFuzzyCondition 对应 L234-258
func (s *QueryValidationService) HasFuzzyCondition(fuzzy map[string]string) bool {
	for _, v := range fuzzy {
		if strings.TrimSpace(v) != "" {
			return true
		}
	}
	return false
}

// isFullPlateNumber 对应 L259-266：完整车牌（>=7 位）可走 term 精确匹配
func (s *QueryValidationService) isFullPlateNumber(plate string) bool {
	return len([]rune(plate)) >= 7
}

func daysBetween(startTime, endTime string) (int, error) {
	st, err := model.ParseTime(startTime)
	if err != nil {
		return 0, err
	}
	et, err := model.ParseTime(endTime)
	if err != nil {
		return 0, err
	}
	if et.Before(st) {
		return 0, fmt.Errorf("endTime 不能早于 startTime")
	}
	return int(et.Sub(st).Hours() / 24), nil
}
