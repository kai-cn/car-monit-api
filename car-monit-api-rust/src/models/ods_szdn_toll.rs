// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnToll.java
// 职责: OdsSzdnToll —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_toll.go（已与 Java 逐字段核对）
// 表: ods_szdn_toll（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnToll {
    #[sqlx(default)]
    pub id: JString,
    #[sqlx(default)]
    #[serde(rename = "roadCode")]
    pub road_code: JString,
    #[sqlx(default)]
    #[serde(rename = "idCard")]
    pub id_card: JString,
    #[sqlx(default)]
    #[serde(rename = "tollCode")]
    pub toll_code: JString,
    #[sqlx(default)]
    #[serde(rename = "tollName")]
    pub toll_name: JString,
    #[sqlx(default)]
    #[serde(rename = "pileNo")]
    pub pile_no: JString,
    #[sqlx(default)]
    #[serde(rename = "orgName")]
    pub org_name: JString,
    #[sqlx(default)]
    #[serde(rename = "hexCode")]
    pub hex_code: JString,
    #[sqlx(default)]
    #[serde(rename = "stateCode")]
    pub state_code: JString,
    #[sqlx(default)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(default)]
    pub longitude: JString,
    #[sqlx(default)]
    pub latitude: JString,
    #[sqlx(default)]
    #[serde(rename = "openDate")]
    pub open_date: Day,
    #[sqlx(default)]
    #[serde(rename = "tollAliasName")]
    pub toll_alias_name: JString,
    #[sqlx(default)]
    #[serde(rename = "inMonitorResource")]
    pub in_monitor_resource: JString,
    #[sqlx(default)]
    #[serde(rename = "laneMonitorResource")]
    pub lane_monitor_resource: JString,
    #[sqlx(default)]
    #[serde(rename = "squareMonitorResource")]
    pub square_monitor_resource: JString,
    #[sqlx(default)]
    #[serde(rename = "dynamicMonitorResource")]
    pub dynamic_monitor_resource: JString,
    #[sqlx(default)]
    #[serde(rename = "tollCodeMerge")]
    pub toll_code_merge: JString,
    #[sqlx(default)]
    #[serde(rename = "stateCodeMerge")]
    pub state_code_merge: JString,
    #[sqlx(default)]
    #[serde(rename = "tollNameMerge")]
    pub toll_name_merge: JString,
    #[sqlx(default)]
    #[serde(rename = "sectionCode")]
    pub section_code: JString,
    #[sqlx(default)]
    #[serde(rename = "tollOrgCode")]
    pub toll_org_code: JString,
    #[sqlx(default)]
    #[serde(rename = "isAccess")]
    pub is_access: JString,
}
