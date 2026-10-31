// 来源: 全部 @Scheduled 方法的集中登记（21 处）
//   com/ruoyi/base/task/CarTask.java:36-212                11 个可疑车辆任务（整个文件在块注释内）
//   com/ruoyi/base/task/TrackTask.java:54,66,84             3 个轨迹任务
//   com/ruoyi/base/task/DataFlowTask.java:37,56             2 个流转任务
//   DataReliabilityService:384,481 / DataLossDetectionService:127 /
//   DelayMonitoringService:329 / GaussEsConsistencyService:178
// 职责: Quartz 6 段式 cron（秒 分 时 日 月 周）与 fixedRate 的等价实现。
//
// DIFF: Java 由 Spring TaskScheduler 托管；Rust 用 tokio 每秒 tick + 显式字段匹配。
// PARITY: CarTask 的 11 个任务登记但禁用 —— Java 侧整个文件处于块注释内，从未被扫描到。
// 且其目标方法依赖的 SQL 在 Mapper XML 中缺失（详见 handlers/selftest.rs）。

use std::sync::Arc;
use std::time::Duration;

use chrono::{Datelike, Local, Timelike};
use tokio::sync::watch;
use tracing::{error, info, warn};

use crate::config::Config;
use crate::services::consistency::ConsistencyService;
use crate::services::delay_monitor::DelayMonitorService;
use crate::services::dict::DictService;
use crate::services::loss_detection::LossDetectionService;
use crate::services::multisource::MultiSourceService;
use crate::services::reliability::ReliabilityService;
use crate::services::sysutil::SysUtilService;

type Action = Arc<dyn Fn() -> futures::future::BoxFuture<'static, ()> + Send + Sync>;

#[derive(Clone)]
enum Schedule {
    Cron(Cron),
    Every(Duration),
}

struct Job {
    name: &'static str,
    schedule: Schedule,
    disabled: bool,
    action: Action,
}

#[derive(Clone)]
struct Cron {
    sec: Field,
    min: Field,
    hour: Field,
    day: Field,
    month: Field,
    dow: Field,
}

#[derive(Clone)]
enum Field {
    Any,
    Values(Vec<u32>),
    Step(u32, u32),
}

impl Field {
    fn parse(s: &str, max: u32) -> Result<Self, String> {
        let s = s.trim();
        if s == "*" || s == "?" {
            return Ok(Field::Any);
        }
        if let Some(rest) = s.strip_prefix("*/") {
            let step: u32 = rest.parse().map_err(|_| format!("非法 cron 字段: {}", s))?;
            return Ok(Field::Step(0, step.max(1)));
        }
        if let Some((start, step)) = s.split_once('/') {
            let start: u32 = start
                .parse()
                .map_err(|_| format!("非法 cron 字段: {}", s))?;
            let step: u32 = step.parse().map_err(|_| format!("非法 cron 字段: {}", s))?;
            return Ok(Field::Step(start, step.max(1)));
        }
        let mut vals = Vec::new();
        for part in s.split(',') {
            let v: u32 = part
                .trim()
                .parse()
                .map_err(|_| format!("非法 cron 字段: {}", s))?;
            if v > max {
                return Err(format!("cron 字段越界: {}", s));
            }
            vals.push(v);
        }
        Ok(Field::Values(vals))
    }

    fn matches(&self, v: u32) -> bool {
        match self {
            Field::Any => true,
            Field::Values(vals) => vals.contains(&v),
            Field::Step(start, step) => v >= *start && (v - start) % step == 0,
        }
    }
}

impl Cron {
    fn parse(spec: &str) -> Result<Self, String> {
        let parts: Vec<&str> = spec.split_whitespace().collect();
        if parts.len() != 6 {
            return Err(format!("Quartz cron 必须是 6 段，当前为 {}", spec));
        }
        Ok(Self {
            sec: Field::parse(parts[0], 59)?,
            min: Field::parse(parts[1], 59)?,
            hour: Field::parse(parts[2], 23)?,
            day: Field::parse(parts[3], 31)?,
            month: Field::parse(parts[4], 12)?,
            dow: Field::parse(parts[5], 7)?,
        })
    }

    fn matches(&self, now: &chrono::DateTime<Local>) -> bool {
        self.sec.matches(now.second())
            && self.min.matches(now.minute())
            && self.hour.matches(now.hour())
            && self.day.matches(now.day())
            && self.month.matches(now.month())
            && self.dow.matches(now.weekday().num_days_from_sunday() + 1)
    }
}

#[derive(Default)]
pub struct Scheduler {
    jobs: Vec<Job>,
}

impl Scheduler {
    fn add(
        &mut self,
        name: &'static str,
        schedule: Schedule,
        disabled: bool,
        action: Action,
    ) -> Result<(), String> {
        if let Schedule::Cron(c) = &schedule {
            let _ = c;
        }
        self.jobs.push(Job {
            name,
            schedule,
            disabled,
            action,
        });
        Ok(())
    }

    fn cron(
        &mut self,
        name: &'static str,
        spec: &str,
        disabled: bool,
        action: Action,
    ) -> Result<(), String> {
        let c = Cron::parse(spec)?;
        self.add(name, Schedule::Cron(c), disabled, action)
    }

    fn every(&mut self, name: &'static str, interval: Duration, action: Action) {
        let _ = self.add(name, Schedule::Every(interval), false, action);
    }

    pub fn count(&self) -> usize {
        self.jobs.len()
    }

    pub fn disabled_count(&self) -> usize {
        self.jobs.iter().filter(|j| j.disabled).count()
    }

    /// 启动调度循环；ctx 取消即退出。每个任务在独立 tokio task 中执行，避免慢任务阻塞其它任务。
    pub async fn run(self, mut stop: watch::Receiver<bool>) {
        info!(jobs = self.jobs.len(), "[定时任务] 调度器已启动");
        let mut last_tick: Option<i64> = None;
        let mut last_run: Vec<Option<std::time::Instant>> =
            self.jobs.iter().map(|_| None).collect();
        loop {
            if *stop.borrow() {
                info!("[定时任务] 调度器已停止");
                return;
            }
            let now = Local::now();
            let secs = now.timestamp();
            if last_tick != Some(secs) {
                last_tick = Some(secs);
                for (i, job) in self.jobs.iter().enumerate() {
                    if job.disabled {
                        continue;
                    }
                    let due = match &job.schedule {
                        Schedule::Cron(c) => c.matches(&now),
                        Schedule::Every(d) => {
                            last_run[i].map(|t| t.elapsed() >= *d).unwrap_or(true)
                        }
                    };
                    if !due {
                        continue;
                    }
                    last_run[i] = Some(std::time::Instant::now());
                    let action = job.action.clone();
                    let name = job.name;
                    tokio::spawn(async move {
                        let fut = std::panic::AssertUnwindSafe(action());
                        if futures::FutureExt::catch_unwind(fut).await.is_err() {
                            error!(job = name, "[定时任务] 执行 panic");
                        }
                    });
                }
            }
            tokio::select! {
                _ = stop.changed() => {
                    if *stop.borrow() {
                        info!("[定时任务] 调度器已停止");
                        return;
                    }
                }
                _ = tokio::time::sleep(Duration::from_millis(200)) => {}
            }
        }
    }
}

fn act<F, Fut>(f: F) -> Action
where
    F: Fn() -> Fut + Send + Sync + 'static,
    Fut: std::future::Future<Output = ()> + Send + 'static,
{
    Arc::new(move || Box::pin(f()))
}

/// 登记全部 21 个 @Scheduled（10 个真实调度 + 11 个 CarTask 禁用）。
pub fn build(
    cfg: &Config,
    dict: Option<DictService>,
    sysutil: Arc<SysUtilService>,
    multisource: MultiSourceService,
    loss: Arc<LossDetectionService>,
    delay: Arc<DelayMonitorService>,
    reliability: Arc<ReliabilityService>,
    consistency: Option<ConsistencyService>,
) -> Result<Scheduler, String> {
    let mut s = Scheduler::default();

    // TrackTask.syncBaseInfo：每天 0 点重建字典缓存
    if let Some(dict) = dict {
        let d = dict.clone();
        s.cron(
            "syncBaseInfo",
            "0 0 0 * * ?",
            false,
            act(move || {
                let d = d.clone();
                async move {
                    if let Err(e) = d.refresh_all().await {
                        error!(err = %e, "[定时任务] 重建基础字典缓存失败");
                    }
                }
            }),
        )?;
    }

    // TrackTask.syncCurrentTrack：每 3 分钟
    {
        let su = sysutil.clone();
        s.cron(
            "syncCurrentTrack",
            "0 0/3 * * * ?",
            false,
            act(move || {
                let su = su.clone();
                async move {
                    if let Err(e) = su.sync_track().await {
                        error!(err = %e, "[定时任务] 同步实时轨迹失败");
                    }
                }
            }),
        )?;
    }
    // TrackTask.syncHistroyTrack：每天 4 点（Java 侧方法名就拼成 Histroy）
    {
        let su = sysutil.clone();
        s.cron(
            "syncHistroyTrack",
            "0 0 4 * * ?",
            false,
            act(move || {
                let su = su.clone();
                async move {
                    if let Err(e) = su.sync_history_track().await {
                        error!(err = %e, "[定时任务] 同步历史轨迹失败");
                    }
                }
            }),
        )?;
    }

    // DataFlowTask.processPendingQueue：每分钟
    {
        let ms = multisource.clone();
        s.cron(
            "processPendingQueue",
            "0 */1 * * * ?",
            false,
            act(move || {
                let ms = ms.clone();
                async move { ms.process_pending_queue().await }
            }),
        )?;
    }
    // DataFlowTask.syncGantryCaptureData：Java 方法体只有日志
    s.cron(
        "syncGantryCaptureData",
        "0 */5 * * * ?",
        false,
        act(|| async {
            info!("[定时任务] 同步门架抓拍数据（Java 侧方法体为空，保留占位）");
        }),
    )?;

    // DataLossDetectionService.scheduledDetection
    {
        let interval = Duration::from_secs((cfg.detection.interval_minutes.max(1) as u64) * 60);
        let l = loss.clone();
        s.every(
            "dataLossDetection",
            interval,
            act(move || {
                let l = l.clone();
                async move { l.scheduled_detection().await }
            }),
        );
    }
    // DelayMonitoringService.generateStatsReport
    {
        let d = delay.clone();
        s.every(
            "delayStatsReport",
            Duration::from_secs(600),
            act(move || {
                let d = d.clone();
                async move { d.generate_stats_report().await }
            }),
        );
    }
    // DataReliabilityService.compensationTask
    {
        let interval = Duration::from_secs(cfg.reliability.compensation_interval_seconds.max(1));
        let r = reliability.clone();
        s.every(
            "reliabilityCompensation",
            interval,
            act(move || {
                let r = r.clone();
                async move { r.compensation_task().await }
            }),
        );
    }
    // DataReliabilityService.checkOfflineDevices
    {
        let r = reliability.clone();
        s.every(
            "checkOfflineDevices",
            Duration::from_secs(300),
            act(move || {
                let r = r.clone();
                async move { r.check_offline_devices().await }
            }),
        );
    }

    // GaussEsConsistencyService.scheduledReconcile
    let reconcile_disabled = !cfg.consistency.reconcile.enabled;
    if let Some(c) = consistency {
        s.cron(
            "gaussEsReconcile",
            &cfg.consistency.reconcile.cron,
            reconcile_disabled,
            act(move || {
                let c = c.clone();
                async move { c.scheduled_reconcile().await }
            }),
        )?;
    }

    // CarTask 的 11 个任务：登记但不执行
    let suspicious = [
        ("syncSuspiciousCar1", "0 0 1 * * ?", "CarTask.java:36-46"),
        ("syncSuspiciousCar2", "0 15 1 * * ?", "CarTask.java:56-66"),
        ("syncSuspiciousCar3", "0 30 1 * * ?", "CarTask.java:75-85"),
        ("syncSuspiciousCar4", "0 45 1 * * ?", "CarTask.java:93-103"),
        ("syncSuspiciousCar5", "0 0 2 * * ?", "CarTask.java:112-122"),
        ("syncSuspiciousCar6", "0 15 2 * * ?", "CarTask.java:130-140"),
        ("syncSuspiciousCar7", "0 30 2 * * ?", "CarTask.java:148-158"),
        ("syncSuspiciousCar8", "0 45 2 * * ?", "CarTask.java:166-176"),
        ("syncSuspiciousCar9", "0 0 3 * * ?", "CarTask.java:184-194"),
        (
            "syncSuspiciousCar10",
            "0 15 3 * * ?",
            "CarTask.java:202-212",
        ),
        ("syncSuspiciousCar", "0 45 3 * * ?", "CarTask.java:220-225"),
    ];
    for (name, spec, java_ref) in suspicious {
        s.cron(name, spec, true, act(move || async move {
            warn!(
                job = name,
                java = java_ref,
                "[定时任务] 未执行：Java 侧 CarTask.java 处于全文件注释状态，且目标方法依赖的 SQL 在 Mapper XML 中缺失"
            );
        }))?;
    }

    info!(
        registered = s.count(),
        disabled = s.disabled_count(),
        "[定时任务] @Scheduled 登记完成"
    );
    Ok(s)
}

/// 供测试：校验仓库里全部 21 个 cron 表达式都能被解析。
pub fn validate_specs(specs: &[&str]) -> Result<(), String> {
    for spec in specs {
        Cron::parse(spec)?;
    }
    Ok(())
}
