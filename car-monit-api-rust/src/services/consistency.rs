// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/GaussEsConsistencyService.java
// 职责: 四层一致性保障的最后一层：GaussDB ↔ ES 定时对账 + 自动修复。
// 对应关系:
//   countInGaussDb / countInEs   ↔ Repo::count_between / EsClient::count
//   driftRatio 告警              ↔ ReconcileConfig.drift_ratio
//   @Scheduled(cron=...)         ↔ scheduler 注册（受 consistency.reconcile.enabled 控制）
//   repair                       ↔ SyncService::repair_sync

use std::sync::Arc;

use serde::Serialize;
use serde_json::json;
use tracing::{error, info, warn};

use crate::config::ReconcileConfig;
use crate::error::AppResult;
use crate::es::EsClient;
use crate::repo::{FeeRecordsRepo, SnapshotFlowRepo, TrailFittingRepo};
use crate::services::query::DataSource;
use crate::services::sync::SyncService;
use crate::utils;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReconcileReport {
    pub ds: String,
    pub start_time: String,
    pub end_time: String,
    pub gauss_count: i64,
    pub es_count: i64,
    pub drift_ratio: f64,
    pub repaired: bool,
}

#[derive(Clone)]
pub struct ConsistencyService {
    pub es: Option<EsClient>,
    pub snapshot: SnapshotFlowRepo,
    pub fee: FeeRecordsRepo,
    pub trail: TrailFittingRepo,
    pub sync: Arc<SyncService>,
    pub cfg: ReconcileConfig,
}

impl ConsistencyService {
    pub fn new(
        es: Option<EsClient>,
        snapshot: SnapshotFlowRepo,
        fee: FeeRecordsRepo,
        trail: TrailFittingRepo,
        sync: Arc<SyncService>,
        cfg: ReconcileConfig,
    ) -> Self {
        Self {
            es,
            snapshot,
            fee,
            trail,
            sync,
            cfg,
        }
    }

    /// 对应 @Scheduled(cron="${consistency.reconcile.cron}")。
    pub async fn scheduled_reconcile(&self) {
        if !self.cfg.enabled {
            info!("[一致性对账] 配置未启用，跳过");
            return;
        }
        let end = chrono::Utc::now();
        let start = end - chrono::Duration::days(30 * self.cfg.lookback_months.max(1) as i64);
        for (ds, index) in [
            (DataSource::Snapshot, self.sync_index(DataSource::Snapshot)),
            (DataSource::Fee, self.sync_index(DataSource::Fee)),
            (DataSource::Trail, self.sync_index(DataSource::Trail)),
        ] {
            if let Err(e) = self.reconcile_one(ds, &index, start, end).await {
                error!(ds = ds.as_str(), err = %e, "[一致性对账] 异常");
            }
        }
    }

    fn sync_index(&self, ds: DataSource) -> String {
        match ds {
            DataSource::Snapshot => "snapshot_flow",
            DataSource::Fee => "fee_records",
            DataSource::Trail => "trail_fitting",
        }
        .to_string()
    }

    pub async fn reconcile_one(
        &self,
        ds: DataSource,
        index: &str,
        start: chrono::DateTime<chrono::Utc>,
        end: chrono::DateTime<chrono::Utc>,
    ) -> AppResult<ReconcileReport> {
        let start_s = utils::format_datetime(&start);
        let end_s = utils::format_datetime(&end);
        let gauss = match ds {
            DataSource::Snapshot => self.snapshot.count_between(&start_s, &end_s).await?,
            DataSource::Fee => self.fee.count_between(&start_s, &end_s).await?,
            DataSource::Trail => self.trail.count_between(&start_s, &end_s).await?,
        };
        let es_count = match &self.es {
            Some(es) => {
                let time_field = match ds {
                    DataSource::Snapshot => "snapshottime",
                    DataSource::Fee => "transtime",
                    DataSource::Trail => "extime",
                };
                let body = json!({
                    "query": { "range": { time_field: {
                        "format": "yyyy-MM-dd HH:mm:ss", "gte": start_s, "lte": end_s
                    }}}
                });
                es.count(index, &body).await.unwrap_or(0)
            }
            None => 0,
        };
        let drift = if gauss == 0 {
            0.0
        } else {
            (gauss - es_count).abs() as f64 / gauss as f64
        };
        let mut repaired = false;
        if drift > self.cfg.drift_ratio {
            warn!(
                ds = ds.as_str(),
                gauss,
                es = es_count,
                drift,
                "[一致性对账] 发现漂移，触发修复"
            );
            if let Err(e) = self.sync.repair_sync(ds, &start_s, &end_s).await {
                error!(ds = ds.as_str(), err = %e, "[一致性对账] 修复失败");
            } else {
                repaired = true;
            }
        }
        info!(
            ds = ds.as_str(),
            gauss,
            es = es_count,
            drift,
            repaired,
            "[一致性对账] 完成"
        );
        Ok(ReconcileReport {
            ds: ds.as_str().into(),
            start_time: start_s,
            end_time: end_s,
            gauss_count: gauss,
            es_count,
            drift_ratio: drift,
            repaired,
        })
    }

    /// 对账窗口：最近 N 个月。
    pub fn window(&self) -> (chrono::DateTime<chrono::Utc>, chrono::DateTime<chrono::Utc>) {
        let end = chrono::Utc::now();
        let start = end - chrono::Duration::days(30 * self.cfg.lookback_months.max(1) as i64);
        (start, end)
    }
}
