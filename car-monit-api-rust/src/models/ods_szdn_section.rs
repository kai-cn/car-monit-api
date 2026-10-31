// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnSection.java
// 职责: OdsSzdnSection —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_section.go（已与 Java 逐字段核对）
// 表: ods_szdn_section（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnSection {
    #[sqlx(default)]
    pub id: JString,
    #[sqlx(default)]
    #[serde(rename = "roadCode")]
    pub road_code: JString,
    #[sqlx(default)]
    #[serde(rename = "roadName")]
    pub road_name: JString,
    #[sqlx(default)]
    #[serde(rename = "sectionCode")]
    pub section_code: JString,
    #[sqlx(default)]
    #[serde(rename = "sectionName")]
    pub section_name: JString,
    #[sqlx(default)]
    #[serde(rename = "startPileNo")]
    pub start_pile_no: JLong,
    #[sqlx(default)]
    #[serde(rename = "endPileNo")]
    pub end_pile_no: JLong,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgName")]
    pub org_name: JString,
    #[sqlx(default)]
    #[serde(rename = "orgLevelCode")]
    pub org_level_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCategory")]
    pub org_category: JString,
    #[sqlx(default)]
    pub mileage: JLong,
    #[sqlx(default)]
    #[serde(rename = "openDate")]
    pub open_date: Day,
}
