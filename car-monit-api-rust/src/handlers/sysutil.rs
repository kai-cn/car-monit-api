// 来源:
//   SysUtilController.java:33-202
//   SysUtilServiceImpl.java:191-274, 1962-2152, 396-1223
// 职责: 轨迹查询与富集接口（/base/sysutil/*）。
// 对应关系:
//   GET  /saveRedis               ↔ save_redis（Java 方法体全注释，空实现）
//   GET  /carTrackQueryByCarNo    ↔ car_track_by_car_no
//   GET  /carTrackQueryByTime     ↔ car_track_by_time（车牌来自 Redis 重点车辆库）
//   POST /changeTrailInfo         ↔ change_trail_info
//   GET  /getByTrailBo            ↔ get_by_trail_bo
//
// PARITY: total 使用「本页行数」（Go 版口径）。Java 的 PageHelper 给出的是匹配总数，
// 但对轨迹查询没有对应 COUNT，硬算会打穿 8 亿级表。

use std::sync::Arc;

use axum::extract::{Query, State};
use axum::response::Response;

use crate::error::{AppError, AppResult};
use crate::handlers::common::*;
use crate::models::*;
use crate::response::{AjaxResult, TableDataInfo};
use crate::services::CAR_LIST_JC;
use crate::state::AppState;
use crate::utils;

pub async fn save_redis(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    state.sysutil.save_redis().await?;
    Ok(json_ok(AjaxResult::success(None)))
}

pub async fn car_track_by_car_no(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut vo): JavaQuery<CarParaVO>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    let p = page_params(&page);
    let mut list = Vec::new();
    let mut total = 0i64;
    if !vo.car_no.trim().is_empty() {
        vo.flag = "bannian".into();
        total = page_query(&state, &mut vo, &p, &mut list).await?;
    }
    let infos = state.sysutil.build_trail_infos(list.clone(), true).await?;
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(infos)?,
        total,
    )))
}

/// 对应 `startPage()` + `carTrackQueryNew()`：先按同一份 WHERE 数出 total，
/// 再按 reasonable 钳位算 offset 并把 LIMIT/OFFSET 下推；pageSize<=0 只出 total 不出行。
async fn page_query(
    state: &Arc<AppState>,
    vo: &mut CarParaVO,
    p: &PageParams,
    out: &mut Vec<ZdataTrailTracks>,
) -> AppResult<i64> {
    let total = state.sysutil.car_track_query_count(vo).await?;
    if p.empty || p.page_size <= 0 {
        return Ok(total);
    }
    let off = p.offset_for(total).max(0);
    *out = state
        .sysutil
        .car_track_query_page(vo, p.page_size, off)
        .await?;
    Ok(total)
}

pub async fn car_track_by_time(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut vo): JavaQuery<CarParaVO>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    let p = page_params(&page);
    let mut list = Vec::new();
    let mut total = 0i64;
    let carlist: Vec<CarVO> = match &state.cache {
        Some(c) => c
            .get_json::<Vec<CarVO>>(CAR_LIST_JC)
            .await?
            .unwrap_or_default(),
        None => vec![],
    };
    if !carlist.is_empty() {
        vo.carlist = carlist.into();
        total = page_query(&state, &mut vo, &p, &mut list).await?;
    }
    // PARITY: Java 的 setTrailPoints("") 在这一分支是注释掉的，因此保留原始轨迹串。
    let infos = state.sysutil.build_trail_infos(list.clone(), false).await?;
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(infos)?,
        total,
    )))
}

pub async fn change_trail_info(
    State(state): State<Arc<AppState>>,
    SpringJson(req): SpringJson<TrailInfo>,
) -> AppResult<Response> {
    let Some(mut tracks) = req.tracks.as_deref().cloned() else {
        return Ok(json_ok(req));
    };
    if req.trail_list.is_empty() {
        // Java L165-190：条件不满足时原样返回入参
        return Ok(json_ok(req));
    }
    fill_decimal(&mut tracks.start_lon_dec, &tracks.start_lon, "startLon")?;
    fill_decimal(&mut tracks.strat_lat_dec, &tracks.strat_lat, "stratLat")?;
    fill_decimal(&mut tracks.end_lon_dec, &tracks.end_lon, "endLon")?;
    fill_decimal(&mut tracks.end_lat_dec, &tracks.end_lat, "endLat")?;
    let mut points = req.trail_list.clone();
    for p in points.iter_mut() {
        p.is_query = "1".into();
    }
    let mut changed = state.sysutil.change_data(&mut tracks, points.value).await?;
    changed.trail_uuid = tracks.plate_key.clone();
    Ok(json_ok(changed))
}

fn fill_decimal(dst: &mut JFloat, raw: &str, field: &str) -> AppResult<()> {
    if raw.trim().is_empty() {
        return Ok(());
    }
    let v = raw
        .trim()
        .parse::<f64>()
        .map_err(|_| AppError::biz(format!("字段 {} 不是合法数值：{}", field, raw)))?;
    *dst = JFloat(Some(v));
    Ok(())
}

pub async fn get_by_trail_bo(
    State(state): State<Arc<AppState>>,
    JavaQuery(bo): JavaQuery<TrailBo>,
) -> AppResult<Response> {
    let result = state.sysutil.get_by_trail_bo(&bo).await?;
    Ok(json_ok(result))
}

/// 供 self-test 接口复用。
pub fn non_empty(s: &str) -> bool {
    !utils::is_blank(s)
}
