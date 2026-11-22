// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataLocationDict.java
// 职责: ZdataLocationDict —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/zdata_location_dict.go（已与 Java 逐字段核对）
// 表: zdata_location_dict（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct ZdataLocationDict {
    #[sqlx(default)]
    pub id: JLong,
    #[sqlx(rename = "type")]
    #[sqlx(default)]
    #[serde(rename = "type")]
    pub r#type: JString,
    #[sqlx(default)]
    pub name: JString,
    #[sqlx(default)]
    #[serde(rename = "rawCode")]
    pub raw_code: JString,
    #[sqlx(default)]
    #[serde(rename = "standardCode")]
    pub standard_code: JString,
    #[sqlx(default)]
    pub roadcode: JString,
    #[sqlx(default)]
    pub roadname: JString,
    #[sqlx(default)]
    pub sectioncode: JString,
    #[sqlx(default)]
    pub sectionname: JString,
    #[sqlx(default)]
    pub tollcode: JString,
    #[sqlx(default)]
    pub tollname: JString,
    #[sqlx(default)]
    pub orgcode: JString,
    #[sqlx(default)]
    pub orgname: JString,
    #[sqlx(default)]
    #[serde(rename = "createdAt")]
    pub created_at: Day,
    #[sqlx(default)]
    #[serde(rename = "updatedAt")]
    pub updated_at: Day,
    #[sqlx(default)]
    pub latitude: JFloat,
    #[sqlx(default)]
    pub longitude: JFloat,
    #[sqlx(default)]
    #[serde(rename = "pileNoK")]
    pub pile_no_k: JString,
    #[sqlx(default)]
    #[serde(rename = "pileNo")]
    pub pile_no: JString,
    #[sqlx(default)]
    pub direction: JString,
    #[sqlx(default)]
    pub remark: JString,
}
