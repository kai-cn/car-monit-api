// 来源:
//   SysUtilServiceImpl.java:284-387      syncTrack（实时轨迹落缓存）
//   TrackTask.java:54-59                 syncCurrentTrack（每 3 分钟）
//   TrackTask.java:84-160                syncHistroyTrack（每天 4 点）
// 职责: 重点车辆（car_list_jc）的实时/历史轨迹缓存链路。
// 对应关系:
//   redisCache.getCacheObject(car_list_jc)        ↔ key_vehicles
//   redisCache.getCacheObject("trail:"+carNo)     ↔ cache.get
//   redisCache.setCacheObject(car_curent_trail:*) ↔ cache.set_json
//   redisCache.setCacheObject(car_history_trail:*) ↔ cache.set_json
//
// PARITY（照抄）:
//   1. Java 变量名 threeMinutesInMillis 实际是 24 小时，阈值按 24h；
//   2. 缓存键是 car_curent_trail（少一个 r），改名会让灰度期读不到旧键；
//   3. 生产环境 Java 从独立的 rediscluster 读 trail:{carNo}；Rust 侧当前读主 Redis
//      （与 Go 版一致），接入前生产实时轨迹会是空的。

use std::collections::HashSet;
use std::time::Duration;

use tracing::{info, warn};

use crate::error::AppResult;
use crate::models::*;
use crate::services::sysutil::SysUtilService;
use crate::services::trail::dedupe_points;
use crate::services::*;
use crate::utils;

impl SysUtilService {
    async fn key_vehicles(&self) -> Vec<CarVO> {
        let Some(c) = &self.cache else { return vec![] };
        match c.get_json::<Vec<CarVO>>(CAR_LIST_JC).await {
            Ok(Some(list)) => list,
            Ok(None) => {
                info!(key = CAR_LIST_JC, "[轨迹同步] 重点车辆缓存为空，本轮跳过");
                vec![]
            }
            Err(e) => {
                warn!(key = CAR_LIST_JC, err = %e, "[轨迹同步] 重点车辆缓存解析失败");
                vec![]
            }
        }
    }

    /// 对应 syncTrack：把 trail:{carNo} 富集后写入 car_curent_trail:{carNo}。
    pub async fn sync_track(&self) -> AppResult<()> {
        let vehicles = self.key_vehicles().await;
        if vehicles.is_empty() {
            return Ok(());
        }
        let local = self.env.eq_ignore_ascii_case("local");
        let now = chrono::Utc::now();
        let today = now.format("%Y%m%d").to_string();
        info!(env = %self.env, cars = vehicles.len(), "[实时轨迹同步] 开始");

        for car in vehicles {
            let car_no = car.car_no.trim().to_string();
            if car_no.is_empty() {
                continue;
            }
            let Some(cache) = &self.cache else { continue };
            let key = format!("trail:{}", car_no);
            let raw = match cache.get(&key).await {
                Ok(Some(v)) if !v.trim().is_empty() => v,
                Ok(_) => continue,
                Err(e) => {
                    warn!(car_no, err = %e, "[实时轨迹同步] 读取原始轨迹失败");
                    continue;
                }
            };
            let arr: Vec<serde_json::Value> = match serde_json::from_str(&raw) {
                Ok(v) => v,
                Err(e) => {
                    warn!(car_no, err = %e, "[实时轨迹同步] 轨迹点不是合法 JSON 数组，跳过该车");
                    continue;
                }
            };
            let mut points = Vec::with_capacity(arr.len());
            for p in arr {
                let get = |k: &str| -> String {
                    p.get(k)
                        .map(|v| match v {
                            serde_json::Value::String(s) => s.clone(),
                            other => other.to_string().trim_matches('"').to_string(),
                        })
                        .unwrap_or_default()
                };
                let mut bo = TrailBo {
                    point_uuid: get("pointUuid").into(),
                    state_type: get("stateType").into(),
                    capture_time: get("captureTime").into(),
                    location_code: get("locationCode").into(),
                    location_name: get("locationName").into(),
                    standard_code: get("standardCode").into(),
                    location_id: get("locationId").into(),
                    platenumber: get("platenumber").into(),
                    ..Default::default()
                };
                bo.dev_code = bo.standard_code.clone();
                bo.dev_name = bo.location_name.clone();
                bo.lon = parse_f64(&get("longitude")).into();
                bo.lat = parse_f64(&get("latitude")).into();
                if !local {
                    // PARITY: 变量名叫 threeMinutesInMillis，实际窗口 24 小时。
                    match utils::parse_time(&bo.capture_time) {
                        Ok(t) if (now - t).num_hours().abs() <= 24 => {}
                        _ => continue,
                    }
                }
                points.push(bo);
            }
            let rtn = dedupe_points(points);
            if rtn.is_empty() {
                continue;
            }
            let mut tracks = ZdataTrailTracks {
                plate_key: car_no.clone().into(),
                uuid: format!("{}@@{}", car_no, today).into(),
                flag: "currentTrack".to_string().into(),
                ..Default::default()
            };
            let info = self.change_data(&mut tracks, rtn).await?;
            let key = format!("{}{}", CAR_CURRENT_TRAIL_PREFIX, car_no);
            cache.set_json(&key, &info, Duration::ZERO).await?;
        }
        Ok(())
    }

    /// 对应 TrackTask.syncHistroyTrack：逐车回放历史轨迹，与 car_history_trail 旧数据按 uuid 合并。
    pub async fn sync_history_track(&self) -> AppResult<()> {
        let vehicles = self.key_vehicles().await;
        if vehicles.is_empty() {
            return Ok(());
        }
        let cars: Vec<String> = vehicles
            .into_iter()
            .map(|c| c.car_no.as_str().to_string())
            .filter(|s| !s.trim().is_empty())
            .collect();
        info!(cars = cars.len(), "[历史轨迹同步] 开始");
        for car_no in cars {
            let Some(cache) = &self.cache else { continue };
            let sync_key = format!("{}{}", CAR_SYNC_TIME_PREFIX, car_no);
            let last_sync = cache.get(&sync_key).await.unwrap_or(None);
            let vo = CarParaVO {
                car_no: car_no.clone().into(),
                car_no_list: vec![car_no.clone()].into(),
                flag: if last_sync.as_deref().unwrap_or("").is_empty() {
                    "bannian".into()
                } else {
                    "yiyue".into()
                },
                ..Default::default()
            };
            let rows = self.trail.get_history_trail(&vo, 0).await?;
            let mut merged: Vec<ZdataTrailTracks> = rows;
            let history_key = format!("{}{}", CAR_HISTORY_TRAIL_PREFIX, car_no);
            if let Ok(Some(old)) = cache.get_json::<Vec<ZdataTrailTracks>>(&history_key).await {
                let mut seen: HashSet<String> =
                    merged.iter().map(|r| r.uuid.as_str().to_string()).collect();
                for o in old {
                    if seen.insert(o.uuid.as_str().to_string()) {
                        merged.push(o);
                    }
                }
            }
            merged.sort_by(|a, b| b.uuid.cmp(&a.uuid));
            cache
                .set_json(&history_key, &merged, Duration::ZERO)
                .await?;
            cache
                .set(&sync_key, utils::format_datetime(&chrono::Utc::now()))
                .await?;
        }
        Ok(())
    }
}

fn parse_f64(s: &str) -> Option<f64> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse().ok()
    }
}
