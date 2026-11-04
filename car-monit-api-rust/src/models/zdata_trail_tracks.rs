// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailTracks.java
// 职责: ZdataTrailTracks —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/zdata_trail_tracks.go（已与 Java 逐字段核对）
// 表: zdata_trail_tracks（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct ZdataTrailTracks {
    #[sqlx(default)]
    pub uuid: JString,
    #[sqlx(rename = "type")]
    #[sqlx(default)]
    #[serde(rename = "type")]
    pub r#type: JInt,
    #[sqlx(default)]
    #[serde(rename = "pointCount")]
    pub point_count: JLong,
    #[sqlx(default)]
    #[serde(rename = "plateKey")]
    pub plate_key: JString,
    #[sqlx(default)]
    #[serde(rename = "enterTime")]
    pub enter_time: JDateTime,
    #[sqlx(default)]
    #[serde(rename = "exitTime")]
    pub exit_time: JDateTime,
    #[sqlx(default)]
    #[serde(rename = "trailPoints")]
    pub trail_points: JString,
    #[sqlx(default)]
    #[serde(rename = "enterLocationcode")]
    pub enter_locationcode: JString,
    #[sqlx(default)]
    #[serde(rename = "exitLocationcode")]
    pub exit_locationcode: JString,
    #[sqlx(skip)]
    #[serde(rename = "trackJosn")]
    pub track_josn: JString,
    #[sqlx(default)]
    pub enaxlecount: JInt,
    #[sqlx(default)]
    pub entolllaneid: JString,
    #[sqlx(default)]
    pub entollstationid: JString,
    #[sqlx(default)]
    pub entollstationname: JString,
    #[sqlx(default)]
    pub envehicleclass: JString,
    #[sqlx(default)]
    pub envehicleid: JString,
    #[sqlx(default)]
    pub envehicletype: JString,
    #[sqlx(default)]
    pub enweight: JDecimal,
    #[sqlx(default)]
    pub extolllaneid: JString,
    #[sqlx(default)]
    pub extollstationid: JString,
    #[sqlx(default)]
    pub extollstationname: JString,
    #[sqlx(default)]
    pub exvehicleclass: JString,
    #[sqlx(default)]
    pub exvehicleid: JString,
    #[sqlx(default)]
    pub exvehicletype: JString,
    #[sqlx(default)]
    pub exweight: JDecimal,
    #[sqlx(skip)]
    #[serde(rename = "startLon")]
    pub start_lon: JString,
    #[sqlx(skip)]
    #[serde(rename = "stratLat")]
    pub strat_lat: JString,
    #[sqlx(skip)]
    #[serde(rename = "endLon")]
    pub end_lon: JString,
    #[sqlx(skip)]
    #[serde(rename = "endLat")]
    pub end_lat: JString,
    #[sqlx(skip)]
    #[serde(rename = "firtStationCode")]
    pub firt_station_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "firtStationName")]
    pub firt_station_name: JString,
    #[sqlx(skip)]
    #[serde(rename = "firtStationTime")]
    pub firt_station_time: JString,
    #[sqlx(skip)]
    #[serde(rename = "plateColor")]
    pub plate_color: JString,
    #[sqlx(skip)]
    #[serde(rename = "carType")]
    pub car_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "carNo")]
    pub car_no: JString,
    #[sqlx(skip)]
    #[serde(rename = "carVehicle")]
    pub car_vehicle: JString,
    #[sqlx(skip)]
    #[serde(rename = "carNum")]
    pub car_num: JLong,
    #[sqlx(skip)]
    #[serde(rename = "passType")]
    pub pass_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "escapedType")]
    pub escaped_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "escapedTypeRemark")]
    pub escaped_type_remark: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime1")]
    pub apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime2")]
    pub apply_time2: JString,
    #[sqlx(skip)]
    pub flag: JString,
    #[sqlx(skip)]
    #[serde(rename = "startLonDec")]
    pub start_lon_dec: JFloat,
    #[sqlx(skip)]
    #[serde(rename = "stratLatDec")]
    pub strat_lat_dec: JFloat,
    #[sqlx(skip)]
    #[serde(rename = "endLonDec")]
    pub end_lon_dec: JFloat,
    #[sqlx(skip)]
    #[serde(rename = "endLatDec")]
    pub end_lat_dec: JFloat,
    #[sqlx(skip)]
    #[serde(rename = "escapedTfcj")]
    pub escaped_tfcj: JString,
    #[sqlx(skip)]
    pub trailtype: JString,
}
