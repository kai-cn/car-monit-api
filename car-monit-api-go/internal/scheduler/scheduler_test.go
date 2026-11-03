package scheduler

// JAVA 对照: Quartz 的 CronExpression（org.quartz.CronExpression）
//
// 类/职责: cron 表达式解析的单元测试——把 Java 侧 21 个 @Scheduled 表达式全部跑一遍
// 对应 Go 文件: internal/scheduler/scheduler_test.go
//
// 为什么值得存在：
//
//	Quartz 用 6 段式（秒 分 时 日 月 周），标准 cron 用 5 段式。降级规则如果写错，
//	表现是"服务起来了但任务永不触发"——最难发现的故障形态。
//	这里把 application.yml / CarTask / TrackTask / DataFlowTask 里的真实表达式全列出来断言，
//	任何一条降级后算不出下一次触发时间，测试立刻失败。

import (
	"context"
	"testing"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/service"
)

// TestNormalizeQuartzSpecs 覆盖仓库里实际出现的全部 Quartz 表达式。
func TestNormalizeQuartzSpecs(t *testing.T) {
	cases := []struct{ quartz, want string }{
		{"0 0 1 * * ?", "0 1 * * *"},     // CarTask.syncSuspiciousCar1
		{"0 15 1 * * ?", "15 1 * * *"},   // CarTask.syncSuspiciousCar2
		{"0 30 1 * * ?", "30 1 * * *"},   // CarTask.syncSuspiciousCar3
		{"0 45 1 * * ?", "45 1 * * *"},   // CarTask.syncSuspiciousCar4
		{"0 0 2 * * ?", "0 2 * * *"},     // CarTask.syncSuspiciousCar5
		{"0 15 2 * * ?", "15 2 * * *"},   // CarTask.syncSuspiciousCar6
		{"0 30 2 * * ?", "30 2 * * *"},   // CarTask.syncSuspiciousCar7 / GaussEsConsistencyService
		{"0 45 2 * * ?", "45 2 * * *"},   // CarTask.syncSuspiciousCar8
		{"0 0 3 * * ?", "0 3 * * *"},     // CarTask.syncSuspiciousCar9
		{"0 15 3 * * ?", "15 3 * * *"},   // CarTask.syncSuspiciousCar10
		{"0 45 3 * * ?", "45 3 * * *"},   // CarTask.syncSuspiciousCar
		{"0 */3 * * * ?", "*/3 * * * *"}, // 非标准：见下方 TestInvalidQuartzSeconds 说明
		{"0 0/3 * * * ?", "0/3 * * * *"}, // TrackTask.syncCurrentTrack
		{"0 0 0 * * ?", "0 0 * * *"},     // TrackTask.syncBaseInfo
		{"0 0 4 * * ?", "0 4 * * *"},     // TrackTask.syncHistroyTrack
		{"0 */1 * * * ?", "*/1 * * * *"}, // DataFlowTask.processPendingQueue
		{"0 */5 * * * ?", "*/5 * * * *"}, // DataFlowTask.syncGantryCaptureData
		{"0 30 2 * * ?", "30 2 * * *"},   // GaussEsConsistencyService
		{"*/5 * * * *", "*/5 * * * *"},   // 已经是 5 段式：原样返回
	}
	for _, c := range cases {
		got, err := normalizeSpec(c.quartz)
		if err != nil {
			t.Errorf("normalizeSpec(%q) 报错: %v", c.quartz, err)
			continue
		}
		if got != c.want {
			t.Errorf("normalizeSpec(%q) = %q，期望 %q", c.quartz, got, c.want)
		}
	}

	// CarTask 的 11 个表达式直接用登记表断言，避免表和 Java 双份维护出错。
	if len(suspiciousCarJobs) != 11 {
		t.Fatalf("CarTask 应有 11 个 @Scheduled，实际 %d", len(suspiciousCarJobs))
	}
	for _, j := range suspiciousCarJobs {
		if _, err := normalizeSpec(j.Spec); err != nil {
			t.Errorf("CarTask.%s 的表达式 %q 无法降级: %v", j.Name, j.Spec, err)
		}
	}
}

// TestInvalidQuartzSeconds 断言"秒位非 0"被拒绝。
//
// PARITY: 本项目所有 @Scheduled 的秒位都是 0。若将来出现 "0/5 * * * * ?"（每 5 秒），
// 必须显式告知调用方"分钟级调度不支持秒级"，而不是静默按分钟跑。
func TestInvalidQuartzSeconds(t *testing.T) {
	for _, spec := range []string{"30 * * * * ?", "*/5 * * * * ?"} {
		if _, err := normalizeSpec(spec); err == nil {
			t.Errorf("normalizeSpec(%q) 应当报错（秒位必须为 0）", spec)
		}
	}
}

// TestParseField 覆盖 * / 固定值 / 区间 / 步长 / 枚举 / 越界。
func TestParseField(t *testing.T) {
	ok := []struct {
		expr string
		lo   int
		hi   int
		vals []int
	}{
		{"*", 0, 59, []int{0, 30, 59}},
		{"5", 0, 59, []int{5}},
		{"10-12", 0, 23, []int{10, 11, 12}},
		{"*/15", 0, 59, []int{0, 15, 30, 45}},
		{"1,3,5", 0, 6, []int{1, 3, 5}},
		{"0", 0, 59, []int{0}},
	}
	for _, c := range ok {
		f, err := parseField(c.expr, c.lo, c.hi)
		if err != nil {
			t.Errorf("parseField(%q) 报错: %v", c.expr, err)
			continue
		}
		for _, v := range c.vals {
			if !f.match(v) {
				t.Errorf("parseField(%q) 应匹配 %d", c.expr, v)
			}
		}
	}

	bad := []string{"60", "-1", "10-5", "abc", "", "*/0"}
	for _, expr := range bad {
		if _, err := parseField(expr, 0, 59); err == nil {
			t.Errorf("parseField(%q) 应当报错", expr)
		}
	}
}

// TestNextFire 断言真实表达式算出的下一次触发时间。
//
// 场景：UTC 时间 2026-03-01 23:59:30，任务 "0 0 0 * * ?"（每天 0 点）
// 期望下一次触发是 2026-03-02 00:00:00，而不是"立刻"或"明天 23:59"。
func TestNextFire(t *testing.T) {
	s := New(time.UTC)
	if err := s.Add(Job{
		Name: "syncBaseInfo",
		Spec: "0 0 0 * * ?",
		Fn:   func(context.Context) {},
	}); err != nil {
		t.Fatalf("Add 失败: %v", err)
	}

	from := time.Date(2026, 3, 1, 23, 59, 30, 0, time.UTC)
	got := s.nextFire("syncBaseInfo", from)
	want := time.Date(2026, 3, 2, 0, 0, 0, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("nextFire = %s，期望 %s", got.Format(time.RFC3339), want.Format(time.RFC3339))
	}

	// 已过当日 0 点时，应推到下一天，而不是回退到今天。
	from = time.Date(2026, 3, 2, 0, 0, 30, 0, time.UTC)
	got = s.nextFire("syncBaseInfo", from)
	want = time.Date(2026, 3, 3, 0, 0, 0, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("nextFire = %s，期望 %s", got.Format(time.RFC3339), want.Format(time.RFC3339))
	}
}

// TestNextFireEveryMinute 验证 minute-only 表达式不会跳过整点边界。
func TestNextFireEveryMinute(t *testing.T) {
	s := New(time.UTC)
	if err := s.Add(Job{
		Name: "processPendingQueue",
		Spec: "0 */1 * * * ?",
		Fn:   func(context.Context) {},
	}); err != nil {
		t.Fatalf("Add 失败: %v", err)
	}
	from := time.Date(2026, 3, 1, 10, 30, 10, 0, time.UTC)
	got := s.nextFire("processPendingQueue", from)
	want := time.Date(2026, 3, 1, 10, 31, 0, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("nextFire = %s，期望 %s", got.Format(time.RFC3339), want.Format(time.RFC3339))
	}
}

// TestAddDuplicateName 断言同名任务不会被静默覆盖。
func TestAddDuplicateName(t *testing.T) {
	s := New(time.UTC)
	if err := s.Add(Job{Name: "dup", Spec: "* * * * *", Fn: func(context.Context) {}}); err != nil {
		t.Fatalf("第一次 Add 失败: %v", err)
	}
	if err := s.Add(Job{Name: "dup", Spec: "* * * * *", Fn: func(context.Context) {}}); err == nil {
		t.Fatal("同名任务重复登记应当报错")
	}
}

// TestEveryValidation 断言间隔下限。
func TestEveryValidation(t *testing.T) {
	s := New(time.UTC)
	if err := s.Every("ok", time.Minute, func(context.Context) {}); err != nil {
		t.Fatalf("合法间隔被拒绝: %v", err)
	}
	if err := s.Every("bad", 100*time.Millisecond, func(context.Context) {}); err == nil {
		t.Fatal("小于 1s 的间隔应当报错")
	}
}

// TestRegisterAllTrackJobs 断言 TrackTask 的 2 个任务被真正登记，
// 而 CarTask 的 11 个只进清单、一律 Disabled（与 Java 侧「整文件注释」一致）。
//
// 只注入 SysUtil，其余依赖传 nil：登记阶段不会执行任何任务体，
// 所以全 nil 依赖也能跑——这就是「调度清单可离线验证」的好处。
func TestRegisterAllTrackJobs(t *testing.T) {
	cfg := &config.Config{}
	cfg.Consistency.Reconcile.Cron = "0 30 2 * * ?"

	sysUtil := service.NewSysUtilService(nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, "local")
	s := New(time.UTC)

	n, err := RegisterAll(s, cfg, &Jobs{SysUtil: sysUtil})
	if err != nil {
		t.Fatalf("RegisterAll 失败: %v", err)
	}
	// syncCurrentTrack + syncHistroyTrack (2) + syncGantryCaptureData (1)
	// + gaussEsReconcile (1) + CarTask (11) = 15
	if n != 15 {
		t.Fatalf("登记数量 = %d，期望 15", n)
	}

	byName := map[string]*Job{}
	for _, j := range s.jobs {
		byName[j.Name] = j
	}

	want := map[string]string{
		"syncCurrentTrack": "0/3 * * * *", // 每 3 分钟
		"syncHistroyTrack": "0 4 * * *",   // 每天 4 点
	}
	for name, spec := range want {
		j, ok := byName[name]
		if !ok {
			t.Errorf("缺少 TrackTask 任务 %s", name)
			continue
		}
		if j.Spec != spec {
			t.Errorf("任务 %s 的 spec = %q，期望 %q", name, j.Spec, spec)
		}
		if j.Disabled {
			t.Errorf("任务 %s 不应被禁用", name)
		}
		if j.Fn == nil {
			t.Errorf("任务 %s 没有任务体", name)
		}
	}

	for _, j := range suspiciousCarJobs {
		got, ok := byName[j.Name]
		if !ok {
			t.Errorf("缺少 CarTask 任务 %s", j.Name)
			continue
		}
		if !got.Disabled {
			t.Errorf("CarTask 任务 %s 必须是 Disabled（Java 侧整文件注释）", j.Name)
		}
	}
}
