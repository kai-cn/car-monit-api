// 来源: SysTestController.java:22-368
// 职责: 运维/自测端点（/base/sysutilTest/*）。
// 对应关系:
//   /syncBaseInfo      ↔ DictService::refresh_all（7 个 updateRedis 的合并）
//   /syncCurrentTrack  ↔ SysUtilService::sync_track（= TrackTask 3 分钟任务）
//   /syncHistroyTrack  ↔ SysUtilService::sync_history_track（= TrackTask 4 点任务）
//   其余 12 个          → 501 + javaRef + reason
//
// PARITY（重要）: 剩下 12 个端点不是「没时间做」，而是 Java 侧本身跑不通/没有消费方：
//   1. 10 个 syncSuspiciousCarN → SysUtilServiceImpl.syncSuspiciousCarQutaz 依赖
//      OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew；
//      该语句在全部 Mapper XML 中缺失，MyBatis 必抛 Invalid bound statement；
//   2. syncOdsSzdnGantry 依赖 selectGantryNum（同样只有声明），且时间串写死为
//      "2025-11-01 00-00-00"（时分秒用短横线），过不了 to_timestamp 解析；
//   3. separateSnapshotFlowTimeList 产出的 car_uspicious:* 唯一消费方无调用方，
//      且会向外部 HTTP 接口推送数据。
// 因此返回 501 而不是 200，避免调用方误以为同步成功。

use std::sync::Arc;

use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

use crate::error::AppResult;
use crate::state::AppState;

pub async fn sync_base_info(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    // Java 方法返回 void：成功时 HTTP 200 + 空响应体；失败则 Spring 500。
    if let Some(d) = &state.dict {
        if d.refresh_all().await.is_err() {
            return Ok(crate::handlers::base::spring_internal_error(
                "/base/sysutilTest/syncBaseInfo",
            ));
        }
    }
    Ok(axum::http::StatusCode::OK.into_response())
}

pub async fn sync_current_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    if state.sysutil.sync_track().await.is_err() {
        return Ok(crate::handlers::base::spring_internal_error(
            "/base/sysutilTest/syncCurrentTrack",
        ));
    }
    Ok(axum::http::StatusCode::OK.into_response())
}

pub async fn sync_histroy_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    if state.sysutil.sync_history_track().await.is_err() {
        return Ok(crate::handlers::base::spring_internal_error(
            "/base/sysutilTest/syncHistroyTrack",
        ));
    }
    Ok(axum::http::StatusCode::OK.into_response())
}

/// 12 个「Java 侧同样无法执行」的端点：501 + 可核对的 Java 出处与原因。
pub fn blocked_endpoints() -> Vec<(&'static str, &'static str, &'static str)> {
    let reason = "依赖 SysUtilServiceImpl.syncSuspiciousCarQutaz，该方法需要 \
OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ListNew —— \
该语句在全部 Mapper XML 中缺失，Java 侧调用时抛 Invalid bound statement";
    let mut out = vec![
        ("/syncSuspiciousCar1", "SysTestController.java:175-185", reason),
        ("/syncSuspiciousCar2", "SysTestController.java:190-200", reason),
        ("/syncSuspiciousCar3", "SysTestController.java:205-215", reason),
        ("/syncSuspiciousCar4", "SysTestController.java:220-230", reason),
        ("/syncSuspiciousCar5", "SysTestController.java:235-245", reason),
        ("/syncSuspiciousCar6", "SysTestController.java:250-260", reason),
        ("/syncSuspiciousCar7", "SysTestController.java:265-275", reason),
        ("/syncSuspiciousCar8", "SysTestController.java:280-290", reason),
        ("/syncSuspiciousCar9", "SysTestController.java:296-306", reason),
        ("/syncSuspiciousCar10", "SysTestController.java:311-321", reason),
        (
            "/syncOdsSzdnGantry",
            "SysTestController.java:327-354",
            "依赖 OdsLwzxsfsjFeeRecords01Mapper.selectGantryNum（只有声明、无 SQL），且入参时间串为 \"2025-11-01 00-00-00\"，过不了 to_timestamp 的格式解析",
        ),
        (
            "/separateSnapshotFlowTimeList",
            "SysTestController.java:359-364",
            "产出 car_uspicious:*，其唯一消费方 syncSuspiciousCarDB() 无任何调用方，且会向外部 HTTP 接口推送数据；输入 js_car_snapshot:* 又只由上面那条中断的链路写入",
        ),
    ];
    out.shrink_to_fit();
    out
}

pub async fn not_ported(
    path: &'static str,
    java_ref: &'static str,
    reason: &'static str,
) -> Response {
    let _ = path;
    (
        StatusCode::NOT_IMPLEMENTED,
        Json(json!({
            "code": 501,
            "msg": format!("SysTestController{} 不提供（Java 侧同样无法执行）：{}", path, reason),
            "data": null,
            "porting": "blocked",
            "javaRef": java_ref,
            "reason": reason,
        })),
    )
        .into_response()
}
