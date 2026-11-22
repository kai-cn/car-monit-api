// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/PulsarMessageRecord.java
// 职责: PulsarMessageRecord —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/pulsar_message_record.go（已与 Java 逐字段核对）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct PulsarMessageRecord {
    #[sqlx(skip)]
    pub id: JString,
    #[sqlx(skip)]
    #[serde(rename = "dataId")]
    pub data_id: JString,
    #[sqlx(skip)]
    pub topic: JString,
    #[sqlx(skip)]
    #[serde(rename = "messageJson")]
    pub message_json: JString,
    #[sqlx(skip)]
    pub status: JInt,
    #[sqlx(skip)]
    #[serde(rename = "retryCount")]
    pub retry_count: JInt,
    #[sqlx(skip)]
    #[serde(rename = "messageId")]
    pub message_id: JString,
    #[sqlx(skip)]
    #[serde(rename = "createTime")]
    pub create_time: JIsoDateTime,
    #[sqlx(skip)]
    #[serde(rename = "sendTime")]
    pub send_time: JIsoDateTime,
    #[sqlx(skip)]
    #[serde(rename = "errorMsg")]
    pub error_msg: JString,
}
