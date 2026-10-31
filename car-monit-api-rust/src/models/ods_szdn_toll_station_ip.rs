// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnTollStationIp.java
// 职责: OdsSzdnTollStationIp —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_toll_station_ip.go（已与 Java 逐字段核对）
// 表: ods_szdn_toll_station_ip（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnTollStationIp {
    #[sqlx(default)]
    pub id: JLong,
    #[sqlx(default)]
    #[serde(rename = "tollCode")]
    pub toll_code: JString,
    #[sqlx(default)]
    #[serde(rename = "tollName")]
    pub toll_name: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    pub ip: JString,
    #[sqlx(default)]
    pub brand: JString,
    #[sqlx(skip)]
    #[serde(rename = "odsSzdnToll")]
    pub ods_szdn_toll: Option<Box<OdsSzdnToll>>,
}
