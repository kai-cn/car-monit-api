// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeRecords01.java
// 职责: OdsLwzxsfsjFeeRecords01 —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_records01.go（已与 Java 逐字段核对）
// 表: ods_lwzxsfsj_fee_records_01（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsLwzxsfsjFeeRecords01 {
    #[sqlx(default)]
    #[serde(rename = "bigId")]
    pub big_id: JString,
    #[sqlx(default)]
    pub algorithmidentifier: JString,
    #[sqlx(default)]
    pub antennaid: JString,
    #[sqlx(default)]
    pub axlecount: JLong,
    #[sqlx(default)]
    pub balanceafter: JDecimal,
    #[sqlx(default)]
    pub balancebefore: JDecimal,
    #[sqlx(default)]
    pub cardfeesumafter: JDecimal,
    #[sqlx(default)]
    pub cardfeesumbefore: JDecimal,
    #[sqlx(default)]
    pub computerorder: JString,
    #[sqlx(default)]
    pub consumetime: JLong,
    #[sqlx(default)]
    pub cpucardid: JString,
    #[sqlx(default)]
    pub cpucardtype: JString,
    #[sqlx(default)]
    pub cpuenddate: JString,
    #[sqlx(default)]
    pub cpuissueid: JString,
    #[sqlx(default)]
    pub cpunetid: JString,
    #[sqlx(default)]
    pub cpustartdate: JString,
    #[sqlx(default)]
    pub cpuvehicleplate: JString,
    #[sqlx(default)]
    pub cpuvehicletype: JString,
    #[sqlx(default)]
    pub cpuversion: JString,
    #[sqlx(default)]
    pub dealstatus: JString,
    #[sqlx(default)]
    pub discountfee: JDecimal,
    #[sqlx(default)]
    pub discountfeegroup: JString,
    #[sqlx(default)]
    pub enlanetype: JString,
    #[sqlx(default)]
    pub entime: JDateTime,
    #[sqlx(default)]
    pub entolllaneid: JString,
    #[sqlx(default)]
    pub entollstationhex: JString,
    #[sqlx(default)]
    pub fee: JDecimal,
    #[sqlx(default)]
    pub feecalcresult: JString,
    #[sqlx(default)]
    pub feecalcspecial: JString,
    #[sqlx(default)]
    pub feecalcspecials: JString,
    #[sqlx(default)]
    pub feegroup: JString,
    #[sqlx(default)]
    pub feeinfo1: JString,
    #[sqlx(default)]
    pub feeinfo2: JString,
    #[sqlx(default)]
    pub feeinfo3: JString,
    #[sqlx(default)]
    pub feemileage: JDecimal,
    #[sqlx(default)]
    pub feeprovbeginhex: JString,
    #[sqlx(default)]
    pub feespare1: JString,
    #[sqlx(default)]
    pub feespare2: JString,
    #[sqlx(default)]
    pub feevehicletype: JString,
    #[sqlx(default)]
    pub gantryhex: JString,
    #[sqlx(default)]
    pub gantryhexopposite: JString,
    #[sqlx(default)]
    pub gantryid: JString,
    #[sqlx(default)]
    pub gantryordernum: JLong,
    #[sqlx(default)]
    pub gantrytype: JString,
    #[sqlx(default)]
    pub holidaystate: JString,
    #[sqlx(default)]
    pub hourbatchno: JString,
    #[sqlx(default)]
    pub keyversion: JString,
    #[sqlx(default)]
    pub lastgantryhex: JString,
    #[sqlx(default)]
    pub lastgantrytime: JDateTime,
    #[sqlx(default)]
    pub matchstatus: JString,
    #[sqlx(default)]
    pub mediatype: JString,
    #[sqlx(default)]
    pub nocardtimesafter: JLong,
    #[sqlx(default)]
    pub nocardtimesbefore: JLong,
    #[sqlx(default)]
    pub obuelectrical: JLong,
    #[sqlx(default)]
    pub obuenddate: JString,
    #[sqlx(default)]
    pub obufeesumafter: JDecimal,
    #[sqlx(default)]
    pub obufeesumbefore: JDecimal,
    #[sqlx(default)]
    pub obuinfotyperead: JString,
    #[sqlx(default)]
    pub obuinfotypewrite: JString,
    #[sqlx(default)]
    pub obuissueid: JString,
    #[sqlx(default)]
    pub obulastgantryhex: JString,
    #[sqlx(default)]
    pub obulastgantrytime: JDateTime,
    #[sqlx(default)]
    pub obumac: JString,
    #[sqlx(default)]
    pub obumileageafter: JDecimal,
    #[sqlx(default)]
    pub obumileagebefore: JDecimal,
    #[sqlx(default)]
    pub obupassstate: JString,
    #[sqlx(default)]
    pub obupayfeesumafter: JDecimal,
    #[sqlx(default)]
    pub obupayfeesumbefore: JDecimal,
    #[sqlx(default)]
    pub obuprovfeesumafter: JDecimal,
    #[sqlx(default)]
    pub obuprovfeesumbefore: JDecimal,
    #[sqlx(default)]
    pub obuprovpayfeesumafter: JDecimal,
    #[sqlx(default)]
    pub obuprovpayfeesumbefore: JDecimal,
    #[sqlx(default)]
    pub obuprovtradesuccnumafter: JLong,
    #[sqlx(default)]
    pub obuprovtradesuccnumbefore: JLong,
    #[sqlx(default)]
    pub obusign: JString,
    #[sqlx(default)]
    pub obusn: JString,
    #[sqlx(default)]
    pub obustartdate: JString,
    #[sqlx(default)]
    pub obustate: JString,
    #[sqlx(default)]
    pub obutotaltradesuccnumafter: JLong,
    #[sqlx(default)]
    pub obutotaltradesuccnumbefore: JLong,
    #[sqlx(default)]
    pub obutraderesult: JString,
    #[sqlx(default)]
    pub obuvehicleplate: JString,
    #[sqlx(default)]
    pub obuvehicletype: JString,
    #[sqlx(default)]
    pub obuversion: JString,
    #[sqlx(default)]
    pub params: JString,
    #[sqlx(default)]
    pub passid: JString,
    #[sqlx(default)]
    pub passstate: JString,
    #[sqlx(default)]
    pub pathfitflag: JString,
    #[sqlx(default)]
    pub payfee: JDecimal,
    #[sqlx(default)]
    pub payfeegroup: JString,
    #[sqlx(default)]
    pub pcrsuversion: JString,
    #[sqlx(default)]
    pub provminfee: JDecimal,
    #[sqlx(default)]
    pub provincenumafter: JLong,
    #[sqlx(default)]
    pub provincenumbefore: JLong,
    #[sqlx(default)]
    pub ratecompute: JString,
    #[sqlx(default)]
    pub ratefitcount: JLong,
    #[sqlx(default)]
    pub rateversion: JString,
    #[sqlx(default)]
    pub readciphertextverify: JString,
    #[sqlx(default)]
    pub receivetime: JDateTime,
    #[sqlx(default)]
    pub servicetype: JString,
    #[sqlx(default)]
    pub stationdbtime: JDateTime,
    #[sqlx(default)]
    pub stationdealtime: JDateTime,
    #[sqlx(default)]
    pub stationmatchtime: JDateTime,
    #[sqlx(default)]
    pub stationvalidtime: JDateTime,
    #[sqlx(default)]
    pub tac: JString,
    #[sqlx(default)]
    pub terminalno: JString,
    #[sqlx(default)]
    pub terminaltransno: JString,
    #[sqlx(default)]
    pub tollintervalid: JString,
    #[sqlx(default)]
    pub tollintervalsign: JString,
    #[sqlx(default)]
    pub totalweight: JDecimal,
    #[sqlx(default)]
    pub tradeid: JString,
    #[sqlx(default)]
    pub tradereadciphertext: JString,
    #[sqlx(default)]
    pub traderesult: JString,
    #[sqlx(default)]
    pub tradetype: JString,
    #[sqlx(default)]
    pub tradewriteciphertext: JString,
    #[sqlx(default)]
    pub transfee: JDecimal,
    #[sqlx(default)]
    pub transno: JString,
    #[sqlx(default)]
    pub transtime: JDateTime,
    #[sqlx(default)]
    pub transtype: JString,
    #[sqlx(default)]
    pub validstatus: JString,
    #[sqlx(default)]
    pub vehicleclass: JString,
    #[sqlx(default)]
    pub vehiclehight: JDecimal,
    #[sqlx(default)]
    pub vehiclelength: JDecimal,
    #[sqlx(default)]
    pub vehicleplate: JString,
    #[sqlx(default)]
    pub vehicleseat: JString,
    #[sqlx(default)]
    pub vehiclesign: JString,
    #[sqlx(default)]
    pub vehicletype: JString,
    #[sqlx(default)]
    pub vehicleusertype: JString,
    #[sqlx(default)]
    pub vehiclewidth: JDecimal,
    #[sqlx(default)]
    pub verifycode: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: JDateTime,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JLong,
    #[sqlx(default)]
    pub cid: JString,
    #[sqlx(skip)]
    #[serde(rename = "cidList")]
    pub cid_list: JList<String>,
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
    #[sqlx(skip)]
    #[serde(rename = "plateColor")]
    pub plate_color: JString,
    #[sqlx(skip)]
    #[serde(rename = "gantryName")]
    pub gantry_name: JString,
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
    #[serde(rename = "transtimeStr")]
    pub transtime_str: JString,
    #[sqlx(skip)]
    #[serde(rename = "lastgantrytimeStr")]
    pub lastgantrytime_str: JString,
    #[sqlx(skip)]
    #[serde(rename = "startNum")]
    pub start_num: JInt,
    #[sqlx(skip)]
    #[serde(rename = "endNum")]
    pub end_num: JInt,
    #[sqlx(skip)]
    pub sectioncode: JString,
    #[sqlx(skip)]
    #[serde(rename = "orderByFlag")]
    pub order_by_flag: JString,
}
