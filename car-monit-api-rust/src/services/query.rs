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
use crate::db::{row_to_json, Db};
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
    match t.trim().to_lowercase().as_str() {
        "" | "snapshot" => Ok(DataSource::Snapshot),
        "fee" => Ok(DataSource::Fee),
        "trail" => Ok(DataSource::Trail),
        other => Err(AppError::bad_request(format!(
            "type 只能是 snapshot / fee / trail，当前为 {}",
            other
        ))),
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
        let from = ((page_num - 1) * page_size).max(0);
        let size = page_size.min(self.cfg.query.max_window);
        if from + size > self.cfg.query.max_window {
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
        if !start_time.trim().is_empty() {
            args.push(start_time.into());
            where_clauses.push(format!("{} >= ${}", meta.time_field, args.len()));
        }
        if !end_time.trim().is_empty() {
            args.push(end_time.into());
            where_clauses.push(format!("{} <= ${}", meta.time_field, args.len()));
        }
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
            args.push(format!("%{}%", v));
            // PARITY: Java QueryWrapper.like → 大小写敏感的 LIKE。
            where_clauses.push(format!("{} LIKE ${}", physical, args.len()));
        }
        let mut sql = format!("SELECT * FROM {}", meta.table);
        if !where_clauses.is_empty() {
            sql.push_str(" WHERE ");
            sql.push_str(&where_clauses.join(" AND "));
        }
        sql.push_str(" LIMIT 1000");

        let mut q = sqlx::query(&sql);
        for a in &args {
            q = q.bind(a);
        }
        let rows = q.fetch_all(&self.db.pool).await?;
        let docs: Vec<Value> = rows.iter().map(row_to_json).collect();
        // 对应 Java queryFromMysql：返回实体对象（camelCase + 瞬态字段），而不是原始列 Map。
        let docs = self.convert_docs(ds, docs);
        Ok(page_in_memory(docs, page_num, page_size))
    }

    /// 对应 Java `JSON.parseObject(hit.getSourceAsString(), targetClass)`：
    /// ES 文档（可能是 snake_case）反序列化为实体，再按 Java 字段名/默认值输出。
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
    let from = ((page_num - 1) * page_size).max(0) as usize;
    if from >= rows.len() {
        return vec![];
    }
    let to = rows.len().min(from + page_size.max(1) as usize);
    rows[from..to].to_vec()
}
