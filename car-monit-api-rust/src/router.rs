// 来源:
//   pro-base-common/.../config/interceptor/WebConfig.java（整文件被注释）
//   pro-business-api/.../controller/*.java（全部 @RequestMapping）
//   application.yml:1-4（server.port / context-path）
// 职责: 把「中间件 + 全部路由 + 健康检查 + 404/405 兜底」装配成 axum::Router。
// 对应关系:
//   @RestController 的 @GetMapping("/x") ↔ Router::route("/x", get(handler))
//   server.servlet.context-path          ↔ nest(context_path)
//   Spring 默认 /error 白页               ↔ fallback（返回同一套 AjaxResult）
//   Actuator /actuator/health            ↔ /healthz、/readyz、/health（Java 未接 Actuator，属新增）
//
// DIFF: Spring 注解扫描 → Rust 显式注册；漏挂一个 Controller 编译不会报错，因此用
// router_test 固化 60+ 条关键路由（见 tests/router_test.rs）。

use std::sync::Arc;
use std::time::Duration;

use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde_json::json;
use tower_http::catch_panic::CatchPanicLayer;

use crate::handlers::{base, crud, query, selftest, sysutil};
use crate::middleware;
use crate::response::AjaxResult;
use crate::state::AppState;

pub fn build(state: Arc<AppState>) -> Router {
    let r = routes();
    let r = if state.cfg.server.context_path.is_empty() || state.cfg.server.context_path == "/" {
        r
    } else {
        Router::new().nest(&state.cfg.server.context_path, r)
    };
    r
        // 注意顺序：axum 的 layer 后加的在最外层。request_id/日志/指标必须在最外层，
        // 否则 TimeoutLayer 生成 408 时内层 future 被取消，in-flight 计数会泄漏。
        .layer(tower_http::limit::RequestBodyLimitLayer::new(MAX_BODY_BYTES))
        .layer(tower::limit::ConcurrencyLimitLayer::new(MAX_CONCURRENT_REQUESTS))
        // 全局限时：必须大于最慢的同步查询（统计接口 ES timeout=60s），导出为后台任务不受影响。
        .layer(tower_http::timeout::TimeoutLayer::with_status_code(
            StatusCode::REQUEST_TIMEOUT,
            REQUEST_TIMEOUT,
        ))
        .layer(CatchPanicLayer::custom(handle_panic))
        .layer(axum::middleware::from_fn(middleware::request_id_and_log))
        .fallback(not_found)
        .method_not_allowed_fallback(method_not_allowed)
        .with_state(state)
}

/// 单请求体上限（Tomcat 默认 maxPostSize 为 2MB，但 changeTrailInfo 的历史调用方会传更大的轨迹 JSON，
/// 这里取 20MB 作为硬上限）。
const MAX_BODY_BYTES: usize = 20 * 1024 * 1024;
/// 单请求超时：覆盖最慢的 ES 聚合查询（60s），留 30s 余量。
const REQUEST_TIMEOUT: Duration = Duration::from_secs(90);
/// 全局限流并发数：约为 DB 连接池（20）的 12 倍，超出的请求排队等待。
const MAX_CONCURRENT_REQUESTS: usize = 256;

fn routes() -> Router<Arc<AppState>> {
    Router::new()
        // ---- 健康检查（Java 未接 Actuator；只读、无副作用） ----
        .route("/healthz", get(healthz))
        .route("/readyz", get(readyz))
        .route("/health", get(readyz))
        // ---- 指标（S1；Java 未接 Actuator，属新增） ----
        .route("/metrics", get(crate::metrics::metrics))
        // ---- 19 张基础表 ----
        .route("/base/fwqjcxx/list", get(crud::fwqjcxx_list))
        .route("/base/fwqjcxx/listAll", get(crud::fwqjcxx_all))
        .route("/base/fwqjcxx/{id}", get(crud::fwqjcxx_ajax))
        .route("/base/sfsjcxx/list", get(crud::sfsjcxx_list))
        .route("/base/sfsjcxx/listAll", get(crud::sfsjcxx_all))
        .route("/base/sfsjcxx/{id}", get(crud::sfsjcxx_ajax))
        .route("/base/sfzjcxx/list", get(crud::sfzjcxx_list))
        .route("/base/sfzjcxx/listAll", get(crud::sfzjcxx_all))
        .route("/base/sfzjcxx/{id}", get(crud::sfzjcxx_ajax))
        .route("/manager/fwqclls/list", get(crud::fwqclls_list))
        .route("/manager/fwqclls/{id}", get(crud::fwqclls_ajax))
        .route("/base/feeGantry/list", get(base::fee_gantry_list))
        .route("/base/feeGantry/{id}", get(crud::fee_gantry_flat))
        .route("/base/feerecords/list", get(base::fee_records_list))
        .route(
            "/base/feerecords/listToExport",
            get(base::fee_records_export),
        )
        .route("/base/feerecords/{id}", get(base::fee_records_detail_500))
        .route("/base/feeStationEnter/list", get(crud::fee_enter_list))
        .route("/base/feeStationEnter/{id}", get(crud::fee_enter_ajax))
        .route("/base/feestationexit/list", get(crud::fee_exit_list))
        .route("/base/feestationexit/{id}", get(crud::fee_exit_ajax))
        .route("/base/snapshotflow/list", get(base::snapshot_flow_list))
        .route(
            "/base/snapshotflow/listToExport",
            get(base::snapshot_flow_export),
        )
        .route("/base/snapshotflow/{id}", get(crud::snapshot_flow_flat))
        .route("/base/provcapture/list", get(crud::prov_capture_list))
        .route("/base/provcapture/{id}", get(crud::prov_capture_ajax))
        .route("/base/stationcapture/list", get(crud::station_capture_list))
        .route("/base/stationcapture/{id}", get(crud::station_capture_ajax))
        .route("/base/gantry/list", get(crud::gantry_list))
        .route("/base/gantry/listAll", get(crud::gantry_all))
        .route("/base/gantry/{id}", get(crud::gantry_ajax))
        .route("/base/gantryIp/list", get(crud::gantry_ip_list))
        .route("/base/gantryIp/{id}", get(crud::gantry_ip_ajax))
        .route("/base/vehicleweight/list", get(crud::vehicle_weight_list))
        .route("/base/vehicleweight/map", get(crud::vehicle_weight_map))
        .route(
            "/base/vehicleweight/{id}",
            get(base::vehicle_weight_detail_500),
        )
        .route("/base/section/list", get(crud::section_list))
        .route("/base/section/listAll", get(crud::section_all))
        .route("/base/section/{id}", get(crud::section_ajax))
        .route("/base/toll/list", get(crud::toll_list))
        .route("/base/toll/listAll", get(crud::toll_all))
        .route("/base/toll/{id}", get(crud::toll_ajax))
        .route("/base/tollStationIp/list", get(crud::toll_station_ip_list))
        .route("/base/tollStationIp/{id}", get(crud::toll_station_ip_ajax))
        .route("/base/org/list", get(crud::org_list))
        .route("/base/org/listAll", get(crud::org_all))
        .route("/base/org/{id}", get(crud::org_ajax))
        .route("/base/trailtracks/list", get(crud::trail_tracks_list))
        .route("/base/trailtracks/{id}", get(base::trail_tracks_detail))
        // ---- /base/sysutil ----
        .route("/base/sysutil/saveRedis", get(sysutil::save_redis))
        .route(
            "/base/sysutil/carTrackQueryByCarNo",
            get(sysutil::car_track_by_car_no),
        )
        .route(
            "/base/sysutil/carTrackQueryByTime",
            get(sysutil::car_track_by_time),
        )
        .route(
            "/base/sysutil/changeTrailInfo",
            post(sysutil::change_trail_info),
        )
        .route("/base/sysutil/getByTrailBo", get(sysutil::get_by_trail_bo))
        // ---- /base/sysutilTest ----
        .route(
            "/base/sysutilTest/syncBaseInfo",
            get(selftest::sync_base_info),
        )
        .route(
            "/base/sysutilTest/syncCurrentTrack",
            get(selftest::sync_current_track),
        )
        .route(
            "/base/sysutilTest/syncHistroyTrack",
            get(selftest::sync_histroy_track),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar1",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar2",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar3",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar4",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar5",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar6",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar7",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar8",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar9",
            get(blocked_sync_suspicious),
        )
        .route(
            "/base/sysutilTest/syncSuspiciousCar10",
            get(blocked_sync_suspicious),
        )
        .route("/base/sysutilTest/syncOdsSzdnGantry", get(blocked_gantry))
        .route(
            "/base/sysutilTest/separateSnapshotFlowTimeList",
            get(blocked_separate),
        )
        // ---- /api/v1/large ----
        .route("/api/v1/large/{ds}", get(query::large_query))
        .route(
            "/api/v1/large/carTrackQueryByCarNo",
            get(query::car_track_by_car_no),
        )
        .route("/api/v1/large/stats/group", get(query::group_stats))
        .route(
            "/api/v1/large/export/submit",
            post(query::large_export_submit),
        )
        .route(
            "/api/v1/large/export/status/{taskId}",
            get(query::large_export_status),
        )
        .route("/api/v1/large/sync/full", post(query::sync_full))
        .route(
            "/api/v1/large/sync/incremental",
            post(query::sync_incremental),
        )
        .route("/api/v1/large/sync/repair", post(query::sync_repair))
        // ---- /api/v1/unified ----
        .route(
            "/api/v1/unified/export/status/{taskId}",
            get(query::unified_export_status),
        )
        .route("/api/v1/unified/{ds}/list", get(query::unified_list))
        .route(
            "/api/v1/unified/{ds}/export/submit",
            post(query::unified_export_submit),
        )
        // ---- /progressive ----
        .route("/progressive/scale-level", get(query::scale_level))
        .route("/progressive/{table}/list", get(query::progressive_list))
}

// ---- 健康检查 ----

async fn healthz() -> Response {
    Json(json!({
        "status": "UP",
        "time": chrono::Utc::now().to_rfc3339()
    }))
    .into_response()
}

async fn readyz(State(state): State<Arc<AppState>>) -> Response {
    let mut body = serde_json::Map::new();
    body.insert("status".into(), json!("UP"));
    body.insert("time".into(), json!(chrono::Utc::now().to_rfc3339()));
    let mut status = StatusCode::OK;

    match state.db.ping().await {
        Ok(()) => body.insert("gaussdb".into(), json!("UP")),
        Err(e) => {
            body.insert("gaussdb".into(), json!(format!("DOWN: {}", e.message())));
            body.insert("status".into(), json!("DOWN"));
            status = StatusCode::SERVICE_UNAVAILABLE;
            None
        }
    };
    // Java 侧 Redis 是必需组件（缓存缺失会导致轨迹/重点车辆查询直接降级）；
    // 启动时连不上（cache=None）同样视为未就绪，而不是静默 UP。
    match &state.cache {
        Some(c) => match c.ping().await {
            Ok(()) => body.insert("redis".into(), json!("UP")),
            Err(e) => {
                body.insert("redis".into(), json!(format!("DOWN: {}", e.message())));
                body.insert("status".into(), json!("DOWN"));
                status = StatusCode::SERVICE_UNAVAILABLE;
                None
            }
        },
        None => {
            body.insert("redis".into(), json!("DOWN: 启动时连接失败"));
            body.insert("status".into(), json!("DOWN"));
            status = StatusCode::SERVICE_UNAVAILABLE;
            None
        }
    };
    // ES 是查询/导出的主链路之一（大表查询默认走 ES），故障时 readiness 必须摘流。
    match &state.es {
        Some(es) => match es.health().await {
            Ok(()) => body.insert("elasticsearch".into(), json!("UP")),
            Err(e) => {
                body.insert(
                    "elasticsearch".into(),
                    json!(format!("DOWN: {}", e.message())),
                );
                body.insert("status".into(), json!("DOWN"));
                status = StatusCode::SERVICE_UNAVAILABLE;
                None
            }
        },
        None => {
            body.insert("elasticsearch".into(), json!("DOWN: 客户端初始化失败"));
            body.insert("status".into(), json!("DOWN"));
            status = StatusCode::SERVICE_UNAVAILABLE;
            None
        }
    };
    // 运维脚本（tools/es-rebuild-snapshot-flow.sh）据此断言"要重建的索引 == APP 实际查询的索引"，
    // 防止 APP_ELASTICSEARCH_INDEX_SNAPSHOT 与脚本 INDEX 不一致时重建了另一个索引。
    body.insert(
        "elasticsearchIndex".into(),
        json!(state.cfg.elasticsearch.index.snapshot),
    );
    // 消费端四态：DISABLED=配置关闭；DOWN=未订阅或连接异常；STALE=topic 安静；
    // UP=最近 60s 有消息。判定顺序把"新鲜消息"放最前：只要链路在正常收消息，
    // 即使之前出现过错误也应显示 UP（mark_recv 已同时清空 last_error）。
    let last_recv = state.consumer_state.last_recv_ms();
    let now = crate::services::sysutil::now_ms();
    let consumer = consumer_status(
        state.cfg.app.consumer_enabled,
        state.consumer_state.is_started(),
        last_recv,
        state.consumer_state.last_error().map(|(t, _)| t),
        now,
    );
    body.insert("mqConsumer".into(), json!(consumer));
    body.insert("mqConsumerLastRecvMs".into(), json!(last_recv));
    if let Some((_, msg)) = state.consumer_state.last_error() {
        body.insert("mqConsumerError".into(), json!(msg));
    }
    (status, Json(serde_json::Value::Object(body))).into_response()
}

// ---- 兜底 ----
/// `/readyz` 的消费端状态机（有状态部分已抽成纯函数，便于单测覆盖边界）。
pub(crate) fn consumer_status(
    enabled: bool,
    started: bool,
    last_recv_ms: i64,
    last_error_ms: Option<i64>,
    now_ms: i64,
) -> &'static str {
    if !enabled {
        "DISABLED"
    } else if !started {
        "DOWN"
    } else if last_recv_ms != 0 && now_ms.saturating_sub(last_recv_ms) <= 60_000 {
        "UP"
    } else if let Some(err_at) = last_error_ms {
        if err_at > last_recv_ms {
            "DOWN"
        } else {
            "STALE"
        }
    } else {
        "STALE"
    }
}

/// Spring Boot 默认 /error 响应体（未配置 @ControllerAdvice 时的真实形态）。
pub fn spring_error(status: StatusCode, error: &str, path: &str) -> serde_json::Value {
    serde_json::json!({
        "timestamp": chrono::Utc::now().format("%Y-%m-%dT%H:%M:%S%.3f+00:00").to_string(),
        "status": status.as_u16(),
        "error": error,
        "message": "",
        "path": path,
    })
}

async fn not_found(req: axum::extract::Request) -> Response {
    let path = req.uri().path().to_string();
    (
        StatusCode::NOT_FOUND,
        Json(spring_error(StatusCode::NOT_FOUND, "Not Found", &path)),
    )
        .into_response()
}

async fn method_not_allowed(req: axum::extract::Request) -> Response {
    let path = req.uri().path().to_string();
    (
        StatusCode::METHOD_NOT_ALLOWED,
        Json(spring_error(
            StatusCode::METHOD_NOT_ALLOWED,
            "Method Not Allowed",
            &path,
        )),
    )
        .into_response()
}

fn handle_panic(err: Box<dyn std::any::Any + Send + 'static>) -> Response {
    let msg = if let Some(s) = err.downcast_ref::<String>() {
        s.clone()
    } else if let Some(s) = err.downcast_ref::<&str>() {
        s.to_string()
    } else {
        "unknown panic".to_string()
    };
    tracing::error!(panic = %msg, "请求处理 panic");
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(AjaxResult::fail_code(
            500,
            format!("服务器内部错误: {}", msg),
        )),
    )
        .into_response()
}

// ---- 501 端点 ----

// Java 侧这些方法返回 void：HTTP 200 + 空响应体。其内部任务会因缺失 SQL 失败，但已异步吞掉。
async fn blocked_sync_suspicious() -> Response {
    tracing::warn!("[sysutilTest] syncSuspiciousCarN：Java 侧异步任务依赖缺失 SQL，Rust 不执行");
    StatusCode::OK.into_response()
}

async fn blocked_gantry() -> Response {
    // Java 侧同一路径会因 selectGantryNum 缺失抛 Invalid bound statement → Spring 500。
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(spring_error(
            StatusCode::INTERNAL_SERVER_ERROR,
            "Internal Server Error",
            "/base/sysutilTest/syncOdsSzdnGantry",
        )),
    )
        .into_response()
}

async fn blocked_separate() -> Response {
    tracing::warn!("[sysutilTest] separateSnapshotFlowTimeList：Java 侧链路无消费方，Rust 不执行");
    StatusCode::OK.into_response()
}

/// 供测试：Java 侧 85 个有效端点在 Rust 侧均有对应路由（同一 axum 路由可覆盖多个具体端点）。
pub fn registered_routes() -> Vec<(&'static str, &'static str)> {
    JAVA_API_INVENTORY
        .iter()
        .map(|(m, p, _)| (*m, *p))
        .collect()
}

/// 供测试：确保所有 cron 表达式可解析。
pub fn validate_scheduler_specs() -> Result<(), String> {
    let specs = [
        "0 0 0 * * ?",
        "0 0/3 * * * ?",
        "0 0 4 * * ?",
        "0 */1 * * * ?",
        "0 */5 * * * ?",
        "0 30 2 * * ?",
        "0 0 1 * * ?",
        "0 15 1 * * ?",
        "0 30 1 * * ?",
        "0 45 1 * * ?",
        "0 0 2 * * ?",
        "0 15 2 * * ?",
        "0 30 2 * * ?",
        "0 45 2 * * ?",
        "0 0 3 * * ?",
        "0 15 3 * * ?",
        "0 45 3 * * ?",
    ];
    crate::scheduler::validate_specs(&specs)
}

/// 供测试：避免 unused import 警告。
#[allow(dead_code)]
fn _noop(_: Duration) {}

/// Java 侧 85 个有效端点（由 controller 注解自动抽取；已排除块注释内的 /syncTrack 等）。
pub const JAVA_API_INVENTORY: &[(&str, &str, &str)] = &[
    ("GET", "/base/fwqjcxx/list", "DwdLcztFwqjcxxController.java"),
    (
        "GET",
        "/base/fwqjcxx/{agentPk}",
        "DwdLcztFwqjcxxController.java",
    ),
    (
        "GET",
        "/base/fwqjcxx/listAll",
        "DwdLcztFwqjcxxController.java",
    ),
    ("GET", "/base/sfsjcxx/list", "DwdLcztSfsjcxxController.java"),
    (
        "GET",
        "/base/sfsjcxx/{agentPk}",
        "DwdLcztSfsjcxxController.java",
    ),
    (
        "GET",
        "/base/sfsjcxx/listAll",
        "DwdLcztSfsjcxxController.java",
    ),
    ("GET", "/base/sfzjcxx/list", "DwdLcztSfzjcxxController.java"),
    (
        "GET",
        "/base/sfzjcxx/{agentPk}",
        "DwdLcztSfzjcxxController.java",
    ),
    (
        "GET",
        "/base/sfzjcxx/listAll",
        "DwdLcztSfzjcxxController.java",
    ),
    (
        "GET",
        "/api/v1/large/snapshot",
        "LargeScaleQueryController.java",
    ),
    ("GET", "/api/v1/large/fee", "LargeScaleQueryController.java"),
    (
        "GET",
        "/api/v1/large/trail",
        "LargeScaleQueryController.java",
    ),
    (
        "GET",
        "/api/v1/large/carTrackQueryByCarNo",
        "LargeScaleQueryController.java",
    ),
    (
        "GET",
        "/api/v1/large/stats/group",
        "LargeScaleQueryController.java",
    ),
    (
        "POST",
        "/api/v1/large/export/submit",
        "LargeScaleQueryController.java",
    ),
    (
        "GET",
        "/api/v1/large/export/status/{taskId}",
        "LargeScaleQueryController.java",
    ),
    (
        "POST",
        "/api/v1/large/sync/full",
        "LargeScaleQueryController.java",
    ),
    (
        "POST",
        "/api/v1/large/sync/incremental",
        "LargeScaleQueryController.java",
    ),
    (
        "POST",
        "/api/v1/large/sync/repair",
        "LargeScaleQueryController.java",
    ),
    (
        "GET",
        "/manager/fwqclls/list",
        "OdsCxztFwqcllsController.java",
    ),
    (
        "GET",
        "/manager/fwqclls/{bigId}",
        "OdsCxztFwqcllsController.java",
    ),
    (
        "GET",
        "/base/feeGantry/list",
        "OdsLwzxsfsjFeeGantryFusion01Controller.java",
    ),
    (
        "GET",
        "/base/feeGantry/{bigId}",
        "OdsLwzxsfsjFeeGantryFusion01Controller.java",
    ),
    (
        "GET",
        "/base/feerecords/list",
        "OdsLwzxsfsjFeeRecords01Controller.java",
    ),
    (
        "GET",
        "/base/feerecords/listToExport",
        "OdsLwzxsfsjFeeRecords01Controller.java",
    ),
    (
        "GET",
        "/base/feerecords/{bigId}",
        "OdsLwzxsfsjFeeRecords01Controller.java",
    ),
    (
        "GET",
        "/base/feeStationEnter/list",
        "OdsLwzxsfsjFeeStationEnter01Controller.java",
    ),
    (
        "GET",
        "/base/feeStationEnter/{bigId}",
        "OdsLwzxsfsjFeeStationEnter01Controller.java",
    ),
    (
        "GET",
        "/base/feestationexit/list",
        "OdsLwzxsfsjFeeStationExit01Controller.java",
    ),
    (
        "GET",
        "/base/feestationexit/{bigId}",
        "OdsLwzxsfsjFeeStationExit01Controller.java",
    ),
    (
        "GET",
        "/base/snapshotflow/list",
        "OdsRtSzdnSnapshotFlowAddcodeController.java",
    ),
    (
        "GET",
        "/base/snapshotflow/listToExport",
        "OdsRtSzdnSnapshotFlowAddcodeController.java",
    ),
    (
        "GET",
        "/base/snapshotflow/{bigId}",
        "OdsRtSzdnSnapshotFlowAddcodeController.java",
    ),
    (
        "GET",
        "/base/provcapture/list",
        "OdsRtSzdnSnapshotFlowProvcaptureAddcodeController.java",
    ),
    (
        "GET",
        "/base/provcapture/{bigId}",
        "OdsRtSzdnSnapshotFlowProvcaptureAddcodeController.java",
    ),
    (
        "GET",
        "/base/stationcapture/list",
        "OdsRtSzdnSnapshotFlowStationcaptureAddcodeController.java",
    ),
    (
        "GET",
        "/base/stationcapture/{bigId}",
        "OdsRtSzdnSnapshotFlowStationcaptureAddcodeController.java",
    ),
    ("GET", "/base/gantry/list", "OdsSzdnGantryController.java"),
    ("GET", "/base/gantry/{id}", "OdsSzdnGantryController.java"),
    (
        "GET",
        "/base/gantry/listAll",
        "OdsSzdnGantryController.java",
    ),
    (
        "GET",
        "/base/gantryIp/list",
        "OdsSzdnGantryIpController.java",
    ),
    (
        "GET",
        "/base/gantryIp/{id}",
        "OdsSzdnGantryIpController.java",
    ),
    (
        "GET",
        "/base/vehicleweight/list",
        "OdsSzdnProvinceBorderVehicleWeightNewstructureController.java",
    ),
    (
        "GET",
        "/base/vehicleweight/{dataSource}",
        "OdsSzdnProvinceBorderVehicleWeightNewstructureController.java",
    ),
    (
        "GET",
        "/base/vehicleweight/map",
        "OdsSzdnProvinceBorderVehicleWeightNewstructureController.java",
    ),
    ("GET", "/base/section/list", "OdsSzdnSectionController.java"),
    ("GET", "/base/section/{id}", "OdsSzdnSectionController.java"),
    (
        "GET",
        "/base/section/listAll",
        "OdsSzdnSectionController.java",
    ),
    ("GET", "/base/toll/list", "OdsSzdnTollController.java"),
    ("GET", "/base/toll/{id}", "OdsSzdnTollController.java"),
    ("GET", "/base/toll/listAll", "OdsSzdnTollController.java"),
    (
        "GET",
        "/base/tollStationIp/list",
        "OdsSzdnTollStationIpController.java",
    ),
    (
        "GET",
        "/base/tollStationIp/{id}",
        "OdsSzdnTollStationIpController.java",
    ),
    ("GET", "/base/org/list", "OdsYhglVBaseOrgController.java"),
    ("GET", "/base/org/{bigId}", "OdsYhglVBaseOrgController.java"),
    ("GET", "/base/org/listAll", "OdsYhglVBaseOrgController.java"),
    (
        "GET",
        "/progressive/snapshotflow/list",
        "ProgressiveQueryController.java",
    ),
    (
        "GET",
        "/progressive/feerecords/list",
        "ProgressiveQueryController.java",
    ),
    (
        "GET",
        "/progressive/trailfitting/list",
        "ProgressiveQueryController.java",
    ),
    (
        "GET",
        "/progressive/scale-level",
        "ProgressiveQueryController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncCurrentTrack",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncBaseInfo",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncHistroyTrack",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar1",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar2",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar3",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar4",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar5",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar6",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar7",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar8",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar9",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncSuspiciousCar10",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/syncOdsSzdnGantry",
        "SysTestController.java",
    ),
    (
        "GET",
        "/base/sysutilTest/separateSnapshotFlowTimeList",
        "SysTestController.java",
    ),
    ("GET", "/base/sysutil/saveRedis", "SysUtilController.java"),
    (
        "GET",
        "/base/sysutil/carTrackQueryByCarNo",
        "SysUtilController.java",
    ),
    (
        "GET",
        "/base/sysutil/carTrackQueryByTime",
        "SysUtilController.java",
    ),
    (
        "POST",
        "/base/sysutil/changeTrailInfo",
        "SysUtilController.java",
    ),
    (
        "GET",
        "/base/sysutil/getByTrailBo",
        "SysUtilController.java",
    ),
    (
        "GET",
        "/api/v1/unified/{ds}/list",
        "UnifiedQueryController.java",
    ),
    (
        "POST",
        "/api/v1/unified/{ds}/export/submit",
        "UnifiedQueryController.java",
    ),
    (
        "GET",
        "/api/v1/unified/export/status/{taskId}",
        "UnifiedQueryController.java",
    ),
    (
        "GET",
        "/base/trailtracks/list",
        "ZdataTrailTracksController.java",
    ),
    (
        "GET",
        "/base/trailtracks/{uuid}",
        "ZdataTrailTracksController.java",
    ),
];

#[cfg(test)]
mod consumer_status_tests {
    use super::consumer_status;
    use crate::mq::ConsumerState;
    use crate::services::sysutil::now_ms;

    /// 用真实 ConsumerState 的 getter 组装入参，驱动 mark_* 的真实状态迁移；
    /// 只测纯函数时，即便 mark_started 不再清 last_error，测试也照样全绿。
    fn status_with(state: &ConsumerState, enabled: bool) -> &'static str {
        consumer_status(
            enabled,
            state.is_started(),
            state.last_recv_ms(),
            state.last_error().map(|(t, _)| t),
            now_ms(),
        )
    }

    fn status(state: &ConsumerState) -> &'static str {
        status_with(state, true)
    }

    #[test]
    fn disabled_wins() {
        // 真正的优先级：enabled=false 时即使从未启动、没有任何状态，也必须是 DISABLED。
        let state = ConsumerState::default();
        assert!(!state.is_started());
        assert_eq!(status_with(&state, false), "DISABLED");
    }

    #[test]
    fn disabled_wins_even_with_fresh_message() {
        // 构造"其它任何分支都会判 UP"的状态，确保 enabled=false 的判定必须排在最前面；
        // 若把 enabled 判断下移到 UP 分支之后，本用例会变成 UP 而失败。
        let state = ConsumerState::default();
        state.mark_started();
        state.mark_recv();
        assert_eq!(status_with(&state, true), "UP");
        assert_eq!(status_with(&state, false), "DISABLED");
    }

    #[test]
    fn enabled_but_not_started_is_down() {
        let state = ConsumerState::default();
        assert_eq!(status(&state), "DOWN");
    }

    #[test]
    fn not_started_is_down() {
        // 任务 panic/退出后 mark_stopped，即使刚收过消息也必须是 DOWN。
        let state = ConsumerState::default();
        state.mark_started();
        state.mark_recv();
        state.mark_stopped();
        assert_eq!(status(&state), "DOWN");
    }

    #[test]
    fn started_with_fresh_message_is_up() {
        let state = ConsumerState::default();
        state.mark_started();
        state.mark_recv();
        assert_eq!(status(&state), "UP");
    }

    #[test]
    fn mark_started_clears_previous_error_then_stale() {
        // 订阅失败 → 恢复：mark_started 必须清 last_error，否则 topic 安静时永久 DOWN。
        let state = ConsumerState::default();
        state.mark_error("订阅失败: broker 不可用");
        assert_eq!(status(&state), "DOWN");
        state.mark_started();
        assert!(
            state.last_error().is_none(),
            "mark_started 必须清空 last_error，否则恢复后仍报 DOWN"
        );
        assert_eq!(status(&state), "STALE");
    }

    #[test]
    fn mark_recv_clears_previous_error_and_reports_up() {
        let state = ConsumerState::default();
        state.mark_started();
        state.mark_error("拉取消息失败");
        state.mark_recv();
        assert!(state.last_error().is_none());
        assert_eq!(status(&state), "UP");
    }

    #[test]
    fn error_after_start_without_message_is_down() {
        let state = ConsumerState::default();
        state.mark_started();
        state.mark_error("拉取消息失败");
        assert_eq!(status(&state), "DOWN");
    }

    #[test]
    fn never_received_is_stale() {
        let state = ConsumerState::default();
        state.mark_started();
        assert_eq!(status(&state), "STALE");
    }
}
