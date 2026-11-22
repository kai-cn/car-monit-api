// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsYhglVBaseOrg.java
// 职责: OdsYhglVBaseOrg —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_yhgl_v_base_org.go（已与 Java 逐字段核对）
// 表: ods_yhgl_v_base_org（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsYhglVBaseOrg {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgName")]
    pub org_name: JString,
    #[sqlx(default)]
    #[serde(rename = "orgShortName")]
    pub org_short_name: JString,
    #[sqlx(default)]
    #[serde(rename = "orgParentId")]
    pub org_parent_id: JString,
    #[sqlx(default)]
    #[serde(rename = "orgLevelCode")]
    pub org_level_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgIsVirtual")]
    pub org_is_virtual: JString,
    #[sqlx(default)]
    #[serde(rename = "orgMaintenance")]
    pub org_maintenance: JString,
    #[sqlx(default)]
    #[serde(rename = "orgSequence")]
    pub org_sequence: JLong,
    #[sqlx(default)]
    #[serde(rename = "orgIsManager")]
    pub org_is_manager: JString,
    #[sqlx(default)]
    #[serde(rename = "orgIsDeleted")]
    pub org_is_deleted: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCategory")]
    pub org_category: JString,
    #[sqlx(default)]
    #[serde(rename = "orgIsAuthorized")]
    pub org_is_authorized: JString,
    #[sqlx(default)]
    #[serde(rename = "orgAddress")]
    pub org_address: JString,
    #[sqlx(default)]
    #[serde(rename = "orgIsYhAutarky")]
    pub org_is_yh_autarky: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: Day,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JInt,
}
