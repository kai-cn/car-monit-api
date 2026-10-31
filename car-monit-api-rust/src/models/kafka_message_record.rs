// 来源: pro-business-api/src/main/java/com/ruoyi/base/domain/KafkaMessageRecord.java
// 职责: KafkaMessageRecord —— Java 实体/DTO 的 Rust 等价定义（字段顺序、JSON 名称与 Java 一致）。
// 对应 Go 文件: internal/model/kafka_message_record.go（已与 Java 逐字段核对）
// 表: jl_data01.kafka_message_record（schema=jl_data01）
// DIFF: Lombok @Data 的 getter/setter 不再生成；字段直接公开。
#![allow(non_snake_case, unused_imports)]

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::*;

#[derive(Debug, Clone, Default, Serialize, Deserialize, sqlx::FromRow)]
#[serde(default)]
pub struct KafkaMessageRecord {
    #[sqlx(default)]
    pub id: JString,
    #[sqlx(default)]
    #[serde(rename = "dataId")]
    pub data_id: JString,
    #[sqlx(default)]
    pub topic: JString,
    #[sqlx(default)]
    #[serde(rename = "messageJson")]
    pub message_json: JString,
    #[sqlx(default)]
    pub status: JInt,
    #[sqlx(default)]
    #[serde(rename = "retryCount")]
    pub retry_count: JInt,
    #[sqlx(default)]
    #[serde(rename = "createTime")]
    pub create_time: JIsoDateTime,
    #[sqlx(default)]
    #[serde(rename = "sendTime")]
    pub send_time: JIsoDateTime,
    #[sqlx(default)]
    #[serde(rename = "errorMsg")]
    pub error_msg: JString,
}

impl KafkaMessageRecord {
    /// 对应 Java @TableName(value = "kafka_message_record", schema = "jl_data01")。
    pub const TABLE: &'static str = "jl_data01.kafka_message_record";
    pub const SCHEMA: &'static str = "jl_data01";
    pub const PK: &'static str = "id";
}
