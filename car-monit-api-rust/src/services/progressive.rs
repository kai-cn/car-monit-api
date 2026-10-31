// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/ProgressiveQueryArchitectureService.java:49-478
// 职责: 按数据量级别（千万/亿/十亿）自动切换三阶段查询策略。
// 对应关系:
//   enum DataScaleLevel                ↔ DataScaleLevel
//   @Value("${optimization.scale-level}") ↔ cfg.scale_level
//   @Autowired(required=false) ES     ↔ Option<EsClient>
//   QueryRequest / QueryResult        ↔ QueryRequest / QueryResult
//
// DIFF: Java 用 switch(enum) 分派到 3 个 private 方法；Rust 保持同样结构。

use std::time::Duration;

use serde::{Deserialize, Serialize};
use tracing::info;

use crate::cache::Cache;
use crate::config::OptimizationConfig;
use crate::error::AppResult;
use crate::es::EsClient;
use crate::models::*;
use crate::repo::*;
use crate::utils;

const TABLE_COUNT_CACHE_PREFIX: &str = "table:count:";
const TABLE_COUNT_TTL_SECS: u64 = 3600;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataScaleLevel {
    Level10M,
    Level100M,
    Level1B,
}

impl DataScaleLevel {
    pub fn name(&self) -> &'static str {
        match self {
            DataScaleLevel::Level100M => "LEVEL_100M",
            DataScaleLevel::Level1B => "LEVEL_1B",
            DataScaleLevel::Level10M => "LEVEL_10M",
        }
    }

    fn parse(s: &str) -> Self {
        match s {
            "LEVEL_100M" => DataScaleLevel::Level100M,
            "LEVEL_1B" => DataScaleLevel::Level1B,
            _ => DataScaleLevel::Level10M,
        }
    }

    fn judge(count: i64) -> Self {
        if count < 50_000_000 {
            DataScaleLevel::Level10M
        } else if count < 500_000_000 {
            DataScaleLevel::Level100M
        } else {
            DataScaleLevel::Level1B
        }
    }
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(default, rename_all = "camelCase")]
pub struct QueryRequest {
    pub start_time: String,
    pub end_time: String,
    pub platenumber: String,
    pub orgname: String,
    pub sectionname: String,
    pub roadname: String,
    pub gantryname: String,
    pub tollname: String,
    pub cursor: String,
    pub page_size: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QueryResult {
    pub data: serde_json::Value,
    pub total: i64,
    pub strategy: String,
}

#[derive(Clone)]
pub struct ProgressiveService {
    configured: DataScaleLevel,
    snapshot: SnapshotFlowRepo,
    fee: FeeRecordsRepo,
    trail: TrailFittingRepo,
    cache: Option<Cache>,
    es: Option<EsClient>,
}

impl ProgressiveService {
    pub fn new(
        cfg: &OptimizationConfig,
        snapshot: SnapshotFlowRepo,
        fee: FeeRecordsRepo,
        trail: TrailFittingRepo,
        cache: Option<Cache>,
        es: Option<EsClient>,
    ) -> Self {
        Self {
            configured: DataScaleLevel::parse(&cfg.scale_level),
            snapshot,
            fee,
            trail,
            cache,
            es,
        }
    }

    pub async fn detect_scale_level(&self, table: &str) -> DataScaleLevel {
        if let Some(c) = &self.cache {
            if let Ok(Some(v)) = c
                .get(&format!("{}{}", TABLE_COUNT_CACHE_PREFIX, table))
                .await
            {
                if let Ok(n) = v.parse::<i64>() {
                    return DataScaleLevel::judge(n);
                }
            }
        }
        self.configured
    }

    pub async fn cache_table_count(&self, table: &str, count: i64) -> AppResult<()> {
        if let Some(c) = &self.cache {
            c.set_ttl(
                &format!("{}{}", TABLE_COUNT_CACHE_PREFIX, table),
                count.to_string(),
                Duration::from_secs(TABLE_COUNT_TTL_SECS),
            )
            .await?;
        }
        Ok(())
    }

    pub async fn query_snapshot_flow(&self, mut req: QueryRequest) -> AppResult<QueryResult> {
        req.page_size = if req.page_size <= 0 {
            20
        } else {
            req.page_size
        };
        let level = self
            .detect_scale_level("ods_rt_szdn_snapshot_flow_addcode")
            .await;
        info!(level = level.name(), "[渐进式查询] 门架抓拍流水");
        match level {
            DataScaleLevel::Level100M => self.snapshot_phase2(&req).await,
            DataScaleLevel::Level1B => self.snapshot_phase3(&req).await,
            DataScaleLevel::Level10M => self.snapshot_phase1(&req).await,
        }
    }

    async fn snapshot_phase1(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        let q = OdsRtSzdnSnapshotFlowAddcode {
            apply_time1: req.start_time.clone().into(),
            apply_time2: req.end_time.clone().into(),
            platenumber: req.platenumber.clone().into(),
            gantryname: req.gantryname.clone().into(),
            roadname: req.roadname.clone().into(),
            sectionname: req.sectionname.clone().into(),
            orgname: req.orgname.clone().into(),
            tollname: req.tollname.clone().into(),
            ..Default::default()
        };
        let list = self
            .snapshot
            .repo
            .list_unbounded(crate::repo::snapshot_filters(&q))
            .await?;
        Ok(result(list, "phase1-gaussdb-gin"))
    }

    async fn snapshot_phase2(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        if !req.cursor.is_empty() {
            let list = self
                .snapshot
                .list_by_cursor_shard(
                    &req.start_time,
                    &req.end_time,
                    &req.cursor,
                    "",
                    req.page_size,
                )
                .await?;
            return Ok(result(list, "phase2-partition-cursor"));
        }
        let q = OdsRtSzdnSnapshotFlowAddcode {
            apply_time1: req.start_time.clone().into(),
            apply_time2: req.end_time.clone().into(),
            platenumber: req.platenumber.clone().into(),
            gantryname: req.gantryname.clone().into(),
            roadname: req.roadname.clone().into(),
            sectionname: req.sectionname.clone().into(),
            orgname: req.orgname.clone().into(),
            tollname: req.tollname.clone().into(),
            ..Default::default()
        };
        let list = self
            .snapshot
            .repo
            .list_unbounded(crate::repo::snapshot_filters(&q))
            .await?;
        Ok(result(list, "phase2-partition-prune"))
    }

    async fn snapshot_phase3(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        if self.es.is_some() {
            let has_fuzzy = !req.platenumber.is_empty()
                || !req.gantryname.is_empty()
                || !req.roadname.is_empty()
                || !req.sectionname.is_empty()
                || !req.orgname.is_empty()
                || !req.tollname.is_empty();
            if has_fuzzy || req.page_size > 100 {
                return Ok(QueryResult {
                    data: serde_json::json!([]),
                    total: 0,
                    strategy: "phase3-elasticsearch".into(),
                });
            }
        }
        self.snapshot_phase2(req).await
    }

    pub async fn query_fee_records(&self, mut req: QueryRequest) -> AppResult<QueryResult> {
        req.page_size = if req.page_size <= 0 {
            20
        } else {
            req.page_size
        };
        let level = self.detect_scale_level("ods_lwzxsfsj_fee_records_01").await;
        info!(level = level.name(), "[渐进式查询] 收费流水");
        match level {
            DataScaleLevel::Level1B => self.fee_phase3(&req).await,
            _ => self.fee_phase1(&req).await,
        }
    }

    async fn fee_phase1(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        let q = OdsLwzxsfsjFeeRecords01 {
            in_apply_time1: req.start_time.clone().into(),
            in_apply_time2: req.end_time.clone().into(),
            vehicleplate: req.platenumber.clone().into(),
            ..Default::default()
        };
        let list = self
            .fee
            .repo
            .list_unbounded(crate::repo::fee_records_filters(&q))
            .await?;
        Ok(result(list, "phase1-gaussdb-gin"))
    }

    async fn fee_phase3(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        if self.es.is_some() && (!req.platenumber.is_empty() || req.page_size > 100) {
            return Ok(QueryResult {
                data: serde_json::json!([]),
                total: 0,
                strategy: "phase3-elasticsearch".into(),
            });
        }
        self.fee_phase1(req).await
    }

    pub async fn query_trail_fitting(&self, mut req: QueryRequest) -> AppResult<QueryResult> {
        req.page_size = if req.page_size <= 0 {
            20
        } else {
            req.page_size
        };
        let level = self.detect_scale_level("zdata_trail_fitting").await;
        info!(level = level.name(), "[渐进式查询] 轨迹拟合");
        match level {
            DataScaleLevel::Level1B => {
                if self.es.is_some() {
                    Ok(QueryResult {
                        data: serde_json::json!([]),
                        total: 0,
                        strategy: "phase3-elasticsearch".into(),
                    })
                } else {
                    self.trail_phase1(&req).await
                }
            }
            _ => self.trail_phase1(&req).await,
        }
    }

    async fn trail_phase1(&self, req: &QueryRequest) -> AppResult<QueryResult> {
        // PARITY: Java 用 Timestamp.valueOf(start) 塞 entime、end 塞 extime（字段名与语义相反），保持原样。
        let mut q = ZdataTrailFitting::default();
        if !req.start_time.is_empty() {
            q.entime = utils::parse_time(&req.start_time)
                .ok()
                .map(Day::new)
                .unwrap_or_default();
        }
        if !req.end_time.is_empty() {
            q.extime = utils::parse_time(&req.end_time)
                .ok()
                .map(JIsoDateTime::from)
                .unwrap_or_default();
        }
        let list = self
            .trail
            .repo
            .list_unbounded(crate::repo::trail_fitting_filters(&q))
            .await?;
        Ok(result(list, "phase1-gaussdb-gin"))
    }
}

fn result<T: Serialize>(rows: Vec<T>, strategy: &str) -> QueryResult {
    let total = rows.len() as i64;
    QueryResult {
        data: serde_json::to_value(rows).unwrap_or(serde_json::json!([])),
        total,
        strategy: strategy.into(),
    }
}
