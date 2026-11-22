// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/SysUtil.java
// 职责: SysUtil —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/sys_util.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct SysUtil {
    #[sqlx(skip)]
    #[serde(rename = "bussType")]
    pub buss_type: JString,
    #[sqlx(skip)]
    #[serde(rename = "bussCode")]
    pub buss_code: JString,
    #[sqlx(skip)]
    #[serde(rename = "queryCondtion")]
    pub query_condtion: JString,
}
