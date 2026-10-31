// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DelayMonitoringService.java:36-471
// 职责: 四段延迟（设备上报 / 消息传输 / 数据处理 / 端到端）的埋点、告警与统计。
// 对应关系:
//   ConcurrentHashMap<String,Long> ×3 ↔ DashMap<String,i64> ×3
//   redisTemplate.opsForList().rightPush + expire ↔ Cache::{right_push, expire}
//   @Scheduled(fixedRate=600000)     ↔ scheduler 注册
//   triggerAlert（1 分钟节流）        ↔ Cache::set_nx

use std::sync::Arc;
use std::time::Duration;

use dashmap::DashMap;
use serde::Serialize;
use tracing::{error, info, warn};

use crate::cache::Cache;
use crate::config::MonitoringConfig;

const DEVICE_DELAY_PREFIX: &str = "monitoring:delay:device:";
const MESSAGE_DELAY_PREFIX: &str = "monitoring:delay:message:";
const PROCESS_DELAY_PREFIX: &str = "monitoring:delay:process:";
const E2E_DELAY_PREFIX: &str = "monitoring:delay:e2e:";
const ALERT_COUNT_PREFIX: &str = "monitoring:alert:count:";
const DELAY_SAMPLE_TTL_SECS: u64 = 172_800;
const ALERT_THROTTLE_SECS: u64 = 60;

#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DelayStats {
    pub device_report_avg: i64,
    pub device_report_max: i64,
    pub message_transfer_avg: i64,
    pub message_transfer_max: i64,
    pub data_process_avg: i64,
    pub data_process_max: i64,
    pub end_to_end_avg: i64,
    pub end_to_end_max: i64,
}

#[derive(Clone)]
pub struct DelayMonitorService {
    cache: Option<Cache>,
    cfg: MonitoringConfig,
    message_produce_times: Arc<DashMap<String, i64>>,
    message_consume_times: Arc<DashMap<String, i64>>,
    device_capture_times: Arc<DashMap<String, i64>>,
}

impl DelayMonitorService {
    pub fn new(cache: Option<Cache>, cfg: MonitoringConfig) -> Self {
        Self {
            cache,
            cfg,
            message_produce_times: Arc::new(DashMap::new()),
            message_consume_times: Arc::new(DashMap::new()),
            device_capture_times: Arc::new(DashMap::new()),
        }
    }

    pub fn init(&self) {
        info!(
            device = self.cfg.device_report_threshold_ms,
            message = self.cfg.message_transfer_threshold_ms,
            process = self.cfg.data_process_threshold_ms,
            e2e = self.cfg.end_to_end_threshold_ms,
            "[延迟监控] 初始化完成"
        );
    }

    pub fn record_device_capture_time(&self, data_id: &str, capture_time: i64) {
        self.device_capture_times
            .insert(data_id.into(), capture_time);
    }

    pub async fn record_service_receive_time(&self, data_id: &str, device_id: &str) -> i64 {
        let Some((_, capture)) = self.device_capture_times.remove(data_id) else {
            return -1;
        };
        let delay = now_ms() - capture;
        let key = format!("{}{}:{}", DEVICE_DELAY_PREFIX, device_id, compact_date());
        self.push_sample(&key, delay).await;
        if delay > self.cfg.device_report_threshold_ms as i64 {
            self.trigger_alert(
                "DEVICE_REPORT_DELAY",
                device_id,
                delay,
                self.cfg.device_report_threshold_ms as i64,
            )
            .await;
        }
        delay
    }

    pub fn record_message_produce_time(&self, message_id: &str) {
        self.message_produce_times
            .insert(message_id.into(), now_ms());
    }

    pub async fn record_message_consume_time(&self, message_id: &str) -> i64 {
        let Some((_, produce)) = self.message_produce_times.remove(message_id) else {
            return -1;
        };
        let delay = now_ms() - produce;
        let key = format!("{}{}", MESSAGE_DELAY_PREFIX, compact_date());
        self.push_sample(&key, delay).await;
        if delay > self.cfg.message_transfer_threshold_ms as i64 {
            self.trigger_alert(
                "MESSAGE_TRANSFER_DELAY",
                message_id,
                delay,
                self.cfg.message_transfer_threshold_ms as i64,
            )
            .await;
        }
        delay
    }

    pub fn record_process_start_time(&self, message_id: &str) {
        self.message_consume_times
            .insert(message_id.into(), now_ms());
    }

    pub async fn record_process_end_time(&self, message_id: &str) -> i64 {
        let Some((_, consume)) = self.message_consume_times.remove(message_id) else {
            return -1;
        };
        let delay = now_ms() - consume;
        let key = format!("{}{}", PROCESS_DELAY_PREFIX, compact_date());
        self.push_sample(&key, delay).await;
        if delay > self.cfg.data_process_threshold_ms as i64 {
            self.trigger_alert(
                "DATA_PROCESS_DELAY",
                message_id,
                delay,
                self.cfg.data_process_threshold_ms as i64,
            )
            .await;
        }
        delay
    }

    pub async fn calculate_end_to_end_delay(
        &self,
        _data_id: &str,
        capture_time: i64,
        storage_time: i64,
        device_id: &str,
    ) -> i64 {
        let delay = storage_time - capture_time;
        let key = format!("{}{}:{}", E2E_DELAY_PREFIX, device_id, compact_date());
        self.push_sample(&key, delay).await;
        if delay > self.cfg.end_to_end_threshold_ms as i64 {
            self.trigger_alert(
                "END_TO_END_DELAY",
                device_id,
                delay,
                self.cfg.end_to_end_threshold_ms as i64,
            )
            .await;
        }
        delay
    }

    async fn trigger_alert(&self, alert_type: &str, target_id: &str, actual: i64, threshold: i64) {
        let Some(c) = &self.cache else { return };
        let key = format!("{}{}:{}", ALERT_COUNT_PREFIX, alert_type, target_id);
        match c
            .set_nx(
                &key,
                now_ms().to_string(),
                Duration::from_secs(ALERT_THROTTLE_SECS),
            )
            .await
        {
            Ok(true) => error!(
                alert_type,
                target_id, actual, threshold, "[延迟监控告警] 延迟超过阈值"
            ),
            _ => {}
        }
    }

    pub async fn generate_stats_report(&self) {
        let stats = self.calculate_stats().await;
        info!(
            device_avg = stats.device_report_avg,
            device_max = stats.device_report_max,
            message_avg = stats.message_transfer_avg,
            message_max = stats.message_transfer_max,
            process_avg = stats.data_process_avg,
            process_max = stats.data_process_max,
            e2e_avg = stats.end_to_end_avg,
            e2e_max = stats.end_to_end_max,
            "[延迟监控统计]"
        );
    }

    pub async fn calculate_stats(&self) -> DelayStats {
        let device = self.get_delays(DEVICE_DELAY_PREFIX).await;
        let message = self.get_delays(MESSAGE_DELAY_PREFIX).await;
        let process = self.get_delays(PROCESS_DELAY_PREFIX).await;
        let e2e = self.get_delays(E2E_DELAY_PREFIX).await;
        DelayStats {
            device_report_avg: avg(&device),
            device_report_max: max(&device),
            message_transfer_avg: avg(&message),
            message_transfer_max: max(&message),
            data_process_avg: avg(&process),
            data_process_max: max(&process),
            end_to_end_avg: avg(&e2e),
            end_to_end_max: max(&e2e),
        }
    }

    async fn get_delays(&self, prefix: &str) -> Vec<i64> {
        let Some(c) = &self.cache else { return vec![] };
        let pattern = format!("{}*:{}", prefix, compact_date());
        let keys = match c.scan_keys(&pattern).await {
            Ok(v) => v,
            Err(e) => {
                warn!(err = %e, "[延迟监控] 扫描样本 key 失败");
                return vec![];
            }
        };
        let mut out = Vec::new();
        for key in keys {
            if let Ok(values) = c.list_range(&key, 0, -1).await {
                out.extend(values.iter().filter_map(|v| v.parse::<i64>().ok()));
            }
        }
        out
    }

    async fn push_sample(&self, key: &str, delay: i64) {
        if let Some(c) = &self.cache {
            if let Err(e) = c.right_push(key, delay.to_string()).await {
                warn!(key, err = %e, "[延迟监控] 写入延迟样本失败");
                return;
            }
            let _ = c
                .expire(key, Duration::from_secs(DELAY_SAMPLE_TTL_SECS))
                .await;
        }
    }
}

fn avg(values: &[i64]) -> i64 {
    if values.is_empty() {
        0
    } else {
        values.iter().sum::<i64>() / values.len() as i64
    }
}

fn max(values: &[i64]) -> i64 {
    values.iter().copied().max().unwrap_or(0)
}

fn compact_date() -> String {
    chrono::Utc::now().format("%Y%m%d").to_string()
}

fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}
