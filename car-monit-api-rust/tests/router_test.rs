// 路由装配测试：不依赖 GaussDB / Redis / Kafka / ES。
// 目的：把「24 个 Controller → 85 条有效端点」的路由清单固化成断言，
// 防止迁移时漏挂某个 Controller（Spring 注解扫描不会漏，Rust 显式注册会）。
// 对应 Java: router_test ↔ @SpringBootTest + MockMvc 的轻量替代。

use std::sync::atomic::AtomicBool;

use axum::body::Body;
use axum::http::Request;
use std::sync::Arc;
use tower::ServiceExt;

use car_monit_api_rust::config::Config;
use car_monit_api_rust::db::Db;
use car_monit_api_rust::es::EsClient;
use car_monit_api_rust::mq::Bus;
use car_monit_api_rust::repo::*;
use car_monit_api_rust::services::consistency::ConsistencyService;
use car_monit_api_rust::services::delay_monitor::DelayMonitorService;
use car_monit_api_rust::services::dict::DictService;
use car_monit_api_rust::services::export::ExportService;
use car_monit_api_rust::services::large::LargeScaleQueryService;
use car_monit_api_rust::services::loss_detection::LossDetectionService;
use car_monit_api_rust::services::multisource::MultiSourceService;
use car_monit_api_rust::services::progressive::ProgressiveService;
use car_monit_api_rust::services::query::QueryService;
use car_monit_api_rust::services::reliability::ReliabilityService;
use car_monit_api_rust::services::sync::SyncService;
use car_monit_api_rust::services::sysutil::SysUtilService;
use car_monit_api_rust::services::trail::TrailAggregationService;
use car_monit_api_rust::state::AppState;

fn build_state() -> Arc<AppState> {
    let cfg = Arc::new(Config::load(Some("config/application.yaml")).expect("加载测试配置"));
    let db = Db::lazy(cfg.master()).expect("惰性连接池");
    let es = Some(EsClient::new(&cfg.elasticsearch).expect("ES 客户端"));

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

    let dict = DictService::new(
        location_dict.clone(),
        gantry_ip.clone(),
        gantry.clone(),
        toll_station_ip.clone(),
        toll.clone(),
        section.clone(),
        None,
    );
    let query = QueryService::new(
        es.clone(),
        db.clone(),
        cfg.optimization.clone(),
        cfg.elasticsearch.clone(),
    );
    let large = LargeScaleQueryService::new(es.clone(), query.clone(), cfg.optimization.clone());
    let export = ExportService::new(es.clone(), query.clone(), cfg.optimization.clone());
    let progressive = ProgressiveService::new(
        &cfg.optimization,
        snapshot_flow.clone(),
        fee_records.clone(),
        trail_fitting.clone(),
        None,
        es.clone(),
    );
    let sync = Arc::new(SyncService::new(
        es.clone(),
        None,
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
        Bus::Noop,
        None,
        kafka_record.clone(),
        cfg.reliability.clone(),
    ));
    let loss = Arc::new(LossDetectionService::new(
        snapshot_flow.clone(),
        None,
        reliability.clone(),
        cfg.detection.clone(),
    ));
    let delay = Arc::new(DelayMonitorService::new(None, cfg.monitoring.clone()));
    let multisource = MultiSourceService::new(None);
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
        None,
        cfg.app.env.clone(),
    ));

    Arc::new(AppState {
        cfg,
        db,
        cache: None,
        es,
        bus: Bus::Noop,
        fwqjcxx,
        sfsjcxx,
        sfzjcxx,
        fwqclls,
        fee_gantry,
        fee_records,
        fee_station_enter,
        fee_station_exit,
        snapshot_flow,
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
        kafka_record,
        dict: Some(dict),
        query,
        large,
        export,
        progressive,
        sync,
        consistency,
        reliability,
        loss_detection: loss,
        delay_monitor: delay,
        multisource,
        trail,
        sysutil,
        consumer_started: Arc::new(AtomicBool::new(false)),
    })
}

#[tokio::test]
async fn router_assembly_does_not_conflict() {
    // axum 的 Router::route 在静态段与参数段冲突时会 panic；
    // 这条断言保证 24 个 Controller 的路由可以同时挂载。
    let state = build_state();
    let _router = car_monit_api_rust::router::build(state);
}

#[test]
fn all_java_routes_are_registered() {
    let routes = car_monit_api_rust::router::registered_routes();
    assert!(routes.len() >= 15, "关键路由清单不应为空");

    // 抽查最容易被漏掉的路径：静态段与 :id 同级、以及 {ds} 通配与 /export/status 并存
    let paths: Vec<&str> = routes.iter().map(|(_, p)| *p).collect();
    for required in [
        "/base/fwqjcxx/list",
        "/base/snapshotflow/list",
        "/base/feerecords/listToExport",
        "/base/sysutilTest/syncBaseInfo",
        "/api/v1/large/snapshot",
        "/api/v1/unified/{ds}/list",
        "/progressive/scale-level",
    ] {
        assert!(paths.contains(&required), "缺少路由: {}", required);
    }
}

#[test]
fn scheduler_cron_specs_are_valid() {
    car_monit_api_rust::router::validate_scheduler_specs().expect("Quartz 6 段 cron 应全部可解析");
}

#[test]
fn java_api_inventory_is_85_endpoints() {
    // 由 Java controller 注解自动抽取的清单（见 router.rs:JAVA_API_INVENTORY）
    assert_eq!(
        car_monit_api_rust::router::JAVA_API_INVENTORY.len(),
        85,
        "Java 侧有效端点应为 85 条（含 SysTest 的 12 个 501 端点）"
    );
    assert_eq!(car_monit_api_rust::router::registered_routes().len(), 85);
}

#[tokio::test]
async fn healthz_over_http_returns_up() {
    // 真正的 HTTP 层集成测试：经过中间件、路由、响应序列化；不依赖数据库。
    let router = car_monit_api_rust::router::build(build_state());
    let resp = router
        .oneshot(
            Request::builder()
                .uri("/healthz")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), 200);
}

#[tokio::test]
async fn unknown_path_returns_spring_error() {
    let router = car_monit_api_rust::router::build(build_state());
    let resp = router
        .oneshot(
            Request::builder()
                .uri("/not-exist")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), 404);
    let bytes = http_body_util::BodyExt::collect(resp.into_body())
        .await
        .unwrap()
        .to_bytes();
    let v: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(v["status"], 404);
    assert_eq!(v["error"], "Not Found");
    assert_eq!(v["path"], "/not-exist");
}
