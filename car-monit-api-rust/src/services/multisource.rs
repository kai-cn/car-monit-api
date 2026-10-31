// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/MultiSourceDataFlowService.java
// 职责: 6 类数据源 → TrailBo → Redis 实时轨迹拼接 + 乱序待处理队列。
// 对应关系:
//   processData(data,dataType)       ↔ process_data
//   tryAppendToTrail / createNewTrail ↔ try_append_to_trail / create_new_trail
//   addToPendingQueue / processPendingQueue ↔ add_to_pending_queue / process_pending_queue
//
// PARITY: Java 把 TrailInfo / PendingEvent 直接塞进 Redis（JDK 序列化），Rust 只能存 JSON，
// 因此 trail:realtime:* / trail:pending:* 两类 key 不能跨版本共用，切换前需清空。

use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::cache::Cache;
use crate::error::AppResult;
use crate::models::*;
use crate::utils;

const REALTIME_TRAIL_KEY_PREFIX: &str = "trail:realtime:";
const PENDING_QUEUE_KEY_PREFIX: &str = "trail:pending:";
const MAX_PENDING_RETRY: i32 = 3;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PendingEvent {
    pub event: TrailBo,
    pub retry_count: i32,
    pub create_time: String,
}

#[derive(Clone)]
pub struct MultiSourceService {
    pub cache: Option<Cache>,
}

impl MultiSourceService {
    pub fn new(cache: Option<Cache>) -> Self {
        Self { cache }
    }

    /// 对应 processData：把事件拼接到实时轨迹，乱序时进入待处理队列。
    pub async fn process_data(&self, data: serde_json::Value, data_type: &str) -> AppResult<()> {
        let Some(cache) = &self.cache else {
            return Ok(());
        };
        let mut event = normalize_event(&data, data_type);
        let plate = event.platenumber.trim().to_string();
        if plate.is_empty() {
            warn!("[多源数据] 事件缺少车牌，跳过");
            return Ok(());
        }
        event.platenumber = plate.clone().into();

        let key = format!("{}{}", REALTIME_TRAIL_KEY_PREFIX, plate);
        let existing = cache.get_json::<TrailInfo>(&key).await?;
        match existing {
            None => self.create_new_trail(cache, &key, &plate, event).await?,
            Some(mut trail) => {
                if self.try_append_to_trail(&mut trail, &event) {
                    cache
                        .set_json(&key, &trail, std::time::Duration::ZERO)
                        .await?;
                } else if let Some(last) = trail.trail_list.last() {
                    if !last.capture_time.is_empty() && event.capture_time < last.capture_time {
                        self.add_to_pending_queue(cache, &plate, event.clone())
                            .await?;
                    } else {
                        trail.trail_list.push(event.clone());
                        trail
                            .trail_list
                            .sort_by(|a, b| a.capture_time.cmp(&b.capture_time));
                        cache
                            .set_json(&key, &trail, std::time::Duration::ZERO)
                            .await?;
                    }
                }
            }
        }
        Ok(())
    }

    fn try_append_to_trail(&self, trail: &mut TrailInfo, event: &TrailBo) -> bool {
        if let Some(last) = trail.trail_list.last() {
            if event.capture_time >= last.capture_time {
                trail.trail_list.push(event.clone());
                if let Some(tracks) = trail.tracks.as_deref_mut() {
                    tracks.point_count = JLong::from(trail.trail_list.len() as i64);
                    tracks.exit_time = utils::parse_time(&event.capture_time)
                        .ok()
                        .map(JDateTime::new)
                        .unwrap_or_default();
                }
                return true;
            }
        }
        false
    }

    async fn create_new_trail(
        &self,
        cache: &Cache,
        key: &str,
        plate: &str,
        event: TrailBo,
    ) -> AppResult<()> {
        let tracks = ZdataTrailTracks {
            uuid: format!("{}-{}", plate, uuid::Uuid::new_v4().simple()).into(),
            plate_key: plate.into(),
            point_count: JLong::from(1),
            enter_time: utils::parse_time(&event.capture_time)
                .ok()
                .map(JDateTime::new)
                .unwrap_or_default(),
            exit_time: utils::parse_time(&event.capture_time)
                .ok()
                .map(JDateTime::new)
                .unwrap_or_default(),
            ..Default::default()
        };
        let trail = TrailInfo {
            trail_uuid: tracks.uuid.clone(),
            tracks: Some(Box::new(tracks)),
            trail_list: vec![event].into(),
            ..Default::default()
        };
        cache
            .set_json(key, &trail, std::time::Duration::ZERO)
            .await?;
        Ok(())
    }

    async fn add_to_pending_queue(
        &self,
        cache: &Cache,
        plate: &str,
        event: TrailBo,
    ) -> AppResult<()> {
        let pending = PendingEvent {
            event,
            retry_count: 0,
            create_time: utils::format_datetime(&chrono::Utc::now()),
        };
        let key = format!("{}{}", PENDING_QUEUE_KEY_PREFIX, plate);
        cache
            .right_push(&key, serde_json::to_string(&pending)?)
            .await?;
        Ok(())
    }

    /// 对应 @Scheduled processPendingQueue：每分钟处理乱序待拼接队列。
    pub async fn process_pending_queue(&self) {
        let Some(cache) = &self.cache else { return };
        let keys = match cache
            .scan_keys(&format!("{}*", PENDING_QUEUE_KEY_PREFIX))
            .await
        {
            Ok(v) => v,
            Err(e) => {
                warn!(err = %e, "[多源数据] 扫描待处理队列失败");
                return;
            }
        };
        if keys.is_empty() {
            return;
        }
        info!(queues = keys.len(), "[多源数据] 处理待拼接队列");
        for queue_key in keys {
            let plate = queue_key
                .strip_prefix(PENDING_QUEUE_KEY_PREFIX)
                .unwrap_or("")
                .to_string();
            if plate.is_empty() {
                continue;
            }
            let items = cache
                .list_range(&queue_key, 0, -1)
                .await
                .unwrap_or_default();
            let _ = cache.del(&[queue_key.clone()]).await;
            let trail_key = format!("{}{}", REALTIME_TRAIL_KEY_PREFIX, plate);
            let mut trail = cache
                .get_json::<TrailInfo>(&trail_key)
                .await
                .ok()
                .flatten()
                .unwrap_or_default();
            for raw in items {
                let mut pending: PendingEvent = match serde_json::from_str(&raw) {
                    Ok(v) => v,
                    Err(e) => {
                        warn!(err = %e, "[多源数据] 待处理事件解析失败，丢弃");
                        continue;
                    }
                };
                if !self.try_append_to_trail(&mut trail, &pending.event) {
                    pending.retry_count += 1;
                    if pending.retry_count < MAX_PENDING_RETRY {
                        let _ = cache
                            .right_push(
                                &queue_key,
                                serde_json::to_string(&pending).unwrap_or_default(),
                            )
                            .await;
                    } else {
                        warn!(plate = %plate, "[多源数据] 待处理事件超过重试上限，丢弃");
                    }
                }
            }
            trail
                .trail_list
                .sort_by(|a, b| a.capture_time.cmp(&b.capture_time));
            let _ = cache
                .set_json(&trail_key, &trail, std::time::Duration::ZERO)
                .await;
        }
    }
}

/// 把任意来源实体规约成统一 TrailBo（对应 Java 的 convertToStandardEvent）。
fn normalize_event(data: &serde_json::Value, data_type: &str) -> TrailBo {
    let obj = data.as_object();
    let get = |k: &str| -> String {
        obj.and_then(|o| o.get(k))
            .map(|v| match v {
                serde_json::Value::String(s) => s.clone(),
                serde_json::Value::Null => String::new(),
                other => other.to_string().trim_matches('"').to_string(),
            })
            .unwrap_or_default()
    };
    let lon = get("lon")
        .parse::<f64>()
        .ok()
        .or_else(|| get("longitude").parse().ok());
    let lat = get("lat")
        .parse::<f64>()
        .ok()
        .or_else(|| get("latitude").parse().ok());
    let capture_time = first_non_empty(&[
        get("snapshottime"),
        get("transtime"),
        get("extime"),
        get("captureTime"),
    ]);
    TrailBo {
        point_uuid: first_non_empty(&[get("datauuid"), get("uuid"), get("bigId"), get("cid")])
            .into(),
        state_type: if get("stateType").is_empty() {
            data_type.to_string()
        } else {
            get("stateType")
        }
        .into(),
        capture_time: capture_time.into(),
        location_code: first_non_empty(&[
            get("locationCode"),
            get("deviceip"),
            get("gantrycode"),
            get("tollcode"),
        ])
        .into(),
        platenumber: first_non_empty(&[
            get("platenumber"),
            get("vehicleplate"),
            get("envehicleid"),
            get("platenumber"),
        ])
        .into(),
        section_code: get("sectioncode").into(),
        org_code: get("orgcode").into(),
        pileno: get("pileno").into(),
        road_code: get("roadcode").into(),
        lon: lon.into(),
        lat: lat.into(),
        ..Default::default()
    }
}

fn first_non_empty(values: &[String]) -> String {
    values
        .iter()
        .find(|v| !v.trim().is_empty())
        .cloned()
        .unwrap_or_default()
}
