// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailBo.java
// 职责: TrailBo —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/trail_bo.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct TrailBo {
    #[sqlx(skip)]
    #[serde(rename = "pointUuid")]
    pub point_uuid: JString,
    #[sqlx(skip)]
    #[serde(rename = "stateType")]
    pub state_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "pointFlag")]
    pub point_flag: JString,
    #[sqlx(skip)]
    #[serde(rename = "pointJosn")]
    pub point_josn: JString,
    #[sqlx(skip)]
    #[serde(rename = "borderWeighingCaptureBO")]
    pub border_weighing_capture_bo: Option<Box<OdsSzdnProvinceBorderVehicleWeightNewstructure>>,
    #[sqlx(skip)]
    #[serde(rename = "gantryCaptureBO")]
    pub gantry_capture_bo: Option<Box<OdsRtSzdnSnapshotFlowAddcode>>,
    #[sqlx(skip)]
    #[serde(rename = "provCaptureBO")]
    pub prov_capture_bo: Option<Box<OdsRtSzdnSnapshotFlowProvcaptureAddcode>>,
    #[sqlx(skip)]
    #[serde(rename = "stationCapture")]
    pub station_capture: Option<Box<OdsRtSzdnSnapshotFlowStationcaptureAddcode>>,
    #[sqlx(skip)]
    #[serde(rename = "feeRecord")]
    pub fee_record: Option<Box<OdsLwzxsfsjFeeRecords01>>,
    #[sqlx(skip)]
    #[serde(rename = "feeStationEnter")]
    pub fee_station_enter: Option<Box<OdsLwzxsfsjFeeStationEnter01>>,
    #[sqlx(skip)]
    #[serde(rename = "feeStationExit")]
    pub fee_station_exit: Option<Box<OdsLwzxsfsjFeeStationExit01>>,
    #[sqlx(skip)]
    #[serde(rename = "captureTime")]
    pub capture_time: JString,
    #[sqlx(skip)]
    #[serde(rename = "directionIn")]
    pub direction_in: JBool,
    #[sqlx(skip)]
    #[serde(rename = "locationCode")]
    pub location_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "locationName")]
    pub location_name: JString,
    #[sqlx(skip)]
    #[serde(rename = "standardCode")]
    pub standard_code: JString,
    #[sqlx(skip)]
    pub longitude: JString,
    #[sqlx(skip)]
    pub latitude: JString,
    #[sqlx(skip)]
    #[serde(rename = "locationFlag")]
    pub location_flag: JString,
    #[sqlx(skip)]
    #[serde(rename = "ipType")]
    pub ip_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "locationJosn")]
    pub location_josn: JString,
    #[sqlx(skip)]
    #[serde(rename = "gantryIpBO")]
    pub gantry_ip_bo: Option<Box<OdsSzdnGantryIp>>,
    #[sqlx(skip)]
    #[serde(rename = "stationIpBO")]
    pub station_ip_bo: Option<Box<OdsSzdnTollStationIp>>,
    #[sqlx(skip)]
    #[serde(rename = "devCode")]
    pub dev_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "devName")]
    pub dev_name: JString,
    #[sqlx(skip)]
    #[serde(rename = "imagesArry")]
    pub images_arry: JString,
    #[sqlx(skip)]
    pub lon: JDecimal,
    #[sqlx(skip)]
    pub lat: JDecimal,
    #[sqlx(skip)]
    #[serde(rename = "roadCode")]
    pub road_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "sectionCode")]
    pub section_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "orgCode")]
    pub org_code: JString,
    #[sqlx(skip)]
    pub direction: JString,
    #[sqlx(skip)]
    pub pileno: JString,
    #[sqlx(skip)]
    #[serde(rename = "preCaptureTime")]
    pub pre_capture_time: JString,
    #[sqlx(skip)]
    #[serde(rename = "countNum")]
    pub count_num: JInt,
    #[sqlx(skip)]
    pub platenumber: JString,
    #[sqlx(skip)]
    #[serde(rename = "locationId")]
    pub location_id: JString,
    #[sqlx(skip)]
    #[serde(rename = "isQuery")]
    pub is_query: JString,
    #[sqlx(skip)]
    pub platecolor: JString,
    #[sqlx(skip)]
    #[serde(rename = "isVirtual")]
    pub is_virtual: JString,
}
