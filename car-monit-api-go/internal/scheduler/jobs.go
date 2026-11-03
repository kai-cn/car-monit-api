package scheduler

// JAVA 对照: 全部 @Scheduled 方法的集中登记（21 处，见下）
//
//	com/ruoyi/base/task/CarTask.java:36-212                11 个可疑车辆任务（**整个文件在块注释内**）
//	com/ruoyi/base/task/TrackTask.java:54,66,84             3 个轨迹任务
//	com/ruoyi/base/task/DataFlowTask.java:37,56             2 个流转任务
//	com/ruoyi/base/service/impl/DataReliabilityService.java:384, 481
//	com/ruoyi/base/service/impl/DataLossDetectionService.java:127
//	com/ruoyi/base/service/impl/DelayMonitoringService.java:329
//	com/ruoyi/base/service/optimization/GaussEsConsistencyService.java:178
//
// 类/职责: 把 Java 里的 @Scheduled 注解逐条翻译成 Scheduler.Add / Scheduler.Every 调用
// 对应 Go 文件: internal/scheduler/jobs.go
// 关键映射:
//
//	@Scheduled(cron = "0 0 0 * * ?")     → Add({Spec: "0 0 0 * * ?"})（Quartz 6 段原样抄）
//	@Scheduled(fixedRate = 300000)       → Every(5*time.Minute)
//	${consistency.reconcile.cron}        → cfg.Consistency.Reconcile.Cron
//	@Scheduled 方法的 log.info(...)       → 由 Scheduler.run 统一打印开始/结束日志
//	被注释掉的调用                        → 不注册（与当前 Java 运行时行为一致）
//
// PARITY（CarTask 的 11 个任务）: CarTask.java 的全部内容都在块注释里——
// 第 1 行是 `/*`、第 231 行是 `*/`，23 个 `/*` 与 23 个 `*/` 成对，剥掉注释后 0 行代码。
// 也就是说这 11 个 @Scheduled 从来没被 Spring 扫描到，一天一次也不会跑。
//
// 即便解除注释也跑不通：它们调的 SysUtilServiceImpl.syncSuspiciousCarQutaz(L1245-1635)
// 在 L1408 调 syncFeeRecords，而后者依赖 OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew
// —— 该语句在全部 23 个 Mapper XML 中缺失（接口只有声明），MyBatis 必抛 Invalid bound statement。
// 所以 Go 侧按原样登记（保留任务名与 cron 表达式，便于和 Java 逐行对照），但一律 Disabled: true，
// 保证「调度清单一致 + 实际不执行」两点都与 Java 相同。

import (
	"context"
	"log/slog"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/config"
	"github.com/ruoyi/car-monit-api-go/internal/service"
)

// Jobs 汇总所有定时任务需要的依赖。
//
// DIFF: Java 由 Spring 容器按类型注入；Go 显式列出，main() 里一眼能看出"定时任务依赖谁"。
type Jobs struct {
	Dict        *service.DictRegistry
	MultiSource *service.MultiSourceDataFlowService
	Loss        *service.DataLossDetectionService
	Delay       *service.DelayMonitoringService
	Reliability *service.DataReliabilityService
	Consistency *service.GaussEsConsistencyService
	// SysUtil 对应 TrackTask 里的 @Autowired ISysUtilService（syncCurrentTrack / syncHistroyTrack）
	SysUtil *service.SysUtilService
}

// qutazTarget 是前 10 个任务真正会调的 Java 方法，单独提出来避免 11 行字面量重复。
const qutazTarget = "SysUtilService.syncSuspiciousCarQutaz"

// suspiciousCarJobs 对应 CarTask.java:36-212 的 11 个 @Scheduled（全部位于块注释内）。
//
// FromTo 对应 Java 的 `for (int i = from; i < to; i++) syncSuspiciousCarQutaz(i, i)`，
// to 是开区间（与 Java 的 `<` 一致）。第 11 个 syncSuspiciousCar 没有循环，
// 它调的是 separateSnapshotFlowTimeList()（门架抓拍 vs 门架交易对比），
// 所以 FromTo 置零、Target 单独写，避免 WARN 日志把两个方法说混。
var suspiciousCarJobs = []struct {
	Name    string
	Spec    string
	FromTo  [2]int
	JavaRef string
	Target  string
}{
	{"syncSuspiciousCar1", "0 0 1 * * ?", [2]int{1, 11}, "CarTask.java:36-46", qutazTarget},
	{"syncSuspiciousCar2", "0 15 1 * * ?", [2]int{11, 21}, "CarTask.java:56-66", qutazTarget},
	{"syncSuspiciousCar3", "0 30 1 * * ?", [2]int{21, 31}, "CarTask.java:75-85", qutazTarget},
	{"syncSuspiciousCar4", "0 45 1 * * ?", [2]int{31, 41}, "CarTask.java:93-103", qutazTarget},
	{"syncSuspiciousCar5", "0 0 2 * * ?", [2]int{41, 51}, "CarTask.java:112-122", qutazTarget},
	{"syncSuspiciousCar6", "0 15 2 * * ?", [2]int{51, 61}, "CarTask.java:130-140", qutazTarget},
	{"syncSuspiciousCar7", "0 30 2 * * ?", [2]int{61, 71}, "CarTask.java:148-158", qutazTarget},
	{"syncSuspiciousCar8", "0 45 2 * * ?", [2]int{71, 81}, "CarTask.java:166-176", qutazTarget},
	{"syncSuspiciousCar9", "0 0 3 * * ?", [2]int{81, 91}, "CarTask.java:184-194", qutazTarget},
	{"syncSuspiciousCar10", "0 15 3 * * ?", [2]int{91, 101}, "CarTask.java:202-212", qutazTarget},
	{"syncSuspiciousCar", "0 45 3 * * ?", [2]int{0, 0}, "CarTask.java:220-225", "SysUtilService.separateSnapshotFlowTimeList"},
}

// RegisterAll 登记所有可实现的任务，返回登记成功的条数。
func RegisterAll(s *Scheduler, cfg *config.Config, jobs *Jobs) (int, error) {
	registered := 0
	add := func(j Job) error {
		if err := s.Add(j); err != nil {
			return err
		}
		registered++
		return nil
	}

	// ---- TrackTask.syncBaseInfo：每天 0 点重建基础字典缓存 ----
	// JAVA: TrackTask.java:66-83 —— 依次调用 7 个 updateRedis()，Go 合并为一次 RefreshAll。
	if jobs.Dict != nil {
		dict := jobs.Dict
		if err := add(Job{
			Name: "syncBaseInfo",
			Spec: "0 0 0 * * ?",
			Fn: func(ctx context.Context) {
				if err := dict.RefreshAll(ctx); err != nil {
					slog.Error("[定时任务] 重建基础字典缓存失败", "err", err)
				}
			},
		}); err != nil {
			return registered, err
		}
	}

	// ---- TrackTask.syncCurrentTrack：每 3 分钟把 trail:{carNo} 富集成实时轨迹 ----
	// JAVA: TrackTask.java:54-59 —— sysUtilService.syncTrack(new CarParaVO())
	if jobs.SysUtil != nil {
		su := jobs.SysUtil
		if err := add(Job{
			Name: "syncCurrentTrack",
			Spec: "0 0/3 * * * ?",
			Fn: func(ctx context.Context) {
				if err := su.SyncTrack(ctx); err != nil {
					slog.Error("[定时任务] 同步实时轨迹失败", "err", err)
				}
			},
		}); err != nil {
			return registered, err
		}

		// ---- TrackTask.syncHistroyTrack：每天 4 点把历史轨迹并入 car_history_trail:{carNo} ----
		// JAVA: TrackTask.java:84-160 —— 方法名在 Java 侧就拼成了 Histroy，这里保留，便于全文检索
		if err := add(Job{
			Name: "syncHistroyTrack",
			Spec: "0 0 4 * * ?",
			Fn: func(ctx context.Context) {
				if err := su.SyncHistoryTrack(ctx); err != nil {
					slog.Error("[定时任务] 同步历史轨迹失败", "err", err)
				}
			},
		}); err != nil {
			return registered, err
		}
	}

	// ---- DataFlowTask.processPendingQueue：每分钟处理乱序待拼接队列 ----
	// JAVA: DataFlowTask.java:37-45
	if jobs.MultiSource != nil {
		ms := jobs.MultiSource
		if err := add(Job{
			Name: "processPendingQueue",
			Spec: "0 */1 * * * ?",
			Fn:   ms.ProcessPendingQueue,
		}); err != nil {
			return registered, err
		}
	}

	// ---- DataFlowTask.syncGantryCaptureData：Java 方法体只有日志，正文全被注释 ----
	// PARITY: 这里保留同名任务 + 同样的"什么都不做"，让 cron 清单与 Java 完全对齐；
	// 真要启用，把 ms.ProcessData 的批量回放补进来即可。
	if err := add(Job{
		Name: "syncGantryCaptureData",
		Spec: "0 */5 * * * ?",
		Fn: func(ctx context.Context) {
			slog.Info("[定时任务] 同步门架抓拍数据（Java 侧方法体为空，保留占位）")
		},
	}); err != nil {
		return registered, err
	}

	// ---- DataLossDetectionService.scheduledDetection ----
	// JAVA: fixedRateString = "${detection.interval-minutes:30}000"
	if jobs.Loss != nil {
		interval := time.Duration(cfg.Detection.IntervalMinutes) * time.Minute
		if interval <= 0 {
			interval = 30 * time.Minute
		}
		loss := jobs.Loss
		if err := s.Every("dataLossDetection", interval, loss.ScheduledDetection); err != nil {
			return registered, err
		}
		registered++
	}

	// ---- DelayMonitoringService.generateStatsReport ----
	// JAVA: @Scheduled(fixedRate = 600000) —— 每 10 分钟
	if jobs.Delay != nil {
		delay := jobs.Delay
		if err := s.Every("delayStatsReport", 10*time.Minute, delay.GenerateStatsReport); err != nil {
			return registered, err
		}
		registered++
	}

	// ---- DataReliabilityService.compensationTask ----
	// JAVA: fixedRateString = "${reliability.compensation-interval-seconds:60}000"
	if jobs.Reliability != nil {
		interval := time.Duration(cfg.Reliability.CompensationIntervalSeconds) * time.Second
		if interval <= 0 {
			interval = time.Minute
		}
		rel := jobs.Reliability
		if err := s.Every("reliabilityCompensation", interval, rel.CompensationTask); err != nil {
			return registered, err
		}
		registered++

		// ---- DataReliabilityService.checkOfflineDevices ----
		// JAVA: @Scheduled(fixedRate = 300000) —— 每 5 分钟
		if err := s.Every("checkOfflineDevices", 5*time.Minute, rel.CheckOfflineDevices); err != nil {
			return registered, err
		}
		registered++
	}

	// ---- GaussEsConsistencyService.scheduledReconcile ----
	// JAVA: @Scheduled(cron = "${consistency.reconcile.cron:0 30 2 * * ?}")
	var reconcileEndpoint func(ctx context.Context)
	if jobs.Consistency != nil {
		reconcileEndpoint = jobs.Consistency.ScheduledReconcile
	}
	if err := add(Job{
		Name:     "gaussEsReconcile",
		Spec:     cfg.Consistency.Reconcile.Cron,
		Fn:       reconcileEndpoint,
		Disabled: !cfg.Consistency.Reconcile.Enabled,
	}); err != nil {
		return registered, err
	}

	// ---- CarTask 的 11 个可疑车辆任务：登记但不执行（Java 侧整文件在块注释内）----
	// 保留 Fn 而不是留空：万一有人在排查时把 Disabled 改成 false，日志会立刻说明为什么仍然不该跑。
	for _, job := range suspiciousCarJobs {
		if err := add(Job{
			Name:     job.Name,
			Spec:     job.Spec,
			Disabled: true,
			Fn: func(ctx context.Context) {
				slog.Warn("[定时任务] 未执行：Java 侧 CarTask.java 处于全文件注释状态，且目标方法依赖的 "+
					"SQL 在 Mapper XML 中缺失（详见 handler/selftest.go 文件头 PARITY）",
					"job", job.Name, "java", job.JavaRef,
					"range", job.FromTo, "wouldCall", job.Target)
			},
		}); err != nil {
			return registered, err
		}
	}

	// 至此 21 个 @Scheduled 全部有归属：
	//   TrackTask 3 + DataFlowTask 2 + Service 内 5 = 10 个真实调度（consistency 受开关控制）；
	//   CarTask 11 个按 Java 现状禁用（Disabled 的任务由 Scheduler.Start 逐条打 Info 日志）。
	slog.Info("[定时任务] @Scheduled 登记完成", "registered", registered, "disabled", len(suspiciousCarJobs))
	return registered, nil
}
