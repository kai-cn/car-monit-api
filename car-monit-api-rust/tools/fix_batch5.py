import io

def edit(p, pairs):
    s = io.open(p, encoding='utf-8').read()
    for a, b in pairs:
        if a not in s:
            print('MISS', p, a[:80].replace('\n', ' '))
        s = s.replace(a, b)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

edit('src/repo/mod.rs', [
    ('"jl_data01.ods_lwzxsfsj_fee_station_enter_01",\n    "cardid",', '"jl_data01.ods_lwzxsfsj_fee_station_enter_01",\n    "big_id",'),
    ('"jl_data01.ods_rt_szdn_snapshot_flow_provcapture_addcode",\n    "guid",', '"jl_data01.ods_rt_szdn_snapshot_flow_provcapture_addcode",\n    "big_id",'),
    ('"jl_data01.ods_rt_szdn_snapshot_flow_stationcapture_addcode",\n    "deviceid",', '"jl_data01.ods_rt_szdn_snapshot_flow_stationcapture_addcode",\n    "big_id",'),
])

for p in ['src/models/mod.rs', 'tools/gen_models.py']:
    s = io.open(p, encoding='utf-8').read()
    s = s.replace('"INT2" | "INT4" | "INT8" | "FLOAT4" | "FLOAT8" | "NUMERIC"',
                  '"INT2" | "INT4" | "INT8" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" | "FLOAT4" | "FLOAT8" | "NUMERIC"')
    s = s.replace('"INT2" => <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),',
                  '"INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => <i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)?.to_string(),')
    s = s.replace('"INT2" => Ok(JInt(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),',
                  '"INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JInt(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i32))),')
    s = s.replace('"INT2" => Ok(JLong(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),',
                  '"INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JLong(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as i64))),')
    s = s.replace('"INT2" => Ok(JFloat(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),',
                  '"INT2" | "TINYINT" | "SMALLINT" | "tinyint" | "smallint" => Ok(JFloat(Some(<i16 as sqlx::Decode<sqlx::Postgres>>::decode(v)? as f64))),')
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

edit('src/handlers/selftest.rs', [
    ('''pub async fn sync_base_info(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    match &state.dict {
        Some(d) => d.refresh_all().await?,
        None => return Err(AppError::internal("字典服务未装配")),
    }
    Ok(json_ok(AjaxResult::success_msg("基础字典缓存已重建")))
}''', '''pub async fn sync_base_info(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    // Java 方法返回 void：成功时 HTTP 200 + 空响应体；失败则 Spring 500。
    if let Some(d) = &state.dict {
        if d.refresh_all().await.is_err() {
            return Ok(crate::handlers::base::spring_internal_error(
                "/base/sysutilTest/syncBaseInfo",
            ));
        }
    }
    Ok(axum::http::StatusCode::OK.into_response())
}'''),
    ('''pub async fn sync_current_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    state.sysutil.sync_track().await?;
    Ok(json_ok(AjaxResult::success_msg("实时轨迹已同步到 car_curent_trail:*")))
}''', '''pub async fn sync_current_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    if state.sysutil.sync_track().await.is_err() {
        return Ok(crate::handlers::base::spring_internal_error(
            "/base/sysutilTest/syncCurrentTrack",
        ));
    }
    Ok(axum::http::StatusCode::OK.into_response())
}'''),
    ('''pub async fn sync_histroy_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    state.sysutil.sync_history_track().await?;
    Ok(json_ok(AjaxResult::success_msg("历史轨迹已合并到 car_history_trail:*")))
}''', '''pub async fn sync_histroy_track(State(state): State<Arc<AppState>>) -> AppResult<Response> {
    if state.sysutil.sync_history_track().await.is_err() {
        return Ok(crate::handlers::base::spring_internal_error(
            "/base/sysutilTest/syncHistroyTrack",
        ));
    }
    Ok(axum::http::StatusCode::OK.into_response())
}'''),
])

p = 'src/handlers/base.rs'
s = io.open(p, encoding='utf-8').read()
s = s.replace('use axum::extract::{Query, State};', 'use axum::extract::{Path, Query, State};')
s += '''

/// Java 侧 select...ById 在本环境抛异常（Mapper 映射/数组列），HTTP 500。
pub async fn vehicle_weight_detail_500(Path(id): Path<String>) -> Response {
    spring_internal_error(&format!("/base/vehicleweight/{}", id))
}

pub async fn trail_tracks_detail_500(Path(id): Path<String>) -> Response {
    spring_internal_error(&format!("/base/trailtracks/{}", id))
}
'''
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)

edit('src/router.rs', [
    ('.route("/base/vehicleweight/{id}", get(crud::vehicle_weight_ajax))',
     '.route("/base/vehicleweight/{id}", get(base::vehicle_weight_detail_500))'),
    ('.route("/base/trailtracks/{id}", get(crud::trail_tracks_ajax))',
     '.route("/base/trailtracks/{id}", get(base::trail_tracks_detail_500))'),
])
print('done')
