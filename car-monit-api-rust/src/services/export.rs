// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedExportService.java:93-330
// 职责: 8 亿级大表的异步导出（ES scroll → 分片 CSV）。
// 对应关系:
//   exportExecutor.submit(...)                 ↔ tokio::spawn
//   ConcurrentHashMap<String,ExportTaskStatus> ↔ Arc<RwLock<HashMap<..>>>
//   executeExportScroll                        ↔ execute_export_scroll
//   @PreDestroy destroy()                      ↔ ExportService::close
//
// DIFF: Java 的线程池会吞掉 Future 异常；Rust 的 tokio task panic 会终止该 task，
// 因此导出循环内部把错误写回任务状态，保证前端轮询能看到 FAILED。

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use tokio::sync::{RwLock, Semaphore};
use tracing::{error, info, warn};
use uuid::Uuid;

use crate::config::OptimizationConfig;
use crate::es::{build_fuzzy_query, EsClient};
use crate::services::query::{DataSource, QueryService};

pub const TASK_PENDING: &str = "PENDING";
pub const TASK_RUNNING: &str = "RUNNING";
pub const TASK_COMPLETED: &str = "COMPLETED";
pub const TASK_FAILED: &str = "FAILED";

#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ExportTaskStatus {
    pub task_id: String,
    pub status: String,
    pub total_exported: i64,
    pub file_part_count: usize,
    pub submit_time: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub finish_time: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_paths: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
}

#[derive(Clone)]
pub struct ExportService {
    pub es: Option<EsClient>,
    pub query: QueryService,
    pub cfg: OptimizationConfig,
    pub tasks: Arc<RwLock<HashMap<String, ExportTaskStatus>>>,
    sem: Arc<Semaphore>,
}

impl ExportService {
    pub fn new(es: Option<EsClient>, query: QueryService, cfg: OptimizationConfig) -> Self {
        Self {
            es,
            query,
            cfg,
            tasks: Arc::new(RwLock::new(HashMap::new())),
            sem: Arc::new(Semaphore::new(2)), // 对应 Java 固定 2 线程
        }
    }

    /// 对应 submitExportTask：立即返回 taskId，导出在后台执行。
    pub async fn submit_export_task(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: HashMap<String, String>,
    ) -> Result<String, String> {
        if start_time.is_empty() || end_time.is_empty() {
            return Err("导出必须指定 startTime 与 endTime".into());
        }
        if self.es.is_none() {
            return Err(
                "Elasticsearch 未启用，无法导出（GaussDB 降级路径不支持大批量导出）".into(),
            );
        }
        let task_id = Uuid::new_v4().to_string();
        let status = ExportTaskStatus {
            task_id: task_id.clone(),
            status: TASK_PENDING.into(),
            submit_time: now_ms(),
            ..Default::default()
        };
        self.tasks.write().await.insert(task_id.clone(), status);

        let tasks = self.tasks.clone();
        let sem = self.sem.clone();
        let this = self.clone();
        let ds_owned = ds;
        let start = start_time.to_string();
        let end = end_time.to_string();
        let task_for_job = task_id.clone();
        tokio::spawn(async move {
            let _permit = sem.acquire().await;
            let result = this
                .execute_export_scroll(&task_for_job, ds_owned, &start, &end, &fuzzy)
                .await;
            let mut map = tasks.write().await;
            if let Some(st) = map.get_mut(&task_for_job) {
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

    pub async fn clean_expired_tasks(&self, max_age: Duration) {
        let cutoff = now_ms() - max_age.as_millis() as i64;
        let mut map = self.tasks.write().await;
        map.retain(|_, st| {
            let finished = st.status == TASK_COMPLETED || st.status == TASK_FAILED;
            !(finished && st.finish_time.map(|t| t < cutoff).unwrap_or(false))
        });
    }

    pub async fn close(&self) {
        // tokio task 无法 join（未保存 JoinHandle）；这里等待信号量全部归还即可视为在途任务结束。
        let _ = self.sem.acquire_many(2).await;
    }

    async fn execute_export_scroll(
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
        info!(task_id, ds = ds.as_str(), "[导出任务] 开始执行");

        let meta = self.query.meta(ds);
        let filters = vec![serde_json::json!({
            "range": { meta.time_field: {
                "format": "yyyy-MM-dd HH:mm:ss", "gte": start_time, "lte": end_time
            }}
        })];
        let mut must = Vec::new();
        for (k, v) in fuzzy {
            if v.is_empty() {
                continue;
            }
            let Some(physical) = meta.logical_to_physical.get(k.as_str()) else {
                self.finish(
                    task_id,
                    TASK_FAILED,
                    &format!("不支持的模糊字段: {}", k),
                    0,
                    None,
                )
                .await;
                return Err(format!("不支持的模糊字段: {}", k));
            };
            must.push(build_fuzzy_query(physical, v));
        }

        let dir = self.task_dir(task_id)?;
        std::fs::create_dir_all(&dir).map_err(|e| format!("创建导出目录失败: {}", e))?;
        let keepalive = format!("{}m", self.cfg.export.scroll_keepalive_min);
        let body = serde_json::json!({
            "size": self.cfg.export.scroll_batch,
            "query": { "bool": { "filter": filters, "must": must } },
            "sort": [ { meta.time_field: { "order": "asc" } } ],
        });

        let (docs, mut scroll_id, mut done) = es
            .scroll_page(&meta.index, &body, &keepalive)
            .await
            .map_err(|e| format!("开始 scroll 失败: {}", e))?;

        let cols = entity_columns(ds);
        let mut total: i64 = 0;
        let mut files: Vec<String> = Vec::new();
        let mut part = 0usize;
        let mut writer: Option<(csv::Writer<std::fs::File>, String)> = None;
        let mut header = false;

        let write_rows = |docs: &[serde_json::Value],
                          writer: &mut Option<(csv::Writer<std::fs::File>, String)>,
                          header: &mut bool,
                          part: &mut usize,
                          total: &mut i64,
                          files: &mut Vec<String>|
         -> Result<(), String> {
            if docs.is_empty() {
                return Ok(());
            }
            if writer.is_none() {
                *part += 1;
                let name = dir.join(format!("{}_part{:04}.csv", ds.as_str(), part));
                let f = std::fs::File::create(&name).map_err(|e| e.to_string())?;
                files.push(name.display().to_string());
                *writer = Some((csv::Writer::from_writer(f), name.display().to_string()));
                *header = true;
            }
            let (w, _) = writer.as_mut().unwrap();
            if *header {
                w.write_record(cols).map_err(|e| e.to_string())?;
                *header = false;
            }
            for d in docs {
                let rec: Vec<String> = cols.iter().map(|c| stringify(d.get(*c))).collect();
                w.write_record(rec).map_err(|e| e.to_string())?;
            }
            *total += docs.len() as i64;
            if *total % self.cfg.export.file_batch < docs.len() as i64 {
                if let Some((mut w, _)) = writer.take() {
                    w.flush().map_err(|e| e.to_string())?;
                }
            }
            Ok(())
        };

        write_rows(
            &docs,
            &mut writer,
            &mut header,
            &mut part,
            &mut total,
            &mut files,
        )?;
        self.add_progress(task_id, docs.len() as i64, part).await;

        while !done {
            let (next, sid, finished) = es
                .scroll_next(&scroll_id, &keepalive)
                .await
                .map_err(|e| format!("scroll 拉取失败: {}", e))?;
            scroll_id = sid;
            done = finished;
            write_rows(
                &next,
                &mut writer,
                &mut header,
                &mut part,
                &mut total,
                &mut files,
            )?;
            self.add_progress(task_id, next.len() as i64, part).await;
        }
        if let Some((mut w, _)) = writer.take() {
            w.flush().map_err(|e| e.to_string())?;
        }
        let _ = es.clear_scroll(&scroll_id).await;
        info!(task_id, total, files = files.len(), "[导出任务] 完成");
        self.finish(task_id, TASK_COMPLETED, "", total, Some(files))
            .await;
        Ok(())
    }

    fn task_dir(&self, task_id: &str) -> Result<PathBuf, String> {
        let base = std::path::absolute(&self.cfg.export.dir)
            .map_err(|e| format!("导出根目录无效: {}", e))?;
        let dir = base.join(Path::new(task_id).file_name().unwrap_or_default());
        if !dir.starts_with(&base) {
            return Err(format!("非法的导出目录: {}", task_id));
        }
        Ok(dir)
    }

    async fn set_status(&self, task_id: &str, status: &str) {
        if let Some(st) = self.tasks.write().await.get_mut(task_id) {
            st.status = status.to_string();
        }
    }

    async fn add_progress(&self, task_id: &str, delta: i64, parts: usize) {
        if let Some(st) = self.tasks.write().await.get_mut(task_id) {
            st.total_exported += delta;
            st.file_part_count = parts;
        }
    }

    async fn finish(
        &self,
        task_id: &str,
        status: &str,
        err: &str,
        total: i64,
        files: Option<Vec<String>>,
    ) {
        if let Some(st) = self.tasks.write().await.get_mut(task_id) {
            st.status = status.to_string();
            st.finish_time = Some(now_ms());
            st.total_exported = total;
            if let Some(f) = files {
                st.file_part_count = f.len();
                st.file_paths = Some(f);
            }
            if !err.is_empty() {
                st.error_message = Some(err.to_string());
            }
        }
    }
}

/// 对应 UnifiedExportService 的静态 COLUMNS 表：保证 CSV 表头稳定。
pub fn entity_columns(ds: DataSource) -> &'static [&'static str] {
    match ds {
        DataSource::Snapshot => &[
            "bigId",
            "platenumber",
            "platecolor",
            "snapshottime",
            "receivedtime",
            "gantrycode",
            "gantryname",
            "roadname",
            "sectionname",
            "tollname",
            "orgname",
            "deviceid",
            "deviceip",
            "direction",
            "laneid",
            "cartype",
            "carcolor",
            "snappicturepath",
        ],
        DataSource::Fee => &[
            "bigId",
            "vehicleplate",
            "transtime",
            "inapplytime",
            "tollstationname",
            "gantryname",
            "sectionname",
            "orgname",
            "fee",
            "feetype",
            "vehicletype",
            "axlenum",
        ],
        DataSource::Trail => &[
            "trailuuid",
            "platekey",
            "entime",
            "extime",
            "startlon",
            "stratlat",
            "endlon",
            "endlat",
            "sectionname",
            "roadname",
            "trailpoints",
        ],
    }
}

pub fn stringify(v: Option<&serde_json::Value>) -> String {
    match v {
        None | Some(serde_json::Value::Null) => String::new(),
        Some(serde_json::Value::String(s)) => s.clone(),
        Some(serde_json::Value::Number(n)) => n.to_string(),
        Some(serde_json::Value::Bool(b)) => b.to_string(),
        Some(other) => other.to_string(),
    }
}

pub fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

pub fn task_not_found() -> serde_json::Value {
    serde_json::json!({ "code": 404, "message": "task not found" })
}

pub fn log_export_error(task_id: &str, err: &str) {
    error!(task_id, err, "[导出任务] 失败");
    warn!(task_id, "导出任务已标记为 FAILED");
}
