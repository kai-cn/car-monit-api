// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/SysUtilServiceImpl.java
//   191-274 saveRedis（方法体整体注释，空实现）
//   1962-2004 carTrackQueryNew
//   2030-2152 getTrailBoList / mapTrailBoList
//   396-962 changeData
//   969-1223 getByTrailBo
// 职责: 轨迹查询与富集；对应 /base/sysutil/*。
// 对应关系:
//   changeData            ↔ change_data
//   getByTrailBo          ↔ get_by_trail_bo
//   getTrailBoList        ↔ trail::parse_trail_points
//   ByQueryUuids 回源       ↔ lookup_by_uuid（含负缓存）
//
// PARITY（照抄 Java 已知缺陷）:
//   1) lat 赋成 lon（Java L481-482）；
//   2) indexType 在循环外声明，stateType 未命中 switch 时沿用上一个点；
//   3) captureTime 仅在含 "T" 时赋值（见 trail.rs）；
//   4) mapTrailBoList 注释写 3 分钟，实际阈值 4 分钟。

use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::de::DeserializeOwned;
use serde::Serialize;
use tracing::{info, warn};

use crate::cache::Cache;
use crate::error::AppResult;
use crate::models::*;
use crate::repo::*;
use crate::services::dict::DictService;
use crate::services::trail::{dedupe_points, parse_trail_points};
use crate::services::*;
use crate::utils;

const INDEX_TYPE_GANTRY: &str = "gantryType";
const INDEX_TYPE_STATION: &str = "stationType";
const INDEX_TYPE_SERVICE_AREA: &str = "service_area";
const TRACK_FLAG_CURRENT: &str = "currentTrack";

#[derive(Clone)]
pub struct SysUtilService {
    pub trail: TrailTracksRepo,
    pub weight: VehicleWeightRepo,
    pub gantry_capture: SnapshotFlowRepo,
    pub prov_capture: ProvCaptureRepo,
    pub fwqclls: FwqcllsRepo,
    pub station_capture: StationCaptureRepo,
    pub fee_records: FeeRecordsRepo,
    pub fee_enter: FeeStationEnterRepo,
    pub fee_exit: FeeStationExitRepo,
    pub dict: Option<DictService>,
    pub cache: Option<Cache>,
    pub env: String,
}

impl SysUtilService {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        trail: TrailTracksRepo,
        weight: VehicleWeightRepo,
        gantry_capture: SnapshotFlowRepo,
        prov_capture: ProvCaptureRepo,
        fwqclls: FwqcllsRepo,
        station_capture: StationCaptureRepo,
        fee_records: FeeRecordsRepo,
        fee_enter: FeeStationEnterRepo,
        fee_exit: FeeStationExitRepo,
        dict: Option<DictService>,
        cache: Option<Cache>,
        env: String,
    ) -> Self {
        Self {
            trail,
            weight,
            gantry_capture,
            prov_capture,
            fwqclls,
            station_capture,
            fee_records,
            fee_enter,
            fee_exit,
            dict,
            cache,
            env,
        }
    }

    /// 对应 saveRedis：Java 方法体全部被注释，只返回成功。
    pub async fn save_redis(&self) -> AppResult<()> {
        info!("[SysUtil] saveRedis 为空实现：Java 侧方法体整体被注释，仅返回成功");
        Ok(())
    }

    pub async fn car_track_query_new(
        &self,
        vo: &mut CarParaVO,
        limit: i64,
        offset: i64,
    ) -> AppResult<Vec<ZdataTrailTracks>> {
        if !vo.carlist.is_empty() {
            vo.car_no_list = vo
                .carlist
                .iter()
                .map(|c| c.car_no.as_str().to_string())
                .filter(|s| !s.trim().is_empty())
                .collect();
        }
        self.trail.get_history_trail(vo, limit, offset).await
    }

    pub async fn build_trail_infos(
        &self,
        list: Vec<ZdataTrailTracks>,
        clear_trail_points: bool,
    ) -> AppResult<Vec<TrailInfo>> {
        let mut out = Vec::with_capacity(list.len());
        for mut tracks in list {
            if tracks.trail_points.trim().is_empty() {
                continue;
            }
            let points = parse_trail_points(&tracks.trail_points);
            if clear_trail_points {
                tracks.trail_points.clear();
            }
            let mut info = self.change_data(&mut tracks, points).await?;
            info.trail_uuid = tracks.plate_key.clone();
            out.push(info);
        }
        Ok(out)
    }

    pub async fn change_data(
        &self,
        tracks: &mut ZdataTrailTracks,
        mut points: Vec<TrailBo>,
    ) -> AppResult<TrailInfo> {
        if points.is_empty() {
            return Ok(TrailInfo {
                tracks: Some(Box::new(tracks.clone())),
                trail_list: vec![].into(),
                ..Default::default()
            });
        }
        let Some(dict) = &self.dict else {
            warn!("[轨迹查询] 字典未装配，跳过 changeData 富集");
            return Ok(TrailInfo {
                tracks: Some(Box::new(tracks.clone())),
                trail_list: points.into(),
                ..Default::default()
            });
        };
        let station_map = dict.station_ip_map().await?;
        let toll_map = dict.toll_map().await?;
        let gantry_map = dict.gantry_ip_map().await?;
        let location_map = dict.location_map().await?;
        let section_map = dict.section_map().await?;

        // PARITY: indexType 在循环外声明（Java 原样）
        let mut index_type = String::new();

        for trail_bo in points.iter_mut() {
            let mut location_code = trail_bo.location_code.as_str().to_string();
            let state_type = trail_bo.state_type.as_str().to_string();
            let section_code = trail_bo.section_code.as_str().to_string();
            let pileno = trail_bo.pileno.as_str().to_string();
            let lon = trail_bo.lon.get();
            // PARITY: Java L482 的笔误 —— lat 取的是 lon
            let lat = trail_bo.lon.get();
            let mut road_code = String::new();

            if !section_code.trim().is_empty() {
                if let Some(section) = section_map.get(&section_code) {
                    road_code = section.road_code.as_str().to_string();
                    trail_bo.road_code = road_code.clone().into();
                }
            }

            match state_type.as_str() {
                DATA_TYPE_BORDER_WEIGHING
                | DATA_TYPE_GANTRY_CAPTURE
                | DATA_TYPE_PROV_CAPTURE
                | DATA_TYPE_FEE_RECORD => index_type = INDEX_TYPE_GANTRY.to_string(),
                DATA_TYPE_SERVICE_AREA_CAPTURE => index_type = INDEX_TYPE_SERVICE_AREA.to_string(),
                DATA_TYPE_STATION_CAPTURE
                | DATA_TYPE_FEE_STATION_ENTER
                | DATA_TYPE_FEE_STATION_EXIT => index_type = INDEX_TYPE_STATION.to_string(),
                _ => {}
            }

            let dev_location_code = location_map
                .get(&location_code)
                .map(|l| l.standard_code.clone())
                .unwrap_or_default();
            let dev_code_id = trail_bo.dev_code.as_str().to_string();

            match index_type.as_str() {
                x if x == INDEX_TYPE_STATION => {
                    if let Some(station) = pick_from_map(
                        &station_map,
                        &[&dev_location_code, &dev_code_id, &location_code],
                    ) {
                        trail_bo.dev_code = station.toll_code.as_str().to_string().into();
                        trail_bo.dev_name = station.toll_name.as_str().to_string().into();
                        if let Some(toll) = &station.ods_szdn_toll {
                            if lon.is_none() && !toll.longitude.trim().is_empty() {
                                trail_bo.lon = parse_f64(&toll.longitude).into();
                            }
                            if lat.is_none() && !toll.latitude.trim().is_empty() {
                                trail_bo.lat = parse_f64(&toll.latitude).into();
                            }
                            if road_code.trim().is_empty() {
                                trail_bo.road_code = toll.road_code.as_str().to_string().into();
                            }
                            if section_code.trim().is_empty() {
                                trail_bo.section_code =
                                    toll.section_code.as_str().to_string().into();
                            }
                            if pileno.trim().is_empty() {
                                trail_bo.pileno = toll.pile_no.as_str().to_string().into();
                            }
                        }
                    }
                }
                x if x == INDEX_TYPE_GANTRY => {
                    if let Some(gantry) = pick_from_map(
                        &gantry_map,
                        &[&dev_location_code, &dev_code_id, &location_code],
                    ) {
                        trail_bo.dev_code = gantry.gantry_code.as_str().to_string().into();
                        trail_bo.dev_name = gantry.gantry_name.as_str().to_string().into();
                        if let Some(g) = &gantry.ods_szdn_gantry {
                            if lon.is_none() && !g.lon.trim().is_empty() {
                                trail_bo.lon = parse_f64(&g.lon).into();
                            }
                            if lat.is_none() && !g.lat.trim().is_empty() {
                                trail_bo.lat = parse_f64(&g.lat).into();
                            }
                            if road_code.trim().is_empty() {
                                trail_bo.road_code = g.road_code.as_str().to_string().into();
                            }
                            if section_code.trim().is_empty() {
                                trail_bo.section_code = g.section_code.as_str().to_string().into();
                            }
                            if pileno.trim().is_empty() {
                                trail_bo.pileno = g.pile_no.as_str().to_string().into();
                            }
                            trail_bo.direction = g.direction.as_str().to_string().into();
                            trail_bo.is_virtual = g.is_virtual.as_str().to_string().into();
                        }
                    }
                }
                x if x == INDEX_TYPE_SERVICE_AREA => {
                    location_code = location_code.replace("devip:", "serviceip:");
                    if let Some(loc) = location_map.get(&location_code) {
                        trail_bo.dev_code = loc.standard_code.as_str().to_string().into();
                        trail_bo.dev_name = loc.name.as_str().to_string().into();
                        if loc.longitude.get().is_some() {
                            trail_bo.lon = loc.longitude.get().into();
                        }
                        if loc.latitude.get().is_some() {
                            trail_bo.lat = loc.latitude.get().into();
                        }
                        trail_bo.road_code = loc.roadcode.as_str().to_string().into();
                        trail_bo.section_code = loc.sectioncode.as_str().to_string().into();
                        trail_bo.pileno = loc.pile_no.as_str().to_string().into();
                        trail_bo.direction = loc.direction.as_str().to_string().into();
                    }
                }
                _ => {}
            }

            if trail_bo.dev_name.trim().is_empty() {
                trail_bo.dev_name = location_code.replace("serviceip:", "").into();
            }
        }

        // 只统计经纬度都齐的点，用于推导起终点
        let jwd: Vec<usize> = points
            .iter()
            .enumerate()
            .filter(|(_, p)| p.lon.get().is_some() && p.lat.get().is_some())
            .map(|(i, _)| i)
            .collect();

        if tracks.flag == TRACK_FLAG_CURRENT {
            if let Some(&first) = jwd.first() {
                tracks.entollstationid = points[first].dev_code.as_str().to_string().into();
                tracks.entollstationname = points[first].dev_name.as_str().to_string().into();
                tracks.start_lon = fmt_opt(points[first].lon.get()).into();
                tracks.strat_lat = fmt_opt(points[first].lat.get()).into();
                if jwd.len() > 1 {
                    let last = *jwd.last().unwrap();
                    tracks.extollstationid = points[last].dev_code.as_str().to_string().into();
                    tracks.extollstationname = points[last].dev_name.as_str().to_string().into();
                    tracks.end_lon = fmt_opt(points[last].lon.get()).into();
                    tracks.end_lat = fmt_opt(points[last].lat.get()).into();
                }
            }
        } else {
            let first_code = tracks.entollstationid.as_str().to_string();
            let first_name = utils::replace_toll_name(&tracks.entollstationname);
            let end_code = tracks.extollstationid.as_str().to_string();
            let end_name = utils::replace_toll_name(&tracks.extollstationname);

            if !first_code.trim().is_empty() {
                if let Some(toll) = toll_map.get(&first_code) {
                    if !toll.longitude.trim().is_empty() {
                        tracks.start_lon = toll.longitude.as_str().to_string().into();
                    }
                    if !toll.latitude.trim().is_empty() {
                        tracks.strat_lat = toll.latitude.as_str().to_string().into();
                    }
                    tracks.entollstationid = toll.toll_code.as_str().to_string().into();
                } else if let Some(g) = gantry_map.get(&first_code) {
                    if let Some(g) = &g.ods_szdn_gantry {
                        if !g.lon.trim().is_empty() {
                            tracks.start_lon = g.lon.as_str().to_string().into();
                        }
                        if !g.lat.trim().is_empty() {
                            tracks.strat_lat = g.lat.as_str().to_string().into();
                        }
                    }
                }
            }
            if tracks.start_lon.trim().is_empty() && !first_name.trim().is_empty() {
                if let Some(station) = station_map.get(&first_name) {
                    if let Some(toll) = &station.ods_szdn_toll {
                        if !toll.longitude.trim().is_empty() {
                            tracks.start_lon = toll.longitude.as_str().to_string().into();
                        }
                        if !toll.latitude.trim().is_empty() {
                            tracks.strat_lat = toll.latitude.as_str().to_string().into();
                        }
                    }
                    tracks.entollstationid = station.toll_code.as_str().to_string().into();
                } else if let Some(g) = gantry_map.get(&first_name) {
                    if let Some(g) = &g.ods_szdn_gantry {
                        if !g.lon.trim().is_empty() {
                            tracks.start_lon = g.lon.as_str().to_string().into();
                        }
                        if !g.lat.trim().is_empty() {
                            tracks.strat_lat = g.lat.as_str().to_string().into();
                        }
                    }
                    tracks.entollstationid = g.gantry_code.as_str().to_string().into();
                }
            }
            if !end_code.trim().is_empty() {
                if let Some(toll) = toll_map.get(&end_code) {
                    if !toll.longitude.trim().is_empty() {
                        tracks.end_lon = toll.longitude.as_str().to_string().into();
                    }
                    if !toll.latitude.trim().is_empty() {
                        tracks.end_lat = toll.latitude.as_str().to_string().into();
                    }
                    tracks.extollstationid = toll.toll_code.as_str().to_string().into();
                } else if let Some(g) = gantry_map.get(&end_code) {
                    if let Some(g) = &g.ods_szdn_gantry {
                        if !g.lon.trim().is_empty() {
                            tracks.end_lon = g.lon.as_str().to_string().into();
                        }
                        if !g.lat.trim().is_empty() {
                            tracks.end_lat = g.lat.as_str().to_string().into();
                        }
                    }
                }
            }
            if tracks.end_lon.trim().is_empty() && !end_name.trim().is_empty() {
                if let Some(station) = station_map.get(&end_name) {
                    if let Some(toll) = &station.ods_szdn_toll {
                        if !toll.longitude.trim().is_empty() {
                            tracks.end_lon = toll.longitude.as_str().to_string().into();
                        }
                        if !toll.latitude.trim().is_empty() {
                            tracks.end_lat = toll.latitude.as_str().to_string().into();
                        }
                    }
                    tracks.extollstationid = station.toll_code.as_str().to_string().into();
                } else if let Some(g) = gantry_map.get(&end_name) {
                    if let Some(g) = &g.ods_szdn_gantry {
                        if !g.lon.trim().is_empty() {
                            tracks.end_lon = g.lon.as_str().to_string().into();
                        }
                        if !g.lat.trim().is_empty() {
                            tracks.end_lat = g.lat.as_str().to_string().into();
                        }
                    }
                    tracks.extollstationid = g.gantry_code.as_str().to_string().into();
                }
            }
        }

        if !tracks.start_lon.trim().is_empty() {
            tracks.start_lon_dec = parse_f64(&tracks.start_lon).into();
        }
        if !tracks.strat_lat.trim().is_empty() {
            tracks.strat_lat_dec = parse_f64(&tracks.strat_lat).into();
        }
        if !tracks.end_lon.trim().is_empty() {
            tracks.end_lon_dec = parse_f64(&tracks.end_lon).into();
        }
        if !tracks.end_lat.trim().is_empty() {
            tracks.end_lat_dec = parse_f64(&tracks.end_lat).into();
        }

        // PARITY: Java L746-753 在富集结束后无条件把入口站/车型等"瞬态字段"覆盖为
        // 空值（这些局部变量在 Java 里从未被赋值）；Rust 必须同样清空，
        // 否则调用方传入的旧值会被原样带回，前端看到与 Java 不一致的 tracks。
        tracks.firt_station_code = "".into();
        tracks.firt_station_name = "".into();
        tracks.firt_station_time = "".into();
        tracks.plate_color = "".into();
        tracks.car_type = "".into();
        tracks.car_vehicle = "".into();
        tracks.car_num = JLong(None);
        tracks.pass_type = "".into();

        Ok(TrailInfo {
            tracks: Some(Box::new(tracks.clone())),
            trail_list: points.into(),
            ..Default::default()
        })
    }

    pub async fn get_by_trail_bo(&self, trail_bo: &TrailBo) -> AppResult<TrailBo> {
        let mut target = trail_bo.clone();
        let (from, to) = day_range(&target.capture_time);
        let state_type = target.state_type.clone();
        let uuid = target.point_uuid.clone();

        match state_type.as_str() {
            DATA_TYPE_BORDER_WEIGHING => {
                if let Some(item) = self.lookup_weight(&uuid).await {
                    let images = item.weighing_images_arry.as_str().to_string();
                    if !images.trim().is_empty() {
                        match parse_weighing_images(&images) {
                            Ok(s) => target.images_arry = utils::delete_end(&s).into(),
                            Err(e) => {
                                warn!(uuid = %uuid, err = %e, "[轨迹查询] 省界称重图片 JSON 解析失败")
                            }
                        }
                    }
                }
            }
            DATA_TYPE_GANTRY_CAPTURE => {
                if let Some(item) = self.lookup_gantry(&uuid, from, to).await {
                    target.images_arry = item.snappicturepath.as_str().to_string().into();
                    target.platecolor = utils::is_null(Some(item.platecolor.clone())).into();
                }
            }
            DATA_TYPE_PROV_CAPTURE => {
                if let Some(item) = self.lookup_prov(&uuid).await {
                    let mut s = String::new();
                    for v in [&item.plateimage, &item.sideimage, &item.headimage] {
                        if !v.trim().is_empty() {
                            s.push_str(v);
                            s.push(',');
                        }
                    }
                    target.images_arry = utils::delete_end(&s).into();
                }
            }
            DATA_TYPE_SERVICE_AREA_CAPTURE => {
                if let Some(item) = self.lookup_fwq(&uuid).await {
                    let mut s = String::new();
                    for v in [&item.targetpicurl, &item.platepicurl] {
                        if !v.trim().is_empty() {
                            s.push_str(v);
                            s.push(',');
                        }
                    }
                    target.images_arry = utils::delete_end(&s).into();
                }
            }
            DATA_TYPE_STATION_CAPTURE => {
                if let Some(item) = self.lookup_station(&uuid, from, to).await {
                    target.images_arry = item.snappicturepath.as_str().to_string().into();
                }
            }
            DATA_TYPE_FEE_RECORD => {
                if let Some(item) = self.lookup_fee_record(&uuid, from, to).await {
                    target.dev_code = item.gantryid.as_str().to_string().into();
                    target.images_arry.clear();
                }
            }
            DATA_TYPE_FEE_STATION_ENTER => {
                let _ = self.lookup_fee_enter(&uuid).await;
                target.images_arry.clear();
            }
            DATA_TYPE_FEE_STATION_EXIT => {
                let _ = self.lookup_fee_exit(&uuid).await;
                target.images_arry.clear();
            }
            _ => {}
        }
        target.images_arry = utils::replace_pic_url(&utils::delete_end(&target.images_arry)).into();
        Ok(target)
    }

    /// 对应 select...ByQueryUuids(String)：逗号分隔 uuid → 对象 Map（/base/vehicleweight/map）。
    pub async fn weight_capture_map(
        &self,
        uuids: &str,
    ) -> HashMap<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> {
        let mut out = HashMap::new();
        if uuids.trim().is_empty() {
            return out;
        }
        for uuid in uuids.split(',').map(|s| s.trim()).filter(|s| !s.is_empty()) {
            let key = format!("{}{}", DATE_BORDER_WEIGHING_PREFIX, uuid);
            if let Some(c) = &self.cache {
                if let Ok(Some(cached)) = c
                    .get_json::<OdsSzdnProvinceBorderVehicleWeightNewstructure>(&key)
                    .await
                {
                    out.insert(uuid.to_string(), cached);
                    continue;
                }
            }
            match self.weight.list_by_datauuid(uuid).await {
                Ok(list) if !list.is_empty() => {
                    if let Some(c) = &self.cache {
                        let _ = c.set_json(&key, &list[0], Duration::ZERO).await;
                    }
                    out.insert(uuid.to_string(), list[0].clone());
                }
                Ok(_) => {
                    // 未命中：只写负缓存，不进 Map（与 Java 一致）
                    if let Some(c) = &self.cache {
                        let probe = OdsSzdnProvinceBorderVehicleWeightNewstructure {
                            datauuid: uuid.into(),
                            ..Default::default()
                        };
                        let _ = c.set_json(&key, &probe, Duration::ZERO).await;
                    }
                }
                Err(e) => warn!(uuid, err = %e, "[称重抓拍] 回源失败"),
            }
        }
        out
    }

    async fn lookup_weight(
        &self,
        uuid: &str,
    ) -> Option<OdsSzdnProvinceBorderVehicleWeightNewstructure> {
        self.lookup_by_uuid(
            DATE_BORDER_WEIGHING_PREFIX,
            uuid,
            OdsSzdnProvinceBorderVehicleWeightNewstructure {
                datauuid: uuid.into(),
                ..Default::default()
            },
            |this| async move {
                this.weight
                    .list_by_datauuid(uuid)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_gantry(
        &self,
        uuid: &str,
        from: i64,
        to: i64,
    ) -> Option<OdsRtSzdnSnapshotFlowAddcode> {
        self.lookup_by_uuid(
            DATE_GANTRY_PREFIX,
            uuid,
            OdsRtSzdnSnapshotFlowAddcode {
                datauuid: uuid.into(),
                ..Default::default()
            },
            |this| async move {
                this.gantry_capture
                    .list_by_datauuid(uuid, from, to)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_prov(&self, uuid: &str) -> Option<OdsRtSzdnSnapshotFlowProvcaptureAddcode> {
        self.lookup_by_uuid(
            DATE_PROV_PREFIX,
            uuid,
            OdsRtSzdnSnapshotFlowProvcaptureAddcode {
                datauuid: uuid.into(),
                ..Default::default()
            },
            |this| async move {
                this.prov_capture
                    .list_by_datauuid(uuid)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_fwq(&self, uuid: &str) -> Option<OdsCxztFwqclls> {
        self.lookup_by_uuid(
            DATE_SERVICE_AREA_PREFIX,
            uuid,
            OdsCxztFwqclls {
                datauuid: uuid.into(),
                ..Default::default()
            },
            |this| async move {
                this.fwqclls
                    .list_by_datauuid(uuid)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_station(
        &self,
        uuid: &str,
        from: i64,
        to: i64,
    ) -> Option<OdsRtSzdnSnapshotFlowStationcaptureAddcode> {
        self.lookup_by_uuid(
            DATE_STATION_PREFIX,
            uuid,
            OdsRtSzdnSnapshotFlowStationcaptureAddcode {
                datauuid: uuid.into(),
                ..Default::default()
            },
            |this| async move {
                this.station_capture
                    .list_by_datauuid(uuid, from, to)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_fee_record(
        &self,
        cid: &str,
        from: i64,
        to: i64,
    ) -> Option<OdsLwzxsfsjFeeRecords01> {
        self.lookup_by_uuid(
            DATE_FEE_RECORD_PREFIX,
            cid,
            OdsLwzxsfsjFeeRecords01 {
                cid: cid.into(),
                ..Default::default()
            },
            |this| async move {
                this.fee_records
                    .list_by_cid(cid, from, to)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_fee_enter(&self, cid: &str) -> Option<OdsLwzxsfsjFeeStationEnter01> {
        self.lookup_by_uuid(
            DATE_FEE_STATION_ENTER_PREFIX,
            cid,
            OdsLwzxsfsjFeeStationEnter01 {
                cid: cid.into(),
                ..Default::default()
            },
            |this| async move {
                this.fee_enter
                    .list_by_cid(cid)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    async fn lookup_fee_exit(&self, cid: &str) -> Option<OdsLwzxsfsjFeeStationExit01> {
        self.lookup_by_uuid(
            DATE_FEE_STATION_EXIT_PREFIX,
            cid,
            OdsLwzxsfsjFeeStationExit01 {
                cid: cid.into(),
                ..Default::default()
            },
            |this| async move {
                this.fee_exit
                    .list_by_cid(cid)
                    .await
                    .map(|v| v.into_iter().next())
            },
        )
        .await
    }

    /// 先读 Redis，未命中回源；回源为空时写入「探测对象」负缓存（与 Java 一致）。
    async fn lookup_by_uuid<T, F, Fut>(
        &self,
        prefix: &str,
        uuid: &str,
        probe: T,
        load: F,
    ) -> Option<T>
    where
        T: Serialize + DeserializeOwned + Clone,
        F: FnOnce(SysUtilService) -> Fut,
        Fut: std::future::Future<Output = AppResult<Option<T>>>,
    {
        if uuid.trim().is_empty() {
            return None;
        }
        let key = format!("{}{}", prefix, uuid);
        if let Some(c) = &self.cache {
            if let Ok(Some(cached)) = c.get_json::<T>(&key).await {
                return Some(cached);
            }
        }
        let item = match load(self.clone()).await {
            Ok(Some(it)) => it,
            Ok(None) => probe,
            Err(e) => {
                warn!(key, err = %e, "[轨迹查询] 抓拍对象回源失败");
                return None;
            }
        };
        if let Some(c) = &self.cache {
            if let Err(e) = c.set_json(&key, &item, Duration::ZERO).await {
                warn!(key, err = %e, "[轨迹查询] 抓拍对象写缓存失败");
            }
        }
        Some(item)
    }
}

fn pick_from_map<'a, T>(m: &'a HashMap<String, T>, keys: &[&str]) -> Option<&'a T> {
    for k in keys {
        if k.trim().is_empty() {
            continue;
        }
        if let Some(v) = m.get(*k) {
            return Some(v);
        }
    }
    None
}

fn parse_f64(s: &str) -> Option<f64> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse().ok()
    }
}

fn fmt_opt(v: Option<f64>) -> String {
    v.map(|x| x.to_string()).unwrap_or_default()
}

/// captureTime → 当天 00:00:00 ~ 23:59:59 的毫秒区间（0 表示不加条件）。
fn day_range(capture_time: &str) -> (i64, i64) {
    if capture_time.trim().is_empty() {
        return (0, 0);
    }
    match utils::parse_time(capture_time) {
        Ok(t) => {
            let day = t.format("%Y-%m-%d").to_string();
            let from = utils::parse_time(&format!("{} 00:00:00", day)).ok();
            let to = utils::parse_time(&format!("{} 23:59:59", day)).ok();
            (
                from.map(to_millis).unwrap_or(0),
                to.map(to_millis).unwrap_or(0),
            )
        }
        Err(_) => {
            info!(capture_time, "[轨迹查询] 日期解析失败");
            (0, 0)
        }
    }
}

fn to_millis(t: chrono::DateTime<chrono::Utc>) -> i64 {
    t.timestamp_millis()
}

fn parse_weighing_images(raw: &str) -> Result<String, serde_json::Error> {
    #[derive(serde::Deserialize)]
    struct Item {
        #[serde(rename = "snapPicturePath", default)]
        snap_picture_path: String,
    }
    let arr: Vec<Item> = serde_json::from_str(raw)?;
    let mut s = String::new();
    for item in arr {
        if !item.snap_picture_path.trim().is_empty() {
            s.push_str(&item.snap_picture_path);
            s.push(',');
        }
    }
    Ok(s)
}

/// 供 handler 使用：轨迹点去重（等价 mapTrailBoList）。
pub fn map_trail_bo_list(list: Vec<TrailBo>) -> Vec<TrailBo> {
    dedupe_points(list)
}

/// 供 sync 任务使用：当前时间戳（毫秒）。
pub fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// 兼容 Java 的 DateUtils 格式化（供 handler 回显）。
pub fn fmt_time(t: &chrono::DateTime<chrono::Utc>) -> String {
    utils::format_datetime(t)
}
