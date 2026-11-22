// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantry.java
// 职责: OdsSzdnGantry —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_gantry.go（已与 Java 逐字段核对）
// 表: ods_szdn_gantry（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnGantry {
    #[sqlx(default)]
    pub id: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryCode")]
    pub gantry_code: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryName")]
    pub gantry_name: JString,
    #[sqlx(default)]
    #[serde(rename = "roadCode")]
    pub road_code: JString,
    #[sqlx(default)]
    #[serde(rename = "sectionCode")]
    pub section_code: JString,
    #[sqlx(default)]
    #[serde(rename = "tollCode")]
    pub toll_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    #[serde(rename = "hexCode")]
    pub hex_code: JString,
    #[sqlx(default)]
    pub direction: JString,
    #[sqlx(default)]
    #[serde(rename = "pileNo")]
    pub pile_no: JString,
    #[sqlx(default)]
    pub lon: JString,
    #[sqlx(default)]
    pub lat: JString,
    #[sqlx(default)]
    #[serde(rename = "isVirtual")]
    pub is_virtual: JString,
    #[sqlx(default)]
    pub mileage: JString,
    #[sqlx(default)]
    #[serde(rename = "boundaryGantryType")]
    pub boundary_gantry_type: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryType")]
    pub gantry_type: JString,
    #[sqlx(default)]
    #[serde(rename = "cityCode")]
    pub city_code: JString,
    #[sqlx(default)]
    #[serde(rename = "districtName")]
    pub district_name: JString,
    #[sqlx(default)]
    #[serde(rename = "belongGroup")]
    pub belong_group: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryCodeMerge")]
    pub gantry_code_merge: JString,
    #[sqlx(default)]
    #[serde(rename = "gantryNameAlias")]
    pub gantry_name_alias: JString,
    #[sqlx(default)]
    pub remark: JString,
    #[sqlx(skip)]
    #[serde(rename = "isData")]
    pub is_data: JString,
}
