// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeGantryFusion01.java
// 职责: OdsLwzxsfsjFeeGantryFusion01 —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_gantry_fusion01.go（已与 Java 逐字段核对）
// 表: ods_lwzxsfsj_fee_gantry_fusion_01（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsLwzxsfsjFeeGantryFusion01 {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JString,
    #[sqlx(default)]
    pub actualfeeclass: JString,
    #[sqlx(default)]
    pub axlecount: JLong,
    #[sqlx(default)]
    pub createtime: JIsoDateTime,
    #[sqlx(default)]
    pub discountfee: JLong,
    #[sqlx(default)]
    pub electricalpercentage: JLong,
    #[sqlx(default)]
    pub enaxlecount: JLong,
    #[sqlx(default)]
    pub entime: JDateTime,
    #[sqlx(default)]
    pub entolllanehex: JString,
    #[sqlx(default)]
    pub entolllaneid: JString,
    #[sqlx(default)]
    pub entollstationid: JString,
    #[sqlx(default)]
    pub entollstationname: JString,
    #[sqlx(default)]
    pub envehicleclass: JLong,
    #[sqlx(default)]
    pub envehicleid: JString,
    #[sqlx(default)]
    pub envehicleidcolor: JString,
    #[sqlx(default)]
    pub envehicletype: JLong,
    #[sqlx(default)]
    pub enweight: JLong,
    #[sqlx(default)]
    pub entryoperatorid: JString,
    #[sqlx(default)]
    pub extime: JDateTime,
    #[sqlx(default)]
    pub extolllaneid: JString,
    #[sqlx(default)]
    pub extollstationid: JString,
    #[sqlx(default)]
    pub extollstationname: JString,
    #[sqlx(default)]
    pub exvehicleclass: JLong,
    #[sqlx(default)]
    pub exvehicleid: JString,
    #[sqlx(default)]
    pub exvehicletype: JLong,
    #[sqlx(default)]
    pub exweight: JLong,
    #[sqlx(default)]
    pub exitid: JString,
    #[sqlx(default)]
    pub fee: JLong,
    #[sqlx(default)]
    pub feeboardplay: JString,
    #[sqlx(default)]
    pub feemileage: JLong,
    #[sqlx(default)]
    pub feerate: JString,
    #[sqlx(default)]
    pub fusiondesc: JString,
    #[sqlx(default)]
    pub fusionflag: JString,
    #[sqlx(default)]
    pub id: JString,
    #[sqlx(default)]
    pub identification: JString,
    #[sqlx(default)]
    pub identifyvehicleid: JString,
    #[sqlx(default)]
    pub identifyvehicleidcolor: JString,
    #[sqlx(default)]
    pub lanetype: JString,
    #[sqlx(default)]
    pub mediano: JString,
    #[sqlx(default)]
    pub mediatype: JString,
    #[sqlx(default)]
    pub nocardcount: JLong,
    #[sqlx(default)]
    pub obuid: JString,
    #[sqlx(default)]
    pub obusign: JString,
    #[sqlx(default)]
    pub obutotalamount: JLong,
    #[sqlx(default)]
    pub obutotaldiscountamount: JLong,
    #[sqlx(default)]
    pub operid: JString,
    #[sqlx(default)]
    pub params: JString,
    #[sqlx(default)]
    pub passid: JString,
    #[sqlx(default)]
    pub paycardid: JString,
    #[sqlx(default)]
    pub payfee: JLong,
    #[sqlx(default)]
    pub paytype: JString,
    #[sqlx(default)]
    pub provfee: JLong,
    #[sqlx(default)]
    pub provtranscount: JLong,
    #[sqlx(default)]
    pub provincecount: JLong,
    #[sqlx(default)]
    pub receivetime: Day,
    #[sqlx(default)]
    pub shift: JString,
    #[sqlx(default)]
    pub shortfee: JLong,
    #[sqlx(default)]
    pub shortfeemileage: JLong,
    #[sqlx(default)]
    pub signstatus: JString,
    #[sqlx(default)]
    pub spcrateversion: JString,
    #[sqlx(default)]
    pub specialtype: JString,
    #[sqlx(default)]
    pub splitprovince: JString,
    #[sqlx(default)]
    pub tac: JString,
    #[sqlx(default)]
    pub terminalno: JString,
    #[sqlx(default)]
    pub terminaltransno: JString,
    #[sqlx(default)]
    pub transfee: JLong,
    #[sqlx(default)]
    pub transpaytype: JString,
    #[sqlx(default)]
    pub transtype: JString,
    #[sqlx(default)]
    pub vehiclesign: JString,
    #[sqlx(default)]
    pub vehiclesignid: JString,
    #[sqlx(default)]
    pub vid: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: Day,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JLong,
    #[sqlx(skip)]
    #[serde(rename = "inApplyTime1")]
    pub in_apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "inApplyTime2")]
    pub in_apply_time2: JString,
    #[sqlx(skip)]
    #[serde(rename = "outApplyTime1")]
    pub out_apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "outApplyTime2")]
    pub out_apply_time2: JString,
}
