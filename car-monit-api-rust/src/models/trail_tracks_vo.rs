// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailTracksVo.java
// 职责: TrailTracksVo —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/trail_tracks_vo.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct TrailTracksVo {
    #[sqlx(skip)]
    #[serde(rename = "plateKey")]
    pub plate_key: JString,
    #[sqlx(skip)]
    #[serde(rename = "enterTime")]
    pub enter_time: JDateTime,
    #[sqlx(skip)]
    #[serde(rename = "exitTime")]
    pub exit_time: JDateTime,
    #[sqlx(skip)]
    pub trailpoints: JString,
    #[sqlx(skip)]
    pub envehicletype: JString,
}
