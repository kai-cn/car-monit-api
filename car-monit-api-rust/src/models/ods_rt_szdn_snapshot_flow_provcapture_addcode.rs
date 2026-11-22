// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowProvcaptureAddcode.java
// 职责: OdsRtSzdnSnapshotFlowProvcaptureAddcode —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_provcapture_addcode.go（已与 Java 逐字段核对）
// 表: ods_rt_szdn_snapshot_flow_provcapture_addcode（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsRtSzdnSnapshotFlowProvcaptureAddcode {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JLong,
    #[sqlx(default)]
    pub deviceip: JString,
    #[sqlx(default)]
    pub tailcapturetimeunix: JLong,
    #[sqlx(default)]
    pub tailcapturetime: JIsoDateTime,
    #[sqlx(default)]
    pub extendattribute: JString,
    #[sqlx(default)]
    pub smallsideimagewidth: JInt,
    #[sqlx(default)]
    pub axletype: JString,
    #[sqlx(default)]
    pub smallsideimageheight: JInt,
    #[sqlx(default)]
    pub platecolorcode: JInt,
    #[sqlx(default)]
    pub platecolor: JString,
    #[sqlx(default)]
    pub cover: JString,
    #[sqlx(default)]
    pub averageauthoritative: JInt,
    #[sqlx(default)]
    pub headlanecode: JInt,
    #[sqlx(default)]
    pub specialvehicle: JInt,
    #[sqlx(default)]
    pub carlength: JInt,
    #[sqlx(default)]
    pub resulttype: JString,
    #[sqlx(default)]
    pub carhight: JInt,
    #[sqlx(default)]
    pub carmodelscode: JInt,
    #[sqlx(default)]
    pub carmodels: JString,
    #[sqlx(default)]
    pub laneposition: JString,
    #[sqlx(default)]
    pub firstauthoritative: JInt,
    #[sqlx(default)]
    pub tailplateimageheight: JInt,
    #[sqlx(default)]
    pub axlecount: JInt,
    #[sqlx(default)]
    pub plateimagewidth: JInt,
    #[sqlx(default)]
    pub specialclass: JString,
    #[sqlx(default)]
    pub tailplatenumber: JString,
    #[sqlx(default)]
    pub tailimage: JString,
    #[sqlx(default)]
    pub sidecapturetimeunix: JLong,
    #[sqlx(default)]
    pub sidecapturetime: Day,
    #[sqlx(default)]
    pub sidelanecode: JInt,
    #[sqlx(default)]
    pub wheelbase: JInt,
    #[sqlx(default)]
    pub attached: JString,
    #[sqlx(default)]
    pub wheelcount: JInt,
    #[sqlx(default)]
    pub guid: JString,
    #[sqlx(default)]
    pub sideimagewidth: JInt,
    #[sqlx(default)]
    pub plateimageheight: JInt,
    #[sqlx(default)]
    pub datasource: JString,
    #[sqlx(default)]
    pub carclass: JString,
    #[sqlx(default)]
    pub gantryid: JString,
    #[sqlx(default)]
    pub smallsideimage: JString,
    #[sqlx(default)]
    pub headimageheight: JInt,
    #[sqlx(default)]
    pub sidescenetypecode: JInt,
    #[sqlx(default)]
    pub sidescenetype: JString,
    #[sqlx(default)]
    pub tailimagewidth: JInt,
    #[sqlx(default)]
    pub envstate: JString,
    #[sqlx(default)]
    pub headscenetypecode: JInt,
    #[sqlx(default)]
    pub headscenetype: JString,
    #[sqlx(default)]
    pub sidedrivingdirectioncode: JInt,
    #[sqlx(default)]
    pub sidedrivingdirection: JString,
    #[sqlx(default)]
    pub sideimageheight: JInt,
    #[sqlx(default)]
    pub speed: JString,
    #[sqlx(default)]
    pub tailplateimage: JString,
    #[sqlx(default)]
    pub headdrivingdirectioncode: JInt,
    #[sqlx(default)]
    pub headdrivingdirection: JString,
    #[sqlx(default)]
    pub cartype: JString,
    #[sqlx(default)]
    pub plateimage: JString,
    #[sqlx(default)]
    pub changelane: JString,
    #[sqlx(default)]
    pub sideimage: JString,
    #[sqlx(default)]
    pub tailplateposition: JString,
    #[sqlx(default)]
    pub headimagewidth: JInt,
    #[sqlx(default)]
    pub headimage: JString,
    #[sqlx(default)]
    pub carweight: JInt,
    #[sqlx(default)]
    pub tailimageheight: JInt,
    #[sqlx(default)]
    pub devicecode: JString,
    #[sqlx(default)]
    pub platenumber: JString,
    #[sqlx(default)]
    pub tailplatecolorcode: JInt,
    #[sqlx(default)]
    pub tailplatecolor: JString,
    #[sqlx(default)]
    pub uploadtimeunix: JLong,
    #[sqlx(default)]
    pub uploadtime: Day,
    #[sqlx(default)]
    pub impostoraxlecount: JInt,
    #[sqlx(default)]
    pub taillanecode: JInt,
    #[sqlx(default)]
    pub siteid: JInt,
    #[sqlx(default)]
    pub headcapturetimeunix: JLong,
    #[sqlx(default)]
    pub headcapturetime: Day,
    #[sqlx(default)]
    pub plateposition: JString,
    #[sqlx(default)]
    pub tailplateimagewidth: JInt,
    #[sqlx(default)]
    pub loadtime: JIsoDateTime,
    #[sqlx(default)]
    pub gradelevel: JInt,
    #[sqlx(default)]
    pub datauuid: JString,
    #[sqlx(default)]
    pub reserve1: JString,
    #[sqlx(default)]
    pub reserve2: JString,
    #[sqlx(default)]
    pub reserve3: JString,
    #[sqlx(skip)]
    #[serde(rename = "queryUuids")]
    pub query_uuids: JString,
}
