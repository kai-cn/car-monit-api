// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/impl/DataLossDetectionService.java:37-417
// 职责: 上报消息 ID 与库内主键的差集统计（丢失 / 重复识别）。
// 对应关系:
//   DetectionResult                         ↔ DetectionResult + passed()
//   @Value("${detection.*}")                ↔ DetectionConfig
//   opsForSet().add/members                 ↔ Cache::{sadd, smembers}
//   @Scheduled(fixedRateString=...)         ↔ scheduler 注册 scheduled_detection

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::Duration;

use serde::Serialize;
use tracing::{error, info, warn};

use crate::cache::Cache;
use crate::config::DetectionConfig;
use crate::error::AppResult;
use crate::repo::SnapshotFlowRepo;
use crate::services::reliability::ReliabilityService;
use crate::utils;

const REPORTED_PREFIX: &str = "detection:reported:";
const REPORT_PREFIX: &str = "detection:report:";
const DEVICE_COUNT_PREFIX: &str = "detection:device:count:";
const REPORTED_SET_TTL_SECS: u64 = 172_800;
const DEVICE_COUNT_TTL_SECS: u64 = 172_800;
const REPORT_TTL_SECS: u64 = 604_800;

#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct DetectionResult {
    pub start_time: String,
    pub end_time: String,
    pub reported_count: usize,
    pub stored_count: usize,
    pub lost_count: usize,
    pub loss_rate: f64,
    pub lost_message_ids: Vec<String>,
    pub duplicate_count: usize,
    pub duplicate_message_ids: Vec<String>,
}

impl DetectionResult {
    pub fn passed(&self) -> bool {
        self.loss_rate == 0.0 && self.duplicate_count == 0
    }
}

#[derive(Clone)]
pub struct LossDetectionService {
    pub snapshot: SnapshotFlowRepo,
    pub cache: Option<Cache>,
    pub reliability: Arc<ReliabilityService>,
    pub cfg: DetectionConfig,
}

impl LossDetectionService {
    pub fn new(
        snapshot: SnapshotFlowRepo,
        cache: Option<Cache>,
        reliability: Arc<ReliabilityService>,
        cfg: DetectionConfig,
    ) -> Self {
        Self {
            snapshot,
            cache,
            reliability,
            cfg,
        }
    }

    pub fn init(&self) {
        info!(
            window_minutes = self.cfg.window_size_minutes,
            interval_minutes = self.cfg.interval_minutes,
            loss_threshold = self.cfg.loss_threshold_percent,
            "[数据丢失检测] 初始化完成"
        );
    }

    pub async fn record_reported_message(&self, message_id: &str, device_id: &str, timestamp: i64) {
        let Some(c) = &self.cache else { return };
        let at =
            chrono::DateTime::from_timestamp_millis(timestamp).unwrap_or_else(chrono::Utc::now);
        let hour_key = format!("{}{}", REPORTED_PREFIX, at.format("%Y-%m-%d %H:00:00"));
        if let Err(e) = c.sadd(&hour_key, message_id).await {
            warn!(message_id, err = %e, "[数据丢失检测] 记录上报消息失败");
        }
        let _ = c
            .expire(&hour_key, Duration::from_secs(REPORTED_SET_TTL_SECS))
            .await;

        let device_key = format!(
            "{}{}:{}",
            DEVICE_COUNT_PREFIX,
            device_id,
            at.format("%Y-%m-%d")
        );
        let _ = c.incr(&device_key, 1).await;
        let _ = c
            .expire(&device_key, Duration::from_secs(DEVICE_COUNT_TTL_SECS))
            .await;
    }

    pub async fn scheduled_detection(&self) {
        let end = chrono::Utc::now();
        let start = end - chrono::Duration::minutes(self.cfg.window_size_minutes.max(1));
        info!(start = %start, end = %end, "[数据丢失检测] 开始检测");
        match self.detect_data_loss(start, end).await {
            Ok(result) => {
                self.generate_report(&result).await;
                if result.loss_rate > self.cfg.loss_threshold_percent {
                    self.send_alert(&result);
                }
            }
            Err(e) => error!(err = %e, "[数据丢失检测] 定时检测异常"),
        }
    }

    pub async fn detect_data_loss(
        &self,
        start: chrono::DateTime<chrono::Utc>,
        end: chrono::DateTime<chrono::Utc>,
    ) -> AppResult<DetectionResult> {
        let start_s = utils::format_datetime(&start);
        let end_s = utils::format_datetime(&end);
        let reported = self.get_reported_message_ids(start, end).await;
        let stored_ids = self.snapshot.list_big_ids_between(&start_s, &end_s).await?;

        let mut stored = HashSet::with_capacity(stored_ids.len());
        let mut seen = HashSet::with_capacity(stored_ids.len());
        let mut duplicates = Vec::new();
        for id in &stored_ids {
            stored.insert(id.clone());
            if !seen.insert(id.clone()) {
                duplicates.push(id.clone());
            }
        }
        let lost: Vec<String> = reported
            .iter()
            .filter(|id| !stored.contains(*id))
            .cloned()
            .collect();
        let reported_count = reported.len();
        let loss_rate = if reported_count > 0 {
            lost.len() as f64 / reported_count as f64 * 100.0
        } else {
            0.0
        };
        let result = DetectionResult {
            start_time: start_s,
            end_time: end_s,
            reported_count,
            stored_count: stored_ids.len(),
            lost_count: lost.len(),
            loss_rate,
            lost_message_ids: lost,
            duplicate_count: duplicates.len(),
            duplicate_message_ids: duplicates,
        };
        info!(
            reported = result.reported_count,
            stored = result.stored_count,
            lost = result.lost_count,
            duplicate = result.duplicate_count,
            loss_rate = format!("{:.2}", result.loss_rate),
            "[数据丢失检测] 检测完成"
        );
        Ok(result)
    }

    async fn get_reported_message_ids(
        &self,
        start: chrono::DateTime<chrono::Utc>,
        end: chrono::DateTime<chrono::Utc>,
    ) -> HashSet<String> {
        let mut ids = HashSet::new();
        let Some(c) = &self.cache else { return ids };
        let mut current = start;
        while current < end {
            let key = format!("{}{}", REPORTED_PREFIX, current.format("%Y-%m-%d %H:00:00"));
            match c.smembers(&key).await {
                Ok(members) => ids.extend(members),
                Err(e) => warn!(key, err = %e, "[数据丢失检测] 读取上报集合失败"),
            }
            current += chrono::Duration::hours(1);
        }
        ids
    }

    async fn generate_report(&self, result: &DetectionResult) {
        let report_id = &uuid::Uuid::new_v4().simple().to_string()[..8];
        let report = serde_json::json!({
            "reportId": report_id,
            "startTime": result.start_time,
            "endTime": result.end_time,
            "reportedCount": result.reported_count,
            "storedCount": result.stored_count,
            "lostCount": result.lost_count,
            "duplicateCount": result.duplicate_count,
            "lossRate": result.loss_rate,
            "generatedTime": utils::format_datetime(&chrono::Utc::now()),
        });
        if let Some(c) = &self.cache {
            if let Err(e) = c
                .set_ttl(
                    &format!("{}{}", REPORT_PREFIX, report_id),
                    report.to_string(),
                    Duration::from_secs(REPORT_TTL_SECS),
                )
                .await
            {
                warn!(report_id, err = %e, "[数据丢失检测] 报告写入失败");
            }
        }
        info!(report_id, "[数据丢失检测] 生成报告");
    }

    fn send_alert(&self, result: &DetectionResult) {
        error!(
            start = %result.start_time,
            end = %result.end_time,
            reported = result.reported_count,
            stored = result.stored_count,
            lost = result.lost_count,
            loss_rate = result.loss_rate,
            "[数据丢失检测告警] 数据丢失率超过阈值"
        );
    }

    pub async fn trigger_compensation(&self, result: &DetectionResult) {
        if result.lost_count == 0 {
            return;
        }
        info!(
            lost_count = result.lost_count,
            "[数据丢失检测] 触发补偿拉取"
        );
        for message_id in &result.lost_message_ids {
            if let Some(c) = &self.cache {
                match c
                    .get(&format!("reliability:msg:content:{}", message_id))
                    .await
                {
                    Ok(Some(_)) => {}
                    Ok(None) => {
                        warn!(message_id, "[数据丢失检测] 丢失消息内容已过期");
                        continue;
                    }
                    Err(e) => {
                        error!(message_id, err = %e, "[数据丢失检测] 补偿拉取异常");
                        continue;
                    }
                }
            }
            self.reliability.retry_send(message_id).await;
        }
    }

    /// device_id 为空时按日期枚举所有设备（对应 Redis KEYS 的前缀扫描）。
    pub async fn get_device_report_stats(
        &self,
        device_id: &str,
        date: chrono::DateTime<chrono::Utc>,
    ) -> AppResult<HashMap<String, i64>> {
        let mut stats = HashMap::new();
        let Some(c) = &self.cache else {
            return Ok(stats);
        };
        let day = date.format("%Y-%m-%d").to_string();
        if !device_id.is_empty() {
            let n = c
                .get_int(&format!("{}{}:{}", DEVICE_COUNT_PREFIX, device_id, day))
                .await?
                .unwrap_or(0);
            stats.insert(device_id.to_string(), n);
            return Ok(stats);
        }
        let keys = c
            .scan_keys(&format!("{}*:{}", DEVICE_COUNT_PREFIX, day))
            .await?;
        for key in keys {
            let rest = key.strip_prefix(DEVICE_COUNT_PREFIX).unwrap_or(&key);
            if let Some(idx) = rest.rfind(':') {
                let dev = &rest[..idx];
                if let Ok(Some(n)) = c.get_int(&key).await {
                    stats.insert(dev.to_string(), n);
                }
            }
        }
        Ok(stats)
    }
}
