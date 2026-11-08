// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeStationEnter01.java
// 职责: OdsLwzxsfsjFeeStationEnter01 —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_station_enter01.go（已与 Java 逐字段核对）
// 表: ods_lwzxsfsj_fee_station_enter_01（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsLwzxsfsjFeeStationEnter01 {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JLong,
    #[sqlx(default)]
    pub cardid: JString,
    #[sqlx(default)]
    pub electricalpercentage: JLong,
    #[sqlx(default)]
    pub enaxlecount: JLong,
    #[sqlx(default)]
    pub entime: Day,
    #[sqlx(default)]
    pub entolllanehex: JString,
    #[sqlx(default)]
    pub entolllaneid: JString,
    #[sqlx(default)]
    pub entollstationid: JString,
    #[sqlx(default)]
    pub enweight: JFloat,
    #[sqlx(default)]
    pub identifyvehicleid: JString,
    #[sqlx(default)]
    pub lanetype: JString,
    #[sqlx(default)]
    pub mediatype: JString,
    #[sqlx(default)]
    pub operid: JString,
    #[sqlx(default)]
    pub operationmedia: JString,
    #[sqlx(default)]
    pub params: JString,
    #[sqlx(default)]
    pub passid: JString,
    #[sqlx(default)]
    pub receivetime: Day,
    #[sqlx(default)]
    pub shift: JString,
    #[sqlx(default)]
    pub signstatus: JString,
    #[sqlx(default)]
    pub specialtype: JString,
    #[sqlx(default)]
    pub tac: JString,
    #[sqlx(default)]
    pub terminalno: JString,
    #[sqlx(default)]
    pub terminaltransno: JString,
    #[sqlx(default)]
    pub transfee: JFloat,
    #[sqlx(default)]
    pub transtype: JString,
    #[sqlx(default)]
    pub vcount: JLong,
    #[sqlx(default)]
    pub vehicleclass: JString,
    #[sqlx(default)]
    pub vehicleid: JString,
    #[sqlx(default)]
    pub vehiclesign: JString,
    #[sqlx(default)]
    pub vehiclesignid: JString,
    #[sqlx(default)]
    pub vehicletype: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: Day,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JString,
    #[sqlx(default)]
    pub cid: JString,
    #[sqlx(skip)]
    #[serde(rename = "cidList")]
    pub cid_list: JList<String>,
}
