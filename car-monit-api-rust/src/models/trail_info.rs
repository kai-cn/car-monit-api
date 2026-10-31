// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailInfo.java
// 职责: TrailInfo —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/trail_info.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct TrailInfo {
    #[sqlx(skip)]
    #[serde(rename = "trailUuid")]
    pub trail_uuid: JString,
    #[sqlx(skip)]
    #[serde(rename = "enterTime")]
    pub enter_time: JIsoDateTime,
    #[sqlx(skip)]
    pub tracks: Option<Box<ZdataTrailTracks>>,
    #[sqlx(skip)]
    #[serde(rename = "trailList")]
    pub trail_list: JList<TrailBo>,
}
