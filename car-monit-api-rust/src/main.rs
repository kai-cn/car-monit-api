// 来源: pro-business-api/src/main/java/com/ruoyi/EcBusinessApiApplication.java
// 职责: 进程入口与组合根（composition root）。
//
// DIFF: Spring 用 @SpringBootApplication + 组件扫描装配全部 Bean；Rust 没有容器，
// 这里逐行显式构造依赖并注入 AppState —— 依赖缺失 = 编译失败，而不是启动后 NPE。
// 装配顺序与 Java Bean 依赖图一致：配置 → 数据源 → 缓存 → 消息总线 → 仓储 → 服务 → 路由。

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

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

    // PARITY: Spring 的 Redis 是懒连接；这里连接失败只告警，避免缓存抖动导致进程起不来。
    let cache = match Cache::connect(&cfg.redis).await {
        Ok(c) => {
            info!(addr = %cfg.redis.addr(), db = cfg.redis.database, "Redis 连接已建立");
            Some(c)
        }
        Err(e) => {
            warn!(err = %e, "Redis 不可用，缓存相关功能降级");
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
    let large =
        LargeScaleQueryService::new(es.clone(), query_svc.clone(), cfg.optimization.clone());
    let export = ExportService::new(es.clone(), query_svc.clone(), cfg.optimization.clone());
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

    let consumer_started = Arc::new(AtomicBool::new(false));
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
        consumer_started: consumer_started.clone(),
    });

    // ---- 后台任务（@PostConstruct / @Scheduled）----
    let (stop_tx, stop_rx) = watch::channel(false);

    if cfg.app.consumer_enabled {
        let consumer = SnapshotFlowConsumer::new(
            snapshot_flow.clone(),
            es.clone(),
            cfg.elasticsearch.index.snapshot.clone(),
            cache.clone(),
            &cfg.pulsar,
        );
        if bus.is_active() {
            consumer_started.store(true, std::sync::atomic::Ordering::SeqCst);
        }
        consumer.start(bus.clone(), stop_rx.clone());
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
        ) {
            Ok(scheduler) => {
                info!(
                    jobs = scheduler.count(),
                    disabled = scheduler.disabled_count(),
                    "定时任务调度器已就绪"
                );
                tokio::spawn(scheduler.run(stop_rx.clone()));
            }
            Err(e) => warn!(err = %e, "定时任务登记失败，调度器不启动"),
        }
    }

    let router = car_monit_api_rust::router::build(state.clone());
    // Spring 的 AntPathMatcher 在「匹配路由之前」就合并连续斜杠、忽略结尾斜杠；
    // axum 的 Router::layer 只能包住已匹配的路由，所以这层必须套在整个 Router 外面。
    let app = tower::ServiceBuilder::new()
        .layer(axum::middleware::from_fn(
            car_monit_api_rust::middleware::spring_negotiation,
        ))
        .service(router);
    let addr = format!("0.0.0.0:{}", cfg.server.port);
    let listener = match tokio::net::TcpListener::bind(&addr).await {
        Ok(l) => l,
        Err(e) => {
            error!(addr = %addr, err = %e, "HTTP 端口监听失败");
            std::process::exit(1);
        }
    };
    info!(addr = %addr, context_path = %cfg.server.context_path, "HTTP 服务已启动");

    let shutdown = async move {
        if let Err(e) = tokio::signal::ctrl_c().await {
            error!(err = %e, "监听退出信号失败");
        }
        info!("收到退出信号，开始优雅关闭");
        let _ = stop_tx.send(true);
    };

    if let Err(e) = axum::serve(listener, tower::make::Shared::new(app))
        .with_graceful_shutdown(shutdown)
        .await
    {
        error!(err = %e, "HTTP 服务异常退出");
    }

    // 关闭顺序与 Go/Java 一致：HTTP → 调度器/消费者（已在 stop 信号后退出）→ 导出 → Redis → GaussDB
    state.export.close().await;
    state.large.close().await;
    if let Some(c) = cache {
        let _ = c.ping().await;
    }
    db.close().await;
    info!("应用已退出");
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
