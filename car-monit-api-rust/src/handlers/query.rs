// 来源:
//   LargeScaleQueryController.java:54-319
//   UnifiedQueryController.java:64-194
//   ProgressiveQueryController.java:53-174
// 职责: 三张大表的查询 / 统计 / 异步导出 / 同步运维接口。
// 对应关系:
//   GET  /api/v1/large/{snapshot,fee,trail}            ↔ large_query
//   GET  /api/v1/large/carTrackQueryByCarNo            ↔ car_track_by_car_no
//   GET  /api/v1/large/stats/group                     ↔ group_stats
//   POST /api/v1/large/export/submit                   ↔ large_export_submit
//   GET  /api/v1/large/export/status/{taskId}          ↔ large_export_status
//   POST /api/v1/large/sync/{full,incremental,repair}  ↔ sync_*
//   GET  /api/v1/unified/{ds}/list                     ↔ unified_list
//   POST /api/v1/unified/{ds}/export/submit            ↔ unified_export_submit
//   GET  /api/v1/progressive/{表}/list                 ↔ progressive_list
//
// PARITY: 两处「同名字段不同来源」原样保留：
//   1. large 的 dataSource 用枚举名（SNAPSHOT/FEE/TRAIL），unified 回显路径参数原串；
//   2. large 导出的请求体仍要求 key 带 "fuzzyFields." 前缀，unified 直接用整个请求体。

use std::collections::HashMap;
use std::sync::Arc;

use axum::extract::{Json, OriginalUri, Path, Query, State};
use axum::http::StatusCode;
use axum::response::Response;
use serde_json::{json, Value};

use crate::handlers::common::*;
use crate::services::export::{TASK_COMPLETED, TASK_FAILED};
use crate::services::query::{parse_data_source, parse_type_lenient, DataSource};
use crate::state::AppState;

type RawQuery = HashMap<String, String>;

fn time_range(c: &RawQuery, path: &str) -> Result<(String, String), Response> {
    let start = c.get("startTime").cloned().unwrap_or_default();
    let end = c.get("endTime").cloned().unwrap_or_default();
    match require_time_range(&start, &end) {
        Ok(()) => Ok((start, end)),
        Err(_) => Err(spring_bad_request(path)),
    }
}

/// 对应 Spring 缺少 @RequestParam 时的默认 400 响应体。
fn spring_bad_request(path: &str) -> Response {
    json_status(
        StatusCode::BAD_REQUEST,
        crate::router::spring_error(StatusCode::BAD_REQUEST, "Bad Request", path),
    )
}

fn page_args(c: &RawQuery, default_size: i64) -> (i64, i64) {
    let page_num = c
        .get("pageNum")
        .and_then(|v| v.parse().ok())
        .filter(|n| *n > 0)
        .unwrap_or(1);
    let page_size = c
        .get("pageSize")
        .and_then(|v| v.parse().ok())
        .filter(|n| *n > 0)
        .unwrap_or(default_size);
    (page_num, page_size)
}

// ============================================================
// /api/v1/large
// ============================================================

pub async fn large_query(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    // Java 只有 /snapshot /fee /trail 三个映射；其余路径是 Spring 404。
    let ds = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(_) => {
            return json_status(
                StatusCode::NOT_FOUND,
                crate::router::spring_error(StatusCode::NOT_FOUND, "Not Found", uri.path()),
            )
        }
    };
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let (page_num, page_size) = page_args(&c, 20);
    let fuzzy = fuzzy_fields(&c);
    match state
        .query
        .query(ds, &start, &end, &fuzzy, page_num, page_size)
        .await
    {
        Ok(list) => map_response(vec![
            ("code", json!(200)),
            ("message", json!("ok")),
            ("dataSource", json!(ds.enum_name())),
            ("pageNum", json!(page_num)),
            ("pageSize", json!(page_size)),
            ("data", serde_json::to_value(list).unwrap_or(json!([]))),
        ]),
        Err(e) => biz_map_error(e.message()),
    }
}

pub async fn car_track_by_car_no(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    if c.get("carNo").map(|v| v.is_empty()).unwrap_or(true) {
        return spring_bad_request(uri.path());
    }
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let (page_num, page_size) = page_args(&c, 20);
    let mut fuzzy = HashMap::new();
    if let Some(car_no) = c.get("carNo") {
        if !car_no.is_empty() {
            fuzzy.insert("platenumber".to_string(), car_no.clone());
        }
    }
    match state
        .query
        .query(DataSource::Trail, &start, &end, &fuzzy, page_num, page_size)
        .await
    {
        Ok(list) => map_response(vec![
            ("code", json!(200)),
            ("message", json!("ok")),
            ("dataSource", json!(DataSource::Trail.enum_name())),
            ("pageNum", json!(page_num)),
            ("pageSize", json!(page_size)),
            ("data", serde_json::to_value(list).unwrap_or(json!([]))),
        ]),
        Err(e) => biz_map_error(e.message()),
    }
}

pub async fn group_stats(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    if c.get("groupBy").map(|v| v.is_empty()).unwrap_or(true) {
        return spring_bad_request(uri.path());
    }
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let group_by = c.get("groupBy").cloned().unwrap_or_default();
    let top_n = c.get("topN").and_then(|v| v.parse().ok()).unwrap_or(100);
    let ds = match parse_type_lenient(&typ) {
        Ok(v) => v,
        Err(e) => return biz_map_error(e.message()),
    };
    match state
        .large
        .aggregation_stats(ds, &start, &end, &group_by, "", &fuzzy_fields(&c), top_n)
        .await
    {
        Ok(stats) => map_response(vec![
            ("code", json!(200)),
            ("message", json!("ok")),
            ("type", json!(typ)),
            ("groupBy", json!(group_by)),
            ("topN", json!(top_n)),
            ("data", Value::Object(stats)),
        ]),
        Err(e) => biz_map_error(e.message()),
    }
}

pub async fn large_export_submit(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let raw = body.map(|Json(b)| b).unwrap_or_default();
    let fields = prefixed_fields(&raw);
    let ds = match parse_type_lenient(&typ) {
        Ok(v) => v,
        Err(e) => return biz_map_error(e.message()),
    };
    match state.large.submit_export(ds, &start, &end, fields).await {
        Ok(task_id) => map_response(vec![
            ("code", json!(200)),
            ("message", json!("导出任务已提交")),
            ("type", json!(typ)),
            ("taskId", json!(task_id)),
        ]),
        Err(e) => biz_map_error(e.message()),
    }
}

pub async fn large_export_status(
    State(state): State<Arc<AppState>>,
    Path(task_id): Path<String>,
) -> Response {
    match state.large.get_export_status(&task_id).await {
        None => json_ok(json!({ "code": 404, "message": "task not found" })),
        Some(st) => map_response(vec![
            ("code", json!(200)),
            ("status", json!(st.status)),
            ("totalExported", json!(st.total_exported)),
            ("filePartCount", json!(st.file_part_count)),
            ("submitTime", json!(st.submit_time)),
            ("endTime", json!(st.finish_time.unwrap_or(0))),
        ]),
    }
}

pub async fn sync_full(State(state): State<Arc<AppState>>) -> Response {
    let svc = state.sync.clone();
    tokio::spawn(async move {
        if let Err(e) = svc.full_sync_one_year().await {
            tracing::error!(err = %e, "[同步-全量] 异常");
        }
    });
    json_ok(json!({ "code": 200, "message": "全量同步任务已在后台启动（三表），预计耗时较长" }))
}

pub async fn sync_incremental(State(state): State<Arc<AppState>>) -> Response {
    match state.sync.incremental_sync().await {
        Ok(()) => {
            json_ok(json!({ "code": 200, "message": "增量同步完成（三表，基于 Redis 水位）" }))
        }
        Err(e) => json_ok(json!({ "code": 500, "message": e.message() })),
    }
}

pub async fn sync_repair(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Query(c): Query<RawQuery>,
) -> Response {
    let typ = c.get("type").cloned().unwrap_or_else(|| "snapshot".into());
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let ds = match parse_type_lenient(&typ) {
        Ok(v) => v,
        Err(e) => return biz_map_error(e.message()),
    };
    let svc = state.sync.clone();
    let message = format!("补同步任务已在后台启动 type={}", typ);
    tokio::spawn(async move {
        if let Err(e) = svc.repair_sync(ds, &start, &end).await {
            tracing::error!(err = %e, "[同步-补录] 异常");
        }
    });
    json_ok(json!({ "code": 200, "message": message }))
}

// ============================================================
// /api/v1/unified
// ============================================================

pub async fn unified_list(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let (page_num, page_size) = page_args(&c, 20);
    match state
        .query
        .query(source, &start, &end, &fuzzy_fields(&c), page_num, page_size)
        .await
    {
        Ok(list) => map_response(vec![
            ("code", json!(200)),
            ("message", json!("ok")),
            ("dataSource", json!(ds)), // Java 回显路径参数原串
            ("pageNum", json!(page_num)),
            ("pageSize", json!(page_size)),
            ("data", serde_json::to_value(list).unwrap_or(json!([]))),
        ]),
        Err(e) => biz_map_error(e.message()),
    }
}

pub async fn unified_export_submit(
    State(state): State<Arc<AppState>>,
    OriginalUri(uri): OriginalUri,
    Path(ds): Path<String>,
    Query(c): Query<RawQuery>,
    body: Option<Json<HashMap<String, String>>>,
) -> Response {
    let source = match parse_data_source(&ds) {
        Ok(v) => v,
        Err(e) => return json_ok(json!({ "code": 400, "message": e.message() })),
    };
    let (start, end) = match time_range(&c, uri.path()) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let raw = body.map(|Json(b)| b).unwrap_or_default();
    match state
        .export
        .submit_export_task(source, &start, &end, raw)
        .await
    {
        Ok(task_id) => json_ok(json!({
            "code": 200,
            "message": "导出任务已提交, 请用 taskId 轮询状态",
            "taskId": task_id
        })),
        Err(e) => biz_map_error(e),
    }
}

pub async fn unified_export_status(
    State(state): State<Arc<AppState>>,
    Path(task_id): Path<String>,
) -> Response {
    match state.export.get_export_status(&task_id).await {
        None => json_ok(json!({ "code": 404, "message": "task not found" })),
        Some(st) => {
            let mut out = serde_json::Map::new();
            out.insert("code".into(), json!(200));
            out.insert("status".into(), json!(st.status));
            out.insert("totalExported".into(), json!(st.total_exported));
            out.insert("filePartCount".into(), json!(st.file_part_count));
            out.insert("submitTime".into(), json!(st.submit_time));
            match st.status.as_str() {
                TASK_COMPLETED => {
                    out.insert("endTime".into(), json!(st.finish_time.unwrap_or(0)));
                    out.insert(
                        "filePaths".into(),
                        json!(st.file_paths.clone().unwrap_or_default()),
                    );
                    out.insert(
                        "costSeconds".into(),
                        json!((st.finish_time.unwrap_or(0) - st.submit_time) / 1000),
                    );
                }
                TASK_FAILED => {
                    out.insert(
                        "errorMessage".into(),
                        json!(st.error_message.clone().unwrap_or_default()),
                    );
                }
                _ => {}
            }
            json_ok(Value::Object(out))
        }
    }
}

// ============================================================
// /progressive
// ============================================================

fn progressive_request(c: &RawQuery) -> crate::services::progressive::QueryRequest {
    let mut req = crate::services::progressive::QueryRequest {
        start_time: c.get("startTime").cloned().unwrap_or_default(),
        end_time: c.get("endTime").cloned().unwrap_or_default(),
        platenumber: c.get("platenumber").cloned().unwrap_or_default(),
        orgname: c.get("orgname").cloned().unwrap_or_default(),
        sectionname: c.get("sectionname").cloned().unwrap_or_default(),
        roadname: c.get("roadname").cloned().unwrap_or_default(),
        gantryname: c.get("gantryname").cloned().unwrap_or_default(),
        tollname: c.get("tollname").cloned().unwrap_or_default(),
        cursor: c.get("cursor").cloned().unwrap_or_default(),
        page_size: c.get("pageSize").and_then(|v| v.parse().ok()).unwrap_or(20),
    };
    if req.page_size <= 0 {
        req.page_size = 20;
    }
    req
}

pub async fn progressive_list(
    State(state): State<Arc<AppState>>,
    Path(table): Path<String>,
    Query(c): Query<RawQuery>,
) -> crate::error::AppResult<Response> {
    let req = progressive_request(&c);
    let result = match table.as_str() {
        "snapshotflow" => state.progressive.query_snapshot_flow(req).await?,
        "feerecords" => {
            // PARITY: Java 侧 Mapper XML 缺失 → Spring 500。
            return Ok(crate::handlers::base::spring_internal_error(
                "/progressive/feerecords/list",
            ));
        }
        "trailfitting" => {
            // PARITY: Java 侧 Mapper XML 缺失 → Spring 500。
            return Ok(crate::handlers::base::spring_internal_error(
                "/progressive/trailfitting/list",
            ));
        }
        other => {
            return Err(crate::error::AppError::NotFound(format!(
                "未知表: {}",
                other
            )))
        }
    };
    // PARITY: Java 的 total 来自 PageInfo 包装的普通 ArrayList，即「本页行数」
    let total = result.data.as_array().map(|a| a.len()).unwrap_or(0) as i64;
    Ok(json_ok(crate::response::TableDataInfo::with_msg(
        result.data,
        total,
        format!("策略: {}", result.strategy),
    )))
}

pub async fn scale_level(State(state): State<Arc<AppState>>) -> Response {
    let levels = json!({
        "ods_rt_szdn_snapshot_flow_addcode": state.progressive.detect_scale_level("ods_rt_szdn_snapshot_flow_addcode").await.name(),
        "ods_lwzxsfsj_fee_records_01": state.progressive.detect_scale_level("ods_lwzxsfsj_fee_records_01").await.name(),
        "zdata_trail_fitting": state.progressive.detect_scale_level("zdata_trail_fitting").await.name(),
    });
    json_ok(crate::response::AjaxResult::success(Some(levels)))
}
