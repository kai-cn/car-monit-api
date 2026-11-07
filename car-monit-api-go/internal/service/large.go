package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleQueryService.java:55-458
// 类/职责: LargeScaleQueryService — 8 亿级大表的模糊查询 / 分组统计 / 明细导出（三表统一）
// 对应 Go 文件: internal/service/large.go
// 关键映射:
//   private static class Target                       → Target 结构体（索引名/时间字段/主键字段/车牌字段）
//   resolve(String type)                              → Resolve(type)
//   fuzzyQuery(type,...)                              → FuzzyQuery
//   aggregationStats(type,...)                        → AggregationStats
//   submitExportTask / getExportStatus                → SubmitExport / GetExportStatus
//   ThreadPoolExecutor("lq-worker", 4..8)             → 每任务一个 goroutine + 并发信号量
//   ExportTaskStatus（public 可变字段）                → 复用 export.go 的结构体（RWMutex 保护）
// DIFF: Java 的这个类与 UnifiedExportService 有约 120 行重复的 scroll 导出代码；
//       Go 侧抽成 detailExport 一个方法，两者共用 scroll 客户端与进度上报逻辑。

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/es"
	"github.com/ruoyi/car-monit-api-go/internal/middleware"
)

// 对应 Java 的 QUERY_TIMEOUT_SECONDS / SCROLL_BATCH_SIZE / EXPORT_BATCH_SIZE（L70-76）
const (
	largeQueryTimeoutSeconds = 30
	largeScrollBatchSize     = 2000
	largeExportBatchSize     = 100000
)

// Target 对应 LargeScaleQueryService.Target（L120-132）
type Target struct {
	DS         DataSource
	IndexName  string
	TimeField  string
	IDField    string
	PlateField string
}

// LargeScaleQueryService 对应 LargeScaleQueryService.java
type LargeScaleQueryService struct {
	es    *es.Client
	query *UnifiedQueryService
	cfg   config.OptimizationConfig

	mu    sync.RWMutex
	tasks map[string]*ExportTaskStatus
	sem   chan struct{}
	wg    sync.WaitGroup
	// baseCtx/baseCancel：导出任务跨请求存活，但 Close() 时必须能取消（同 UnifiedExportService）
	baseCtx    context.Context
	baseCancel context.CancelFunc
}

// NewLargeScaleQueryService 构造（对应 @Autowired EsIndexManageService + @Value export.dir）
func NewLargeScaleQueryService(esClient *es.Client, query *UnifiedQueryService,
	cfg config.OptimizationConfig) *LargeScaleQueryService {
	baseCtx, baseCancel := context.WithCancel(context.Background())
	return &LargeScaleQueryService{
		es:         esClient,
		query:      query,
		cfg:        cfg,
		tasks:      make(map[string]*ExportTaskStatus),
		sem:        make(chan struct{}, 4), // 对应 Java 线程池核心线程数 4
		baseCtx:    baseCtx,
		baseCancel: baseCancel,
	}
}

// Resolve 对应 resolve(String type)（L137-161）。
//
// 索引名统一从 UnifiedQueryService.Meta 取，保证「查询 / 导出 / 同步 / 对账」四处用同一个索引，
// 这正是 Java 里注入 EsIndexManageService 的目的。
func (s *LargeScaleQueryService) Resolve(ds DataSource) Target {
	meta := s.query.Meta(ds)
	t := Target{DS: ds, IndexName: meta.Index, TimeField: meta.TimeField}
	switch ds {
	case DsFee:
		t.IDField, t.PlateField = "big_id", "vehicleplate"
	case DsTrail:
		t.IDField, t.PlateField = "cid", "envehicleid"
	default:
		t.IDField, t.PlateField = "datauuid", "platenumber"
	}
	return t
}

// ParseType 对应 Java 的 `switch (type.toLowerCase())` 映射（L143-157）。
func ParseType(t string) (DataSource, error) {
	switch strings.ToLower(strings.TrimSpace(t)) {
	case "", "snapshot":
		return DsSnapshot, nil
	case "fee":
		return DsFee, nil
	case "trail":
		return DsTrail, nil
	}
	return 0, middleware.NewBizError(400, "type 只能是 snapshot / fee / trail，当前为 "+t)
}

// ============================================================
// 模块 1：全字段模糊查询（对应 L171-246）
// ============================================================

// FuzzyQuery 对应 fuzzyQuery(type,...)（L186-228）。
//
// 性能要点（与 Java 注释一致）：
//  1. 时间范围先过滤，把扫描限制在少量分片上；
//  2. 模糊字段走 ngram 倒排（match on .ngram）；
//  3. from+size 只做窗口内浅分页，深翻页走导出接口。
func (s *LargeScaleQueryService) FuzzyQuery(ctx context.Context, ds DataSource, startTime, endTime string,
	fuzzy map[string]string, pageNum, pageSize int) ([]any, error) {

	if s.es == nil {
		return nil, middleware.NewBizError(500, "Elasticsearch 未启用")
	}
	if pageNum <= 0 {
		pageNum = 1
	}
	if pageSize <= 0 {
		pageSize = 20
	}

	target := s.Resolve(ds)
	start := time.Now()

	filters := []any{
		map[string]any{"range": map[string]any{target.TimeField: map[string]any{
			"format": "yyyy-MM-dd HH:mm:ss", "gte": startTime, "lte": endTime,
		}}},
	}
	must := make([]any, 0, len(fuzzy))
	for k, v := range fuzzy {
		if strings.TrimSpace(v) == "" {
			continue
		}
		must = append(must, buildFuzzyQuery(k, v))
	}

	body := map[string]any{
		"from":             (pageNum - 1) * pageSize,
		"size":             pageSize,
		"query":            map[string]any{"bool": map[string]any{"filter": filters, "must": must}},
		"sort":             []any{map[string]any{target.TimeField: map[string]any{"order": "desc"}}},
		"terminate_after":  1000000, // 单次最多扫描 100 万，防慢查询
		"timeout":          fmt.Sprintf("%ds", largeQueryTimeoutSeconds),
		"track_total_hits": true,
	}

	resp, err := s.es.Search(ctx, target.IndexName, body)
	if err != nil {
		return nil, fmt.Errorf("大规模数据查询服务异常：%w", err)
	}
	// 与 Java 一致：ES 命中的是文档，返回前必须绑成领域对象（否则缺失字段会连键一起消失）。
	rows := extractHits(resp, s.query.Meta(ds).Decode)
	slog.Info("[全字段模糊查询]", "type", ds.String(), "total", totalHits(resp),
		"returned", len(rows), "costMs", time.Since(start).Milliseconds())
	return rows, nil
}

// totalHits 取 hits.total（ES 7+ 是对象，ES 6 是数字，两种都兼容）
func totalHits(resp map[string]any) int64 {
	hits, _ := resp["hits"].(map[string]any)
	switch v := hits["total"].(type) {
	case float64:
		return int64(v)
	case map[string]any:
		if n, ok := v["value"].(float64); ok {
			return int64(n)
		}
	}
	return 0
}

// ============================================================
// 模块 2：分组统计（对应 L259-305）
// ============================================================

// AggregationStats 对应 aggregationStats(type,...)（L259-305）。
//
// 关键点：聚合在 ES 分片上并行完成，只有 topN 个桶回到应用层——
// 这是「8 亿条不拉进内存」的核心手段。
func (s *LargeScaleQueryService) AggregationStats(ctx context.Context, ds DataSource,
	startTime, endTime, groupBy, countField string, fuzzy map[string]string, topN int) (map[string]int64, error) {

	if s.es == nil {
		return nil, middleware.NewBizError(500, "Elasticsearch 未启用")
	}
	if groupBy == "" {
		return nil, middleware.NewBizError(400, "groupBy 不能为空")
	}
	if topN <= 0 {
		topN = 100
	}
	target := s.Resolve(ds)
	start := time.Now()

	filters := []any{
		map[string]any{"range": map[string]any{target.TimeField: map[string]any{
			"format": "yyyy-MM-dd HH:mm:ss", "gte": startTime, "lte": endTime,
		}}},
	}
	must := make([]any, 0, len(fuzzy))
	for k, v := range fuzzy {
		if strings.TrimSpace(v) != "" {
			must = append(must, buildFuzzyQuery(k, v))
		}
	}

	body := map[string]any{
		"size":    0,
		"timeout": "60s",
		"query":   map[string]any{"bool": map[string]any{"filter": filters, "must": must}},
		"aggs": map[string]any{
			"group_by_" + groupBy: map[string]any{
				"terms": map[string]any{"field": groupBy + ".keyword", "size": topN},
			},
		},
	}
	resp, err := s.es.Search(ctx, target.IndexName, body)
	if err != nil {
		return nil, fmt.Errorf("统计查询异常：%w", err)
	}

	out := map[string]int64{}
	aggs, _ := resp["aggregations"].(map[string]any)
	grp, _ := aggs["group_by_"+groupBy].(map[string]any)
	buckets, _ := grp["buckets"].([]any)
	for _, b := range buckets {
		bm, ok := b.(map[string]any)
		if !ok {
			continue
		}
		key := fmt.Sprint(bm["key"])
		var n int64
		if dc, ok := bm["doc_count"].(float64); ok {
			n = int64(dc)
		}
		out[key] = n
	}
	slog.Info("[统计查询]", "type", ds.String(), "groupBy", groupBy,
		"buckets", len(out), "costMs", time.Since(start).Milliseconds())
	return out, nil
}

// ============================================================
// 模块 3：异步明细导出（对应 L315-431）
// ============================================================

// SubmitExport 对应 submitExportTask（L315-334）：立即返回 taskId。
//
// DIFF: Java 把任务丢进 ThreadPoolExecutor（队列满时 CallerRunsPolicy 会阻塞调用线程）；
// Go 侧用 goroutine + 信号量，信号量满时同样阻塞提交方——行为对齐，但需要 WaitGroup
// 保证进程退出前把文件写完（否则 CSV 会被截断）。
func (s *LargeScaleQueryService) SubmitExport(_ context.Context, ds DataSource,
	startTime, endTime string, fuzzy map[string]string) (string, error) {

	if s.es == nil {
		return "", middleware.NewBizError(500, "Elasticsearch 未启用，无法导出")
	}
	taskID := uuid.NewString()
	st := &ExportTaskStatus{
		TaskID:     taskID,
		Status:     TaskPending,
		SubmitTime: time.Now().UnixMilli(),
	}
	s.mu.Lock()
	s.tasks[taskID] = st
	s.mu.Unlock()

	// 进程级 context：HTTP 返回后任务继续跑，Close() 时统一取消。
	taskCtx := s.baseCtx
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		defer func() {
			if r := recover(); r != nil {
				s.finish(taskID, TaskFailed, fmt.Sprintf("导出任务 panic: %v", r), 0, 0)
			}
		}()
		s.sem <- struct{}{}
		defer func() { <-s.sem }()
		if err := s.detailExport(taskCtx, taskID, ds, startTime, endTime, fuzzy); err != nil {
			s.finish(taskID, TaskFailed, err.Error(), 0, 0)
		}
	}()
	return taskID, nil
}

// GetExportStatus 对应 getExportStatus（L339-341）：返回副本，避免与写线程竞争。
func (s *LargeScaleQueryService) GetExportStatus(taskID string) *ExportTaskStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	st, ok := s.tasks[taskID]
	if !ok {
		return nil
	}
	cp := *st
	return &cp
}

// Close 对应 @PreDestroy destroy()（L105-110）：取消并等待在途导出结束。
func (s *LargeScaleQueryService) Close() {
	if s.baseCancel != nil {
		s.baseCancel()
	}
	s.wg.Wait()
}

// detailExport 对应 executeExportScroll（L350-431）。
//
// 与 UnifiedExportService 的差别：CSV 列是「主键, 车牌, 时间, 整行 JSON」，
// 用于把原始明细整体交付给下游系统（不做列裁剪）。
func (s *LargeScaleQueryService) detailExport(ctx context.Context, taskID string, ds DataSource,
	startTime, endTime string, fuzzy map[string]string) error {

	target := s.Resolve(ds)
	s.setStatus(taskID, TaskRunning)
	lg := slog.Default().With("taskId", taskID, "type", ds.String())
	lg.Info("[导出任务] 开始执行")

	filters := []any{
		map[string]any{"range": map[string]any{target.TimeField: map[string]any{
			"format": "yyyy-MM-dd HH:mm:ss", "gte": startTime, "lte": endTime,
		}}},
	}
	must := make([]any, 0, len(fuzzy))
	for k, v := range fuzzy {
		if strings.TrimSpace(v) != "" {
			must = append(must, buildFuzzyQuery(k, v))
		}
	}

	dir, err := s.exportDir(taskID)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("创建导出目录失败: %w", err)
	}

	keepalive := fmt.Sprintf("%dm", s.cfg.Export.ScrollKeepaliveMin)
	body := map[string]any{
		"size":    largeScrollBatchSize,
		"query":   map[string]any{"bool": map[string]any{"filter": filters, "must": must}},
		"sort":    []any{map[string]any{target.TimeField: map[string]any{"order": "desc"}}},
		"timeout": "120s",
	}

	docs, scrollID, done, err := s.es.ScrollPage(ctx, target.IndexName, body, keepalive)
	if err != nil {
		return fmt.Errorf("开始 scroll 失败: %w", err)
	}
	defer func() {
		cctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
		defer cancel()
		if cerr := s.es.ClearScroll(cctx, scrollID); cerr != nil {
			slog.Warn("清理 scroll 失败（ES 会在 keepalive 后自动回收）", "err", cerr)
		}
	}()

	var (
		total  int64
		part   int
		file   *os.File
		writer *csv.Writer
		header bool
	)
	closeFile := func() {
		if writer != nil {
			writer.Flush()
		}
		if file != nil {
			_ = file.Close()
		}
		file, writer, header = nil, nil, false
	}
	defer closeFile()

	writeDocs := func(batch []map[string]any) error {
		if len(batch) == 0 {
			return nil
		}
		if file == nil {
			part++
			name := filepath.Join(dir, fmt.Sprintf("export_%s_%s_p%d.csv", ds.String(), taskID, part))
			f, cerr := os.Create(name)
			if cerr != nil {
				return cerr
			}
			file, writer, header = f, csv.NewWriter(f), true
		}
		if header {
			if err := writer.Write([]string{target.IDField, target.PlateField, target.TimeField, "detail"}); err != nil {
				return err
			}
			header = false
		}
		for _, d := range batch {
			// detail 列是整行 JSON；CSV 里换行会破坏行结构，替换为空格（与 Java 一致）
			raw, _ := json.Marshal(d)
			detail := strings.ReplaceAll(strings.ReplaceAll(string(raw), "\n", " "), "\r", "")
			rec := []string{
				stringify(d[target.IDField]),
				stringify(d[target.PlateField]),
				stringify(d[target.TimeField]),
				detail,
			}
			if err := writer.Write(rec); err != nil {
				return err
			}
			total++
		}
		s.addProgress(taskID, int64(len(batch)), part)
		// 每 largeExportBatchSize 条切一个文件（对应 Java 的 totalCount % EXPORT_BATCH_SIZE == 0）
		if total%int64(largeExportBatchSize) < int64(len(batch)) {
			closeFile()
		}
		return nil
	}

	if err := writeDocs(docs); err != nil {
		return err
	}
	for !done {
		if err := ctx.Err(); err != nil {
			return fmt.Errorf("任务被取消: %w", err)
		}
		next, sid, finished, serr := s.es.ScrollNext(ctx, scrollID, keepalive)
		if serr != nil {
			return fmt.Errorf("scroll 拉取失败: %w", serr)
		}
		scrollID, done = sid, finished
		if err := writeDocs(next); err != nil {
			return err
		}
	}

	s.finish(taskID, TaskCompleted, "", total, part)
	lg.Info("[导出任务] 完成", "total", total, "parts", part)
	return nil
}

// exportDir 计算导出目录（SECURITY: taskID 为 uuid，再做一次 Base + 前缀校验防目录穿越）
func (s *LargeScaleQueryService) exportDir(taskID string) (string, error) {
	base, err := filepath.Abs(s.cfg.Export.Dir)
	if err != nil {
		return "", fmt.Errorf("导出根目录无效: %w", err)
	}
	dir := filepath.Join(base, filepath.Base(taskID))
	if !strings.HasPrefix(dir, base+string(os.PathSeparator)) {
		return "", fmt.Errorf("非法的导出目录: %s", taskID)
	}
	return dir, nil
}

func (s *LargeScaleQueryService) setStatus(taskID, status string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if st, ok := s.tasks[taskID]; ok {
		st.Status = status
	}
}

func (s *LargeScaleQueryService) addProgress(taskID string, delta int64, parts int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if st, ok := s.tasks[taskID]; ok {
		st.TotalExported += delta
		st.FilePartCount = parts
	}
}

func (s *LargeScaleQueryService) finish(taskID, status, errMsg string, total int64, parts int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	st, ok := s.tasks[taskID]
	if !ok {
		return
	}
	st.Status = status
	st.FinishTime = time.Now().UnixMilli()
	st.TotalExported = total
	if parts > 0 {
		st.FilePartCount = parts
	}
	st.ErrorMessage = errMsg
}

// SortedKeys 把统计结果转成「有序的 key 列表」，便于 handler 输出稳定顺序。
// （Java 用 LinkedHashMap 天然有序；Go 的 map 无序，必须显式排序）
func SortedKeys(m map[string]int64) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
