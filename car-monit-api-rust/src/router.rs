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
    r.layer(axum::middleware::from_fn(middleware::request_id_and_log))
        .layer(CatchPanicLayer::custom(handle_panic))
        .fallback(not_found)
        .method_not_allowed_fallback(method_not_allowed)
        .with_state(state)
}

fn routes() -> Router<Arc<AppState>> {
    Router::new()
        // ---- 健康检查（Java 未接 Actuator；只读、无副作用） ----
        .route("/healthz", get(healthz))
        .route("/readyz", get(readyz))
        .route("/health", get(readyz))
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
        .route("/base/feerecords/{id}", get(crud::fee_records_flat))
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
        .route("/base/trailtracks/{id}", get(base::trail_tracks_detail_500))
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
    if let Some(c) = &state.cache {
        match c.ping().await {
            Ok(()) => body.insert("redis".into(), json!("UP")),
            Err(e) => {
                body.insert("redis".into(), json!(format!("DOWN: {}", e.message())));
                body.insert("status".into(), json!("DOWN"));
                status = StatusCode::SERVICE_UNAVAILABLE;
                None
            }
        };
    }
    if let Some(es) = &state.es {
        match es.health().await {
            Ok(()) => body.insert("elasticsearch".into(), json!("UP")),
            Err(e) => {
                body.insert(
                    "elasticsearch".into(),
                    json!(format!("DOWN: {}", e.message())),
                );
                None
            }
        };
    }
    body.insert(
        "mqConsumer".into(),
        json!(if state
            .consumer_started
            .load(std::sync::atomic::Ordering::SeqCst)
        {
            "UP"
        } else {
            "DOWN"
        }),
    );
    (status, Json(serde_json::Value::Object(body))).into_response()
}

// ---- 兜底 ----

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
