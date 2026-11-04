// 来源:
//   OdsLwzxsfsjFeeRecords01Controller.java:31-205
//   OdsRtSzdnSnapshotFlowAddcodeController.java:28-147
//   OdsSzdnProvinceBorderVehicleWeightNewstructureController.java:24-60
// 职责: 两张「列表需要回填/加工」的基础表，以及省界称重 /map。
//
// 对应关系:
//   list/listToExport 的查询范围开关        ↔ in_query_all_scope
//   feerecords 车牌去类型/时间格式化/门架回填 ↔ decorate_fee_records
//   snapshotflow id=UUID/时间格式化/图片域名 ↔ decorate_snapshot_flow
//   vehicleweight /map 写死两个 uuid         ↔ crud::vehicle_weight_map
//
// PARITY: fee_records 表没有 org 列，Java 的 flag="JiAnDong" 无法落 SQL（Mapper XML 亦缺失）；
// Rust 侧与 Go 版一致：记 WARN 后按「不过滤」执行。

use std::collections::HashMap;
use std::sync::Arc;

use axum::extract::{OriginalUri, Path, Query, State};
use axum::response::{IntoResponse, Response};
use serde_json::Value;

use crate::error::AppResult;
use crate::handlers::common::*;
use crate::models::*;
use crate::response::{AjaxResult, TableDataInfo};
use crate::state::AppState;
use crate::utils;

const SYS_CONFIG_DATA_QUERY: &str = "sys_config:data_query";

async fn in_query_all_scope(state: &AppState) -> bool {
    // PARITY: Redis 不可用时 Java 抛异常（500）；这里降级为更严格的数据权限（noall）。
    match &state.cache {
        Some(c) => c
            .get(SYS_CONFIG_DATA_QUERY)
            .await
            .ok()
            .flatten()
            .map(|v| v.trim().eq_ignore_ascii_case("queryall"))
            .unwrap_or(false),
        None => false,
    }
}

fn split_csv(s: &str) -> Vec<String> {
    s.split(',')
        .map(|x| x.trim())
        .filter(|x| !x.is_empty())
        .map(|x| x.to_string())
        .collect()
}

// ============================================================
// 收费流水（list / listToExport / {bigId}）
// ============================================================

/// PARITY: Java `selectOdsLwzxsfsjFeeRecords01List` 无 Mapper XML，MyBatis 抛
/// Invalid bound statement → Spring 默认 500。这里**故意不绑定查询参数**：
/// Spring 的 PropertyEditor 永不报错（解析失败只是把条件丢掉），所以无论传什么，
/// Java 都会走到同一个 500；Rust 若先反序列化实体，就会在非法日期上返回 400。
pub async fn fee_records_list() -> Response {
    spring_internal_error("/base/feerecords/list")
}

pub async fn fee_records_export() -> Response {
    spring_internal_error("/base/feerecords/listToExport")
}

/// Spring Boot 默认 500 响应体（用于复刻 Java 侧因缺失 Mapper XML 抛出的错误）。
pub fn spring_internal_error(path: &str) -> Response {
    (
        axum::http::StatusCode::INTERNAL_SERVER_ERROR,
        axum::Json(crate::router::spring_error(
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            "Internal Server Error",
            path,
        )),
    )
        .into_response()
}

#[allow(dead_code)]
async fn prepare_fee_records(state: &AppState, q: &mut OdsLwzxsfsjFeeRecords01) {
    if !in_query_all_scope(state).await && q.vehicleplate.trim().is_empty() {
        q.flag = "JiAnDong".into();
        tracing::warn!(
            "[收费流水] 数据权限标记 JiAnDong 无法翻译为 SQL（表无 org 列），已按不过滤执行"
        );
    }
    if !q.section_code_str.trim().is_empty() {
        q.section_list = split_csv(&q.section_code_str).into();
    }
    let code = utils::delete_end(&q.code);
    if !code.is_empty() {
        q.code_list = split_csv(&code).into();
        q.code.clear();
    }
}

#[allow(dead_code)]
async fn decorate_fee_records(
    state: &AppState,
    rows: &mut [OdsLwzxsfsjFeeRecords01],
) -> AppResult<()> {
    if rows.is_empty() {
        return Ok(());
    }
    let gantry_map: HashMap<String, OdsSzdnGantry> = match &state.dict {
        Some(d) => d.gantry_map().await?,
        None => {
            let list = state.gantry.list_all().await?;
            list.into_iter()
                .map(|g| (g.gantry_code.as_str().to_string(), g))
                .collect()
        }
    };
    for r in rows {
        let vehicleplate = r.vehicleplate.clone();
        if let Some(idx) = vehicleplate.find('_') {
            r.vehicleplate = vehicleplate[..idx].to_string().into();
        }
        if let Some(t) = r.transtime.utc() {
            r.transtime_str = utils::format_datetime(&t).into();
        }
        if let Some(t) = r.lastgantrytime.utc() {
            r.lastgantrytime_str = utils::format_datetime(&t).into();
        }
        if let Some(g) = gantry_map.get(r.gantryid.as_str()) {
            r.gantry_name = g.gantry_name.clone();
            r.section_code_str = g.section_code.clone();
        }
    }
    Ok(())
}

// ============================================================
// 收费门架融合流水：列表 id 由 Java 临时生成为 UUID
// ============================================================

pub async fn fee_gantry_list(
    State(state): State<Arc<AppState>>,
    JavaQuery(q): JavaQuery<OdsLwzxsfsjFeeGantryFusion01>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    let p = page_params(&page);
    let order = order_by_clause(&page)?;
    let total = state.fee_gantry.count(&q).await?;
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state
            .fee_gantry
            .list_ordered(&q, p.page_size, p.offset_for(total), order.as_deref())
            .await?
    };
    for r in &mut rows {
        r.id = utils::uuid_simple().into();
    }
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(rows)?,
        total,
    )))
}

// ============================================================
// 门架抓拍流水（list / listToExport / {bigId}）
// ============================================================

pub async fn snapshot_flow_list(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut q): JavaQuery<OdsRtSzdnSnapshotFlowAddcode>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    prepare_snapshot(&state, &mut q).await;
    let p = page_params(&page);
    let order = order_by_clause(&page)?;
    let total = state.snapshot_flow.count(&q).await?;
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state
            .snapshot_flow
            .list_ordered(&q, p.page_size, p.offset_for(total), order.as_deref())
            .await?
    };
    decorate_snapshot(&mut rows, true);
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(rows)?,
        total,
    )))
}

pub async fn snapshot_flow_export(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut q): JavaQuery<OdsRtSzdnSnapshotFlowAddcode>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    prepare_snapshot(&state, &mut q).await;
    let p = page_params(&page);
    let order = order_by_clause(&page)?;
    let total = state.snapshot_flow.count(&q).await?;
    let mut rows = if p.empty {
        Vec::new()
    } else {
        state
            .snapshot_flow
            .list_ordered(&q, p.page_size, p.offset_for(total), order.as_deref())
            .await?
    };
    // PARITY: listToExport 不做图片域名替换（Java 只做 id + 时间格式化）
    decorate_snapshot(&mut rows, false);
    Ok(json_ok(serde_json::to_value(rows)?))
}

async fn prepare_snapshot(state: &AppState, q: &mut OdsRtSzdnSnapshotFlowAddcode) {
    if !in_query_all_scope(state).await && q.platenumber.trim().is_empty() {
        q.flag = "JiAnDong".into();
    }
    if !q.section_code_str.trim().is_empty() {
        q.section_list = split_csv(&q.section_code_str).into();
        q.sectioncode.clear();
    }
    let code = utils::delete_end(&q.code);
    if !code.is_empty() {
        q.code_list = split_csv(&code).into();
        q.code.clear();
    }
}

fn decorate_snapshot(rows: &mut [OdsRtSzdnSnapshotFlowAddcode], with_pic_url: bool) {
    for r in rows {
        r.id = utils::uuid_simple().into();
        if let Some(t) = r.snapshottime.utc() {
            r.snapshottime_str = utils::format_datetime_local(&t).into();
        }
        if with_pic_url {
            r.snappicturepath =
                utils::replace_pic_url(&utils::delete_end(&r.snappicturepath)).into();
        }
    }
}

/// 供 /api/v1/large 等接口复用：把数据源枚举名回显为 Java `ds.name()`。
pub fn enum_name(ds: crate::services::query::DataSource) -> &'static str {
    ds.enum_name()
}

/// 供 handler 复用：空数组（避免 null）。
pub fn empty_array() -> Value {
    Value::Array(vec![])
}

/// Java 侧 select...ById 在本环境抛异常（Mapper 映射/数组列），HTTP 500。
/// Java 侧这些 `{id}` 端点因 Mapper XML 缺失直接 500，Rust 复刻同一状态。
/// 注意路径要取 **原始 requestURI**：`axum::extract::Path` 会给解码后的值，
/// 而 Spring 的 /error 体里 `path` 是未解码的原始 URI（实测 `/base/vehicleweight/%27`）。
pub async fn vehicle_weight_detail_500(OriginalUri(uri): OriginalUri) -> Response {
    spring_internal_error(uri.path())
}

pub async fn trail_tracks_detail_500(OriginalUri(uri): OriginalUri) -> Response {
    spring_internal_error(uri.path())
}

/// `/base/feerecords/{bigId}`：与 list / listToExport 同因（无 Mapper XML）→ Spring 500。
pub async fn fee_records_detail_500(OriginalUri(uri): OriginalUri) -> Response {
    spring_internal_error(uri.path())
}

/// 对应 `ZdataTrailTracksController.getInfo(@PathVariable("uuid") String)`。
/// PARITY: `zdata_trail_tracks.uuid` 不唯一，MyBatis `selectOne()` 命中多行会抛
/// `TooManyResultsException`（实测同一 uuid 有 17 行）→ Spring 500；
/// 命中 0 行返回 `AjaxResult.success(null)`；恰好 1 行才正常返回。
pub async fn trail_tracks_detail(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> AppResult<Response> {
    let rows = state
        .trail_tracks
        .repo
        .list(vec![crate::repo::Cond::Eq("uuid", id.clone().into())], 2, 0)
        .await?;
    match rows.len() {
        0 => Ok(json_ok(AjaxResult::success(None::<Value>))),
        1 => {
            let body = AjaxResult::success(Some(serde_json::to_value(&rows[0])?));
            Ok(json_ok(body))
        }
        _ => Ok(spring_internal_error(&format!("/base/trailtracks/{}", id))),
    }
}
