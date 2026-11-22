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

use axum::extract::{Json, Query, State};
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

/// 深页保护：分页下推到 SQL（LIMIT/OFFSET），只在 offset 异常时拒绝请求，不截断结果。
/// 注意：pageSize 已在 `page_params` 统一钳到 1000（与 Go 版保护上限一致），
/// 因此这里不再单独判断 pageSize 上限，语义是"单页最多 1000 行"。
const MAX_TRACK_OFFSET: i64 = 50_000_000;

fn check_track_page(p: &PageParams) -> AppResult<()> {
    if p.offset() > MAX_TRACK_OFFSET {
        return Err(AppError::bad_request(format!(
            "分页过深：offset={} 超过上限 {}",
            p.offset(),
            MAX_TRACK_OFFSET
        )));
    }
    Ok(())
}

pub async fn car_track_by_car_no(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut vo): JavaQuery<CarParaVO>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    let p = page_params(&page);
    let mut list = Vec::new();
    if !p.empty && !vo.car_no.trim().is_empty() {
        check_track_page(&p)?;
        vo.flag = "bannian".into();
        vo.page_num = JInt::from(p.page_num.min(i32::MAX as i64) as i32);
        vo.page_size = JInt::from(p.page_size.min(i32::MAX as i64) as i32);
        list = state
            .sysutil
            .car_track_query_new(&mut vo, p.page_size, p.offset())
            .await?;
    }
    let infos = state.sysutil.build_trail_infos(list.clone(), true).await?;
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(infos)?,
        list.len() as i64,
    )))
}

pub async fn car_track_by_time(
    State(state): State<Arc<AppState>>,
    JavaQuery(mut vo): JavaQuery<CarParaVO>,
    Query(page): Query<PageQuery>,
) -> AppResult<Response> {
    let p = page_params(&page);
    let mut list = Vec::new();
    let carlist: Vec<CarVO> = match &state.cache {
        Some(c) => c
            .get_json::<Vec<CarVO>>(CAR_LIST_JC)
            .await?
            .unwrap_or_default(),
        None => vec![],
    };
    if !p.empty && !carlist.is_empty() {
        check_track_page(&p)?;
        vo.carlist = carlist.into();
        vo.page_num = JInt::from(p.page_num.min(i32::MAX as i64) as i32);
        vo.page_size = JInt::from(p.page_size.min(i32::MAX as i64) as i32);
        list = state
            .sysutil
            .car_track_query_new(&mut vo, p.page_size, p.offset())
            .await?;
    }
    // PARITY: Java 的 setTrailPoints("") 在这一分支是注释掉的，因此保留原始轨迹串。
    let infos = state.sysutil.build_trail_infos(list.clone(), false).await?;
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(infos)?,
        list.len() as i64,
    )))
}

pub async fn change_trail_info(
    State(state): State<Arc<AppState>>,
    Json(req): Json<TrailInfo>,
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
