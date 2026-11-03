// Package scheduler 提供"定时任务"的 Go 等价物。
//
// JAVA 对照:
//
//	pro-business-api/src/main/java/com/ruoyi/base/task/CarTask.java:36-221（整个文件在块注释内，见 jobs.go）
//	pro-business-api/src/main/java/com/ruoyi/base/task/TrackTask.java:54-85
//	pro-business-api/src/main/java/com/ruoyi/base/task/DataFlowTask.java:37-56
//	pro-business-api/.../service/impl/DataReliabilityService.java:384, 481
//	pro-business-api/.../service/impl/DataLossDetectionService.java:127
//	pro-business-api/.../service/impl/DelayMonitoringService.java:329
//	pro-business-api/.../service/optimization/GaussEsConsistencyService.java:178
//	pro-business-api/src/main/java/com/ruoyi/ProApplication.java（@EnableScheduling）
//
// 对应 Go 文件: internal/scheduler/scheduler.go
//
// 关键映射:
//
//	@EnableScheduling                      → main() 里显式构造 Scheduler 并 Start(ctx)
//	@Scheduled(cron = "0 */1 * * * ?")     → Add("名字", "*/1 * * * *", fn)
//	@Scheduled(fixedRate = 300000)         → Every("名字", 5*time.Minute, fn)
//	Spring 的单线程调度器（默认 poolSize=1） → 每个 job 一个 goroutine（见 DIFF）
//	@Scheduled 方法抛异常被 Spring 吞掉      → run() 里的 recover + 日志（语义一致，进程不退出）
//
// 架构决策（为什么不用 robfig/cron）:
//
//	项目对 cron 的需求只有"分钟级、5 段式、Quartz 的 6 段能降级"这三条；
//	引入第三方库会让"Quartz 的 ? 与 6 段语义"变成隐式适配，反而更难对照 Java。
//	这里用 80 行自研解析器，支持 * / 数字 / 逗号 / 区间 / 步长，
//	超出范围的表达式在 Add() 时就返回错误（fail fast），不会静默不执行。
//	需要秒级/星期别名等完整语法时，替换本文件为 robfig/cron/v3 即可，调用方零改动。
package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Job 是一条定时任务。
type Job struct {
	// Name 用于日志标识（对应 Java 的方法名，如 "syncBaseInfo"）
	Name string
	// Spec 是 5 段式 cron 表达式（minute hour day-of-month month day-of-week）
	Spec string
	// Fn 是任务体。**必须**自己处理业务错误：返回 error 没有意义（Java 侧也是 void）。
	Fn func(ctx context.Context)
	// Disabled 为 true 时只登记不执行（用于配置开关，如 consistency.reconcile.enabled=false）
	Disabled bool
}

// Scheduler 是极简定时调度器。
type Scheduler struct {
	mu     sync.Mutex
	jobs   []*Job
	cancel context.CancelFunc
	wg     sync.WaitGroup
	loc    *time.Location
}

// New 构造调度器。loc 传 nil 时使用本地时区（与 JVM 的 serverTimezone=Asia/Shanghai 对齐）。
func New(loc *time.Location) *Scheduler {
	if loc == nil {
		loc = time.Local
	}
	return &Scheduler{loc: loc}
}

// Add 登记一条 cron 任务；表达式非法时立刻返回错误。
//
// PARITY: Quartz 的 6 段式（秒 分 时 日 月 周，如 "0 30 2 * * ?"）在这里被降级为 5 段式：
// 秒位必须为 0/固定值（本项目的表达式全为 "0"），末位 "?" 等价于 "*"，
// 因此 "0 30 2 * * ?" → "30 2 * * *"。降级规则写死在这里，调用方直接抄 application.yml。
func (s *Scheduler) Add(job Job) error {
	spec, err := normalizeSpec(job.Spec)
	if err != nil {
		return fmt.Errorf("任务 %s 的 cron 表达式 %q 非法: %w", job.Name, job.Spec, err)
	}
	sched, err := parseCron(spec)
	if err != nil {
		return fmt.Errorf("任务 %s 的 cron 表达式 %q 非法: %w", job.Name, job.Spec, err)
	}
	job.Spec = spec

	s.mu.Lock()
	defer s.mu.Unlock()
	for _, old := range s.jobs {
		if old.Name == job.Name {
			return fmt.Errorf("任务名重复: %s", job.Name)
		}
	}
	s.jobs = append(s.jobs, &Job{Name: job.Name, Spec: job.Spec, Fn: job.Fn, Disabled: job.Disabled})
	cronexprs[job.Name] = sched
	return nil
}

// Every 登记一条固定间隔任务，对应 @Scheduled(fixedRate = N)。
//
// DIFF: Java 的 fixedRate 以"上次开始时间"为基准（即使上一次没跑完也会按时再来）；
// Go 用 ticker + 串行执行，天然是"上一次结束后再等一个周期"，
// 对补偿/检测这类幂等任务没有行为差异，反而避免任务堆积。
func (s *Scheduler) Every(name string, interval time.Duration, fn func(ctx context.Context)) error {
	if interval < time.Second {
		return fmt.Errorf("任务 %s 的间隔必须 >= 1s", name)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, old := range s.jobs {
		if old.Name == name {
			return fmt.Errorf("任务名重复: %s", name)
		}
	}
	s.jobs = append(s.jobs, &Job{Name: name, Spec: "@every " + interval.String(), Fn: fn})
	intervals[name] = interval
	return nil
}

// Start 为每个任务起一个 goroutine。
//
// DIFF: Spring 默认 poolSize=1（所有 @Scheduled 串行，一个慢任务会拖垮全部）；
// Go 侧每个任务独立 goroutine，互不影响——这是本次迁移里**唯一有意改变并发语义**的地方，
// 因为 8 亿级表的补偿/检测任务耗时差异极大，串行会导致分钟级任务长时间漂移。
//
// PARITY: Disabled 的任务不参与调度，也不会起 goroutine（启动时只打一条 Info）。
func (s *Scheduler) Start(ctx context.Context) {
	s.mu.Lock()
	ctx, cancel := context.WithCancel(ctx)
	s.cancel = cancel
	jobs := append([]*Job(nil), s.jobs...)
	s.mu.Unlock()

	for _, j := range jobs {
		if j.Disabled {
			slog.Info("[定时任务] 已按配置禁用", "job", j.Name, "spec", j.Spec)
			continue
		}
		s.wg.Add(1)
		go func(j *Job) {
			defer s.wg.Done()
			defer func() {
				if r := recover(); r != nil {
					slog.Error("[定时任务] 协程 panic 退出", "job", j.Name, "panic", r)
				}
			}()
			if d, ok := intervals[j.Name]; ok {
				s.runTicker(ctx, j, d)
				return
			}
			s.runCron(ctx, j)
		}(j)
	}
	if len(jobs) > 0 {
		slog.Info("[定时任务] 调度器已启动", "jobs", len(jobs))
	}
}

// Stop 停止调度并等待正在执行的任务结束（对应 Spring 容器优雅关闭）。
func (s *Scheduler) Stop() {
	s.mu.Lock()
	cancel := s.cancel
	s.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	s.wg.Wait()
	slog.Info("[定时任务] 调度器已停止")
}

func (s *Scheduler) runTicker(ctx context.Context, j *Job, d time.Duration) {
	ticker := time.NewTicker(d)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.run(ctx, j)
		}
	}
}

func (s *Scheduler) runCron(ctx context.Context, j *Job) {
	for {
		next := s.nextFire(j.Name, time.Now())
		if next.IsZero() {
			slog.Warn("[定时任务] 表达式在未来一年内无触发点，任务停止", "job", j.Name, "spec", j.Spec)
			return
		}
		wait := time.Until(next)
		if wait < 0 {
			wait = 0
		}
		timer := time.NewTimer(wait)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
			s.run(ctx, j)
		}
	}
}

// run 执行任务体，吞掉 panic 与耗时日志。
//
// PARITY: Java 的 @Scheduled 方法抛异常由 TaskUtils 记日志后继续下次调度——进程不会退出；
// Go 里 goroutine panic 会杀掉整个进程，所以 recover 是**必需**的。
func (s *Scheduler) run(ctx context.Context, j *Job) {
	start := time.Now()
	defer func() {
		if r := recover(); r != nil {
			slog.Error("[定时任务] 执行 panic", "job", j.Name, "panic", r,
				"costMs", time.Since(start).Milliseconds())
		}
	}()
	slog.Debug("[定时任务] 开始执行", "job", j.Name)
	j.Fn(ctx)
	slog.Info("[定时任务] 执行完成", "job", j.Name, "costMs", time.Since(start).Milliseconds())
}

func (s *Scheduler) nextFire(name string, after time.Time) time.Time {
	e := cronexprs[name]
	if e == nil {
		return time.Time{}
	}
	t := after.In(s.loc).Truncate(time.Minute).Add(time.Minute)
	for i := 0; i < 366*24*60; i++ {
		if e.matches(t) {
			return t
		}
		t = t.Add(time.Minute)
	}
	return time.Time{}
}

// ---- cron 表达式解析 ----

// cronexprs / intervals 是 Add/Every 写、Start 读的登记表。
//
// DIFF: 用包级 map 而不是塞进 Job，是为了让 runCron 不必反解析 Spec 字符串
// （反解析多一层出错面，且 nextFire 需要的是预编译结果）。
var (
	cronexprs = map[string]*cronExpr{}
	intervals = map[string]time.Duration{}
)

type cronExpr struct {
	minute, hour, dom, month, dow fieldMatcher
}

func (e *cronExpr) matches(t time.Time) bool {
	if !e.minute.match(t.Minute()) || !e.hour.match(t.Hour()) || !e.month.match(int(t.Month())) {
		return false
	}
	// 标准 cron：日 与 周 只要有一个是 "*" 就只看另一个；两者都限定则取"或"。
	domAny := e.dom.any
	dowAny := e.dow.any
	switch {
	case domAny && dowAny:
		return true
	case domAny:
		return e.dow.match(int(t.Weekday()))
	case dowAny:
		return e.dom.match(t.Day())
	default:
		return e.dom.match(t.Day()) || e.dow.match(int(t.Weekday()))
	}
}

// fieldMatcher 是单个字段的匹配器：* / 固定值 / 区间 / 步长 / 枚举。
type fieldMatcher struct {
	any   bool
	vals  map[int]struct{}
	raw   string
	lo    int
	hi    int
	names map[string]int
}

func (f fieldMatcher) match(v int) bool {
	if f.any {
		return true
	}
	_, ok := f.vals[v]
	return ok
}

func normalizeSpec(spec string) (string, error) {
	spec = strings.TrimSpace(spec)
	if spec == "" {
		return "", fmt.Errorf("表达式为空")
	}
	fields := strings.Fields(spec)
	switch len(fields) {
	case 5:
		return strings.Join(fields, " "), nil
	case 6:
		// Quartz：秒 分 时 日 月 周
		sec := fields[0]
		if sec != "0" {
			return "", fmt.Errorf("Quartz 秒位只支持 0（分钟级调度），实际为 %q", sec)
		}
		// 末位 "?" 表示"不指定"，等价于 "*"
		norm := make([]string, 0, 5)
		norm = append(norm, fields[1:]...)
		if norm[len(norm)-1] == "?" {
			norm[len(norm)-1] = "*"
		}
		for i := 0; i < len(norm)-1; i++ {
			if norm[i] == "?" {
				norm[i] = "*"
			}
		}
		return strings.Join(norm, " "), nil
	default:
		return "", fmt.Errorf("需要 5 段或 6 段，实际 %d 段", len(fields))
	}
}

func parseCron(spec string) (*cronExpr, error) {
	fields := strings.Fields(spec)
	if len(fields) != 5 {
		return nil, fmt.Errorf("需要 5 段，实际 %d 段", len(fields))
	}
	minute, err := parseField(fields[0], 0, 59)
	if err != nil {
		return nil, fmt.Errorf("分钟位: %w", err)
	}
	hour, err := parseField(fields[1], 0, 23)
	if err != nil {
		return nil, fmt.Errorf("小时位: %w", err)
	}
	dom, err := parseField(fields[2], 1, 31)
	if err != nil {
		return nil, fmt.Errorf("日位: %w", err)
	}
	month, err := parseField(fields[3], 1, 12)
	if err != nil {
		return nil, fmt.Errorf("月位: %w", err)
	}
	dow, err := parseField(fields[4], 0, 6)
	if err != nil {
		return nil, fmt.Errorf("周位: %w", err)
	}
	return &cronExpr{minute: minute, hour: hour, dom: dom, month: month, dow: dow}, nil
}

func parseField(expr string, lo, hi int) (fieldMatcher, error) {
	f := fieldMatcher{vals: map[int]struct{}{}, raw: expr, lo: lo, hi: hi}
	if expr == "*" {
		f.any = true
		return f, nil
	}
	for _, part := range strings.Split(expr, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			return f, fmt.Errorf("空片段")
		}
		step := 1
		if i := strings.Index(part, "/"); i >= 0 {
			n, err := strconv.Atoi(part[i+1:])
			if err != nil || n <= 0 {
				return f, fmt.Errorf("步长非法: %q", part)
			}
			step = n
			part = part[:i]
		}
		var start, end int
		switch {
		case part == "*":
			start, end = lo, hi
		case strings.Contains(part, "-"):
			segs := strings.SplitN(part, "-", 2)
			s, err1 := strconv.Atoi(segs[0])
			e, err2 := strconv.Atoi(segs[1])
			if err1 != nil || err2 != nil {
				return f, fmt.Errorf("区间非法: %q", part)
			}
			start, end = s, e
		default:
			n, err := strconv.Atoi(part)
			if err != nil {
				return f, fmt.Errorf("取值非法: %q", part)
			}
			start, end = n, n
			if step > 1 {
				end = hi
			}
		}
		if start < lo || end > hi || start > end {
			return f, fmt.Errorf("超出范围 [%d,%d]: %q", lo, hi, part)
		}
		for v := start; v <= end; v += step {
			f.vals[v] = struct{}{}
		}
	}
	if len(f.vals) == 0 {
		return f, fmt.Errorf("无有效取值")
	}
	return f, nil
}
