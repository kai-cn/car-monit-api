// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleQueryService.java:55-458
// 职责: 大表模糊查询 / 分组统计 / 明细导出（三表统一）。
// 对应关系:
//   resolve(type)             ↔ resolve
//   fuzzyQuery                ↔ fuzzy_query
//   aggregationStats          ↔ aggregation_stats
//   submitExportTask          ↔ submit_export
//   ThreadPoolExecutor(4..8)  ↔ tokio::spawn + Semaphore(4)

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use serde_json::{json, Value};
use tokio::sync::{RwLock, Semaphore};
use tracing::info;
use uuid::Uuid;

use crate::config::OptimizationConfig;
use crate::error::{AppError, AppResult};
use crate::es::{build_fuzzy_query, extract_hits, total_hits, EsClient};
use crate::services::export::{
    now_ms, stringify, ExportTaskStatus, TASK_COMPLETED, TASK_FAILED, TASK_PENDING, TASK_RUNNING,
};
use crate::services::query::{DataSource, QueryService};

const QUERY_TIMEOUT_SECONDS: u64 = 30;
const SCROLL_BATCH_SIZE: i64 = 2000;
const EXPORT_BATCH_SIZE: i64 = 100_000;

#[derive(Debug, Clone)]
pub struct Target {
    pub ds: DataSource,
    pub index_name: String,
    pub time_field: &'static str,
    pub id_field: &'static str,
    pub plate_field: &'static str,
}

#[derive(Clone)]
pub struct LargeScaleQueryService {
    es: Option<EsClient>,
    query: QueryService,
    cfg: OptimizationConfig,
    tasks: Arc<RwLock<HashMap<String, ExportTaskStatus>>>,
    sem: Arc<Semaphore>,
}

impl LargeScaleQueryService {
    pub fn new(es: Option<EsClient>, query: QueryService, cfg: OptimizationConfig) -> Self {
        Self {
            es,
            query,
            cfg,
            tasks: Arc::new(RwLock::new(HashMap::new())),
            sem: Arc::new(Semaphore::new(4)),
        }
    }

    pub fn resolve(&self, ds: DataSource) -> Target {
        let meta = self.query.meta(ds);
        let (id_field, plate_field) = match ds {
            DataSource::Fee => ("big_id", "vehicleplate"),
            DataSource::Trail => ("cid", "envehicleid"),
            DataSource::Snapshot => ("datauuid", "platenumber"),
        };
        Target {
            ds,
            index_name: meta.index,
            time_field: meta.time_field,
            id_field,
            plate_field,
        }
    }

    pub async fn fuzzy_query(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        page_num: i64,
        page_size: i64,
    ) -> AppResult<Vec<Value>> {
        let es = self
            .es
            .as_ref()
            .ok_or_else(|| AppError::internal("Elasticsearch 未启用"))?;
        let page_num = page_num.max(1);
        let page_size = if page_size <= 0 { 20 } else { page_size };
        let target = self.resolve(ds);
        let started = Instant::now();
        let filters = vec![json!({
            "range": { target.time_field: {
                "format": "yyyy-MM-dd HH:mm:ss", "gte": start_time, "lte": end_time
            }}
        })];
        let must: Vec<Value> = fuzzy
            .iter()
            .filter(|(_, v)| !v.trim().is_empty())
            .map(|(k, v)| build_fuzzy_query(k, v))
            .collect();
        let body = json!({
            "from": (page_num - 1) * page_size,
            "size": page_size,
            "query": { "bool": { "filter": filters, "must": must } },
            "sort": [ { target.time_field: { "order": "desc" } } ],
            "terminate_after": 1_000_000,
            "timeout": format!("{}s", QUERY_TIMEOUT_SECONDS),
            "track_total_hits": true,
        });
        let resp = es
            .search(&target.index_name, &body)
            .await
            .map_err(|e| AppError::biz(format!("大规模数据查询服务异常：{}", e)))?;
        let rows = self.query.convert_docs(ds, extract_hits(&resp).0);
        info!(
            ds = ds.as_str(),
            total = total_hits(&resp),
            returned = rows.len(),
            cost_ms = started.elapsed().as_millis() as u64,
            "[全字段模糊查询]"
        );
        Ok(rows)
    }

    pub async fn aggregation_stats(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        group_by: &str,
        _count_field: &str,
        fuzzy: &HashMap<String, String>,
        top_n: i64,
    ) -> AppResult<serde_json::Map<String, Value>> {
        let es = self
            .es
            .as_ref()
            .ok_or_else(|| AppError::internal("Elasticsearch 未启用"))?;
        if group_by.is_empty() {
            return Err(AppError::bad_request("groupBy 不能为空"));
        }
        let top_n = if top_n <= 0 { 100 } else { top_n };
        let target = self.resolve(ds);
        let filters = vec![json!({
            "range": { target.time_field: {
                "format": "yyyy-MM-dd HH:mm:ss", "gte": start_time, "lte": end_time
            }}
        })];
        let must: Vec<Value> = fuzzy
            .iter()
            .filter(|(_, v)| !v.trim().is_empty())
            .map(|(k, v)| build_fuzzy_query(k, v))
            .collect();
        let body = json!({
            "size": 0,
            "timeout": "60s",
            "query": { "bool": { "filter": filters, "must": must } },
            "aggs": { format!("group_by_{}", group_by): {
                "terms": { "field": format!("{}.keyword", group_by), "size": top_n }
            }}
        });
        let resp = es
            .search(&target.index_name, &body)
            .await
            .map_err(|e| AppError::biz(format!("统计查询异常：{}", e)))?;
        let mut out = serde_json::Map::new();
        if let Some(buckets) = resp
            .get("aggregations")
            .and_then(|a| a.get(format!("group_by_{}", group_by)))
            .and_then(|g| g.get("buckets"))
            .and_then(|b| b.as_array())
        {
            for b in buckets {
                let key = b.get("key").map(|k| match k {
                    Value::String(s) => s.clone(),
                    other => other.to_string(),
                });
                let count = b.get("doc_count").and_then(|c| c.as_i64()).unwrap_or(0);
                if let Some(k) = key {
                    out.insert(k, Value::Number(count.into()));
                }
            }
        }
        Ok(out)
    }

    pub async fn submit_export(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: HashMap<String, String>,
    ) -> AppResult<String> {
        if self.es.is_none() {
            return Err(AppError::internal("Elasticsearch 未启用，无法导出"));
        }
        let task_id = Uuid::new_v4().to_string();
        let st = ExportTaskStatus {
            task_id: task_id.clone(),
            status: TASK_PENDING.into(),
            submit_time: now_ms(),
            ..Default::default()
        };
        self.tasks.write().await.insert(task_id.clone(), st);
        let this = self.clone();
        let id = task_id.clone();
        let start = start_time.to_string();
        let end = end_time.to_string();
        tokio::spawn(async move {
            let _permit = this.sem.acquire().await;
            let result = this.detail_export(&id, ds, &start, &end, &fuzzy).await;
            let mut map = this.tasks.write().await;
            if let Some(st) = map.get_mut(&id) {
                if let Err(e) = result {
                    st.status = TASK_FAILED.into();
                    st.finish_time = Some(now_ms());
                    st.error_message = Some(e);
                }
            }
        });
        Ok(task_id)
    }

    pub async fn get_export_status(&self, task_id: &str) -> Option<ExportTaskStatus> {
        self.tasks.read().await.get(task_id).cloned()
    }

    async fn detail_export(
        &self,
        task_id: &str,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
    ) -> Result<(), String> {
        let es = self
            .es
            .as_ref()
            .ok_or_else(|| "Elasticsearch 未启用".to_string())?;
        self.set_status(task_id, TASK_RUNNING).await;
        let target = self.resolve(ds);
        let filters = vec![json!({
            "range": { target.time_field: {
                "format": "yyyy-MM-dd HH:mm:ss", "gte": start_time, "lte": end_time
            }}
        })];
        let must: Vec<Value> = fuzzy
            .iter()
            .filter(|(_, v)| !v.trim().is_empty())
            .map(|(k, v)| build_fuzzy_query(k, v))
            .collect();
        let dir = self.export_dir(task_id)?;
        std::fs::create_dir_all(&dir).map_err(|e| format!("创建导出目录失败: {}", e))?;
        let keepalive = format!("{}m", self.cfg.export.scroll_keepalive_min);
        let body = json!({
            "size": SCROLL_BATCH_SIZE,
            "query": { "bool": { "filter": filters, "must": must } },
            "sort": [ { target.time_field: { "order": "desc" } } ],
            "timeout": "120s",
        });
        let (docs, mut scroll_id, mut done) = es
            .scroll_page(&target.index_name, &body, &keepalive)
            .await
            .map_err(|e| format!("开始 scroll 失败: {}", e))?;

        let mut total = 0i64;
        let mut part = 0usize;
        let mut writer: Option<csv::Writer<std::fs::File>> = None;
        let mut header = false;
        let write_batch = |batch: &[Value],
                           writer: &mut Option<csv::Writer<std::fs::File>>,
                           header: &mut bool,
                           part: &mut usize,
                           total: &mut i64|
         -> Result<(), String> {
            if batch.is_empty() {
                return Ok(());
            }
            if writer.is_none() {
                *part += 1;
                let name = dir.join(format!("export_{}_{}_p{}.csv", ds.as_str(), task_id, part));
                let f = std::fs::File::create(name).map_err(|e| e.to_string())?;
                *writer = Some(csv::Writer::from_writer(f));
                *header = true;
            }
            let w = writer.as_mut().unwrap();
            if *header {
                w.write_record([
                    target.id_field,
                    target.plate_field,
                    target.time_field,
                    "detail",
                ])
                .map_err(|e| e.to_string())?;
                *header = false;
            }
            for d in batch {
                let raw = serde_json::to_string(d)
                    .unwrap_or_default()
                    .replace('\n', " ")
                    .replace('\r', "");
                let rec = [
                    pick_field(d, &[target.id_field, "bigId", "datauuid", "cid"]),
                    pick_field(
                        d,
                        &[
                            target.plate_field,
                            "platenumber",
                            "vehicleplate",
                            "envehicleid",
                        ],
                    ),
                    pick_field(
                        d,
                        &[target.time_field, "snapshottime", "transtime", "extime"],
                    ),
                    raw,
                ];
                w.write_record(rec).map_err(|e| e.to_string())?;
                *total += 1;
            }
            if *total % EXPORT_BATCH_SIZE < batch.len() as i64 {
                if let Some(mut w) = writer.take() {
                    w.flush().map_err(|e| e.to_string())?;
                }
            }
            Ok(())
        };

        write_batch(&docs, &mut writer, &mut header, &mut part, &mut total)?;
        self.add_progress(task_id, docs.len() as i64, part).await;
        while !done {
            let (next, sid, finished) = es
                .scroll_next(&scroll_id, &keepalive)
                .await
                .map_err(|e| format!("scroll 拉取失败: {}", e))?;
            scroll_id = sid;
            done = finished;
            write_batch(&next, &mut writer, &mut header, &mut part, &mut total)?;
            self.add_progress(task_id, next.len() as i64, part).await;
        }
        if let Some(mut w) = writer.take() {
            w.flush().map_err(|e| e.to_string())?;
        }
        let _ = es.clear_scroll(&scroll_id).await;
        let mut map = self.tasks.write().await;
        if let Some(st) = map.get_mut(task_id) {
            st.status = TASK_COMPLETED.into();
            st.finish_time = Some(now_ms());
            st.total_exported = total;
            st.file_part_count = part;
        }
        Ok(())
    }

    fn export_dir(&self, task_id: &str) -> Result<std::path::PathBuf, String> {
        let base = std::path::absolute(&self.cfg.export.dir)
            .map_err(|e| format!("导出根目录无效: {}", e))?;
        let dir = base.join(
            std::path::Path::new(task_id)
                .file_name()
                .unwrap_or_default(),
        );
        if !dir.starts_with(&base) {
            return Err(format!("非法的导出目录: {}", task_id));
        }
        Ok(dir)
    }

    async fn set_status(&self, task_id: &str, status: &str) {
        if let Some(st) = self.tasks.write().await.get_mut(task_id) {
            st.status = status.into();
        }
    }

    async fn add_progress(&self, task_id: &str, delta: i64, parts: usize) {
        if let Some(st) = self.tasks.write().await.get_mut(task_id) {
            st.total_exported += delta;
            st.file_part_count = parts;
        }
    }

    pub async fn close(&self) {
        let _ = self.sem.acquire_many(4).await;
    }
}

/// 供 handler 输出的稳定排序（Java 用 LinkedHashMap；JSON Map 无序）。
pub fn sorted_keys(m: &serde_json::Map<String, Value>) -> Vec<String> {
    let mut keys: Vec<String> = m.keys().cloned().collect();
    keys.sort();
    keys
}

/// 从 ES 文档里按候选列名取第一个非空值（兼容 Debezium 的 snake_case 与实体 JSON 的 camelCase）。
fn pick_field(doc: &Value, names: &[&str]) -> String {
    for n in names {
        if let Some(v) = doc.get(*n) {
            if !v.is_null() {
                let s = stringify(Some(v));
                if !s.is_empty() {
                    return s;
                }
            }
        }
    }
    String::new()
}
