package service

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedExportService.java:93-330
// 类/职责: UnifiedExportService — 8 亿级大表的异步导出（ES scroll → 分片 CSV）
// 对应 Go 文件: internal/service/export.go
// 关键映射:
//   ThreadPoolExecutor（固定 2 线程）      → 每任务一个 goroutine + 全局并发信号量
//   ConcurrentHashMap<String,ExportTaskStatus> → sync.RWMutex + map
//   executeExportScroll（ES scroll 循环）  → executeExportScroll（同样的 scroll → 写盘 → clear）
//   @PreDestroy destroy()                → Close()（等待 in-flight 任务退出）
// DIFF: Java 用 Executors 提交 Runnable，异常被 Future 吞掉；Go 的 goroutine 异常会 panic 整个进程，
//       所以这里的导出循环必须自带 recover，并把失败写回 task 状态。

import (
	"context"
	"encoding/csv"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/es"
)

// 导出任务状态常量（对应 Java 里 "PENDING/RUNNING/COMPLETED/FAILED" 字符串）
const (
	TaskPending   = "PENDING"
	TaskRunning   = "RUNNING"
	TaskCompleted = "COMPLETED"
	TaskFailed    = "FAILED"
)

// ExportTaskStatus 对应 UnifiedExportService.ExportTaskStatus：
// 字段名与 Java 侧一致（status/totalExported/filePartCount/submitTime/finishTime/filePaths/errorMessage），
// 前端轮询接口的响应字段因此不需要改。
type ExportTaskStatus struct {
	TaskID        string   `json:"taskId"`
	Status        string   `json:"status"`
	TotalExported int64    `json:"totalExported"`
	FilePartCount int      `json:"filePartCount"`
	SubmitTime    int64    `json:"submitTime"`
	FinishTime    int64    `json:"finishTime,omitempty"`
	FilePaths     []string `json:"filePaths,omitempty"`
	ErrorMessage  string   `json:"errorMessage,omitempty"`
}

// UnifiedExportService 对应 UnifiedExportService.java
type UnifiedExportService struct {
	es    *es.Client
	query *UnifiedQueryService
	cfg   config.OptimizationConfig

	mu     sync.RWMutex
	tasks  map[string]*ExportTaskStatus
	sem    chan struct{} // 并发上限，等价于 ThreadPoolExecutor 的线程数
	wg     sync.WaitGroup
	cancel context.CancelFunc
}

// NewUnifiedExportService 构造（对应 @Value 注入 scrollBatchSize/exportBatchSize/exportDir）
func NewUnifiedExportService(esClient *es.Client, query *UnifiedQueryService, cfg config.OptimizationConfig) *UnifiedExportService {
	return &UnifiedExportService{
		es:    esClient,
		query: query,
		cfg:   cfg,
		tasks: make(map[string]*ExportTaskStatus),
		sem:   make(chan struct{}, 2),
	}
}

// SubmitExportTask 对应 L140-171：提交任务并立即返回 taskId。
//
// DIFF: Java 用 exportExecutor.submit(...) 把任务丢掉线程池；Go 用 goroutine，
// 但必须自己维护 WaitGroup，否则进程退出时正在写盘的文件会被截断。
func (s *UnifiedExportService) SubmitExportTask(ctx context.Context, ds DataSource,
	startTime, endTime string, fuzzy map[string]string) (string, error) {

	// 校验：导出必须带时间范围（对应 QueryValidationService.validateExportQuery 的拦截）
	if startTime == "" || endTime == "" {
		return "", fmt.Errorf("导出必须指定 startTime 与 endTime")
	}
	if s.es == nil {
		return "", fmt.Errorf("Elasticsearch 未启用，无法导出（GaussDB 降级路径不支持大批量导出）")
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

	// 任务使用独立 context：HTTP 请求结束时导出不应被取消
	taskCtx := context.WithoutCancel(ctx)
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		defer func() {
			if r := recover(); r != nil {
				s.finish(taskID, TaskFailed, fmt.Sprintf("导出任务 panic: %v", r), 0, nil)
			}
		}()
		s.sem <- struct{}{}
		defer func() { <-s.sem }()
		s.executeExportScroll(taskCtx, taskID, ds, startTime, endTime, fuzzy)
	}()

	return taskID, nil
}

// GetExportStatus 对应 L173-180：返回副本，避免并发读写同一结构体。
func (s *UnifiedExportService) GetExportStatus(taskID string) *ExportTaskStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	st, ok := s.tasks[taskID]
	if !ok {
		return nil
	}
	cp := *st
	cp.FilePaths = append([]string(nil), st.FilePaths...)
	return &cp
}

// CleanExpiredTasks 对应 L182-190：清理超过 maxAge 的已完成任务
func (s *UnifiedExportService) CleanExpiredTasks(maxAge time.Duration) {
	cutoff := time.Now().Add(-maxAge).UnixMilli()
	s.mu.Lock()
	defer s.mu.Unlock()
	for id, st := range s.tasks {
		if (st.Status == TaskCompleted || st.Status == TaskFailed) && st.FinishTime > 0 && st.FinishTime < cutoff {
			delete(s.tasks, id)
		}
	}
}

// Close 对应 @PreDestroy destroy()：等待在途任务结束。
//
// DIFF: Java 的线程池 shutdownNow 会中断线程；Go 的 goroutine 不能被强行中断，
// 只能"等它自己结束"——因此导出循环必须频繁检查 ctx（这里是每批 scroll 检查一次）。
func (s *UnifiedExportService) Close() {
	s.wg.Wait()
}

// executeExportScroll 对应 L205-324。
func (s *UnifiedExportService) executeExportScroll(ctx context.Context, taskID string,
	ds DataSource, startTime, endTime string, fuzzy map[string]string) {

	lg := slog.Default().With("taskId", taskID, "ds", ds.String())
	s.setStatus(taskID, TaskRunning)

	meta := s.query.Meta(ds)
	filters := []any{map[string]any{"range": map[string]any{meta.TimeField: map[string]any{
		"format": "yyyy-MM-dd HH:mm:ss", "gte": startTime, "lte": endTime,
	}}}}
	must := []any{}
	for k, v := range fuzzy {
		if v == "" {
			continue
		}
		physical, ok := meta.LogicalToPhysical[k]
		if !ok {
			s.finish(taskID, TaskFailed, "不支持的模糊字段: "+k, 0, nil)
			return
		}
		must = append(must, buildFuzzyQuery(physical, v))
	}

	dir, err := s.taskDir(taskID)
	if err != nil {
		s.finish(taskID, TaskFailed, err.Error(), 0, nil)
		return
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		s.finish(taskID, TaskFailed, "创建导出目录失败: "+err.Error(), 0, nil)
		return
	}

	keepalive := fmt.Sprintf("%dm", s.cfg.Export.ScrollKeepaliveMin)
	body := map[string]any{
		"size":  s.cfg.Export.ScrollBatch,
		"query": map[string]any{"bool": map[string]any{"filter": filters, "must": must}},
		"sort":  []any{map[string]any{meta.TimeField: map[string]any{"order": "asc"}}},
	}

	var (
		total    int64
		files    []string
		scrollID string
		part     int
		writer   *csv.Writer
		file     *os.File
		header   bool
	)

	closeFile := func() {
		if writer != nil {
			writer.Flush()
		}
		if file != nil {
			_ = file.Close()
		}
		writer, file, header = nil, nil, false
	}

	writeRows := func(docs []map[string]any) error {
		if len(docs) == 0 {
			return nil
		}
		if file == nil {
			part++
			name := filepath.Join(dir, fmt.Sprintf("%s_part%04d.csv", ds.String(), part))
			f, err := os.Create(name)
			if err != nil {
				return err
			}
			file, writer, header = f, csv.NewWriter(f), true
			files = append(files, name)
		}
		cols := entityColumns(ds)
		if header {
			if err := writer.Write(cols); err != nil {
				return err
			}
			header = false
		}
		for _, d := range docs {
			rec := make([]string, 0, len(cols))
			for _, c := range cols {
				rec = append(rec, stringify(d[c]))
			}
			if err := writer.Write(rec); err != nil {
				return err
			}
		}
		total += int64(len(docs))
		s.addProgress(taskID, int64(len(docs)), part)
		// 每 fileBatch 条切一个文件（对应 application.yml:226 file-batch）
		if total%int64(s.cfg.Export.FileBatch) < int64(len(docs)) {
			closeFile()
		}
		return nil
	}

	docs, sid, done, err := s.es.ScrollPage(ctx, meta.Index, body, keepalive)
	if err != nil {
		s.finish(taskID, TaskFailed, "开始 scroll 失败: "+err.Error(), total, files)
		return
	}
	scrollID = sid
	if err := writeRows(docs); err != nil {
		s.finish(taskID, TaskFailed, "写盘失败: "+err.Error(), total, files)
		s.clearScroll(ctx, scrollID)
		return
	}

	for !done {
		if ctx.Err() != nil {
			closeFile()
			s.clearScroll(ctx, scrollID)
			s.finish(taskID, TaskFailed, "任务被取消: "+ctx.Err().Error(), total, files)
			return
		}
		docs, sid, done, err = s.es.ScrollNext(ctx, scrollID, keepalive)
		if err != nil {
			closeFile()
			s.clearScroll(ctx, scrollID)
			s.finish(taskID, TaskFailed, "scroll 拉取失败: "+err.Error(), total, files)
			return
		}
		scrollID = sid
		if err := writeRows(docs); err != nil {
			closeFile()
			s.clearScroll(ctx, scrollID)
			s.finish(taskID, TaskFailed, "写盘失败: "+err.Error(), total, files)
			return
		}
	}

	closeFile()
	s.clearScroll(ctx, scrollID)
	lg.Info("导出完成", "total", total, "files", len(files))
	s.finish(taskID, TaskCompleted, "", total, files)
}

func (s *UnifiedExportService) clearScroll(ctx context.Context, id string) {
	if id == "" {
		return
	}
	cctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
	defer cancel()
	if err := s.es.ClearScroll(cctx, id); err != nil {
		slog.Warn("清理 scroll 失败（ES 会在 keepalive 后自动回收）", "err", err)
	}
}

func (s *UnifiedExportService) setStatus(taskID, status string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if st, ok := s.tasks[taskID]; ok {
		st.Status = status
	}
}

func (s *UnifiedExportService) addProgress(taskID string, delta int64, parts int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if st, ok := s.tasks[taskID]; ok {
		st.TotalExported += delta
		st.FilePartCount = parts
	}
}

func (s *UnifiedExportService) finish(taskID, status, errMsg string, total int64, files []string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	st, ok := s.tasks[taskID]
	if !ok {
		return
	}
	st.Status = status
	st.FinishTime = time.Now().UnixMilli()
	st.TotalExported = total
	if files != nil {
		st.FilePaths = files
		st.FilePartCount = len(files)
	}
	st.ErrorMessage = errMsg
}

// entityColumns 对应 Java 里的 COLUMNS 静态表（UnifiedExportService.java:106-139）
//
// DIFF: Java 用 Map<DataSource, List<String>> 硬编码列顺序；Go 侧同样显式列出，
// 保证 CSV 表头稳定（消费者按列位解析，不能随 ES 文档的键顺序漂移）。
func entityColumns(ds DataSource) []string {
	switch ds {
	case DsSnapshot:
		return []string{"bigId", "platenumber", "platecolor", "snapshottime", "receivedtime",
			"gantrycode", "gantryname", "roadname", "sectionname", "tollname", "orgname",
			"deviceid", "deviceip", "direction", "laneid", "cartype", "carcolor", "snappicturepath"}
	case DsFee:
		return []string{"bigId", "vehicleplate", "transtime", "inapplytime", "tollstationname",
			"gantryname", "sectionname", "orgname", "fee", "feetype", "vehicletype", "axlenum"}
	default:
		return []string{"trailuuid", "platekey", "entime", "extime", "startlon", "stratlat",
			"endlon", "endlat", "sectionname", "roadname", "trailpoints"}
	}
}

func stringify(v any) string {
	switch x := v.(type) {
	case nil:
		return ""
	case string:
		return x
	case map[string]any, []any:
		return fmt.Sprintf("%v", x)
	case float64:
		// ES 的数值在 JSON 解码后统一是 float64；整数避免输出 1.0 这种形态
		if x == float64(int64(x)) {
			return fmt.Sprintf("%d", int64(x))
		}
		return fmt.Sprintf("%v", x)
	default:
		return fmt.Sprintf("%v", x)
	}
}

// sortedKeys 已移除：仅在调试时需要，避免留下未使用函数（staticcheck U1000）。

// taskDir 计算并校验导出目录。
// SECURITY: taskID 由 uuid.NewString() 生成，不含分隔符；这里再做一次 Clean + 前缀校验，
// 防止后续有人把 taskID 改成请求参数时留下目录穿越隐患。
func (s *UnifiedExportService) taskDir(taskID string) (string, error) {
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
