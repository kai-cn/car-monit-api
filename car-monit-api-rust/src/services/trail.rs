// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/TrailAggregationService.java:35-445
// 职责: 轨迹补点（位置富集 + 缺失点补齐）、质量评估、多轨迹合并。
// 对应关系:
//   performTrailFitting        ↔ perform_trail_fitting
//   enrichLocationInfo         ↔ enrich_location_info
//   fillMissingPoints          ↔ fill_missing_points
//   assessTrailQuality         ↔ assess_trail_quality
//   mergeTrails                ↔ merge_trails
//
// PARITY: Java 的 tryFillBetween 目前只打日志、不产出补点（TODO），Rust 保持同样空实现：
// 凭空造点会让轨迹变成假数据，比缺点更危险。

use std::collections::HashMap;

use chrono::Utc;
use serde::Serialize;
use tracing::{debug, info, warn};

use crate::error::AppResult;
use crate::models::*;
use crate::services::dict::DictService;
use crate::services::{DATA_TYPE_GANTRY_CAPTURE, DATA_TYPE_STATION_CAPTURE};
use crate::utils;

const FILL_TIME_GAP_THRESHOLD_MINUTES: i64 = 30;

#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct TrailQuality {
    pub score: f64,
    pub level: String,
    pub point_count: usize,
    pub duration_hours: f64,
    pub location_complete_rate: f64,
}

#[derive(Clone)]
pub struct TrailAggregationService {
    pub dict: Option<DictService>,
}

impl TrailAggregationService {
    pub fn new(dict: Option<DictService>) -> Self {
        Self { dict }
    }

    pub async fn perform_trail_fitting(
        &self,
        original: Option<TrailInfo>,
    ) -> AppResult<Option<TrailInfo>> {
        let Some(original) = original else {
            warn!("[轨迹补点] 原始轨迹为空，跳过");
            return Ok(None);
        };
        if original.trail_list.is_empty() {
            warn!(trail_uuid = %original.trail_uuid, "[轨迹补点] 原始轨迹点为空，跳过");
            return Ok(Some(original));
        }
        let original_count = original.trail_list.len();
        let enriched = self.enrich_location_info(&original.trail_list).await?;
        let mut fitted = self.fill_missing_points(enriched);
        // Java: Comparator.comparing(String) —— 字典序
        fitted.sort_by(|a, b| a.capture_time.cmp(&b.capture_time));
        let new_trail = self.build_new_trail_version(&original, fitted);
        info!(
            trail_uuid = %original.trail_uuid,
            original = original_count,
            fitted = new_trail.trail_list.len(),
            added = new_trail.trail_list.len() as i64 - original_count as i64,
            "[轨迹补点] 补点完成"
        );
        Ok(Some(new_trail))
    }

    async fn enrich_location_info(&self, points: &[TrailBo]) -> AppResult<Vec<TrailBo>> {
        let Some(dict) = &self.dict else {
            warn!("[轨迹补点] 字典未装配，跳过位置富集");
            return Ok(points.to_vec());
        };
        let location = dict.location_map().await?;
        let gantry_ip = dict.gantry_ip_map().await?;
        let station_ip = dict.station_ip_map().await?;
        let section = dict.section_map().await?;

        let mut out = Vec::with_capacity(points.len());
        for p in points {
            let mut e = p.clone();
            let code = e.location_code.as_str().to_string();
            if !code.trim().is_empty() {
                if let Some(loc) = location.get(&code) {
                    enrich_from_location_dict(&mut e, loc);
                }
                if let Some(g) = gantry_ip.get(&code) {
                    enrich_from_gantry_ip(&mut e, g);
                }
                if let Some(s) = station_ip.get(&code) {
                    enrich_from_station_ip(&mut e, s);
                }
                let _ = &section; // Java 侧该参数未使用，保留加载顺序
            }
            out.push(e);
        }
        Ok(out)
    }

    fn fill_missing_points(&self, points: Vec<TrailBo>) -> Vec<TrailBo> {
        if points.len() < 2 {
            return points;
        }
        let mut result = Vec::with_capacity(points.len());
        result.push(points[0].clone());
        for i in 1..points.len() {
            let (prev, curr) = (&points[i - 1], &points[i]);
            result.push(curr.clone());
            let fill = self.try_fill_between(prev, curr);
            if !fill.is_empty() {
                let tail = result.pop().unwrap();
                result.extend(fill);
                result.push(tail);
            }
        }
        result
    }

    fn try_fill_between(&self, prev: &TrailBo, curr: &TrailBo) -> Vec<TrailBo> {
        if prev.section_code.trim().is_empty() || curr.section_code.trim().is_empty() {
            return vec![];
        }
        if prev.section_code != curr.section_code {
            return vec![];
        }
        let Ok(pt) = utils::parse_time(&prev.capture_time) else {
            return vec![];
        };
        let Ok(ct) = utils::parse_time(&curr.capture_time) else {
            return vec![];
        };
        if (ct - pt).num_minutes().abs() > FILL_TIME_GAP_THRESHOLD_MINUTES {
            debug!(prev = %prev.point_uuid, curr = %curr.point_uuid, "[轨迹补点] 发现可能缺失点");
        }
        // TODO（与 Java 一致）：接入路段门架序列后生成虚拟补点
        vec![]
    }

    fn build_new_trail_version(&self, original: &TrailInfo, points: Vec<TrailBo>) -> TrailInfo {
        let mut tracks = original.tracks.as_deref().cloned().unwrap_or_default();
        tracks.point_count = JLong::from(points.len() as i64);
        if let (Some(first), Some(last)) = (points.first(), points.last()) {
            tracks.enter_time = parse_jdt(&first.capture_time);
            tracks.exit_time = parse_jdt(&last.capture_time);
        }
        if points.len() >= 5 {
            tracks.r#type = JInt::from(1);
        }
        tracks.trail_points = serde_json::to_string(&points).unwrap_or_default().into();
        TrailInfo {
            trail_uuid: original.trail_uuid.clone(),
            enter_time: original.enter_time,
            tracks: Some(Box::new(tracks)),
            trail_list: points.into(),
        }
    }

    pub fn assess_trail_quality(&self, trail: Option<&TrailInfo>) -> TrailQuality {
        let Some(trail) = trail else {
            return TrailQuality {
                level: "EMPTY".into(),
                ..Default::default()
            };
        };
        if trail.trail_list.is_empty() {
            return TrailQuality {
                level: "EMPTY".into(),
                ..Default::default()
            };
        }
        let points = &trail.trail_list;
        let n = points.len();
        let point_score = (1.0f64).min(n as f64 / 10.0) * 30.0;
        let first = utils::parse_time(&points[0].capture_time).unwrap_or_else(|_| Utc::now());
        let last = utils::parse_time(&points[n - 1].capture_time).unwrap_or_else(|_| Utc::now());
        let duration_hours = (last - first).num_minutes() as f64 / 60.0;
        let duration_score = (1.0f64).min(duration_hours / 2.0) * 30.0;
        let complete = points
            .iter()
            .filter(|p| p.lon.get().is_some() && p.lat.get().is_some())
            .count();
        let location_score = complete as f64 / n as f64 * 40.0;
        let total = point_score + duration_score + location_score;
        let level = if total >= 90.0 {
            "EXCELLENT"
        } else if total >= 70.0 {
            "GOOD"
        } else if total >= 50.0 {
            "FAIR"
        } else {
            "POOR"
        };
        TrailQuality {
            score: total,
            level: level.into(),
            point_count: n,
            duration_hours,
            location_complete_rate: complete as f64 / n as f64,
        }
    }

    pub fn merge_trails(&self, trails: Vec<TrailInfo>) -> Option<TrailInfo> {
        if trails.is_empty() {
            return None;
        }
        if trails.len() == 1 {
            return trails.into_iter().next();
        }
        info!(count = trails.len(), "[轨迹合并] 开始合并");
        let mut all: Vec<TrailBo> = trails
            .iter()
            .flat_map(|t| t.trail_list.value.clone())
            .collect();
        if all.is_empty() {
            warn!("[轨迹合并] 所有轨迹点均为空，返回空结果");
            return None;
        }
        all.sort_by(|a, b| a.capture_time.cmp(&b.capture_time));
        let first_uuid = trails[0]
            .tracks
            .as_deref()
            .map(|t| t.uuid.clone())
            .unwrap_or_default();
        let first_plate = trails[0]
            .tracks
            .as_deref()
            .map(|t| t.plate_key.clone())
            .unwrap_or_default();
        let mut tracks = ZdataTrailTracks {
            uuid: first_uuid.clone(),
            plate_key: first_plate,
            point_count: JLong::from(all.len() as i64),
            enter_time: parse_jdt(&all[0].capture_time),
            exit_time: parse_jdt(&all[all.len() - 1].capture_time),
            r#type: JInt::from(if all.len() >= 5 { 1 } else { 0 }),
            trail_points: serde_json::to_string(&all).unwrap_or_default().into(),
            ..Default::default()
        };
        if tracks.plate_key.is_empty() {
            tracks.plate_key = trails[0]
                .tracks
                .as_deref()
                .map(|t| t.plate_key.clone())
                .unwrap_or_default();
        }
        Some(TrailInfo {
            trail_uuid: tracks.uuid.clone(),
            enter_time: JIsoDateTime::default(),
            tracks: Some(Box::new(tracks)),
            trail_list: all.into(),
        })
    }
}

fn parse_f64(s: &str) -> Option<f64> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse::<f64>().ok()
    }
}

fn parse_jdt(s: &str) -> JDateTime {
    if s.trim().is_empty() {
        return JDateTime::default();
    }
    utils::parse_time(s)
        .ok()
        .map(JDateTime::new)
        .unwrap_or_default()
}

fn enrich_from_location_dict(point: &mut TrailBo, loc: &ZdataLocationDict) {
    if point.lon.get().is_none() {
        point.lon = loc.longitude.get().into();
    }
    if point.lat.get().is_none() {
        point.lat = loc.latitude.get().into();
    }
    if point.road_code.trim().is_empty() {
        point.road_code = loc.roadcode.as_str().to_string().into();
    }
    if point.section_code.trim().is_empty() {
        point.section_code = loc.sectioncode.as_str().to_string().into();
    }
    if point.dev_name.trim().is_empty() {
        point.dev_name = loc.name.as_str().to_string().into();
    }
    point.standard_code = loc.standard_code.as_str().to_string().into();
}

fn enrich_from_gantry_ip(point: &mut TrailBo, ip: &OdsSzdnGantryIp) {
    point.gantry_ip_bo = Some(Box::new(ip.clone()));
    point.dev_code = ip.gantry_code.as_str().to_string().into();
    point.dev_name = ip.gantry_name.as_str().to_string().into();
    if let Some(g) = &ip.ods_szdn_gantry {
        if point.lon.get().is_none() {
            point.lon = parse_f64(&g.lon).into();
        }
        if point.lat.get().is_none() {
            point.lat = parse_f64(&g.lat).into();
        }
        if point.road_code.trim().is_empty() {
            point.road_code = g.road_code.as_str().to_string().into();
        }
        if point.section_code.trim().is_empty() {
            point.section_code = g.section_code.as_str().to_string().into();
        }
        if point.pileno.trim().is_empty() {
            point.pileno = g.pile_no.as_str().to_string().into();
        }
        point.direction = g.direction.as_str().to_string().into();
        point.is_virtual = g.is_virtual.as_str().to_string().into();
    }
    point.location_flag = "1".into();
}

fn enrich_from_station_ip(point: &mut TrailBo, ip: &OdsSzdnTollStationIp) {
    point.station_ip_bo = Some(Box::new(ip.clone()));
    point.dev_code = ip.toll_code.as_str().to_string().into();
    point.dev_name = ip.toll_name.as_str().to_string().into();
    if let Some(t) = &ip.ods_szdn_toll {
        if point.lon.get().is_none() {
            point.lon = parse_f64(&t.longitude).into();
        }
        if point.lat.get().is_none() {
            point.lat = parse_f64(&t.latitude).into();
        }
        if point.road_code.trim().is_empty() {
            point.road_code = t.road_code.as_str().to_string().into();
        }
        if point.section_code.trim().is_empty() {
            point.section_code = t.section_code.as_str().to_string().into();
        }
    }
    point.location_flag = "1".into();
}

/// 取出第一个括号平衡的 JSON 数组（对应 FastJSON parseArray「读到一个数组就停」）。
fn json_array_prefix(s: &str) -> Option<&str> {
    let bytes = s.as_bytes();
    let start = bytes.iter().position(|b| *b == b'[')?;
    let mut depth = 0usize;
    let mut in_str = false;
    let mut escaped = false;
    for i in start..bytes.len() {
        let b = bytes[i];
        if in_str {
            if escaped {
                escaped = false;
            } else if b == b'\\' {
                escaped = true;
            } else if b == b'"' {
                in_str = false;
            }
            continue;
        }
        match b {
            b'"' => in_str = true,
            b'[' | b'{' => depth += 1,
            b']' | b'}' => {
                depth -= 1;
                if depth == 0 && b == b']' {
                    return Some(&s[start..=i]);
                }
            }
            _ => {}
        }
    }
    None
}

/// 供 SysUtilService 复用：按字段白名单提取轨迹点。
pub fn parse_trail_points(raw: &str) -> Vec<TrailBo> {
    let mut s = raw.trim().to_string();
    if s.is_empty() || s == "{}" {
        return vec![];
    }
    s = s.replace('\\', "");
    s = s.replace("{\"{", "[{");
    s = s.replace("}\"}", "}]");
    s = s.replace("\",\"{", ",{");
    s = s.replace("ZdTrails:", "");
    let arr: Vec<serde_json::Value> = match serde_json::from_str(&s) {
        Ok(v) => v,
        // PARITY: 历史轨迹的 trailpoints 是 jsonb 里塞了一段被转义过的数组文本，
        // Java 侧 replace 之后尾部仍残留引号/花括号等脏字符；FastJSON 的 parseArray
        // 只要求前缀是一个完整数组就返回，serde 严格解析会整体失败 → trailList 空，
        // 起终点经纬度也随之丢失。这里补一次「取平衡数组前缀」的重试。
        Err(e) => match json_array_prefix(&s) {
            Some(prefix) => match serde_json::from_str(prefix) {
                Ok(v) => v,
                Err(_) => {
                    warn!(err = %e, raw = %s, "[轨迹查询] 轨迹点 JSON 解析失败");
                    return vec![];
                }
            },
            None => {
                warn!(err = %e, raw = %s, "[轨迹查询] 轨迹点 JSON 解析失败");
                return vec![];
            }
        },
    };
    let mut out = Vec::with_capacity(arr.len());
    for obj in arr {
        // PARITY: FastJSON 的 `JSONObject.getString(key)` 在 key 不存在时返回 **null**，
        // 于是 Java 侧对应字段保持 null；之前 Rust 统一给成空串，响应里就多了
        // `"orgCode": ""` 这种 Java 没有的值。这里改成 Option，缺键即 None。
        let get = |k: &str| -> Option<String> {
            obj.get(k).and_then(|v| match v {
                serde_json::Value::Null => None,
                serde_json::Value::String(s) => Some(s.clone()),
                other => Some(other.to_string().trim_matches('"').to_string()),
            })
        };
        let mut bo = TrailBo::default();
        // PARITY: Java 只在含 "T" 时赋值 captureTime，其余保持空串。
        let capture = get("captureTime").unwrap_or_default();
        if capture.contains('T') {
            if let Ok(t) = utils::parse_time(&capture) {
                bo.capture_time = utils::format_datetime(&t).into();
            }
        }
        bo.state_type = get("stateType").into();
        bo.platenumber = get("platenumber").into();
        bo.location_id = get("locationId").into();
        bo.location_code = get("locationCode").into();
        bo.point_uuid = get("pointUuid").into();
        bo.section_code = get("sectionCode").into();
        bo.org_code = get("orgCode").into();
        bo.pileno = get("pileNo").into();
        // Java: CommonUtil.isNotBlank(lon) → new BigDecimal(lon)
        if let Some(lon) = get("lon") {
            if !lon.trim().is_empty() {
                bo.lon = parse_f64(&lon).into();
            }
        }
        if let Some(lat) = get("lat") {
            if !lat.trim().is_empty() {
                bo.lat = parse_f64(&lat).into();
            }
        }
        out.push(bo);
    }
    dedupe_points(out)
}

/// 对应 mapTrailBoList：同一 stateType+locationCode 4 分钟内只保留一条，图片逗号累加。
pub fn dedupe_points(list: Vec<TrailBo>) -> Vec<TrailBo> {
    let mut out: Vec<TrailBo> = Vec::with_capacity(list.len());
    let mut seen: HashMap<String, usize> = HashMap::new();
    for bo in list {
        let key = format!("{}{}", bo.state_type.trim(), bo.location_code.trim());
        let images = utils::delete_end(&bo.images_arry);
        let remember =
            bo.state_type == DATA_TYPE_GANTRY_CAPTURE || bo.state_type == DATA_TYPE_STATION_CAPTURE;
        if let Some(&idx) = seen.get(&key) {
            let prev_time = out[idx].capture_time.clone();
            let curr_time = bo.capture_time.clone();
            if !curr_time.trim().is_empty() && !prev_time.trim().is_empty() {
                match (utils::parse_time(&curr_time), utils::parse_time(&prev_time)) {
                    (Ok(t1), Ok(t2)) => {
                        if (t2 - t1).num_minutes().abs() > 4 {
                            out.push(bo);
                        } else if !images.is_empty() {
                            let prev_images = utils::delete_end(&out[idx].images_arry);
                            out[idx].images_arry = if prev_images.is_empty() {
                                images.into()
                            } else {
                                format!("{},{}", prev_images, images).into()
                            };
                        }
                    }
                    _ => out.push(bo),
                }
            } else {
                out.push(bo);
            }
        } else {
            out.push(bo);
        }
        if remember {
            // 只记录最新一条（对应 Java 的 seen.put 覆盖）
            seen.insert(key, out.len() - 1);
        }
    }
    out
}
