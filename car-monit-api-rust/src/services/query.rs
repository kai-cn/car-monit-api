// 来源: pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedQueryService.java
// 职责: 三张 8 亿级大表的统一查询路由：ES 优先 / GaussDB 降级。
// 对应关系:
//   query(ds,start,end,fuzzy,pageNum,pageSize) ↔ QueryService::query
//   shouldRouteToES                          ↔ should_route_to_es
//   queryFromES / queryFromDB                ↔ query_from_es / query_from_db
//   buildFieldTranslation                    ↔ Meta.logical_to_physical
//
// DIFF: Java 用 MyBatis-Plus 的 QueryWrapper 直接拼列名，存在注入面；Rust 只接受
// 白名单里的逻辑字段（与 Go 版一致），未知字段返回 400。

use std::collections::HashMap;
use std::time::Instant;

use serde_json::{json, Value};
use tracing::{error, info, warn};

use crate::config::{ElasticsearchConfig, OptimizationConfig};
use crate::db::Db;
use crate::error::{AppError, AppResult};
use crate::es::{build_fuzzy_query, extract_hits, EsClient};
use crate::models::{OdsLwzxsfsjFeeRecords01, OdsRtSzdnSnapshotFlowAddcode, ZdataTrailFitting};
use crate::utils;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataSource {
    Snapshot,
    Fee,
    Trail,
}

impl DataSource {
    pub fn as_str(&self) -> &'static str {
        match self {
            DataSource::Snapshot => "snapshot",
            DataSource::Fee => "fee",
            DataSource::Trail => "trail",
        }
    }

    /// Java 的 enum.name()（全大写），large 接口回显它。
    pub fn enum_name(&self) -> &'static str {
        match self {
            DataSource::Snapshot => "SNAPSHOT",
            DataSource::Fee => "FEE",
            DataSource::Trail => "TRAIL",
        }
    }
}

/// 对应 UnifiedQueryController.parseDataSource：非法值报 400。
pub fn parse_data_source(s: &str) -> AppResult<DataSource> {
    match s.trim().to_lowercase().as_str() {
        "snapshot" => Ok(DataSource::Snapshot),
        "fee" => Ok(DataSource::Fee),
        "trail" => Ok(DataSource::Trail),
        other => Err(AppError::bad_request(format!(
            "未知数据源: {}, 合法取值: snapshot / fee / trail",
            other
        ))),
    }
}

/// 对应 LargeScaleQueryController.resolveDs：非法值静默降级为 snapshot。
pub fn parse_type_lenient(t: &str) -> AppResult<DataSource> {
    // PARITY: Java 的 resolve(type)/resolveDs(type) 对未知取值不报错，一律落到 SNAPSHOT 分支
    // （switch default），所以 stats/export/sync 接口传 type=bogus 时仍按门架快照查询执行。
    match t.trim().to_lowercase().as_str() {
        "fee" => Ok(DataSource::Fee),
        "trail" => Ok(DataSource::Trail),
        _ => Ok(DataSource::Snapshot),
    }
}

#[derive(Debug, Clone)]
pub struct Meta {
    pub index: String,
    pub time_field: &'static str,
    pub table: &'static str,
    pub logical_to_physical: HashMap<&'static str, &'static str>,
}

#[derive(Clone)]
pub struct QueryService {
    es: Option<EsClient>,
    db: Db,
    cfg: OptimizationConfig,
    es_cfg: ElasticsearchConfig,
}

impl QueryService {
    pub fn new(
        es: Option<EsClient>,
        db: Db,
        cfg: OptimizationConfig,
        es_cfg: ElasticsearchConfig,
    ) -> Self {
        Self {
            es,
            db,
            cfg,
            es_cfg,
        }
    }

    pub fn meta(&self, ds: DataSource) -> Meta {
        match ds {
            DataSource::Snapshot => Meta {
                index: self.es_cfg.index.snapshot.clone(),
                time_field: "snapshottime",
                table: "jl_data01.ods_rt_szdn_snapshot_flow_addcode",
                logical_to_physical: HashMap::from([
                    ("platenumber", "platenumber"),
                    ("orgname", "orgname"),
                    ("sectionname", "sectionname"),
                    ("roadname", "roadname"),
                    ("gantryname", "gantryname"),
                    ("tollname", "tollname"),
                ]),
            },
            DataSource::Fee => Meta {
                index: self.es_cfg.index.fee.clone(),
                time_field: "transtime",
                // PARITY: Java 实体 @TableName("ods_lwzxsfsj_fee_records_01") 未带 schema，
                // MyBatis-Plus 生成的是非限定表名，降级查询能否成功取决于 search_path。
                table: "ods_lwzxsfsj_fee_records_01",
                logical_to_physical: HashMap::from([
                    ("platenumber", "vehicleplate"),
                    ("orgname", "orgname"),
                    ("sectionname", "sectionname"),
                    ("roadname", "roadname"),
                    ("gantryname", "gantryname"),
                    ("tollname", "tollname"),
                ]),
            },
            DataSource::Trail => Meta {
                index: self.es_cfg.index.trail.clone(),
                time_field: "extime",
                // PARITY: 同 Fee，Java @TableName("zdata_trail_fitting") 不带 schema。
                table: "zdata_trail_fitting",
                logical_to_physical: HashMap::from([
                    ("platenumber", "envehicleid"),
                    ("orgname", "orgname"),
                    ("sectionname", "sectionname"),
                    ("roadname", "roadname"),
                    ("gantryname", "gantryname"),
                    ("tollname", "tollname"),
                ]),
            },
        }
    }

    /// 查询入口：ES 失败自动降级到 GaussDB。
    pub async fn query(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        page_num: i64,
        page_size: i64,
    ) -> AppResult<Vec<Value>> {
        let use_es = self.should_route_to_es(start_time, end_time, fuzzy, ds);
        let started = Instant::now();
        match self
            .query_route(ds, start_time, end_time, fuzzy, page_num, page_size, use_es)
            .await
        {
            Ok(rows) => {
                info!(
                    ds = ds.as_str(),
                    use_es,
                    cost_ms = started.elapsed().as_millis() as u64,
                    "统一查询完成"
                );
                Ok(rows)
            }
            Err(e) => {
                error!(ds = ds.as_str(), use_es, err = %e, "统一查询失败");
                // PARITY: Java UnifiedQueryService.query 捕获所有异常后返回空列表，
                // 降级查询也失败时同样回空（控制器始终 200 + code=200）。
                if use_es {
                    warn!(ds = ds.as_str(), "ES 查询失败，降级到 GaussDB");
                    match self
                        .query_from_db(ds, start_time, end_time, fuzzy, page_num, page_size)
                        .await
                    {
                        Ok(rows) => Ok(rows),
                        Err(ex) => {
                            error!(ds = ds.as_str(), err = %ex, "降级 GaussDB 也失败");
                            Ok(Vec::new())
                        }
                    }
                } else {
                    Ok(Vec::new())
                }
            }
        }
    }

    // 参数与 Java queryRoute(...) 对应；拆结构体会让调用链难以与 Java 对照。
    #[allow(clippy::too_many_arguments)]
    async fn query_route(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        page_num: i64,
        page_size: i64,
        use_es: bool,
    ) -> AppResult<Vec<Value>> {
        if use_es {
            self.query_from_es(ds, start_time, end_time, fuzzy, page_num, page_size)
                .await
        } else {
            self.query_from_db(ds, start_time, end_time, fuzzy, page_num, page_size)
                .await
        }
    }

    /// 对应 shouldRouteToES：有模糊条件 / 超 N 天 / fee&trail 一律走 ES。
    pub fn should_route_to_es(
        &self,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        ds: DataSource,
    ) -> bool {
        if fuzzy.values().any(|v| !v.trim().is_empty()) {
            return true;
        }
        let (Ok(st), Ok(et)) = (utils::parse_time(start_time), utils::parse_time(end_time)) else {
            return true; // 时间格式异常：保守走 ES（与 Java 注释一致）
        };
        if (et - st).num_days() > self.cfg.query.es_force_days {
            return true;
        }
        matches!(ds, DataSource::Fee | DataSource::Trail)
    }

    /// 对应 queryFromES：range + 白名单模糊条件 + 浅分页。
    pub async fn query_from_es(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        page_num: i64,
        page_size: i64,
    ) -> AppResult<Vec<Value>> {
        let Some(es) = &self.es else {
            return Err(AppError::internal("Elasticsearch 未启用"));
        };
        let meta = self.meta(ds);
        let filters = vec![json!({
            "range": { meta.time_field: {
                "format": "yyyy-MM-dd HH:mm:ss", "gte": start_time, "lte": end_time
            }}
        })];
        let mut must = Vec::new();
        for (k, v) in fuzzy {
            if v.trim().is_empty() {
                continue;
            }
            let Some(physical) = meta.logical_to_physical.get(k.as_str()) else {
                return Err(AppError::bad_request(format!(
                    "不支持的模糊查询字段: {}",
                    k
                )));
            };
            must.push(build_fuzzy_query(physical, v));
        }
        // 饱和乘法：pageNum 已在上层钳到 MAX_PAGE_NUM，但这里仍防御直接调用方传入 i64 极值。
        let from = page_num.saturating_sub(1).saturating_mul(page_size).max(0);
        let size = page_size.min(self.cfg.query.max_window);
        if from.saturating_add(size) > self.cfg.query.max_window {
            return Err(AppError::bad_request(format!(
                "浅分页超过 max_result_window={}，请使用 export 接口或 search_after",
                self.cfg.query.max_window
            )));
        }
        let body = json!({
            "from": from,
            "size": size,
            "query": { "bool": { "filter": filters, "must": must } },
            "sort": [ { meta.time_field: { "order": "desc" } } ],
            "timeout": format!("{}ms", self.cfg.query.timeout_ms),
            "track_total_hits": true,
        });
        let resp = es.search(&meta.index, &body).await?;
        Ok(self.convert_docs(ds, extract_hits(&resp).0))
    }

    /// 对应 queryFromDB：GaussDB 降级路径，LIMIT 1000 + 内存分页。
    /// 用 sqlx 直接解码成实体（与 Mapper 的 resultMap 等价），保证列类型/时区处理
    /// 与 `/base/.../list` 完全一致。
    async fn fetch_entities<T>(&self, sql: &str, args: &[String]) -> AppResult<Vec<T>>
    where
        T: for<'r> sqlx::FromRow<'r, sqlx::postgres::PgRow> + Send + Unpin,
    {
        let mut q = sqlx::query_as::<_, T>(sql);
        for a in args {
            q = q.bind(a);
        }
        Ok(q.fetch_all(&self.db.pool).await?)
    }

    /// 对应 Java `queryFromMysql`：用 Mapper 直接取**实体**（`selectList(QueryWrapper)`），
    /// 再把实体序列化输出。
    ///
    /// PARITY: 之前这里是 `SELECT *` + `row_to_json` + `from_value`，`row_to_json` 对
    /// `timestamp without time zone` 走 `DateTime<Utc>` 会解码失败并静默变成 null，
    /// 导致 `/api/v1/large|unified` 的降级结果里 snapshottime/receivedtime/loadtime 全为 null，
    /// 而 Java 返回实体（走 sqlx 的 JIsoDateTime/Day 解码 + 与 Jackson 一致的格式化）。
    /// 改为直接 `query_as::<_, 实体>` 后，编码与 `/base/.../list` 完全一致。
    pub async fn query_from_db(
        &self,
        ds: DataSource,
        start_time: &str,
        end_time: &str,
        fuzzy: &HashMap<String, String>,
        page_num: i64,
        page_size: i64,
    ) -> AppResult<Vec<Value>> {
        let meta = self.meta(ds);
        let mut where_clauses: Vec<String> = Vec::new();
        let mut args: Vec<String> = Vec::new();

        // Java 用 java.sql.Timestamp.valueOf(...)，无法解析时抛异常 -> query() 捕获 -> 空列表。
        let mut push_time = |col: &str, op: &str, v: &str| -> AppResult<bool> {
            if v.trim().is_empty() {
                return Ok(true);
            }
            match utils::parse_time(v) {
                Ok(t) => {
                    args.push(utils::format_datetime(&t));
                    where_clauses.push(format!(
                        "{} {} to_timestamp(${}, 'yyyy-mm-dd HH24:MI:SS')",
                        col,
                        op,
                        args.len()
                    ));
                    Ok(true)
                }
                Err(_) => Ok(false),
            }
        };
        if !push_time(meta.time_field, ">=", start_time)? {
            return Ok(Vec::new());
        }
        if !push_time(meta.time_field, "<=", end_time)? {
            return Ok(Vec::new());
        }

        for (k, v) in fuzzy {
            if v.trim().is_empty() {
                continue;
            }
            // PARITY: Java 用 translation.getOrDefault(key, key)，未知字段直接当物理列名拼进 SQL
            // （可注入）。Rust 只允许白名单内的逻辑字段，未知字段直接拒绝，绝不进入 SQL 文本。
            let Some(physical) = meta.logical_to_physical.get(k.as_str()).copied() else {
                return Err(AppError::bad_request(format!(
                    "不支持的模糊查询字段: {}",
                    k
                )));
            };
            args.push(format!("%{}%", v));
            // PARITY: Java QueryWrapper.like -> 大小写敏感的 LIKE。
            where_clauses.push(format!("{} LIKE ${}", physical, args.len()));
        }

        let mut sql = format!("SELECT * FROM {}", meta.table);
        if !where_clauses.is_empty() {
            sql.push_str(" WHERE ");
            sql.push_str(&where_clauses.join(" AND "));
        }
        sql.push_str(" LIMIT 1000");

        let rows_value: Value = match ds {
            DataSource::Snapshot => serde_json::to_value(
                self.fetch_entities::<OdsRtSzdnSnapshotFlowAddcode>(&sql, &args)
                    .await?,
            )?,
            DataSource::Fee => serde_json::to_value(
                self.fetch_entities::<OdsLwzxsfsjFeeRecords01>(&sql, &args)
                    .await?,
            )?,
            DataSource::Trail => serde_json::to_value(
                self.fetch_entities::<ZdataTrailFitting>(&sql, &args)
                    .await?,
            )?,
        };
        let docs: Vec<Value> = rows_value.as_array().cloned().unwrap_or_default();
        Ok(page_in_memory(docs, page_num, page_size))
    }

    pub fn convert_docs(&self, ds: DataSource, docs: Vec<Value>) -> Vec<Value> {
        docs.into_iter()
            .map(|doc| {
                let normalized = normalize_doc_keys(doc);
                let typed = match ds {
                    DataSource::Snapshot => {
                        serde_json::from_value::<OdsRtSzdnSnapshotFlowAddcode>(normalized.clone())
                            .ok()
                            .and_then(|e| serde_json::to_value(e).ok())
                    }
                    DataSource::Fee => {
                        serde_json::from_value::<OdsLwzxsfsjFeeRecords01>(normalized.clone())
                            .ok()
                            .and_then(|e| serde_json::to_value(e).ok())
                    }
                    DataSource::Trail => {
                        serde_json::from_value::<ZdataTrailFitting>(normalized.clone())
                            .ok()
                            .and_then(|e| serde_json::to_value(e).ok())
                    }
                };
                typed.unwrap_or(normalized)
            })
            .collect()
    }

    pub fn es(&self) -> Option<&EsClient> {
        self.es.as_ref()
    }

    pub fn db(&self) -> &Db {
        &self.db
    }

    pub fn cfg(&self) -> &OptimizationConfig {
        &self.cfg
    }
}

/// ES 文档键名 snake_case → camelCase（FastJSON 的 smart match 等价物）。
fn normalize_doc_keys(doc: Value) -> Value {
    match doc {
        Value::Object(map) => {
            let mut out = serde_json::Map::new();
            for (k, v) in map {
                let key = if k.contains('_') {
                    let mut parts = k.split('_');
                    let first = parts.next().unwrap_or("");
                    let mut s = String::from(first);
                    for p in parts {
                        let mut chars = p.chars();
                        if let Some(c) = chars.next() {
                            s.push(c.to_ascii_uppercase());
                            s.push_str(chars.as_str());
                        }
                    }
                    s
                } else {
                    k
                };
                out.insert(key, v);
            }
            Value::Object(out)
        }
        other => other,
    }
}

pub fn page_in_memory<T: Clone>(rows: Vec<T>, page_num: i64, page_size: i64) -> Vec<T> {
    // 饱和运算：极值 pageNum 不得 panic（debug）或因回绕退化成第 1 页（release）。
    let from = page_num
        .saturating_sub(1)
        .saturating_mul(page_size)
        .max(0) as usize;
    if from >= rows.len() {
        return vec![];
    }
    let to = rows
        .len()
        .min(from.saturating_add(page_size.max(1) as usize));
    rows[from..to].to_vec()
}

#[cfg(test)]
mod paging_tests {
    use super::page_in_memory;

    #[test]
    fn huge_page_num_returns_empty_without_overflow() {
        let rows = vec![1, 2, 3];
        assert!(page_in_memory(rows, i64::MAX, 20).is_empty());
    }

    #[test]
    fn first_page_still_works() {
        let rows = vec![1, 2, 3, 4, 5];
        assert_eq!(page_in_memory(rows.clone(), 1, 2), vec![1, 2]);
        assert_eq!(page_in_memory(rows.clone(), 2, 2), vec![3, 4]);
        assert_eq!(page_in_memory(rows, 3, 2), vec![5]);
    }
}
