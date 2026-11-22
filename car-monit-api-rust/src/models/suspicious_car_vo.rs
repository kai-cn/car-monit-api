// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/SuspiciousCarVO.java
// 职责: SuspiciousCarVO —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/suspicious_car_vo.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct SuspiciousCarVO {
    #[sqlx(skip)]
    #[serde(rename = "signatureKey")]
    pub signature_key: JString,
    #[sqlx(skip)]
    #[serde(rename = "timeStamp")]
    pub time_stamp: JLong,
    #[sqlx(skip)]
    pub signature: JString,
    #[sqlx(skip)]
    #[serde(rename = "trailInfoList")]
    pub trail_info_list: Vec<TrailInfo>,
}
