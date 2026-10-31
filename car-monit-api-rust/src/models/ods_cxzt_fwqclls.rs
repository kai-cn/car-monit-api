// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsCxztFwqclls.java
// 职责: OdsCxztFwqclls —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_cxzt_fwqclls.go（已与 Java 逐字段核对）
// 表: ods_cxzt_fwqclls（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsCxztFwqclls {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JLong,
    #[sqlx(default)]
    pub datauuid: JString,
    #[sqlx(default)]
    pub targetpicurl: JString,
    #[sqlx(default)]
    pub vehiclebrand: JString,
    #[sqlx(default)]
    pub platepicurl: JString,
    #[sqlx(default)]
    pub rollvehiclestype: JString,
    #[sqlx(default)]
    pub plateno: JString,
    #[sqlx(default)]
    pub directionname: JString,
    #[sqlx(default)]
    pub platetype: JString,
    #[sqlx(default)]
    pub dangmark: JString,
    #[sqlx(default)]
    pub crosstime: JIsoDateTime,
    #[sqlx(default)]
    pub axles: JString,
    #[sqlx(default)]
    pub devicename: JString,
    #[sqlx(default)]
    pub ipaddress: JString,
    #[sqlx(default)]
    pub servicename: JString,
    #[sqlx(default)]
    pub vehicletype: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: JString,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JString,
    #[sqlx(skip)]
    #[serde(rename = "uuidList")]
    pub uuid_list: JList<String>,
}
