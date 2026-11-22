// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowStationcaptureAddcode.java
// 职责: OdsRtSzdnSnapshotFlowStationcaptureAddcode —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_stationcapture_addcode.go（已与 Java 逐字段核对）
// 表: ods_rt_szdn_snapshot_flow_stationcapture_addcode（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsRtSzdnSnapshotFlowStationcaptureAddcode {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JLong,
    #[sqlx(default)]
    pub datasource: JString,
    #[sqlx(default)]
    pub cameratype: JString,
    #[sqlx(default)]
    pub deviceid: JString,
    #[sqlx(default)]
    pub deviceip: JString,
    #[sqlx(default)]
    pub tollcode: JString,
    #[sqlx(default)]
    pub tollname: JString,
    #[sqlx(default)]
    pub orgcode: JLong,
    #[sqlx(default)]
    pub siteid: JLong,
    #[sqlx(default)]
    pub laneid: JInt,
    #[sqlx(default)]
    pub snapshottimeunix: JLong,
    #[sqlx(default)]
    pub snapshottime: Day,
    #[sqlx(default)]
    pub receivedtimeunix: JLong,
    #[sqlx(default)]
    pub receivedtime: Day,
    #[sqlx(default)]
    pub platenumber: JString,
    #[sqlx(default)]
    pub platecolorcode: JInt,
    #[sqlx(default)]
    pub platecolor: JString,
    #[sqlx(default)]
    pub platetypecode: JInt,
    #[sqlx(default)]
    pub platetype: JString,
    #[sqlx(default)]
    pub plateconfidence: JInt,
    #[sqlx(default)]
    pub carbrand: JString,
    #[sqlx(default)]
    pub carcolorcode: JInt,
    #[sqlx(default)]
    pub carcolor: JString,
    #[sqlx(default)]
    pub cartypecode: JInt,
    #[sqlx(default)]
    pub cartype: JString,
    #[sqlx(default)]
    pub cardirectioncode: JInt,
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
    pub maindirection: JString,
    #[sqlx(default)]
    pub maindirectionname: JString,
    #[sqlx(default)]
    pub reserve3: JString,
    #[sqlx(skip)]
    #[serde(rename = "queryUuids")]
    pub query_uuids: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime1")]
    pub apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime2")]
    pub apply_time2: JString,
}
