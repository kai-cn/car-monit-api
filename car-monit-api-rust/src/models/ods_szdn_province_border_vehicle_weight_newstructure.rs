// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnProvinceBorderVehicleWeightNewstructure.java
// 职责: OdsSzdnProvinceBorderVehicleWeightNewstructure —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/ods_szdn_province_border_vehicle_weight_newstructure.go（已与 Java 逐字段核对）
// 表: ods_szdn_province_border_vehicle_weight_newstructure（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct OdsSzdnProvinceBorderVehicleWeightNewstructure {
    #[sqlx(rename = "dataSource")]
    #[sqlx(default)]
    #[serde(rename = "dataSource")]
    pub data_source: JString,
    #[sqlx(rename = "dataType")]
    #[sqlx(default)]
    #[serde(rename = "dataType")]
    pub data_type: JString,
    #[sqlx(rename = "plateNo")]
    #[sqlx(default)]
    #[serde(rename = "plateNo")]
    pub plate_no: JString,
    #[sqlx(rename = "siteId")]
    #[sqlx(default)]
    #[serde(rename = "siteId")]
    pub site_id: JString,
    #[sqlx(default)]
    pub location: JString,
    #[sqlx(rename = "driveNo")]
    #[sqlx(default)]
    #[serde(rename = "driveNo")]
    pub drive_no: JLong,
    #[sqlx(rename = "plateColor")]
    #[sqlx(default)]
    #[serde(rename = "plateColor")]
    pub plate_color: JString,
    #[sqlx(rename = "plateColorCode")]
    #[sqlx(default)]
    #[serde(rename = "plateColorCode")]
    pub plate_color_code: JString,
    #[sqlx(rename = "plateType")]
    #[sqlx(default)]
    #[serde(rename = "plateType")]
    pub plate_type: JString,
    #[sqlx(rename = "plateTypeCode")]
    #[sqlx(default)]
    #[serde(rename = "plateTypeCode")]
    pub plate_type_code: JString,
    #[sqlx(rename = "vehicleColor")]
    #[sqlx(default)]
    #[serde(rename = "vehicleColor")]
    pub vehicle_color: JString,
    #[sqlx(rename = "vehicleColorCode")]
    #[sqlx(default)]
    #[serde(rename = "vehicleColorCode")]
    pub vehicle_color_code: JString,
    #[sqlx(rename = "vehicleType")]
    #[sqlx(default)]
    #[serde(rename = "vehicleType")]
    pub vehicle_type: JString,
    #[sqlx(rename = "vehicleTypeCode")]
    #[sqlx(default)]
    #[serde(rename = "vehicleTypeCode")]
    pub vehicle_type_code: JString,
    #[sqlx(rename = "vehicleSpeed")]
    #[sqlx(default)]
    #[serde(rename = "vehicleSpeed")]
    pub vehicle_speed: JLong,
    #[sqlx(rename = "isOverweight")]
    #[sqlx(default)]
    #[serde(rename = "isOverweight")]
    pub is_overweight: JLong,
    #[sqlx(rename = "axleNum")]
    #[sqlx(default)]
    #[serde(rename = "axleNum")]
    pub axle_num: JLong,
    #[sqlx(rename = "overWeight")]
    #[sqlx(default)]
    #[serde(rename = "overWeight")]
    pub over_weight: JLong,
    #[sqlx(rename = "vehicleWeight")]
    #[sqlx(default)]
    #[serde(rename = "vehicleWeight")]
    pub vehicle_weight: JLong,
    #[sqlx(rename = "limitWeight")]
    #[sqlx(default)]
    #[serde(rename = "limitWeight")]
    pub limit_weight: JLong,
    #[sqlx(rename = "checkTimeUnix")]
    #[sqlx(default)]
    #[serde(rename = "checkTimeUnix")]
    pub check_time_unix: JLong,
    #[sqlx(rename = "checkTime")]
    #[sqlx(default)]
    #[serde(rename = "checkTime")]
    pub check_time: Day,
    #[sqlx(rename = "axleModel")]
    #[sqlx(default)]
    #[serde(rename = "axleModel")]
    pub axle_model: JLong,
    #[sqlx(rename = "loadRate")]
    #[sqlx(default)]
    #[serde(rename = "loadRate")]
    pub load_rate: JLong,
    #[sqlx(rename = "axleArray")]
    #[sqlx(default)]
    #[serde(rename = "axleArray")]
    pub axle_array: JString,
    #[sqlx(rename = "weighingImagesArry")]
    #[sqlx(default)]
    #[serde(rename = "weighingImagesArry")]
    pub weighing_images_arry: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: Day,
    #[sqlx(default)]
    #[serde(rename = "gradeLevel")]
    pub grade_level: JLong,
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
