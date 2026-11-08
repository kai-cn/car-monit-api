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
use crate::services::export::ExportService;
use crate::services::large::LargeScaleQueryService;
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
            Field::Step(start, step) => v >= *start && (v - start).is_multiple_of(*step),
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
    ///
    /// 多副本：配置了 Redis 时用租约保证同一时刻只有一个副本执行任务；
    /// 未配置 Redis 时退回单副本模式（需部署侧保证 enable-scheduler 只在一个副本为 true）。
    pub async fn run(
        self,
        stop: watch::Receiver<bool>,
        cache: Option<crate::cache::Cache>,
        instance_id: String,
        lease_required: bool,
        shutdown_grace: Duration,
    ) {
        info!(
            lease_required,
            shutdown_grace_seconds = shutdown_grace.as_secs(),
            "[定时任务] 运行参数：scheduler-lease-required={}（true=多副本严格模式；false=单副本降级）",
            lease_required
        );
        let Some(cache) = cache else {
            warn!("[定时任务] 未配置 Redis，按单副本模式运行（多副本请仅在一个副本设置 ENABLE_SCHEDULER=true）");
            return self
                .run_inner(stop, None, instance_id, lease_required, shutdown_grace)
                .await;
        };
        info!(
            instance = %instance_id,
            "[定时任务] 启用 Redis 租约，仅 leader 副本执行任务"
        );
        self.run_inner(
            stop,
            Some(cache),
            instance_id,
            lease_required,
            shutdown_grace,
        )
        .await
    }

    async fn run_inner(
        self,
        mut stop: watch::Receiver<bool>,
        lease_cache: Option<crate::cache::Cache>,
        instance_id: String,
        lease_required: bool,
        shutdown_grace: Duration,
    ) {
        info!(jobs = self.jobs.len(), "[定时任务] 调度器已启动");
        let mut last_tick: Option<i64> = None;
        let mut last_run: Vec<Option<std::time::Instant>> =
            self.jobs.iter().map(|_| None).collect();
        // per-job 防重入：上一轮未结束时跳过本轮，避免慢任务叠加。
        let running: Vec<std::sync::Arc<std::sync::atomic::AtomicBool>> = self
            .jobs
            .iter()
            .map(|_| std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)))
            .collect();
        // 任务句柄：包装为 AbortOnDropHandler，保证调度器任务被外部 abort/丢弃时
        // 在途 job 也会被中止，而不是 detach 后继续写 DB/Redis。
        let mut job_handles: Vec<Option<JobHandle>> = self.jobs.iter().map(|_| None).collect();
        let mut degraded_warned = false;
        let mut strict_warned_at: Option<std::time::Instant> = None;
        // 调度器分得的停机预算：最多 10s，且不超过总预算的一半，给导出/DB 留余量。
        let job_drain = std::cmp::min(
            Duration::from_secs(10),
            Duration::from_secs((shutdown_grace.as_secs() / 2).max(1)),
        );
        let mut is_leader = lease_cache.is_none();
        let mut last_lease_check = std::time::Instant::now()
            .checked_sub(Duration::from_secs(60))
            .unwrap_or_else(std::time::Instant::now);
        loop {
            if *stop.borrow() {
                drain_jobs(&mut job_handles, job_drain).await;
                info!("[定时任务] 调度器已停止");
                return;
            }
            if let Some(cache) = &lease_cache {
                if last_lease_check.elapsed() >= Duration::from_secs(5) {
                    last_lease_check = std::time::Instant::now();
                    match cache
                        .acquire_lease(LEADER_KEY, &instance_id, Duration::from_secs(20))
                        .await
                    {
                        Ok(leader) => {
                            if degraded_warned {
                                info!("[定时任务] Redis 租约已恢复，回到 leader 选举模式");
                                degraded_warned = false;
                            }
                            if leader != is_leader {
                                info!(
                                    leader,
                                    "[定时任务] 调度权变更（leader=true 表示本副本开始执行任务）"
                                );
                            }
                            is_leader = leader;
                        }
                        Err(e) if lease_required => {
                            // 严格模式：限频 60s，避免每 5s 刷屏。
                            let should_warn = strict_warned_at
                                .map(|t| t.elapsed() >= Duration::from_secs(60))
                                .unwrap_or(true);
                            if should_warn {
                                strict_warned_at = Some(std::time::Instant::now());
                                warn!(
                                    err = %e,
                                    "[定时任务] 获取调度租约失败，多副本严格模式暂停执行任务（同类告警 60s 内只打一次）"
                                );
                            }
                            is_leader = false;
                        }
                        Err(e) => {
                            if !degraded_warned {
                                warn!(
                                    err = %e,
                                    "[定时任务] 获取租约失败；scheduler-lease-required=false，按单副本降级继续执行"
                                );
                                degraded_warned = true;
                            }
                            is_leader = true;
                        }
                    }
                }
            }
            let now = Local::now();
            let secs = now.timestamp();
            if is_leader && last_tick != Some(secs) {
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
                    if running[i].swap(true, std::sync::atomic::Ordering::SeqCst) {
                        warn!(
                            job = job.name,
                            "[定时任务] 上一轮仍在执行，跳过本轮（防重入）"
                        );
                        continue;
                    }
                    last_run[i] = Some(std::time::Instant::now());
                    let action = job.action.clone();
                    let name = job.name;
                    let flag = running[i].clone();
                    job_handles[i] = Some(JobHandle::new(tokio::spawn(async move {
                        let fut = std::panic::AssertUnwindSafe(action());
                        match tokio::time::timeout(JOB_TIMEOUT, futures::FutureExt::catch_unwind(fut))
                            .await
                        {
                            Ok(Ok(())) => {}
                            Ok(Err(_)) => error!(job = name, "[定时任务] 执行 panic"),
                            Err(_) => error!(
                                job = name,
                                timeout_seconds = JOB_TIMEOUT.as_secs(),
                                "[定时任务] 执行超时，已取消本轮"
                            ),
                        }
                        flag.store(false, std::sync::atomic::Ordering::SeqCst);
                    })));
                }
            }
            tokio::select! {
                r = stop.changed() => {
                    // Sender 提前 drop 时 changed() 返回 Err；等价于停机，否则会忙循环。
                    if r.is_err() || *stop.borrow() {
                        drain_jobs(&mut job_handles, job_drain).await;
                        info!("[定时任务] 调度器已停止");
                        return;
                    }
                }
                _ = tokio::time::sleep(Duration::from_millis(200)) => {}
            }
        }
    }
}

/// 调度任务句柄：持有 JoinHandle 的同时保留 AbortHandle。
/// Drop 时若 JoinHandle 仍未被取走（说明调度器被外部 abort/丢弃，来不及 drain），
/// 立即中止任务，避免 detach 后在后台继续写库。
struct JobHandle {
    inner: Option<tokio::task::JoinHandle<()>>,
    abort: tokio::task::AbortHandle,
}

impl JobHandle {
    fn new(handle: tokio::task::JoinHandle<()>) -> Self {
        let abort = handle.abort_handle();
        Self {
            inner: Some(handle),
            abort,
        }
    }

    fn is_finished(&self) -> bool {
        self.inner.as_ref().map(|h| h.is_finished()).unwrap_or(true)
    }

    /// 取走 JoinHandle 用于 join（之后 Drop 不再 abort，由 drain 的超时逻辑负责）。
    fn take_join(&mut self) -> Option<tokio::task::JoinHandle<()>> {
        self.inner.take()
    }
}

impl Drop for JobHandle {
    fn drop(&mut self) {
        if self.inner.is_some() {
            self.abort.abort();
        }
    }
}

/// drain 期间的兜底：若调度器任务在等待 join 时被外部 abort/丢弃，
/// Drop 会中止所有在途 job，避免 JoinHandle 移出包装后 detach。
struct AbortAllOnDrop {
    handles: Vec<tokio::task::AbortHandle>,
    armed: bool,
}

impl Drop for AbortAllOnDrop {
    fn drop(&mut self) {
        if self.armed {
            for a in &self.handles {
                a.abort();
            }
        }
    }
}

/// 协作式停机：先等待在途任务自然结束（最多 grace），超时才 abort。
/// 多步任务（同步/对账/导出）因此有机会在宽限期内收尾，不会一收到信号就被腰斩。
async fn drain_jobs(handles: &mut [Option<JobHandle>], grace: Duration) {
    let mut joins = Vec::new();
    let mut aborts = Vec::new();
    for slot in handles.iter_mut() {
        let Some(mut wrapper) = slot.take() else {
            continue;
        };
        if wrapper.is_finished() {
            continue;
        }
        aborts.push(wrapper.abort.clone());
        if let Some(h) = wrapper.take_join() {
            joins.push(h);
        }
    }
    if joins.is_empty() {
        return;
    }
    let mut guard = AbortAllOnDrop {
        handles: aborts.clone(),
        armed: true,
    };
    info!(
        jobs = joins.len(),
        grace_seconds = grace.as_secs(),
        "[定时任务] 等待在途任务收尾"
    );
    if tokio::time::timeout(grace, futures::future::join_all(joins))
        .await
        .is_err()
    {
        warn!(
            jobs = aborts.len(),
            grace_seconds = grace.as_secs(),
            "[定时任务] 宽限期内未全部结束，强制中止剩余任务（可能留下半成品）"
        );
        for a in &aborts {
            a.abort();
        }
    } else {
        info!("[定时任务] 在途任务已全部收尾");
    }
    guard.armed = false;
}

/// 调度器 leader 租约 key（Redis）。
/// 语义：租约 TTL=20s，每 5s 原子续期；leader 崩溃后新 leader 最迟 20s 接管。
/// 故障切换窗口内同一 cron 可能被执行「至多一次额外」——即调度语义是 at-least-once，
/// 所有定时任务必须幂等（与 Java 单机 @Scheduled 的唯一性假设不同，属多副本的固有代价）。
const LEADER_KEY: &str = "car_monit:scheduler:leader";
/// 单个任务的最长执行时间；超时后取消本轮（可能留下半成品，业务侧需可重入）。
const JOB_TIMEOUT: Duration = Duration::from_secs(10 * 60);

fn act<F, Fut>(f: F) -> Action
where
    F: Fn() -> Fut + Send + Sync + 'static,
    Fut: std::future::Future<Output = ()> + Send + 'static,
{
    Arc::new(move || Box::pin(f()))
}

/// 登记全部 21 个 @Scheduled（10 个真实调度 + 11 个 CarTask 禁用）。
/// 参数与 Java 各个 Bean 的依赖一一对应，拆成结构体会掩盖装配关系，故保留长参数列表。
#[allow(clippy::too_many_arguments)]
pub fn build(
    cfg: &Config,
    dict: Option<DictService>,
    sysutil: Arc<SysUtilService>,
    multisource: MultiSourceService,
    loss: Arc<LossDetectionService>,
    delay: Arc<DelayMonitorService>,
    reliability: Arc<ReliabilityService>,
    consistency: Option<ConsistencyService>,
    export: ExportService,
    large: LargeScaleQueryService,
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

    // S4：每天 3:45 清理过期的导出任务状态与导出目录（保留 24 小时）
    {
        let e = export.clone();
        let l = large.clone();
        s.cron(
            "exportCleanup",
            "0 45 3 * * ?",
            false,
            act(move || {
                let e = e.clone();
                let l = l.clone();
                async move {
                    let age = Duration::from_secs(24 * 3600);
                    e.clean_expired_tasks(age).await;
                    l.clean_expired_tasks(age).await;
                    match e.clean_expired_files(age) {
                        Ok(n) => info!(removed_dirs = n, "[定时任务] 导出目录清理完成"),
                        Err(err) => warn!(err = %err, "[定时任务] 导出目录清理失败"),
                    }
                }
            }),
        )?;
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

#[cfg(test)]
mod job_handle_tests {
    use super::{drain_jobs, AbortAllOnDrop, JobHandle};
    use std::time::Duration;
    use tokio::sync::oneshot::error::TryRecvError;

    /// Drop JobHandle（未取走 JoinHandle）必须中止任务，否则调度器被 abort 时 job 会 detach。
    #[tokio::test]
    async fn dropping_job_handle_aborts_the_task() {
        let (tx, mut rx) = tokio::sync::oneshot::channel::<()>();
        let handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(3600)).await;
            let _ = tx.send(());
        });
        drop(JobHandle::new(handle));
        tokio::time::sleep(Duration::from_millis(100)).await;
        assert!(matches!(rx.try_recv(), Err(TryRecvError::Closed)));
    }

    /// drain 过程中调度器任务被外部 abort：AbortAllOnDrop 必须把在途 job 一并中止。
    #[tokio::test]
    async fn cancelling_drain_aborts_inflight_jobs() {
        let (tx, mut rx) = tokio::sync::oneshot::channel::<()>();
        let handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_secs(3600)).await;
            let _ = tx.send(());
        });
        let mut slots = vec![Some(JobHandle::new(handle))];
        let drain = tokio::spawn(async move {
            drain_jobs(&mut slots, Duration::from_secs(3600)).await;
        });
        tokio::time::sleep(Duration::from_millis(50)).await;
        drain.abort();
        tokio::time::sleep(Duration::from_millis(100)).await;
        assert!(matches!(rx.try_recv(), Err(TryRecvError::Closed)));
    }

    /// 正常 drain：在宽限期内结束的 job 必须自然完成，不能被提前 abort。
    #[tokio::test]
    async fn normal_drain_lets_jobs_finish_without_abort() {
        let (tx, mut rx) = tokio::sync::oneshot::channel::<()>();
        let handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(30)).await;
            let _ = tx.send(());
        });
        let mut slots = vec![Some(JobHandle::new(handle))];
        drain_jobs(&mut slots, Duration::from_secs(2)).await;
        assert!(
            rx.try_recv().is_ok(),
            "正常 drain 不应中止已按时完成的任务"
        );
    }

    /// 正常收尾后 guard 必须 disarm（armed=false），否则 Drop 仍会 abort 句柄。
    #[tokio::test]
    async fn disarmed_abort_guard_does_not_abort() {
        let (tx, mut rx) = tokio::sync::oneshot::channel::<()>();
        let handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(200)).await;
            let _ = tx.send(());
        });
        drop(AbortAllOnDrop {
            handles: vec![handle.abort_handle()],
            armed: false,
        });
        tokio::time::sleep(Duration::from_millis(300)).await;
        assert!(
            rx.try_recv().is_ok(),
            "armed=false 的 guard 不得中止任务（正常 drain 分支）"
        );
    }
}
