// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataReliabilityService.java:48-723
// 职责: 消息「三重确认 + 超时补偿 + 死信」保障。
// 对应关系:
//   ReliableMessageWrapper / MessageMeta   ↔ ReliableMessageWrapper / MessageMeta
//   ConcurrentHashMap<String,MessageMeta>  ↔ DashMap<String, Arc<MessageMeta>>
//   setIfAbsent / opsForList               ↔ Cache::{set_nx, right_push, list_range, lrem}
//   @Scheduled(fixedRate=...)              ↔ scheduler 注册（compensation_task / check_offline_devices）

use std::sync::atomic::{AtomicI32, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use tracing::{error, info, warn};
use uuid::Uuid;

use crate::cache::Cache;
use crate::config::ReliabilityConfig;
use crate::error::AppResult;
use crate::models::{JInt, JIsoDateTime, KafkaMessageRecord};
use crate::mq::{Bus, Message};
use crate::repo::KafkaMessageRecordRepo;
use crate::utils;

const MSG_STATUS_PREFIX: &str = "reliability:msg:status:";
const MSG_CONTENT_PREFIX: &str = "reliability:msg:content:";
const TIMEOUT_QUEUE: &str = "reliability:timeout:queue";
const DEVICE_HEARTBEAT_PREFIX: &str = "reliability:device:heartbeat:";
const LATENCY_STATS_PREFIX: &str = "reliability:latency:stats:";
const MSG_CONTENT_TTL_SECS: u64 = 86_400;
const OFFLINE_THRESHOLD_MS: i64 = 300_000;
const DEVICE_HEARTBEAT_TTL_SECS: u64 = 300;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MessageStatus {
    Pending,
    Sent,
    Confirmed,
    Dead,
}

impl MessageStatus {
    fn as_str(&self) -> &'static str {
        match self {
            MessageStatus::Pending => "PENDING",
            MessageStatus::Sent => "SENT",
            MessageStatus::Confirmed => "CONFIRMED",
            MessageStatus::Dead => "DEAD",
        }
    }

    fn parse(s: &str) -> Option<Self> {
        match s {
            "PENDING" => Some(MessageStatus::Pending),
            "SENT" => Some(MessageStatus::Sent),
            "CONFIRMED" => Some(MessageStatus::Confirmed),
            "DEAD" => Some(MessageStatus::Dead),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReliableMessageWrapper {
    pub message_id: String,
    pub data_id: String,
    pub checksum: String,
    pub operation_type: String,
    pub data: serde_json::Value,
    pub timestamp: i64,
    pub version: i32,
}

#[derive(Debug)]
pub struct MessageMeta {
    pub message_id: String,
    pub data_id: String,
    pub topic: String,
    pub checksum: String,
    pub status: std::sync::Mutex<MessageStatus>,
    pub create_time: i64,
    pub kafka_offset: std::sync::Mutex<i64>,
    pub retry_count: AtomicI32,
    pub error: std::sync::Mutex<String>,
}

#[derive(Clone)]
pub struct ReliabilityService {
    pub bus: Bus,
    pub cache: Option<Cache>,
    pub repo: KafkaMessageRecordRepo,
    pub cfg: ReliabilityConfig,
    pub pending: Arc<DashMap<String, Arc<MessageMeta>>>,
}

impl ReliabilityService {
    pub fn new(
        bus: Bus,
        cache: Option<Cache>,
        repo: KafkaMessageRecordRepo,
        cfg: ReliabilityConfig,
    ) -> Self {
        Self {
            bus,
            cache,
            repo,
            cfg,
            pending: Arc::new(DashMap::new()),
        }
    }

    pub async fn send_reliable_message(
        &self,
        data: serde_json::Value,
        data_id: &str,
        topic: &str,
    ) -> AppResult<String> {
        let message_id = generate_message_id(data_id);
        let checksum = self.calculate_checksum(&data);
        let wrapper = ReliableMessageWrapper {
            message_id: message_id.clone(),
            data_id: data_id.into(),
            checksum: checksum.clone(),
            operation_type: "INSERT".into(),
            data,
            timestamp: now_ms(),
            version: 1,
        };
        let meta = Arc::new(MessageMeta {
            message_id: message_id.clone(),
            data_id: data_id.into(),
            topic: topic.into(),
            checksum,
            status: std::sync::Mutex::new(MessageStatus::Pending),
            create_time: now_ms(),
            kafka_offset: std::sync::Mutex::new(-1),
            retry_count: AtomicI32::new(0),
            error: std::sync::Mutex::new(String::new()),
        });
        self.pending.insert(message_id.clone(), meta);

        let raw = serde_json::to_string(&wrapper)?;
        if let Some(c) = &self.cache {
            let _ = c
                .set_ttl(
                    &format!("{}{}", MSG_CONTENT_PREFIX, message_id),
                    raw.clone(),
                    Duration::from_secs(MSG_CONTENT_TTL_SECS),
                )
                .await;
            let _ = c
                .set_ttl(
                    &format!("{}{}", MSG_STATUS_PREFIX, message_id),
                    MessageStatus::Pending.as_str(),
                    Duration::from_secs(MSG_CONTENT_TTL_SECS),
                )
                .await;
        }
        self.send_to_bus(wrapper, topic, &message_id).await;
        self.schedule_timeout_check(message_id.clone());
        info!(message_id = %message_id, data_id, topic, "[可靠性服务] 发送可靠消息");
        Ok(message_id)
    }

    async fn send_to_bus(&self, wrapper: ReliableMessageWrapper, topic: &str, message_id: &str) {
        let msg = Message {
            topic: topic.into(),
            key: wrapper.data_id.clone(),
            value: serde_json::to_vec(&wrapper).unwrap_or_default(),
            headers: Default::default(),
            attempt: 0,
        };
        match self.bus.publish(msg).await {
            Ok(()) => self.handle_kafka_ack(message_id, 0).await,
            Err(e) => self.handle_send_failure(message_id, &e.to_string()).await,
        }
    }

    pub async fn handle_kafka_ack(&self, message_id: &str, offset: i64) {
        if let Some(meta) = self.pending.get(message_id) {
            *meta.status.lock().unwrap() = MessageStatus::Sent;
            *meta.kafka_offset.lock().unwrap() = offset;
            if let Some(c) = &self.cache {
                let _ = c
                    .set(
                        &format!("{}{}", MSG_STATUS_PREFIX, message_id),
                        MessageStatus::Sent.as_str(),
                    )
                    .await;
            }
        }
    }

    pub async fn handle_send_failure(&self, message_id: &str, err_msg: &str) {
        let Some(meta) = self.pending.get(message_id).map(|m| m.clone()) else {
            return;
        };
        let n = meta.retry_count.fetch_add(1, Ordering::SeqCst) + 1;
        warn!(
            message_id,
            retry_count = n,
            err = err_msg,
            "[可靠性服务] 消息发送失败"
        );
        if n < self.cfg.max_retry_count {
            let this = self.clone();
            let id = message_id.to_string();
            tokio::spawn(async move { this.retry_send(&id).await });
            return;
        }
        self.mark_as_dead_letter(message_id, err_msg).await;
    }

    pub async fn retry_send(&self, message_id: &str) {
        let Some(meta) = self.pending.get(message_id).map(|m| m.clone()) else {
            return;
        };
        let mut attempt = meta.retry_count.load(Ordering::SeqCst);
        loop {
            if attempt >= self.cfg.max_retry_count {
                self.mark_as_dead_letter(message_id, "重试次数超限").await;
                return;
            }
            attempt += 1;
            let delay = Duration::from_secs(1u64 << (attempt.min(10) as u64));
            tokio::time::sleep(delay).await;
            let published = self.publish_cached(message_id).await;
            match published {
                Ok(()) => {
                    self.handle_kafka_ack(message_id, 0).await;
                    info!(
                        message_id,
                        retry_count = attempt,
                        "[可靠性服务] 重试消息成功"
                    );
                    return;
                }
                Err(e) => {
                    warn!(message_id, retry_count = attempt, err = %e, "[可靠性服务] 重试消息失败");
                }
            }
        }
    }

    /// 从 Redis 取消息体并发送；失败返回 Err。与 send_to_bus 的区别：
    /// 这里不回调 handle_send_failure，避免 async 递归导致 future 无法判定 Send。
    async fn publish_cached(&self, message_id: &str) -> Result<(), String> {
        let Some(cache) = &self.cache else {
            return Err("缓存未启用".into());
        };
        let content = match cache
            .get(&format!("{}{}", MSG_CONTENT_PREFIX, message_id))
            .await
        {
            Ok(Some(v)) => v,
            _ => return Err("消息内容已过期".into()),
        };
        let wrapper: ReliableMessageWrapper =
            serde_json::from_str(&content).map_err(|e| e.to_string())?;
        let topic = self
            .pending
            .get(message_id)
            .map(|m| m.topic.clone())
            .unwrap_or_default();
        self.bus
            .publish(Message {
                topic: topic.clone(),
                key: wrapper.data_id.clone(),
                value: serde_json::to_vec(&wrapper).map_err(|e| e.to_string())?,
                headers: Default::default(),
                attempt: 0,
            })
            .await
            .map_err(|e| e.to_string())
    }

    async fn mark_as_dead_letter(&self, message_id: &str, err_msg: &str) {
        let Some((_, meta)) = self.pending.remove(message_id) else {
            return;
        };
        *meta.status.lock().unwrap() = MessageStatus::Dead;
        *meta.error.lock().unwrap() = err_msg.into();
        if let Some(c) = &self.cache {
            let _ = c
                .set(
                    &format!("{}{}", MSG_STATUS_PREFIX, message_id),
                    MessageStatus::Dead.as_str(),
                )
                .await;
        }
        let content = match &self.cache {
            Some(c) => c
                .get(&format!("{}{}", MSG_CONTENT_PREFIX, message_id))
                .await
                .ok()
                .flatten()
                .unwrap_or_default(),
            None => String::new(),
        };
        let rec = KafkaMessageRecord {
            id: Uuid::new_v4().to_string().into(),
            data_id: meta.data_id.clone().into(),
            topic: meta.topic.clone().into(),
            message_json: content.into(),
            status: JInt::from(KafkaMessageRecordRepo::STATUS_DEAD),
            retry_count: JInt::from(meta.retry_count.load(Ordering::SeqCst)),
            create_time: JIsoDateTime::from(chrono::Utc::now()),
            send_time: JIsoDateTime::default(),
            error_msg: err_msg.into(),
        };
        if let Err(e) = self.repo.insert(&rec).await {
            error!(message_id, err = %e, "[可靠性服务] 死信入库失败");
        }
        error!(message_id, data_id = %meta.data_id, err = err_msg, "[可靠性服务] 消息进入死信队列");
        self.send_alert(
            "DEAD_LETTER",
            &format!("消息进入死信队列: {}, 错误: {}", message_id, err_msg),
        );
    }

    pub async fn confirm_consumption(&self, message_id: &str, consumer_type: &str) {
        let Some((_, meta)) = self.pending.remove(message_id) else {
            return;
        };
        let latency = now_ms() - meta.create_time;
        *meta.status.lock().unwrap() = MessageStatus::Confirmed;
        if let Some(c) = &self.cache {
            let _ = c
                .set(
                    &format!("{}{}", MSG_STATUS_PREFIX, message_id),
                    MessageStatus::Confirmed.as_str(),
                )
                .await;
            let key = format!(
                "{}{}:{}",
                LATENCY_STATS_PREFIX,
                consumer_type,
                chrono::Utc::now().format("%Y-%m-%d")
            );
            let _ = c.right_push(&key, latency.to_string()).await;
            let _ = c.ltrim(&key, -1000, -1).await;
        }
        info!(
            message_id,
            consumer = consumer_type,
            latency_ms = latency,
            "[可靠性服务] 消费端确认"
        );
        if latency > self.cfg.alert_threshold_ms as i64 {
            self.send_alert(
                "HIGH_LATENCY",
                &format!("消息处理延迟过高: {}, 延迟: {}ms", message_id, latency),
            );
        }
    }

    fn schedule_timeout_check(&self, message_id: String) {
        let this = self.clone();
        let timeout = Duration::from_millis(self.cfg.message_timeout_ms);
        tokio::spawn(async move {
            tokio::time::sleep(timeout).await;
            let mut status = None;
            if let Some(c) = &this.cache {
                if let Ok(Some(v)) = c.get(&format!("{}{}", MSG_STATUS_PREFIX, message_id)).await {
                    status = MessageStatus::parse(&v);
                }
            }
            if status != Some(MessageStatus::Confirmed) {
                this.handle_message_timeout(&message_id, status).await;
            }
        });
    }

    async fn handle_message_timeout(&self, message_id: &str, status: Option<MessageStatus>) {
        warn!(
            message_id,
            status = status.map(|s| s.as_str()).unwrap_or("UNKNOWN"),
            "[可靠性服务] 消息超时"
        );
        if let Some(c) = &self.cache {
            let _ = c.right_push(TIMEOUT_QUEUE, message_id.to_string()).await;
        }
        self.send_alert(
            "MESSAGE_TIMEOUT",
            &format!(
                "消息超时未确认: {}, 状态: {}",
                message_id,
                status.map(|s| s.as_str()).unwrap_or("UNKNOWN")
            ),
        );
    }

    /// 对应 @Scheduled compensationTask：取超时队列前 50 条按状态补偿。
    pub async fn compensation_task(&self) {
        let Some(c) = &self.cache else { return };
        let ids = match c.list_range(TIMEOUT_QUEUE, 0, 50).await {
            Ok(v) => v,
            Err(e) => {
                error!(err = %e, "[可靠性服务] 补偿任务读取超时队列失败");
                return;
            }
        };
        if ids.is_empty() {
            return;
        }
        info!(count = ids.len(), "[可靠性服务] 补偿任务处理");
        for message_id in ids {
            let _ = c.lrem(TIMEOUT_QUEUE, 1, &message_id).await;
            let mut status = None;
            if let Ok(Some(v)) = c.get(&format!("{}{}", MSG_STATUS_PREFIX, message_id)).await {
                status = MessageStatus::parse(&v);
            }
            match status {
                Some(MessageStatus::Pending) => self.retry_send(&message_id).await,
                Some(MessageStatus::Sent) => self.resend_message(&message_id).await,
                Some(MessageStatus::Confirmed) | Some(MessageStatus::Dead) => {}
                None => warn!(message_id, status = "UNKNOWN", "[可靠性服务] 未知状态"),
            }
        }
    }

    async fn resend_message(&self, message_id: &str) {
        let Some(c) = &self.cache else { return };
        let content = match c
            .get(&format!("{}{}", MSG_CONTENT_PREFIX, message_id))
            .await
        {
            Ok(Some(v)) => v,
            _ => {
                error!(message_id, "[可靠性服务] 重发失败：消息内容已过期");
                return;
            }
        };
        let wrapper: ReliableMessageWrapper = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(e) => {
                error!(message_id, err = %e, "[可靠性服务] 重发失败：消息体解析异常");
                return;
            }
        };
        let topic = self
            .pending
            .get(message_id)
            .map(|m| m.topic.clone())
            .unwrap_or_default();
        self.send_to_bus(wrapper, &topic, message_id).await;
        info!(message_id, "[可靠性服务] 重发消息");
    }

    pub async fn update_device_heartbeat(&self, device_id: &str) {
        if let Some(c) = &self.cache {
            let _ = c
                .set_ttl(
                    &format!("{}{}", DEVICE_HEARTBEAT_PREFIX, device_id),
                    now_ms().to_string(),
                    Duration::from_secs(DEVICE_HEARTBEAT_TTL_SECS),
                )
                .await;
        }
    }

    /// 对应 @Scheduled(fixedRate=300000) checkOfflineDevices。
    pub async fn check_offline_devices(&self) {
        let Some(c) = &self.cache else { return };
        let keys = match c.scan_keys(&format!("{}*", DEVICE_HEARTBEAT_PREFIX)).await {
            Ok(v) => v,
            Err(e) => {
                warn!(err = %e, "[可靠性服务] 扫描设备心跳失败");
                return;
            }
        };
        let now = now_ms();
        for key in keys {
            let v = c.get_int(&key).await.ok().flatten().unwrap_or(0);
            let device_id = key.strip_prefix(DEVICE_HEARTBEAT_PREFIX).unwrap_or(&key);
            if now - v > OFFLINE_THRESHOLD_MS {
                warn!(
                    device_id,
                    since_sec = (now - v) / 1000,
                    "[可靠性服务] 设备离线"
                );
                self.send_alert("DEVICE_OFFLINE", &format!("设备离线: {}", device_id));
            }
        }
    }

    pub fn calculate_checksum(&self, data: &serde_json::Value) -> String {
        utils::md5_hex(&serde_json::to_string(data).unwrap_or_default())
    }

    pub fn verify_checksum(&self, data: &serde_json::Value, expected: &str) -> bool {
        let actual = self.calculate_checksum(data);
        if actual != expected {
            warn!(expected, actual, "[可靠性服务] 数据完整性校验失败");
            return false;
        }
        true
    }

    pub async fn is_message_processed(&self, message_id: &str) -> bool {
        match &self.cache {
            Some(c) => c
                .exists(&format!("{}{}", MSG_STATUS_PREFIX, message_id))
                .await
                .unwrap_or(false),
            None => false,
        }
    }

    pub async fn mark_message_processed(&self, message_id: &str) {
        if let Some(c) = &self.cache {
            let _ = c
                .set_ttl(
                    &format!("{}{}", MSG_STATUS_PREFIX, message_id),
                    MessageStatus::Confirmed.as_str(),
                    Duration::from_secs(MSG_CONTENT_TTL_SECS),
                )
                .await;
        }
    }

    fn send_alert(&self, alert_type: &str, message: &str) {
        error!(alert_type, message, "[告警]");
    }
}

fn generate_message_id(data_id: &str) -> String {
    format!(
        "{}-{}-{}-{}",
        now_ms(),
        now_ms() % 1_000_000,
        &Uuid::new_v4().simple().to_string()[..8],
        java_hash(data_id)
    )
}

fn java_hash(s: &str) -> i32 {
    s.chars()
        .fold(0i32, |h, c| h.wrapping_mul(31).wrapping_add(c as i32))
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}
