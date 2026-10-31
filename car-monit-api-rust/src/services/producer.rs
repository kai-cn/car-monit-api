// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/KafkaProducerService.java:41-285
// 职责: 消息生产入口：可靠发送 + 失败消息后台重试 + 延迟/丢失埋点。
// 对应关系:
//   KafkaTemplate.send                     ↔ Bus::publish（同步 ack）
//   ListenableFutureCallback               ↔ publish 的 Ok/Err 分支
//   kafkaMessageRecordMapper.updateStatus  ↔ KafkaMessageRecordRepo::update_status_by_id
//   startRetryTask（线程池）                ↔ tokio::spawn + watch 停止信号

use std::sync::Arc;
use std::time::Duration;

use tracing::{error, info, warn};

use crate::config::KafkaConfig;
use crate::mq::{Bus, Message};
use crate::repo::KafkaMessageRecordRepo;
use crate::services::delay_monitor::DelayMonitorService;
use crate::services::loss_detection::LossDetectionService;
use crate::services::reliability::ReliabilityService;

const RETRY_BATCH_SIZE: i64 = 100;
const RETRY_INTERVAL_SECS: u64 = 30;
const RETRY_ERROR_BACKOFF_SECS: u64 = 60;

#[derive(Clone)]
pub struct KafkaProducerService {
    pub bus: Bus,
    pub repo: KafkaMessageRecordRepo,
    pub reliability: Arc<ReliabilityService>,
    pub loss: Arc<LossDetectionService>,
    pub delay: Arc<DelayMonitorService>,
    pub topic: String,
    pub max_retry: i32,
}

impl KafkaProducerService {
    pub fn new(
        bus: Bus,
        repo: KafkaMessageRecordRepo,
        reliability: Arc<ReliabilityService>,
        loss: Arc<LossDetectionService>,
        delay: Arc<DelayMonitorService>,
        cfg: &KafkaConfig,
    ) -> Self {
        Self {
            bus,
            repo,
            reliability,
            loss,
            delay,
            topic: if cfg.topic.snapshot_flow.is_empty() {
                "ods-rt-szdn-snapshot-flow".into()
            } else {
                cfg.topic.snapshot_flow.clone()
            },
            max_retry: if cfg.max_retry_count <= 0 {
                10
            } else {
                cfg.max_retry_count
            },
        }
    }

    pub fn start(self, mut stop: tokio::sync::watch::Receiver<bool>) {
        info!(topic = %self.topic, max_retry = self.max_retry, "[Kafka生产者服务] 初始化完成");
        let this = self.clone();
        tokio::spawn(async move {
            loop {
                if *stop.borrow() {
                    info!("[Kafka生产者] 重试任务退出");
                    return;
                }
                let ok = this.run_retry_once().await;
                let wait = if ok {
                    RETRY_INTERVAL_SECS
                } else {
                    RETRY_ERROR_BACKOFF_SECS
                };
                tokio::select! {
                    _ = stop.changed() => {
                        if *stop.borrow() { return; }
                    }
                    _ = tokio::time::sleep(Duration::from_secs(wait)) => {}
                }
            }
        });
    }

    /// 对应 sendSnapshotFlowData：生产时间 → 可靠发送 → 记录上报消息 ID。
    pub async fn send_snapshot_flow_data(
        &self,
        data: serde_json::Value,
        data_id: &str,
    ) -> crate::error::AppResult<String> {
        self.delay.record_message_produce_time(data_id);
        let message_id = self
            .reliability
            .send_reliable_message(data.clone(), data_id, &self.topic)
            .await?;
        let device = extract_device_id(&data);
        self.loss
            .record_reported_message(&message_id, &device, chrono::Utc::now().timestamp_millis())
            .await;
        info!(data_id, message_id = %message_id, "[Kafka生产者] 发送消息");
        Ok(message_id)
    }

    pub async fn send_batch_snapshot_flow_data(&self, data_list: Vec<serde_json::Value>) {
        info!(count = data_list.len(), "[Kafka生产者] 批量发送消息");
        for data in data_list {
            let id = extract_data_id(&data);
            if id.is_empty() {
                continue;
            }
            if let Err(e) = self.send_snapshot_flow_data(data, &id).await {
                error!(data_id = %id, err = %e, "[Kafka生产者] 批量发送异常");
            }
        }
    }

    async fn run_retry_once(&self) -> bool {
        let records = match self
            .repo
            .select_failed_records(self.max_retry, RETRY_BATCH_SIZE)
            .await
        {
            Ok(v) => v,
            Err(e) => {
                error!(err = %e, "[Kafka生产者] 重试任务异常");
                return false;
            }
        };
        if records.is_empty() {
            return true;
        }
        info!(count = records.len(), "[Kafka生产者] 开始重试消息");
        for r in records {
            let topic = if r.topic.is_empty() {
                self.topic.clone()
            } else {
                r.topic.as_str().to_string()
            };
            let result = self
                .bus
                .publish(Message {
                    topic: topic.clone(),
                    key: r.data_id.as_str().to_string(),
                    value: r.message_json.as_str().as_bytes().to_vec(),
                    headers: Default::default(),
                    attempt: 0,
                })
                .await;
            match result {
                Ok(()) => {
                    info!(data_id = %r.data_id, "[Kafka生产者] 消息发送成功");
                    if let Err(e) = self
                        .repo
                        .update_status_by_id(
                            &r.id,
                            KafkaMessageRecordRepo::STATUS_SUCCESS,
                            chrono::Utc::now(),
                        )
                        .await
                    {
                        error!(id = %r.id, err = %e, "[Kafka生产者] 更新发送状态失败");
                    }
                    self.reliability.handle_kafka_ack(&r.data_id, 0).await;
                }
                Err(e) => {
                    warn!(data_id = %r.data_id, err = %e, "[Kafka生产者] 消息发送失败");
                    if let Err(e2) = self.repo.increment_retry_count(&r.id, &e.to_string()).await {
                        error!(id = %r.id, err = %e2, "[Kafka生产者] 累加重试次数失败");
                    }
                }
            }
        }
        true
    }
}

const DEVICE_ID_FIELDS: &[&str] = &[
    "deviceId",
    "deviceid",
    "device_ip",
    "deviceIp",
    "gantrycode",
    "gantryId",
];
const DATA_ID_FIELDS: &[&str] = &["bigId", "id", "uuid", "dataId"];

pub fn extract_device_id(data: &serde_json::Value) -> String {
    first_non_empty(data, DEVICE_ID_FIELDS).unwrap_or_else(|| "unknown".into())
}

pub fn extract_data_id(data: &serde_json::Value) -> String {
    first_non_empty(data, DATA_ID_FIELDS).unwrap_or_default()
}

fn first_non_empty(data: &serde_json::Value, fields: &[&str]) -> Option<String> {
    let obj = data.as_object()?;
    for f in fields {
        if let Some(v) = obj.get(*f) {
            if v.is_null() {
                continue;
            }
            let s = match v {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            if !s.is_empty() {
                return Some(s);
            }
        }
    }
    None
}
