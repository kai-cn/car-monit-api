// 来源: pro-business-api/src/main/java/com/ruoyi/EcBusinessApiApplication.java
// 职责: 进程入口与组合根（composition root）。
//
// DIFF: Spring 用 @SpringBootApplication + 组件扫描装配全部 Bean；Rust 没有容器，
// 这里逐行显式构造依赖并注入 AppState —— 依赖缺失 = 编译失败，而不是启动后 NPE。
// 装配顺序与 Java Bean 依赖图一致：配置 → 数据源 → 缓存 → 消息总线 → 仓储 → 服务 → 路由。

use std::future::IntoFuture;
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::watch;
use tracing::{error, info, warn};

use car_monit_api_rust::cache::Cache;
use car_monit_api_rust::config::Config;
use car_monit_api_rust::db::Db;
use car_monit_api_rust::es::EsClient;
use car_monit_api_rust::mq::Bus;
use car_monit_api_rust::repo::*;
use car_monit_api_rust::services::consistency::ConsistencyService;
use car_monit_api_rust::services::consumer::SnapshotFlowConsumer;
use car_monit_api_rust::services::delay_monitor::DelayMonitorService;
use car_monit_api_rust::services::dict::DictService;
use car_monit_api_rust::services::export::ExportService;
use car_monit_api_rust::services::large::LargeScaleQueryService;
use car_monit_api_rust::services::loss_detection::LossDetectionService;
use car_monit_api_rust::services::multisource::MultiSourceService;
use car_monit_api_rust::services::producer::KafkaProducerService;
use car_monit_api_rust::services::progressive::ProgressiveService;
use car_monit_api_rust::services::query::QueryService;
use car_monit_api_rust::services::reliability::ReliabilityService;
use car_monit_api_rust::services::sync::SyncService;
use car_monit_api_rust::services::sysutil::SysUtilService;
use car_monit_api_rust::services::trail::TrailAggregationService;
use car_monit_api_rust::state::AppState;

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--version" || a == "-version") {
        println!("car-monit-api-rust 1.0.0");
        return;
    }
    let config_path = args
        .iter()
        .position(|a| a == "--config" || a == "-config")
        .and_then(|i| args.get(i + 1))
        .map(|s| s.as_str());

    let cfg = match Config::load(config_path) {
        Ok(c) => Arc::new(c),
        Err(e) => {
            eprintln!("配置加载失败: {}", e);
            std::process::exit(1);
        }
    };
    init_tracing(&cfg);

    // 配置自检：不连接任何外部组件，验证配置可解析 + 21 个 cron 可解析。
    // 用法: cargo run -- --check-config
    if args.iter().any(|a| a == "--check-config") {
        match car_monit_api_rust::router::validate_scheduler_specs() {
            Ok(()) => {
                println!(
                    "CONFIG_OK port={} context_path={} db={} redis={} kafka={} es={} cron_ok=true",
                    cfg.server.port,
                    cfg.server.context_path,
                    cfg.master().url,
                    cfg.redis.addr(),
                    cfg.kafka.bootstrap_servers,
                    cfg.elasticsearch.base_url()
                );
                return;
            }
            Err(e) => {
                eprintln!("CRON_INVALID {}", e);
                std::process::exit(1);
            }
        }
    }

    info!(
        version = "1.0.0",
        config = config_path.unwrap_or("config/application.yaml"),
        env = %cfg.app.env,
        "开始装配应用"
    );

    let db = match Db::connect(cfg.master()).await {
        Ok(db) => db,
        Err(e) => {
            error!(err = %e, "GaussDB 连接失败");
            std::process::exit(1);
        }
    };
    info!(max_open = cfg.master().max_open_conns, "GaussDB 连接已建立");

    // PARITY: Spring 的 Redis 是懒连接；Cache 内部按需重连，连接失败不影响进程启动，
    // 但 /readyz 会通过 ping() 反映真实状态。
    let cache = match Cache::connect(&cfg.redis).await {
        Ok(c) => {
            if c.ping().await.is_ok() {
                info!(addr = %cfg.redis.addr(), db = cfg.redis.database, "Redis 连接已建立");
            } else {
                warn!(addr = %cfg.redis.addr(), "Redis 暂不可用，将在后续请求中自动重连");
            }
            Some(c)
        }
        Err(e) => {
            warn!(err = %e, "Redis 客户端创建失败，缓存相关功能降级");
            None
        }
    };

    let es = match EsClient::new(&cfg.elasticsearch) {
        Ok(c) => {
            info!(
                base_url = %cfg.elasticsearch.base_url(),
                snapshot = %cfg.elasticsearch.index.snapshot,
                fee = %cfg.elasticsearch.index.fee,
                trail = %cfg.elasticsearch.index.trail,
                "Elasticsearch 客户端已创建"
            );
            Some(c)
        }
        Err(e) => {
            warn!(err = %e, "Elasticsearch 客户端创建失败，ES 相关接口将返回错误");
            None
        }
    };

    // 对应 Java EsIndexManageService 的 @PostConstruct：ILM 幂等创建 + auto-create 时补索引结构。
    // 放后台执行，避免 ES 不可用时拖慢启动；失败重试 3 次（5s/15s 退避）后升级为 error。
    if let Some(client) = &es {
        let client = client.clone();
        let es_cfg = cfg.elasticsearch.clone();
        tokio::spawn(async move {
            let mut last_problems: Vec<String> = Vec::new();
            for attempt in 1..=3u32 {
                let c = client.clone();
                let ec = es_cfg.clone();
                match tokio::time::timeout(Duration::from_secs(15), async move {
                    c.ensure_indices(&ec).await
                })
                .await
                {
                    Ok(problems) if problems.is_empty() => {
                        info!(attempt, "[ES] 索引结构与 ILM 已就绪");
                        return;
                    }
                    Ok(problems) => last_problems = problems,
                    Err(_) => {
                        last_problems = vec!["ensure_indices 超时（15s）".to_string()];
                    }
                }
                if attempt < 3 {
                    let backoff = Duration::from_secs(if attempt == 1 { 5 } else { 15 });
                    warn!(
                        attempt,
                        backoff_secs = backoff.as_secs(),
                        "ES 索引初始化未完成，稍后重试"
                    );
                    tokio::time::sleep(backoff).await;
                }
            }
            for p in last_problems {
                error!(
                    problem = %p,
                    "ES 索引/ILM 初始化失败（已重试 3 次），请执行 tools/es-rebuild-snapshot-flow.sh"
                );
            }
        });
    }

    let bus = match Bus::new(&cfg.kafka, &cfg.pulsar) {
        Ok(b) => b,
        Err(e) => {
            error!(err = %e, "消息总线初始化失败");
            std::process::exit(1);
        }
    };

    // ---- 19 张基础表 Repo ----
    let fwqjcxx = FwqjcxxRepo::new(db.clone());
    let sfsjcxx = SfsjcxxRepo::new(db.clone());
    let sfzjcxx = SfzjcxxRepo::new(db.clone());
    let fwqclls = FwqcllsRepo::new(db.clone());
    let fee_gantry = FeeGantryRepo::new(db.clone());
    let fee_records = FeeRecordsRepo::new(db.clone());
    let fee_station_enter = FeeStationEnterRepo::new(db.clone());
    let fee_station_exit = FeeStationExitRepo::new(db.clone());
    let snapshot_flow = SnapshotFlowRepo::new(db.clone());
    let prov_capture = ProvCaptureRepo::new(db.clone());
    let station_capture = StationCaptureRepo::new(db.clone());
    let gantry = GantryRepo::new(db.clone());
    let gantry_ip = GantryIpRepo::new(db.clone());
    let vehicle_weight = VehicleWeightRepo::new(db.clone());
    let section = SectionRepo::new(db.clone());
    let toll = TollRepo::new(db.clone());
    let toll_station_ip = TollStationIpRepo::new(db.clone());
    let org = OrgRepo::new(db.clone());
    let trail_tracks = TrailTracksRepo::new(db.clone());
    let location_dict = LocationDictRepo::new(db.clone());
    let trail_fitting = TrailFittingRepo::new(db.clone());
    let kafka_record = KafkaMessageRecordRepo::new(db.clone());

    // ---- 服务 ----
    let dict = DictService::new(
        location_dict.clone(),
        gantry_ip.clone(),
        gantry.clone(),
        toll_station_ip.clone(),
        toll.clone(),
        section.clone(),
        cache.clone(),
    );

    let query_svc = QueryService::new(
        es.clone(),
        db.clone(),
        cfg.optimization.clone(),
        cfg.elasticsearch.clone(),
    );
    let large = LargeScaleQueryService::new(
        es.clone(),
        query_svc.clone(),
        cfg.optimization.clone(),
        cache.clone(),
    );
    let export = ExportService::new(
        es.clone(),
        query_svc.clone(),
        cfg.optimization.clone(),
        cache.clone(),
    );
    let progressive = ProgressiveService::new(
        &cfg.optimization,
        snapshot_flow.clone(),
        fee_records.clone(),
        trail_fitting.clone(),
        cache.clone(),
        es.clone(),
    );
    let sync = Arc::new(SyncService::new(
        es.clone(),
        cache.clone(),
        cfg.elasticsearch.clone(),
        cfg.sync.clone(),
        snapshot_flow.clone(),
        fee_records.clone(),
        trail_fitting.clone(),
    ));
    let consistency = ConsistencyService::new(
        es.clone(),
        snapshot_flow.clone(),
        fee_records.clone(),
        trail_fitting.clone(),
        sync.clone(),
        cfg.consistency.reconcile.clone(),
    );
    let reliability = Arc::new(ReliabilityService::new(
        bus.clone(),
        cache.clone(),
        kafka_record.clone(),
        cfg.reliability.clone(),
    ));
    let loss = Arc::new(LossDetectionService::new(
        snapshot_flow.clone(),
        cache.clone(),
        reliability.clone(),
        cfg.detection.clone(),
    ));
    let delay = Arc::new(DelayMonitorService::new(
        cache.clone(),
        cfg.monitoring.clone(),
    ));
    loss.init();
    delay.init();
    let multisource = MultiSourceService::new(cache.clone());
    let trail = TrailAggregationService::new(Some(dict.clone()));
    let sysutil = Arc::new(SysUtilService::new(
        trail_tracks.clone(),
        vehicle_weight.clone(),
        snapshot_flow.clone(),
        prov_capture.clone(),
        fwqclls.clone(),
        station_capture.clone(),
        fee_records.clone(),
        fee_station_enter.clone(),
        fee_station_exit.clone(),
        Some(dict.clone()),
        cache.clone(),
        cfg.app.env.clone(),
    ));

    let consumer_state = car_monit_api_rust::mq::ConsumerState::default();
    let state = Arc::new(AppState {
        cfg: cfg.clone(),
        db: db.clone(),
        cache: cache.clone(),
        es: es.clone(),
        bus: bus.clone(),
        fwqjcxx,
        sfsjcxx,
        sfzjcxx,
        fwqclls,
        fee_gantry,
        fee_records: fee_records.clone(),
        fee_station_enter,
        fee_station_exit,
        snapshot_flow: snapshot_flow.clone(),
        prov_capture,
        station_capture,
        gantry,
        gantry_ip,
        vehicle_weight,
        section,
        toll,
        toll_station_ip,
        org,
        trail_tracks,
        location_dict,
        trail_fitting,
        kafka_record: kafka_record.clone(),
        dict: Some(dict.clone()),
        query: query_svc,
        large,
        export,
        progressive,
        sync: sync.clone(),
        consistency: consistency.clone(),
        reliability: reliability.clone(),
        loss_detection: loss.clone(),
        delay_monitor: delay.clone(),
        multisource: multisource.clone(),
        trail,
        sysutil: sysutil.clone(),
        consumer_state: consumer_state.clone(),
    });

    // ---- 后台任务（@PostConstruct / @Scheduled）----
    // 停机预算只在这里计算一次（clamp 5–300s），调度器与后续关闭阶段共用同一有效值。
    let shutdown_grace = Duration::from_secs(cfg.app.shutdown_grace_seconds.clamp(5, 300));
    // 部署校验：把决定多副本行为的开关打印出来，避免"以为开了严格模式其实没开"。
    info!(
        env = %cfg.app.env,
        consumer_enabled = cfg.app.consumer_enabled,
        enable_scheduler = cfg.app.enable_scheduler,
        scheduler_lease_required = cfg.app.scheduler_lease_required,
        shutdown_grace_seconds = shutdown_grace.as_secs(),
        "启动开关（scheduler_lease_required=true 表示多副本严格模式）"
    );
    let (stop_tx, stop_rx) = watch::channel(false);

    let mut consumer_handle: Option<tokio::task::JoinHandle<()>> = None;
    if cfg.app.consumer_enabled {
        let consumer = SnapshotFlowConsumer::new(
            snapshot_flow.clone(),
            es.clone(),
            cfg.elasticsearch.index.snapshot.clone(),
            cache.clone(),
            &cfg.pulsar,
        );
        // 由消费端在 subscribe 成功后置位，避免"进程起来了但订阅失败"时探针误报 UP。
        consumer_handle = consumer.start(bus.clone(), stop_rx.clone(), consumer_state.clone());
    } else {
        warn!("consumer-enabled=false，快照消费者不启动");
    }

    let producer = KafkaProducerService::new(
        bus.clone(),
        kafka_record,
        reliability,
        loss,
        delay,
        &cfg.kafka,
    );
    producer.start(stop_rx.clone());

    let mut scheduler_handle: Option<tokio::task::JoinHandle<()>> = None;
    if cfg.app.enable_scheduler {
        match car_monit_api_rust::scheduler::build(
            &cfg,
            Some(dict),
            sysutil,
            multisource,
            state.loss_detection.clone(),
            state.delay_monitor.clone(),
            state.reliability.clone(),
            Some(consistency),
            state.export.clone(),
            state.large.clone(),
        ) {
            Ok(scheduler) => {
                info!(
                    jobs = scheduler.count(),
                    disabled = scheduler.disabled_count(),
                    "定时任务调度器已就绪"
                );
                let instance_id = uuid::Uuid::new_v4().simple().to_string();
                scheduler_handle = Some(tokio::spawn(scheduler.run(
                    stop_rx.clone(),
                    cache.clone(),
                    instance_id,
                    cfg.app.scheduler_lease_required,
                    shutdown_grace,
                )));
            }
            Err(e) => warn!(err = %e, "定时任务登记失败，调度器不启动"),
        }
    }

    let router = car_monit_api_rust::router::build(state.clone());
    let addr = format!("0.0.0.0:{}", cfg.server.port);
    let listener = match tokio::net::TcpListener::bind(&addr).await {
        Ok(l) => l,
        Err(e) => {
            error!(addr = %addr, err = %e, "HTTP 端口监听失败");
            std::process::exit(1);
        }
    };
    info!(addr = %addr, context_path = %cfg.server.context_path, "HTTP 服务已启动");

    // 优雅停机的总预算从"收到信号"起算：HTTP 排空 → 消费端 → 调度器 → 导出 → DB。
    // 各阶段都从剩余预算里取；但调度器与 DB 关闭各保留 1s 最低尝试窗口，
    // 极端情况下总耗时可比 shutdown-grace-seconds 多约 2 秒（启动日志用实测耗时，
    // 不再用 saturating_sub 把超支掩盖成"恰好等于 grace"）。
    // 部署侧 terminationGracePeriodSeconds 必须比该值大（建议 +5s）。
    let grace = shutdown_grace;
    let signal_at: Arc<std::sync::Mutex<Option<std::time::Instant>>> =
        Arc::new(std::sync::Mutex::new(None));
    let (sig_tx, sig_rx) = tokio::sync::oneshot::channel::<()>();
    let signal_marker = signal_at.clone();
    let shutdown = async move {
        wait_for_shutdown_signal().await;
        if let Ok(mut g) = signal_marker.lock() {
            *g = Some(std::time::Instant::now());
        }
        info!(
            grace_seconds = grace.as_secs(),
            "收到退出信号，开始优雅关闭：HTTP 排空 → 消费 → 调度 → 导出 → 缓存/数据库"
        );
        let _ = sig_tx.send(());
        let _ = stop_tx.send(true);
    };

    // HTTP 排空：最多占用总预算的 60%，必须给消费端/调度器/导出/DB 留出时间。
    // 否则 HTTP 吃满 grace 后 remaining=0，调度器会被 timeout(0) 立即 abort，
    // 在途 job 变成 detach 继续写库。
    let http_budget = Duration::from_millis((grace.as_millis() as u64).saturating_mul(6) / 10);
    info!(
        http_drain_seconds = http_budget.as_secs(),
        total_grace_seconds = grace.as_secs(),
        "HTTP 排空预算（总预算的 60%）"
    );
    let serve = axum::serve(listener, router)
        .with_graceful_shutdown(shutdown)
        .into_future();
    tokio::pin!(serve);
    let http_deadline = async move {
        let _ = sig_rx.await;
        tokio::time::sleep(http_budget).await;
    };
    tokio::select! {
        r = &mut serve => {
            if let Err(e) = r {
                error!(err = %e, "HTTP 服务异常退出");
            }
        }
        _ = http_deadline => {
            warn!(
                http_drain_seconds = http_budget.as_secs(),
                "HTTP 排空超出预算，放弃剩余连接继续关闭资源"
            );
        }
    };

    // 剩余预算必须随耗时动态计算，否则前一段用掉的时间不会被扣除。
    let remaining = || {
        let used = signal_at
            .lock()
            .ok()
            .and_then(|g| *g)
            .map(|t| t.elapsed())
            .unwrap_or_default();
        grace.saturating_sub(used)
    };

    // 消费端：循环以 receive 超时 1s 为粒度检查 stop，给 3s（不超过剩余预算）自然退出。
    // 超时则 abort，并把状态标为 DOWN/错误，避免任务 detach 后仍显示 UP。
    if let Some(mut handle) = consumer_handle.take() {
        let budget = std::cmp::min(remaining(), Duration::from_secs(3));
        match tokio::time::timeout(budget, &mut handle).await {
            Ok(Ok(())) => info!("消费端已退出"),
            Ok(Err(e)) => {
                consumer_state.mark_error(&format!("消费任务异常退出: {}", e));
                consumer_state.mark_stopped();
                warn!(err = %e, "消费任务异常退出");
            }
            Err(_) => {
                warn!("消费端未在预算内退出，强制中止");
                handle.abort();
                // abort 只是请求取消；必须 join 等任务真正结束，避免后续关闭阶段
                // 与仍在清理中的消费任务并发（也避免任务脱离管理）。
                let _ = handle.await;
                consumer_state.mark_error("停机预算内未退出，已强制中止");
                consumer_state.mark_stopped();
            }
        }
    }

    // 调度器内部按 shutdown_grace/2（≤10s）做协作等待；这里再给至少 1s 收尾余量。
    if let Some(handle) = scheduler_handle.take() {
        let abort = handle.abort_handle();
        let budget = std::cmp::max(
            std::cmp::min(remaining(), Duration::from_secs(11)),
            Duration::from_secs(1),
        );
        match tokio::time::timeout(budget, handle).await {
            Ok(_) => info!("调度器已退出"),
            Err(_) => {
                warn!(
                    budget_seconds = budget.as_secs(),
                    "调度器未在预算内结束，强制中止（在途 job 由 JobHandle Drop 一并中止）"
                );
                abort.abort();
            }
        }
    }

    // 关闭顺序与 Go/Java 一致：HTTP → 调度器/消费者 → 导出 → Redis → GaussDB。
    // 导出/大查询在剩余预算内等待；close 超时会显式 abort 剩余任务（不再 detach），
    // 预算为 0 时 timeout(0) 立即 abort，避免带着仍在写库的任务去关闭 DB。
    let export_budget = remaining();
    if !state.export.close(export_budget).await {
        warn!(
            budget_ms = export_budget.as_millis() as u64,
            "导出任务未在停机预算内结束，已中止剩余任务"
        );
    }
    let large_budget = remaining();
    if !state.large.close(large_budget).await {
        warn!(
            budget_ms = large_budget.as_millis() as u64,
            "大查询导出任务未在停机预算内结束，已中止剩余任务"
        );
    }
    if let Some(c) = cache {
        if remaining() > Duration::from_secs(1) {
            let _ = c.ping().await;
        }
    }
    // PgPool::close 会等在途连接归还；外部依赖异常时可能长期挂起，
    // 取剩余预算且不超过 5s；即使预算耗尽也至少尝试 1s。
    let db_budget = std::cmp::max(
        std::cmp::min(remaining(), Duration::from_secs(5)),
        Duration::from_secs(1),
    );
    if tokio::time::timeout(db_budget, db.close()).await.is_err() {
        warn!("GaussDB 连接池关闭超时，放弃等待");
    }
    // 用真实起止时间统计，而不是 grace - remaining()：后者的剩余预算在最后阶段
    // 仍可能因 1s 最低窗口被超出，saturating_sub 会把超支低报成"恰好等于 grace"。
    let total_elapsed = signal_at
        .lock()
        .ok()
        .and_then(|g| *g)
        .map(|t| t.elapsed())
        .unwrap_or_default();
    info!(
        total_elapsed_ms = total_elapsed.as_millis() as u64,
        grace_ms = grace.as_millis() as u64,
        "应用已退出"
    );
}

/// 退出信号：Ctrl+C（全部平台）+ SIGTERM（Linux/K8s 滚动发布）。
async fn wait_for_shutdown_signal() {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{signal, SignalKind};
        let mut sigterm = match signal(SignalKind::terminate()) {
            Ok(s) => Some(s),
            Err(e) => {
                warn!(err = %e, "注册 SIGTERM 处理器失败，仅监听 Ctrl+C");
                None
            }
        };
        tokio::select! {
            r = tokio::signal::ctrl_c() => {
                if let Err(e) = r {
                    error!(err = %e, "监听 Ctrl+C 失败");
                } else {
                    info!("收到 SIGINT(Ctrl+C)");
                }
            }
            _ = async {
                match sigterm.as_mut() {
                    Some(s) => { s.recv().await; }
                    None => std::future::pending::<()>().await,
                }
            } => {
                info!("收到 SIGTERM");
            }
        }
    }
    #[cfg(not(unix))]
    {
        if let Err(e) = tokio::signal::ctrl_c().await {
            error!(err = %e, "监听退出信号失败");
        } else {
            info!("收到 Ctrl+C");
        }
    }
}

fn init_tracing(cfg: &Config) {
    use tracing_subscriber::prelude::*;
    let level = std::env::var("RUST_LOG").unwrap_or_else(|_| cfg.logging.level.clone());
    let filter = tracing_subscriber::EnvFilter::try_new(&level)
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info"));
    if cfg.logging.format.eq_ignore_ascii_case("json") {
        tracing_subscriber::registry()
            .with(filter)
            .with(tracing_subscriber::fmt::layer().json())
            .init();
    } else {
        tracing_subscriber::registry()
            .with(filter)
            .with(tracing_subscriber::fmt::layer())
            .init();
    }
}
