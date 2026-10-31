// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailFitting.java
// 职责: ZdataTrailFitting —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/zdata_trail_fitting.go（已与 Java 逐字段核对）
// 表: zdata_trail_fitting（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct ZdataTrailFitting {
    #[sqlx(default)]
    pub cid: JString,
    #[sqlx(default)]
    pub enaxlecount: JInt,
    #[sqlx(default)]
    pub entime: Day,
    #[sqlx(default)]
    pub entolllaneid: JString,
    #[sqlx(default)]
    pub entollstationid: JString,
    #[sqlx(default)]
    pub entollstationname: JString,
    #[sqlx(default)]
    pub envehicleclass: JInt,
    #[sqlx(default)]
    pub envehicleid: JString,
    #[sqlx(default)]
    pub envehicletype: JInt,
    #[sqlx(default)]
    pub enweight: JLong,
    #[sqlx(default)]
    pub extime: JIsoDateTime,
    #[sqlx(default)]
    pub extolllaneid: JString,
    #[sqlx(default)]
    pub extollstationid: JString,
    #[sqlx(default)]
    pub extollstationname: JString,
    #[sqlx(default)]
    pub exvehicleclass: JInt,
    #[sqlx(default)]
    pub exvehicleid: JString,
    #[sqlx(default)]
    pub exvehicletype: JInt,
    #[sqlx(default)]
    pub exweight: JLong,
    #[sqlx(default)]
    pub trailpoints: JString,
}
