// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleDataSyncService.java:59-540
// 职责: GaussDB → Elasticsearch 的全量 / 增量 / 补同步（三表统一）。
// 对应关系:
//   SyncTask（表描述符）              ↔ SyncKind + read_batch
//   CursorReader                     ↔ 各 Repo::list_by_cursor_shard
//   BulkProcessor(1000/5s)           ↔ bulk 攒批（1000 条 flush）
//   AtomicLong 计数器                 ↔ AtomicI64 ×3
//   watermark（Redis）                ↔ cache.get/set("es:sync:watermark:*")

use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde_json::Value;
use tracing::{error, info};

use crate::cache::Cache;
use crate::config::{ElasticsearchConfig, SyncConfig};
use crate::error::{AppError, AppResult};
use crate::es::EsClient;
use crate::repo::*;
use crate::services::query::DataSource;
use crate::utils;

const WATERMARK_PREFIX: &str = "es:sync:watermark:";
const WATERMARK_BACKOFF_SECS: i64 = 10;
const PAGE_SIZE: i64 = 2000;
const BULK_BATCH_SIZE: usize = 1000;

#[derive(Debug, Clone, Copy)]
pub enum SyncKind {
    Snapshot,
    Fee,
    Trail,
}

impl SyncKind {
    fn watermark_key(&self) -> String {
        let suffix = match self {
            SyncKind::Snapshot => "snapshot",
            SyncKind::Fee => "fee",
            SyncKind::Trail => "trail",
        };
        format!("{}{}", WATERMARK_PREFIX, suffix)
    }

    fn ds_str(&self) -> &'static str {
        match self {
            SyncKind::Snapshot => "snapshot",
            SyncKind::Fee => "fee",
            SyncKind::Trail => "trail",
        }
    }
}

struct SyncRecord {
    id: String,
    time: String,
    doc: Value,
}

#[derive(Clone)]
pub struct SyncService {
    pub es: Option<EsClient>,
    pub cache: Option<Cache>,
    pub es_cfg: ElasticsearchConfig,
    pub cfg: SyncConfig,
    pub snapshot: SnapshotFlowRepo,
    pub fee: FeeRecordsRepo,
    pub trail: TrailFittingRepo,
    pub total_read: Arc<AtomicI64>,
    pub total_ok: Arc<AtomicI64>,
    pub total_err: Arc<AtomicI64>,
}

impl SyncService {
    pub fn new(
        es: Option<EsClient>,
        cache: Option<Cache>,
        es_cfg: ElasticsearchConfig,
        cfg: SyncConfig,
        snapshot: SnapshotFlowRepo,
        fee: FeeRecordsRepo,
        trail: TrailFittingRepo,
    ) -> Self {
        Self {
            es,
            cache,
            es_cfg,
            cfg,
            snapshot,
            fee,
            trail,
            total_read: Arc::new(AtomicI64::new(0)),
            total_ok: Arc::new(AtomicI64::new(0)),
            total_err: Arc::new(AtomicI64::new(0)),
        }
    }

    pub fn stats(&self) -> (i64, i64, i64) {
        (
            self.total_read.load(Ordering::SeqCst),
            self.total_ok.load(Ordering::SeqCst),
            self.total_err.load(Ordering::SeqCst),
        )
    }

    fn index_name(&self, kind: SyncKind) -> String {
        match kind {
            SyncKind::Snapshot => self.es_cfg.index.snapshot.clone(),
            SyncKind::Fee => self.es_cfg.index.fee.clone(),
            SyncKind::Trail => self.es_cfg.index.trail.clone(),
        }
    }

    async fn read_batch(
        &self,
        kind: SyncKind,
        start: &str,
        end: &str,
        cursor_time: &str,
        cursor_id: &str,
    ) -> AppResult<Vec<SyncRecord>> {
        match kind {
            SyncKind::Snapshot => {
                let rows = self
                    .snapshot
                    .list_by_cursor_shard(start, end, cursor_time, cursor_id, PAGE_SIZE)
                    .await?;
                Ok(rows
                    .into_iter()
                    .map(|r| SyncRecord {
                        id: r.datauuid.as_str().to_string(),
                        time: r
                            .snapshottime
                            .utc()
                            .map(|t| utils::format_datetime(&t))
                            .unwrap_or_default(),
                        doc: entity_doc(
                            &r,
                            &r.big_id,
                            &[
                                "id",
                                "snapshottimeStr",
                                "applyTime1",
                                "applyTime2",
                                "queryUuids",
                                "flag",
                                "sectionCodeStr",
                                "type",
                                "code",
                                "codeList",
                                "sectionList",
                                "startNum",
                                "endNum",
                            ],
                        ),
                    })
                    .collect())
            }
            SyncKind::Fee => {
                let rows = self
                    .fee
                    .list_by_cursor_shard(start, end, cursor_time, cursor_id, PAGE_SIZE)
                    .await?;
                Ok(rows
                    .into_iter()
                    .map(|r| SyncRecord {
                        id: r.big_id.as_str().to_string(),
                        time: r
                            .transtime
                            .utc()
                            .map(|d| utils::format_datetime(&d))
                            .unwrap_or_default(),
                        doc: entity_doc(
                            &r,
                            &r.big_id,
                            &[
                                "inApplyTime1",
                                "inApplyTime2",
                                "flag",
                                "code",
                                "codeList",
                                "sectionList",
                                "startNum",
                                "endNum",
                                "cidList",
                            ],
                        ),
                    })
                    .collect())
            }
            SyncKind::Trail => {
                let rows = self
                    .trail
                    .list_by_cursor_shard(start, end, cursor_time, cursor_id, PAGE_SIZE)
                    .await?;
                Ok(rows
                    .into_iter()
                    .map(|r| SyncRecord {
                        id: r.cid.as_str().to_string(),
                        time: r
                            .extime
                            .utc()
                            .map(|t| utils::format_datetime(&t))
                            .unwrap_or_default(),
                        doc: entity_doc(&r, &r.cid, &["entimeStr", "extimeStr"]),
                    })
                    .collect())
            }
        }
    }

    /// 对应 fullSyncOneYear：最近一年，三表串行。
    pub async fn full_sync_one_year(&self) -> AppResult<()> {
        let end = Utc::now();
        let start = end - chrono::Duration::days(365);
        info!(range = %format!("{} ~ {}", utils::format_datetime(&start), utils::format_datetime(&end)), "[全量同步] 开始");
        for kind in [SyncKind::Snapshot, SyncKind::Fee, SyncKind::Trail] {
            self.sync_range(kind, start, end).await?;
        }
        info!(
            read = self.total_read.load(Ordering::SeqCst),
            ok = self.total_ok.load(Ordering::SeqCst),
            failed = self.total_err.load(Ordering::SeqCst),
            "[全量同步] 完成"
        );
        Ok(())
    }

    /// 对应 incrementalSync：从 Redis 水位开始，回退 10 秒规避库侧写入延迟。
    pub async fn incremental_sync(&self) -> AppResult<()> {
        let end = Utc::now();
        let end_safe = end - chrono::Duration::seconds(WATERMARK_BACKOFF_SECS);
        for kind in [SyncKind::Snapshot, SyncKind::Fee, SyncKind::Trail] {
            let start = self
                .load_watermark(kind)
                .await
                .unwrap_or_else(|| end - chrono::Duration::days(1));
            self.sync_range(kind, start, end_safe).await?;
            self.save_watermark(kind, end_safe).await;
        }
        Ok(())
    }

    /// 对应 repairSync：重放指定数据源 + 时间窗。
    pub async fn repair_sync(&self, ds: DataSource, start: &str, end: &str) -> AppResult<()> {
        let kind = match ds {
            DataSource::Snapshot => SyncKind::Snapshot,
            DataSource::Fee => SyncKind::Fee,
            DataSource::Trail => SyncKind::Trail,
        };
        let start = utils::parse_time(start).map_err(AppError::biz)?;
        let end = utils::parse_time(end).map_err(AppError::biz)?;
        self.sync_range(kind, start, end).await
    }

    async fn sync_range(
        &self,
        kind: SyncKind,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> AppResult<()> {
        let Some(es) = &self.es else {
            return Err(AppError::internal("Elasticsearch 未启用"));
        };
        let index = self.index_name(kind);
        if index.is_empty() {
            return Ok(());
        }
        info!(
            ds = kind.ds_str(),
            index = %index,
            range = %format!("{} ~ {}", utils::format_datetime(&start), utils::format_datetime(&end)),
            "[同步] 开始"
        );

        // 按 1 小时分片（对应 Java 的 shardReaderPool）
        let mut shard_start = start;
        let mut buffer: Vec<Value> = Vec::with_capacity(BULK_BATCH_SIZE);
        let mut shard_read = 0i64;
        let mut shard_ok = 0i64;
        let mut shard_err = 0i64;

        while shard_start < end {
            let shard_end = (shard_start + chrono::Duration::hours(1)).min(end);
            let start_s = utils::format_datetime(&shard_start);
            let end_s = utils::format_datetime(&shard_end);
            let mut cursor_time = String::new();
            let mut cursor_id = String::new();
            loop {
                let batch = self
                    .read_batch(kind, &start_s, &end_s, &cursor_time, &cursor_id)
                    .await?;
                if batch.is_empty() {
                    break;
                }
                shard_read += batch.len() as i64;
                let last = batch.last().unwrap();
                cursor_time = last.time.clone();
                cursor_id = last.id.clone();
                for rec in batch {
                    buffer.push(rec.doc);
                    if buffer.len() >= BULK_BATCH_SIZE {
                        info!(ds = kind.ds_str(), docs = buffer.len(), "[同步] 写入 ES");
                        match es.bulk_upsert(&index, "_id", &buffer).await {
                            Ok(n) => shard_ok += n,
                            Err(e) => {
                                shard_err += buffer.len() as i64;
                                error!(ds = kind.ds_str(), err = %e, "[同步] bulk 写入失败");
                            }
                        }
                        buffer.clear();
                    }
                }
                if cursor_time.is_empty() {
                    break;
                }
            }
            info!(ds = kind.ds_str(), shard = %start_s, "[同步] 分片完成");
            shard_start = shard_end;
        }
        if !buffer.is_empty() {
            match es.bulk_upsert(&index, "_id", &buffer).await {
                Ok(n) => shard_ok += n,
                Err(e) => {
                    shard_err += buffer.len() as i64;
                    error!(ds = kind.ds_str(), err = %e, "[同步] bulk 写入失败");
                }
            }
        }
        self.total_read.fetch_add(shard_read, Ordering::SeqCst);
        self.total_ok.fetch_add(shard_ok, Ordering::SeqCst);
        self.total_err.fetch_add(shard_err, Ordering::SeqCst);
        info!(
            ds = kind.ds_str(),
            read = shard_read,
            ok = shard_ok,
            failed = shard_err,
            "[同步] 完成"
        );
        Ok(())
    }

    async fn load_watermark(&self, kind: SyncKind) -> Option<DateTime<Utc>> {
        let c = self.cache.as_ref()?;
        let v = c.get(&kind.watermark_key()).await.ok().flatten()?;
        utils::parse_time(&v).ok()
    }

    async fn save_watermark(&self, kind: SyncKind, at: DateTime<Utc>) {
        if let Some(c) = &self.cache {
            let _ = c
                .set_ttl(
                    &kind.watermark_key(),
                    utils::format_datetime(&at),
                    Duration::from_secs(86_400 * 30),
                )
                .await;
        }
    }
}

fn entity_doc<T: serde::Serialize>(entity: &T, id_field: &str, transient: &[&str]) -> Value {
    let mut doc = serde_json::to_value(entity).unwrap_or(Value::Null);
    if let Some(obj) = doc.as_object_mut() {
        for k in transient {
            obj.remove(*k);
        }
        obj.insert("_id".into(), Value::String(id_field.into()));
    }
    doc
}
