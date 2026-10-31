// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowAddcode.java
// 职责: OdsRtSzdnSnapshotFlowAddcode —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_addcode.go（已与 Java 逐字段核对）
// 表: jl_data01.ods_rt_szdn_snapshot_flow_addcode（schema=jl_data01）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsRtSzdnSnapshotFlowAddcode {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JString,
    #[sqlx(default)]
    pub datasource: JString,
    #[sqlx(default)]
    pub cameratype: JString,
    #[sqlx(default)]
    pub deviceid: JString,
    #[sqlx(default)]
    pub gantrycode: JString,
    #[sqlx(default)]
    pub gantryname: JString,
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
    pub direction: JInt,
    #[sqlx(default)]
    pub hexcode: JString,
    #[sqlx(default)]
    pub pileno: JString,
    #[sqlx(default)]
    pub lon: JFloat,
    #[sqlx(default)]
    pub lat: JFloat,
    #[sqlx(default)]
    pub deviceip: JString,
    #[sqlx(default)]
    pub siteid: JLong,
    #[sqlx(default)]
    pub laneid: JInt,
    #[sqlx(default)]
    pub snapshottimeunix: JLong,
    #[sqlx(default)]
    pub snapshottime: JIsoDateTime,
    #[sqlx(default)]
    pub receivedtimeunix: JLong,
    #[sqlx(default)]
    pub receivedtime: Day,
    #[sqlx(default)]
    pub platenumber: JString,
    #[sqlx(default)]
    pub platecolor: JString,
    #[sqlx(default)]
    pub platecolorcode: JInt,
    #[sqlx(default)]
    pub platetype: JString,
    #[sqlx(default)]
    pub platetypecode: JInt,
    #[sqlx(default)]
    pub plateconfidence: JInt,
    #[sqlx(default)]
    pub carbrand: JString,
    #[sqlx(default)]
    pub carcolor: JString,
    #[sqlx(default)]
    pub carcolorcode: JInt,
    #[sqlx(default)]
    pub cartype: JString,
    #[sqlx(default)]
    pub cartypecode: JInt,
    #[sqlx(default)]
    pub cardirection: JString,
    #[sqlx(default)]
    pub snappicturepath: JString,
    #[sqlx(default)]
    pub loadtime: Day,
    #[sqlx(default)]
    pub gradelevel: JInt,
    #[sqlx(default)]
    pub datauuid: JString,
    #[sqlx(default)]
    pub reserve3: JString,
    #[sqlx(skip)]
    pub id: JString,
    #[sqlx(skip)]
    #[serde(rename = "snapshottimeStr")]
    pub snapshottime_str: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime1")]
    pub apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime2")]
    pub apply_time2: JString,
    #[sqlx(skip)]
    #[serde(rename = "queryUuids")]
    pub query_uuids: JString,
    #[sqlx(skip)]
    pub flag: JString,
    #[sqlx(skip)]
    #[serde(rename = "sectionCodeStr")]
    pub section_code_str: JString,
    #[sqlx(skip)]
    #[serde(rename = "type")]
    pub r#type: JString,
    #[sqlx(skip)]
    pub code: JString,
    #[sqlx(skip)]
    #[serde(rename = "codeList")]
    pub code_list: JList<String>,
    #[sqlx(skip)]
    #[serde(rename = "sectionList")]
    pub section_list: JList<String>,
    #[sqlx(skip)]
    #[serde(rename = "startNum")]
    pub start_num: JInt,
    #[sqlx(skip)]
    #[serde(rename = "endNum")]
    pub end_num: JInt,
}

impl OdsRtSzdnSnapshotFlowAddcode {
    /// 对应 Java @TableName(value = "ods_rt_szdn_snapshot_flow_addcode", schema = "jl_data01")。
    pub const TABLE: &'static str = "jl_data01.ods_rt_szdn_snapshot_flow_addcode";
    pub const SCHEMA: &'static str = "jl_data01";
    pub const PK: &'static str = "big_id";
}
