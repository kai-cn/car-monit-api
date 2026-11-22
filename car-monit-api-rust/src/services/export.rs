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

use serde::{Deserialize, Serialize};
use tokio::sync::{Mutex, RwLock, Semaphore};
use tracing::{error, info, warn};
use uuid::Uuid;

use crate::cache::Cache;
use crate::config::OptimizationConfig;
use crate::es::{build_fuzzy_query, EsClient};
use crate::services::query::{DataSource, QueryService};

pub const TASK_PENDING: &str = "PENDING";
pub const TASK_RUNNING: &str = "RUNNING";
pub const TASK_COMPLETED: &str = "COMPLETED";
pub const TASK_FAILED: &str = "FAILED";

/// 任务状态在 Redis 中的前缀与保留期（多副本共享轮询结果）。
const TASK_KEY_PREFIX: &str = "car_monit:export:task:";
const TASK_REDIS_TTL_SECS: u64 = 86_400;

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ExportTaskStatus {
    pub task_id: String,
    pub status: String,
    pub total_exported: i64,
    pub file_part_count: usize,
    pub submit_time: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub finish_time: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub file_paths: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
}

#[derive(Clone)]
pub struct ExportService {
    pub es: Option<EsClient>,
    pub query: QueryService,
    pub cfg: OptimizationConfig,
    pub tasks: Arc<RwLock<HashMap<String, ExportTaskStatus>>>,
    /// 多副本：任务状态镜像到 Redis，任一副本轮询都能命中。
    store: Option<Cache>,
    sem: Arc<Semaphore>,
    /// 在途导出的 JoinHandle：关闭时在宽限期内 join，超时则告警放弃。
    handles: Arc<Mutex<Vec<tokio::task::JoinHandle<()>>>>,
}

impl ExportService {
    pub fn new(
        es: Option<EsClient>,
        query: QueryService,
        cfg: OptimizationConfig,
        store: Option<Cache>,
    ) -> Self {
        Self {
            es,
            query,
            cfg,
            tasks: Arc::new(RwLock::new(HashMap::new())),
            store,
            sem: Arc::new(Semaphore::new(2)), // 对应 Java 固定 2 线程
            handles: Arc::new(Mutex::new(Vec::new())),
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
        self.tasks.write().await.insert(task_id.clone(), status.clone());
        persist_task(&self.store, &status).await;

        let tasks = self.tasks.clone();
        let sem = self.sem.clone();
        let this = self.clone();
        let ds_owned = ds;
        let start = start_time.to_string();
        let end = end_time.to_string();
        let task_for_job = task_id.clone();
        let handle = tokio::spawn(async move {
            let _permit = sem.acquire().await;
            let result = this
                .execute_export_scroll(&task_for_job, ds_owned, &start, &end, &fuzzy)
                .await;
            let failed = {
                let mut map = tasks.write().await;
                match (map.get_mut(&task_for_job), result) {
                    (Some(st), Err(e)) => {
                        st.status = TASK_FAILED.into();
                        st.finish_time = Some(now_ms());
                        st.error_message = Some(e);
                        Some(st.clone())
                    }
                    _ => None,
                }
            };
            // 多副本：失败状态必须同步到 Redis，否则其它副本永远看到 RUNNING。
            if let Some(st) = failed {
                persist_task(&this.store, &st).await;
            }
        });
        let mut hs = self.handles.lock().await;
        hs.retain(|h| !h.is_finished());
        hs.push(handle);
        Ok(task_id)
    }

    pub async fn get_export_status(&self, task_id: &str) -> Option<ExportTaskStatus> {
        if let Some(st) = self.tasks.read().await.get(task_id) {
            return Some(st.clone());
        }
        // 多副本：本副本没有该任务时回落到 Redis 快照。
        load_task(&self.store, task_id).await
    }

    pub async fn clean_expired_tasks(&self, max_age: Duration) {
        let cutoff = now_ms() - max_age.as_millis() as i64;
        let mut map = self.tasks.write().await;
        map.retain(|_, st| {
            let finished = st.status == TASK_COMPLETED || st.status == TASK_FAILED;
            !(finished && st.finish_time.map(|t| t < cutoff).unwrap_or(false))
        });
    }

    /// S4：清理超过保留期的导出目录。运行中的任务会持续写文件，目录 mtime 会被刷新，
    /// 因此按 mtime 判断不会误删在途任务；清理失败只返回错误由调用方告警。
    pub fn clean_expired_files(&self, max_age: Duration) -> std::io::Result<usize> {
        let base = std::path::absolute(&self.cfg.export.dir)?;
        let entries = match std::fs::read_dir(&base) {
            Ok(e) => e,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(0),
            Err(e) => return Err(e),
        };
        let mut removed = 0usize;
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            let Ok(meta) = entry.metadata() else { continue };
            let Ok(modified) = meta.modified() else {
                continue;
            };
            let Ok(age) = SystemTime::now().duration_since(modified) else {
                continue;
            };
            if age < max_age {
                continue;
            }
            if std::fs::remove_dir_all(&path).is_ok() {
                removed += 1;
            }
        }
        Ok(removed)
    }

    /// 关闭：在宽限期内 join 所有在途导出任务；超时则**显式 abort** 剩余任务。
    /// 只丢弃 join_all future 会让任务 detach，随后 db.close() 会与仍在写库的任务并发。
    pub async fn close(&self, grace: Duration) -> bool {
        let mut handles: Vec<tokio::task::JoinHandle<()>> = {
            let mut hs = self.handles.lock().await;
            std::mem::take(&mut *hs)
        };
        if handles.is_empty() {
            return true;
        }
        info!(
            tasks = handles.len(),
            grace_seconds = grace.as_secs(),
            "[导出任务] 等待后台任务结束"
        );
        let aborts: Vec<tokio::task::AbortHandle> =
            handles.iter().map(|h| h.abort_handle()).collect();
        // 顺序 await 与 join_all 等价（任务本身已并发运行），且超时后 JoinHandle 仍归本函数所有，
        // 可以 abort 后再 join，避免 close 返回时任务仍停在同步 CSV/文件 I/O。
        let wait_all = async {
            for h in handles.iter_mut() {
                let _ = h.await;
            }
        };
        match tokio::time::timeout(grace, wait_all).await {
            Ok(_) => {
                info!("[导出任务] 后台任务已全部结束");
                true
            }
            Err(_) => {
                for a in &aborts {
                    a.abort();
                }
                let drain = async {
                    for h in handles.iter_mut() {
                        let _ = h.await;
                    }
                };
                // 500ms 是"放弃等待"上限，不是"确保停止"：CSV 使用同步 std::fs::File，
                // 取消只能在下一次 await 点生效，同步 I/O 段落最长会再延后一次写盘。
                if tokio::time::timeout(Duration::from_millis(500), drain)
                    .await
                    .is_err()
                {
                    warn!(
                        tasks = aborts.len(),
                        "[导出任务] abort 已发出，但 500ms 内任务仍停在同步 I/O；最长再延后一次写盘"
                    );
                }
                warn!(
                    tasks = aborts.len(),
                    grace_seconds = grace.as_secs(),
                    "[导出任务] 宽限期内仍有任务未结束，已中止剩余任务"
                );
                false
            }
        }
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
        let snapshot = {
            let mut map = self.tasks.write().await;
            map.get_mut(task_id).map(|st| {
                st.status = status.to_string();
                st.clone()
            })
        };
        if let Some(st) = snapshot {
            persist_task(&self.store, &st).await;
        }
    }

    async fn add_progress(&self, task_id: &str, delta: i64, parts: usize) {
        let snapshot = {
            let mut map = self.tasks.write().await;
            map.get_mut(task_id).map(|st| {
                st.total_exported += delta;
                st.file_part_count = parts;
                st.clone()
            })
        };
        if let Some(st) = snapshot {
            persist_task(&self.store, &st).await;
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
        let snapshot = {
            let mut map = self.tasks.write().await;
            map.get_mut(task_id).map(|st| {
                st.status = status.to_string();
                st.finish_time = Some(now_ms());
                st.total_exported = total;
                if let Some(ref f) = files {
                    st.file_part_count = f.len();
                    st.file_paths = Some(f.clone());
                }
                if !err.is_empty() {
                    st.error_message = Some(err.to_string());
                }
                st.clone()
            })
        };
        if let Some(st) = snapshot {
            persist_task(&self.store, &st).await;
        }
    }
}

/// 把任务快照写入 Redis（失败只告警，不影响本副本内存状态）。
/// 供 UnifiedExportService / LargeScaleQueryService 共用。
pub async fn persist_task(store: &Option<Cache>, st: &ExportTaskStatus) {
    let Some(store) = store else { return };
    let Ok(json) = serde_json::to_string(st) else {
        return;
    };
    if let Err(e) = store
        .set_ttl(
            &format!("{}{}", TASK_KEY_PREFIX, st.task_id),
            json,
            Duration::from_secs(TASK_REDIS_TTL_SECS),
        )
        .await
    {
        warn!(task_id = %st.task_id, err = %e, "[导出任务] 写入 Redis 任务状态失败");
    }
}

/// 从 Redis 读取其它副本写入的任务快照。
pub async fn load_task(store: &Option<Cache>, task_id: &str) -> Option<ExportTaskStatus> {
    let store = store.as_ref()?;
    match store
        .get_json::<ExportTaskStatus>(&format!("{}{}", TASK_KEY_PREFIX, task_id))
        .await
    {
        Ok(v) => v,
        Err(e) => {
            warn!(task_id, err = %e, "[导出任务] 读取 Redis 任务状态失败");
            None
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
