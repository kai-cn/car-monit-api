// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/CarParaVO.java
// 职责: CarParaVO —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/car_para_vo.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct CarParaVO {
    #[sqlx(skip)]
    pub carlist: JList<CarVO>,
    #[sqlx(skip)]
    #[serde(rename = "carNo")]
    pub car_no: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime1")]
    pub apply_time1: JString,
    #[sqlx(skip)]
    #[serde(rename = "applyTime2")]
    pub apply_time2: JString,
    #[sqlx(skip)]
    #[serde(rename = "carNoList")]
    pub car_no_list: JList<String>,
    #[sqlx(skip)]
    #[serde(rename = "pageNum")]
    pub page_num: JInt,
    #[sqlx(skip)]
    #[serde(rename = "pageSize")]
    pub page_size: JInt,
    #[sqlx(skip)]
    #[serde(rename = "startNum")]
    pub start_num: JInt,
    #[sqlx(skip)]
    #[serde(rename = "endNum")]
    pub end_num: JInt,
    #[sqlx(skip)]
    #[serde(rename = "starTime")]
    pub star_time: JInt,
    #[sqlx(skip)]
    #[serde(rename = "endTime")]
    pub end_time: JInt,
    #[sqlx(skip)]
    pub flag: JString,
    #[sqlx(skip)]
    #[serde(rename = "sectionList")]
    pub section_list: JList<String>,
    #[sqlx(skip)]
    #[serde(rename = "lastExitTime")]
    pub last_exit_time: JIsoDateTime,
}
