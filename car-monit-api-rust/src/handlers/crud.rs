// 来源: pro-base-common/.../core/controller/BaseController.java:60-140
//       pro-business-api/.../controller/*Controller.java（19 个基础表的 list/listAll/listToExport/{id}）
// 职责: 19 张基础表的只读 CRUD 路由。对应 Java 每个 Controller 的样板方法：
//   GET {base}/list          → TableDataInfo{total,rows}   （startPage + selectList + getDataTable）
//   GET {base}/listAll       → 裸数组                     （selectListAll）
//   GET {base}/listToExport  → 裸数组（分页但不包 TableDataInfo）
//   GET {base}/{id}          → 裸对象 / AjaxResult
//
// DIFF: Java 每个 Controller 抄一遍这四段；Rust 用宏 + 泛型函数生成 19 组。
// 分页从 PageHelper 的 ThreadLocal 变成显式 LIMIT/OFFSET，语义等价。

use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::response::Response;
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::error::AppResult;
use crate::handlers::common::*;
use crate::models::*;
use crate::repo::ReadRepo;
use crate::response::{AjaxResult, TableDataInfo};
use crate::state::AppState;

/// 通用列表：SELECT + COUNT + 分页。
pub async fn list_impl<T, R>(repo: &R, q: T, page: &PageQuery) -> AppResult<Response>
where
    T: DeserializeOwned + Serialize + Send + Sync,
    R: ReadRepo<T>,
{
    let p = page_params(page);
    let rows = if p.empty {
        Vec::new()
    } else {
        repo.list(&q, p.page_size, p.offset()).await?
    };
    let total = repo.count(&q).await?;
    Ok(json_ok(TableDataInfo::new(
        serde_json::to_value(rows)?,
        total,
    )))
}

pub async fn export_impl<T, R>(repo: &R, q: T, page: &PageQuery) -> AppResult<Response>
where
    T: DeserializeOwned + Serialize + Send + Sync,
    R: ReadRepo<T>,
{
    let p = page_params(page);
    let rows = if p.empty {
        Vec::new()
    } else {
        repo.list(&q, p.page_size, p.offset()).await?
    };
    Ok(json_ok(serde_json::to_value(rows)?))
}

pub async fn all_impl<T, R>(repo: &R) -> AppResult<Response>
where
    T: Serialize,
    R: ReadRepo<T>,
{
    let rows = repo.list_all().await?;
    Ok(json_ok(serde_json::to_value(rows)?))
}

/// 对应 `public AjaxResult getInfo(@PathVariable id)`。
pub async fn info_ajax_impl<T, R>(repo: &R, id: &str) -> AppResult<Response>
where
    T: Serialize,
    R: ReadRepo<T>,
{
    let obj = repo.get_by_id(id).await?;
    Ok(json_ok(AjaxResult::success(
        obj.map(serde_json::to_value).transpose()?,
    )))
}

/// 对应 `public T getInfo(@PathVariable id)`：null 时 Spring 写空响应体 + 200。
pub async fn info_flat_impl<T, R>(repo: &R, id: &str) -> AppResult<Response>
where
    T: Serialize,
    R: ReadRepo<T>,
{
    match repo.get_by_id(id).await? {
        Some(obj) => Ok(json_ok(obj)),
        None => Ok(empty_ok()),
    }
}

macro_rules! crud_handlers {
    ($list:ident, $export:ident, $all:ident, $ajax:ident, $flat:ident, $field:ident, $ty:ty) => {
        pub async fn $list(
            State(s): State<Arc<AppState>>,
            JavaQuery(q): JavaQuery<$ty>,
            Query(p): Query<PageQuery>,
        ) -> AppResult<Response> {
            list_impl(&s.$field, q, &p).await
        }

        pub async fn $export(
            State(s): State<Arc<AppState>>,
            JavaQuery(q): JavaQuery<$ty>,
            Query(p): Query<PageQuery>,
        ) -> AppResult<Response> {
            export_impl(&s.$field, q, &p).await
        }

        pub async fn $all(State(s): State<Arc<AppState>>) -> AppResult<Response> {
            all_impl(&s.$field).await
        }

        pub async fn $ajax(
            State(s): State<Arc<AppState>>,
            Path(id): Path<String>,
        ) -> AppResult<Response> {
            info_ajax_impl(&s.$field, &id).await
        }

        pub async fn $flat(
            State(s): State<Arc<AppState>>,
            Path(id): Path<String>,
        ) -> AppResult<Response> {
            info_flat_impl(&s.$field, &id).await
        }
    };
}

crud_handlers!(
    fwqjcxx_list,
    fwqjcxx_export,
    fwqjcxx_all,
    fwqjcxx_ajax,
    fwqjcxx_flat,
    fwqjcxx,
    DwdLcztFwqjcxx
);
crud_handlers!(
    sfsjcxx_list,
    sfsjcxx_export,
    sfsjcxx_all,
    sfsjcxx_ajax,
    sfsjcxx_flat,
    sfsjcxx,
    DwdLcztSfsjcxx
);
crud_handlers!(
    sfzjcxx_list,
    sfzjcxx_export,
    sfzjcxx_all,
    sfzjcxx_ajax,
    sfzjcxx_flat,
    sfzjcxx,
    DwdLcztSfzjcxx
);
crud_handlers!(
    fwqclls_list,
    fwqclls_export,
    fwqclls_all,
    fwqclls_ajax,
    fwqclls_flat,
    fwqclls,
    OdsCxztFwqclls
);
crud_handlers!(
    fee_gantry_list,
    fee_gantry_export,
    fee_gantry_all,
    fee_gantry_ajax,
    fee_gantry_flat,
    fee_gantry,
    OdsLwzxsfsjFeeGantryFusion01
);
crud_handlers!(
    fee_enter_list,
    fee_enter_export,
    fee_enter_all,
    fee_enter_ajax,
    fee_enter_flat,
    fee_station_enter,
    OdsLwzxsfsjFeeStationEnter01
);
crud_handlers!(
    fee_exit_list,
    fee_exit_export,
    fee_exit_all,
    fee_exit_ajax,
    fee_exit_flat,
    fee_station_exit,
    OdsLwzxsfsjFeeStationExit01
);
crud_handlers!(
    prov_capture_list,
    prov_capture_export,
    prov_capture_all,
    prov_capture_ajax,
    prov_capture_flat,
    prov_capture,
    OdsRtSzdnSnapshotFlowProvcaptureAddcode
);
crud_handlers!(
    station_capture_list,
    station_capture_export,
    station_capture_all,
    station_capture_ajax,
    station_capture_flat,
    station_capture,
    OdsRtSzdnSnapshotFlowStationcaptureAddcode
);
crud_handlers!(
    gantry_list,
    gantry_export,
    gantry_all,
    gantry_ajax,
    gantry_flat,
    gantry,
    OdsSzdnGantry
);
crud_handlers!(
    gantry_ip_list,
    gantry_ip_export,
    gantry_ip_all,
    gantry_ip_ajax,
    gantry_ip_flat,
    gantry_ip,
    OdsSzdnGantryIp
);
crud_handlers!(
    vehicle_weight_list,
    vehicle_weight_export,
    vehicle_weight_all,
    vehicle_weight_ajax,
    vehicle_weight_flat,
    vehicle_weight,
    OdsSzdnProvinceBorderVehicleWeightNewstructure
);
crud_handlers!(
    section_list,
    section_export,
    section_all,
    section_ajax,
    section_flat,
    section,
    OdsSzdnSection
);
crud_handlers!(
    toll_list,
    toll_export,
    toll_all,
    toll_ajax,
    toll_flat,
    toll,
    OdsSzdnToll
);
crud_handlers!(
    toll_station_ip_list,
    toll_station_ip_export,
    toll_station_ip_all,
    toll_station_ip_ajax,
    toll_station_ip_flat,
    toll_station_ip,
    OdsSzdnTollStationIp
);
crud_handlers!(
    org_list,
    org_export,
    org_all,
    org_ajax,
    org_flat,
    org,
    OdsYhglVBaseOrg
);
crud_handlers!(
    trail_tracks_list,
    trail_tracks_export,
    trail_tracks_all,
    trail_tracks_ajax,
    trail_tracks_flat,
    trail_tracks,
    ZdataTrailTracks
);
crud_handlers!(
    fee_records_list_plain,
    fee_records_export_plain,
    fee_records_all,
    fee_records_ajax,
    fee_records_flat,
    fee_records,
    OdsLwzxsfsjFeeRecords01
);
crud_handlers!(
    snapshot_flow_list_plain,
    snapshot_flow_export_plain,
    snapshot_flow_all,
    snapshot_flow_ajax,
    snapshot_flow_flat,
    snapshot_flow,
    OdsRtSzdnSnapshotFlowAddcode
);

/// 车辆称重 /map：两个写死的 uuid（Java 源码字面量，不是配置项）。
pub async fn vehicle_weight_map(State(s): State<Arc<AppState>>) -> AppResult<Response> {
    let uuids = "18f8e2af-6ebe-4b33-8f37-a688f441de37,7379e7aa-e325-449b-9728-b8f6940c77f1";
    let map = s.sysutil.weight_capture_map(uuids).await;
    Ok(json_ok(AjaxResult::success(Some(serde_json::to_value(
        map,
    )?))))
}
