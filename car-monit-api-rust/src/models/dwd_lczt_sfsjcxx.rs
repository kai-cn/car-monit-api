// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/DwdLcztSfsjcxx.java
// 职责: DwdLcztSfsjcxx —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/dwd_lczt_sfsjcxx.go（已与 Java 逐字段核对）
// 表: dwd_lczt_sfsjcxx（schema=）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct DwdLcztSfsjcxx {
    #[sqlx(default)]
    #[serde(rename = "agentPk")]
    pub agent_pk: JString,
    #[sqlx(default)]
    pub yxtzj: JString,
    #[sqlx(default)]
    pub sfsbm: JString,
    #[sqlx(default)]
    pub sfsmc: JString,
    #[sqlx(default)]
    pub jd: JString,
    #[sqlx(default)]
    pub wd: JString,
    #[sqlx(default)]
    pub sslxbh: JString,
    #[sqlx(default)]
    pub sslxmc: JString,
    #[sqlx(default)]
    pub ssldbh: JString,
    #[sqlx(default)]
    pub ssldmc: JString,
    #[sqlx(default)]
    #[serde(rename = "sczhK")]
    pub sczh_k: JString,
    #[sqlx(default)]
    #[serde(rename = "sczhN")]
    pub sczh_n: JString,
    #[sqlx(default)]
    pub ssglzxbm: JString,
    #[sqlx(default)]
    pub ssglzxmc: JString,
    #[sqlx(default)]
    pub lyxt: JString,
    #[sqlx(default)]
    #[serde(rename = "loadTime")]
    pub load_time: JString,
    #[sqlx(default)]
    #[serde(rename = "allColPk")]
    pub all_col_pk: JString,
}
