// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantryIp.java
// 职责: OdsSzdnGantryIp —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_gantry_ip.go（已与 Java 逐字段核对）
// 表: ods_szdn_gantry_ip（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnGantryIp {
    #[sqlx(default)]
    pub id: JLong,
    #[sqlx(default)]
    #[serde(rename = "gantryCode")]
    pub gantry_code: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryName")]
    pub gantry_name: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    pub ip: JString,
    #[sqlx(default)]
    pub brand: JString,
    #[sqlx(rename = "type")]
    #[sqlx(default)]
    #[serde(rename = "type")]
    pub r#type: JString,
    #[sqlx(skip)]
    #[serde(rename = "odsSzdnGantry")]
    pub ods_szdn_gantry: Option<Box<OdsSzdnGantry>>,
}
