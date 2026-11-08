// 来源: pro-business-api/src/main/java/com/ruoyi/mq/config/ElasticsearchConfig.java
//       pro-business-api/src/main/java/com/ruoyi/base/service/optimization/EsQueryService.java
//       pro-business-api/src/main/java/com/ruoyi/base/service/optimization/EsIndexManageService.java
// 职责: Elasticsearch REST 客户端（search / scroll / bulk / count / 索引管理）。
// 对应关系:
//   RestHighLevelClient.search          ↔ EsClient::search
//   SearchScrollRequest / Scroll        ↔ EsClient::scroll_page / scroll_next
//   ClearScrollRequest                  ↔ EsClient::clear_scroll
//   BulkRequest (upsert, _id = 主键)     ↔ EsClient::bulk_upsert
//
// DIFF: Java 强绑定 ES 客户端大版本；Rust 用 reqwest 直连 REST，只实现用到的 6 个动作，
// 升级 ES 集群不需要升级依赖，也不会出现 SDK 版本不匹配。

use std::time::Duration;

use reqwest::Client;
use serde_json::{json, Value};

use crate::config::ElasticsearchConfig;
use crate::error::{AppError, AppResult};

#[derive(Clone)]
pub struct EsClient {
    http: Client,
    base: String,
    auth: Option<(String, String)>,
}

impl EsClient {
    pub fn new(cfg: &ElasticsearchConfig) -> anyhow::Result<Self> {
        let http = Client::builder()
            .connect_timeout(Duration::from_millis(cfg.connection_timeout_ms))
            .timeout(Duration::from_millis(cfg.socket_timeout_ms))
            .build()?;
        let auth = if cfg.username.is_empty() {
            None
        } else {
            Some((cfg.username.clone(), cfg.password.clone()))
        };
        Ok(Self {
            http,
            base: cfg.base_url(),
            auth,
        })
    }

    fn request(&self, method: reqwest::Method, path: &str) -> reqwest::RequestBuilder {
        let mut rb = self.http.request(method, format!("{}{}", self.base, path));
        if let Some((u, p)) = &self.auth {
            rb = rb.basic_auth(u, Some(p));
        }
        rb
    }

    pub async fn health(&self) -> AppResult<()> {
        let resp = self
            .request(reqwest::Method::GET, "/_cluster/health")
            .send()
            .await?;
        if !resp.status().is_success() {
            return Err(AppError::biz(format!(
                "Elasticsearch 健康检查失败: HTTP {}",
                resp.status()
            )));
        }
        // PARITY: 只看 HTTP 200 会把 red 集群当成健康；red 表示主分片不可用，必须摘流。
        let v: Value = resp.json().await.unwrap_or(Value::Null);
        match v.get("status").and_then(|s| s.as_str()).unwrap_or("") {
            "red" => Err(AppError::biz("Elasticsearch 集群状态 red")),
            _ => Ok(()),
        }
    }

    /// 对应 SearchRequest：GET /{index}/_search。
    pub async fn search(&self, index: &str, body: &Value) -> AppResult<Value> {
        let resp = self
            .request(
                reqwest::Method::POST,
                &format!("/{}/_search", encode_index(index)),
            )
            .json(body)
            .send()
            .await?;
        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            return Err(es_exception(status, &text));
        }
        Ok(resp.json().await?)
    }

    pub async fn count(&self, index: &str, body: &Value) -> AppResult<i64> {
        let resp = self
            .request(
                reqwest::Method::POST,
                &format!("/{}/_count", encode_index(index)),
            )
            .json(body)
            .send()
            .await?;
        let v: Value = resp.json().await?;
        Ok(v.get("count").and_then(|x| x.as_i64()).unwrap_or(0))
    }

    /// 对应 SearchScrollRequest 首次调用：返回 (docs, scroll_id, done)。
    pub async fn scroll_page(
        &self,
        index: &str,
        body: &Value,
        keepalive: &str,
    ) -> AppResult<(Vec<Value>, String, bool)> {
        let resp = self
            .request(
                reqwest::Method::POST,
                &format!("/{}/_search?scroll={}", encode_index(index), keepalive),
            )
            .json(body)
            .send()
            .await?;
        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            return Err(AppError::biz(format!(
                "开始 scroll 失败 HTTP {}: {}",
                status, text
            )));
        }
        let v: Value = resp.json().await?;
        let scroll_id = v
            .get("_scroll_id")
            .and_then(|x| x.as_str())
            .ok_or_else(|| AppError::biz("ES 未返回 _scroll_id"))?
            .to_string();
        let (docs, done) = extract_hits(&v);
        Ok((docs, scroll_id, done))
    }

    /// 对应 SearchScrollRequest 后续调用。
    pub async fn scroll_next(
        &self,
        scroll_id: &str,
        keepalive: &str,
    ) -> AppResult<(Vec<Value>, String, bool)> {
        let body = json!({ "scroll": keepalive, "scroll_id": scroll_id });
        let resp = self
            .request(reqwest::Method::POST, "/_search/scroll")
            .json(&body)
            .send()
            .await?;
        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            return Err(AppError::biz(format!(
                "scroll 拉取失败 HTTP {}: {}",
                status, text
            )));
        }
        let v: Value = resp.json().await?;
        let next_id = v
            .get("_scroll_id")
            .and_then(|x| x.as_str())
            .unwrap_or(scroll_id)
            .to_string();
        let (docs, done) = extract_hits(&v);
        Ok((docs, next_id, done))
    }

    pub async fn clear_scroll(&self, scroll_id: &str) -> AppResult<()> {
        let resp = self
            .request(reqwest::Method::DELETE, "/_search/scroll")
            .json(&json!({ "scroll_id": [scroll_id] }))
            .send()
            .await?;
        if resp.status().is_success() {
            Ok(())
        } else {
            Err(AppError::biz(format!(
                "清理 scroll 失败 HTTP {}",
                resp.status()
            )))
        }
    }
}

/// Bulk 响应摘要：ok=成功条数，failed=失败条数，first_error=首条错误原文。
#[derive(Debug, Default, Clone)]
pub struct BulkOutcome {
    pub ok: i64,
    pub failed: i64,
    pub first_error: Option<String>,
}

impl BulkOutcome {
    pub fn is_all_ok(&self) -> bool {
        self.failed == 0
    }
}

/// 解析 bulk 响应并按文档数收敛计数（纯函数，便于单测）。
/// 规则：
/// - 每条带 error 计 failed，否则计 ok；
/// - items 少于请求数：缺失条目一律计 failed（无法确认成功）；
/// - items 多于请求数：clamp `ok`/`failed`，保证 `ok + failed <= docs_len`；
/// - `errors=true` 但无任何失败明细：整批按失败处理。
fn parse_bulk_response(v: &Value, docs_len: usize) -> BulkOutcome {
    let mut outcome = BulkOutcome::default();
    let items = v.get("items").and_then(|x| x.as_array());
    let item_count = items.map(|a| a.len()).unwrap_or(0);
    if let Some(items) = items {
        for item in items {
            // 每条形如 {"index": {"_id": "...", "status": 201, "error": {...}}}
            let result = item.as_object().and_then(|o| o.values().next());
            match result {
                Some(r) if r.get("error").is_some() => {
                    outcome.failed += 1;
                    if outcome.first_error.is_none() {
                        outcome.first_error = Some(
                            r.get("error")
                                .map(|e| e.to_string())
                                .unwrap_or_else(|| "unknown error".to_string()),
                        );
                    }
                }
                Some(_) => outcome.ok += 1,
                None => outcome.failed += 1,
            }
        }
    }
    if item_count < docs_len {
        let missing = (docs_len - item_count) as i64;
        outcome.failed += missing;
        if outcome.first_error.is_none() {
            outcome.first_error = Some(format!("bulk 响应缺少 {} 条 items", missing));
        }
    }
    if item_count > docs_len {
        let cap = docs_len as i64;
        let had_failure = outcome.failed > 0;
        outcome.ok = outcome.ok.min(cap);
        outcome.failed = outcome.failed.min(cap.saturating_sub(outcome.ok));
        // 只钳 ok 不够：当成功数先占满 cap 时，把 failed 钳成 0 会让"多出来的失败条目"
        // 被静默吞掉（调用方看到 is_all_ok=true）。只要原始 items 里出现过 error，
        // 失败计数就必须至少为 1，宁可多报失败也不能少报。
        if had_failure && outcome.failed == 0 {
            outcome.failed = 1;
        }
    }
    let errors_flag = v
        .get("errors")
        .and_then(|e| e.as_bool())
        .unwrap_or(false);
    if errors_flag && outcome.failed == 0 {
        outcome.failed = docs_len as i64;
        outcome.ok = 0;
        outcome.first_error = Some("bulk 响应 errors=true 但未提供失败明细".to_string());
    }
    outcome
}

impl EsClient {
    /// 对应 BulkRequest：_id 即主键，实现 upsert（index 动作覆盖同 _id 文档）。
    ///
    /// DIFF: `_id` 只属于 bulk 元数据，绝不能出现在 `_source` 里（ES 会以
    /// mapper_parsing_exception 拒绝整条文档）。这里发送前统一剥离，并解析
    /// items[].error 按条计数返回，避免 HTTP 200 + errors=true 被当成成功。
    pub async fn bulk_upsert(
        &self,
        index: &str,
        id_field: &str,
        docs: &[Value],
    ) -> AppResult<BulkOutcome> {
        if docs.is_empty() {
            return Ok(BulkOutcome::default());
        }
        let mut body = String::new();
        for doc in docs {
            // 主键缺失时不能回退随机 UUID：那样每次重跑都会写出新文档，破坏幂等。
            // 统一由调用方保证 _id 非空（同步链路已把空主键计 skipped）。
            let id = doc
                .get(id_field)
                .and_then(|v| v.as_str())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .ok_or_else(|| {
                    AppError::biz(format!(
                        "ES bulk 文档缺少非空主键字段 {}，拒绝写入（避免生成非幂等文档）",
                        id_field
                    ))
                })?;
            body.push_str(&serde_json::to_string(
                &json!({ "index": { "_index": index, "_id": id } }),
            )?);
            body.push('\n');
            let mut source = doc.clone();
            if let Some(obj) = source.as_object_mut() {
                obj.remove("_id");
            }
            body.push_str(&serde_json::to_string(&source)?);
            body.push('\n');
        }
        let resp = self
            .request(reqwest::Method::POST, "/_bulk")
            .header("Content-Type", "application/x-ndjson")
            .body(body)
            .send()
            .await?;
        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            return Err(AppError::biz(format!(
                "ES bulk 失败 HTTP {}: {}",
                status, text
            )));
        }
        let v: Value = resp.json().await?;
        let item_count = v
            .get("items")
            .and_then(|x| x.as_array())
            .map(|a| a.len())
            .unwrap_or(0);
        if item_count != docs.len() {
            tracing::warn!(
                index,
                docs = docs.len(),
                items = item_count,
                "[ES] bulk 响应 items 数与请求文档数不一致"
            );
        }
        Ok(parse_bulk_response(&v, docs.len()))
    }

    pub async fn delete_by_id(&self, index: &str, id: &str) -> AppResult<()> {
        let resp = self
            .request(
                reqwest::Method::DELETE,
                &format!("/{}/_doc/{}", encode_index(index), id),
            )
            .send()
            .await?;
        if resp.status().is_success() || resp.status() == reqwest::StatusCode::NOT_FOUND {
            Ok(())
        } else {
            Err(AppError::biz(format!("ES 删除失败 HTTP {}", resp.status())))
        }
    }

    pub async fn create_index_if_absent(&self, index: &str, body: &Value) -> AppResult<bool> {
        let exists = self
            .request(reqwest::Method::HEAD, &format!("/{}", encode_index(index)))
            .send()
            .await?
            .status()
            .is_success();
        if exists {
            return Ok(false);
        }
        let resp = self
            .request(reqwest::Method::PUT, &format!("/{}", encode_index(index)))
            .json(body)
            .send()
            .await?;
        if resp.status().is_success() {
            Ok(true)
        } else {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            // HEAD 与 PUT 之间存在竞态：并发实例可能已创建同名索引，视为“已存在”。
            if text.contains("resource_already_exists_exception") {
                Ok(false)
            } else {
                Err(AppError::biz(format!(
                    "创建索引 {} 失败 HTTP {}: {}",
                    index, status, text
                )))
            }
        }
    }

    /// 读取索引 mapping（供运维/启动自检确认 date/ngram 结构）。
    pub async fn get_mapping(&self, index: &str) -> AppResult<Value> {
        let resp = self
            .request(
                reqwest::Method::GET,
                &format!("/{}/_mapping", encode_index(index)),
            )
            .send()
            .await?;
        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            return Err(AppError::biz(format!(
                "读取索引 {} mapping 失败 HTTP {}: {}",
                index, status, text
            )));
        }
        Ok(resp.json().await?)
    }

    /// 幂等创建 ILM 策略（hot → warm → cold → delete），与 Java EsIndexManageService 一致。
    pub async fn ensure_ilm_policy(&self, policy: &str) -> AppResult<()> {
        let escaped = encode_index(policy);
        let exists = self
            .request(
                reqwest::Method::GET,
                &format!("/_ilm/policy/{}", escaped),
            )
            .send()
            .await?;
        if exists.status().is_success() {
            return Ok(());
        }
        if exists.status() != reqwest::StatusCode::NOT_FOUND {
            return Err(AppError::biz(format!(
                "查询 ILM 策略 {} 失败 HTTP {}",
                policy,
                exists.status()
            )));
        }
        let body = json!({
            "policy": {
                "phases": {
                    "hot": {
                        "min_age": "0ms",
                        "actions": {
                            "set_priority": { "priority": 100 },
                            "rollover": { "max_age": "30d", "max_primary_shard_size": "50gb" }
                        }
                    },
                    "warm": {
                        "min_age": "30d",
                        "actions": {
                            "set_priority": { "priority": 50 },
                            "forcemerge": { "max_num_segments": 1 },
                            "shrink": { "number_of_shards": 1 }
                        }
                    },
                    "cold": {
                        "min_age": "90d",
                        "actions": { "set_priority": { "priority": 0 }, "freeze": {} }
                    },
                    "delete": {
                        "min_age": "365d",
                        "actions": { "delete": {} }
                    }
                }
            }
        });
        let resp = self
            .request(
                reqwest::Method::PUT,
                &format!("/_ilm/policy/{}", escaped),
            )
            .json(&body)
            .send()
            .await?;
        if resp.status().is_success() {
            tracing::info!(policy, "[ES] ILM 策略已创建");
            Ok(())
        } else {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            Err(AppError::biz(format!(
                "创建 ILM 策略 {} 失败 HTTP {}: {}",
                policy, status, text
            )))
        }
    }

    /// 启动/运维自检：确保 ILM 存在；auto-create=true 时按内置 mapping 创建缺失索引。
    /// 返回问题列表（空表示全部就绪），不直接中断启动。
    pub async fn ensure_indices(&self, cfg: &ElasticsearchConfig) -> Vec<String> {
        let mut problems = Vec::new();
        if !cfg.index.ilm_policy.is_empty() {
            if let Err(e) = self.ensure_ilm_policy(&cfg.index.ilm_policy).await {
                problems.push(format!(
                    "ILM 策略 {} 初始化失败: {}",
                    cfg.index.ilm_policy,
                    e.message()
                ));
            }
        }
        if !cfg.index.auto_create {
            return problems;
        }
        let specs: [(&str, &str, &str, &str); 3] = [
            (
                cfg.index.snapshot.as_str(),
                include_str!("../resources/es/index/snapshot_flow.json"),
                "snapshottime",
                "platenumber",
            ),
            (
                cfg.index.fee.as_str(),
                include_str!("../resources/es/index/fee_records.json"),
                "transtime",
                "vehicleplate",
            ),
            (
                cfg.index.trail.as_str(),
                include_str!("../resources/es/index/trail_fitting.json"),
                "extime",
                "envehicleid",
            ),
        ];
        for (name, tpl, date_field, ngram_field) in specs {
            if name.is_empty() {
                continue;
            }
            let body = match build_index_body(tpl, cfg) {
                Ok(v) => v,
                Err(e) => {
                    problems.push(format!("索引 {} mapping 解析失败: {}", name, e));
                    continue;
                }
            };
            match self.create_index_if_absent(name, &body).await {
                Ok(true) => tracing::info!(index = name, "[ES] 索引已按内置 mapping 创建"),
                Ok(false) => tracing::info!(index = name, "[ES] 索引已存在，跳过创建"),
                Err(e) => {
                    problems.push(format!("索引 {} 创建失败: {}", name, e.message()));
                    continue;
                }
            }
            // PUT 成功/已存在后复查 mapping，防止历史动态映射（text/无 ngram）继续被使用。
            match self.get_mapping(name).await {
                Ok(m) => {
                    if let Err(e) =
                        validate_index_mapping(&m, name, date_field, ngram_field)
                    {
                        problems.push(e);
                    }
                }
                Err(e) => problems.push(format!(
                    "索引 {} mapping 读取失败: {}",
                    name,
                    e.message()
                )),
            }
        }
        problems
    }
}

/// 校验索引结构：关键时间字段必须是 date，关键字段必须有 .ngram 子字段。
fn validate_index_mapping(
    mapping: &Value,
    index: &str,
    date_field: &str,
    ngram_field: &str,
) -> Result<(), String> {
    let props = mapping
        .get(index)
        .and_then(|v| v.get("mappings"))
        .and_then(|m| m.get("properties"))
        .ok_or_else(|| format!("索引 {} mapping 缺少 properties（可能已按动态映射创建）", index))?;
    let date_type = props
        .get(date_field)
        .and_then(|f| f.get("type"))
        .and_then(|t| t.as_str());
    if date_type != Some("date") {
        return Err(format!(
            "索引 {} 字段 {} 不是 date（实际 {:?}），range/sort 会 400",
            index, date_field, date_type
        ));
    }
    if props
        .get(ngram_field)
        .and_then(|f| f.get("fields"))
        .and_then(|f| f.get("ngram"))
        .is_none()
    {
        return Err(format!(
            "索引 {} 字段 {} 缺少 .ngram 子字段，模糊查询会 0 命中",
            index, ngram_field
        ));
    }
    Ok(())
}

/// 用运行期分片/副本替换内置 mapping 模板的占位符，并按需挂载 ILM。
fn build_index_body(tpl: &str, cfg: &ElasticsearchConfig) -> Result<Value, String> {
    let raw = tpl
        .replace("__NUMBER_OF_SHARDS__", &cfg.index.shards.to_string())
        .replace("__NUMBER_OF_REPLICAS__", &cfg.index.replicas.to_string());
    let mut body: Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if cfg.index.attach_ilm && !cfg.index.ilm_policy.is_empty() {
        if let Some(settings) = body.get_mut("settings").and_then(|s| s.as_object_mut()) {
            settings.insert(
                "index.lifecycle.name".to_string(),
                json!(cfg.index.ilm_policy),
            );
        }
    }
    Ok(body)
}

/// 提取 hits.hits[]._source；done 表示本批为空（scroll 结束）。
pub fn extract_hits(v: &Value) -> (Vec<Value>, bool) {
    let arr = v
        .get("hits")
        .and_then(|h| h.get("hits"))
        .and_then(|h| h.as_array())
        .cloned()
        .unwrap_or_default();
    let docs: Vec<Value> = arr
        .iter()
        .filter_map(|h| h.get("_source").cloned())
        .collect();
    let done = docs.is_empty();
    (docs, done)
}

/// 取 hits.total（ES7+ 是对象，ES6 是数字）。
pub fn total_hits(v: &Value) -> i64 {
    match v.get("hits").and_then(|h| h.get("total")) {
        Some(Value::Number(n)) => n.as_i64().unwrap_or(0),
        Some(Value::Object(o)) => o.get("value").and_then(|x| x.as_i64()).unwrap_or(0),
        _ => 0,
    }
}

/// 构造三段式模糊查询（与 Java QueryBuilders 的 term/match/wildcard 策略一致）。
pub fn build_fuzzy_query(field: &str, value: &str) -> Value {
    let chars = value.chars().count();
    if chars >= 7 && (field == "platenumber" || field == "gantrycode" || field == "sectioncode") {
        json!({ "term": { format!("{}.keyword", field): value } })
    } else if chars >= 3 {
        json!({ "match": { format!("{}.ngram", field): value } })
    } else {
        json!({ "wildcard": { format!("{}.keyword", field): format!("*{}*", value) } })
    }
}

/// 把 ES 错误体转成 Java `ElasticsearchException#getMessage()` 的文本格式。
fn es_exception(status: reqwest::StatusCode, text: &str) -> AppError {
    if let Ok(v) = serde_json::from_str::<Value>(text) {
        let root = v
            .get("error")
            .and_then(|e| e.get("root_cause"))
            .and_then(|r| r.as_array())
            .and_then(|a| a.first())
            .or_else(|| v.get("error"));
        if let Some(err) = root {
            let ty = err
                .get("type")
                .and_then(|x| x.as_str())
                .unwrap_or("unknown");
            let reason = err.get("reason").and_then(|x| x.as_str()).unwrap_or("");
            return AppError::biz(format!(
                "Elasticsearch exception [type={}, reason={}]",
                ty, reason
            ));
        }
    }
    AppError::biz(format!("ES 查询失败 HTTP {}: {}", status, text))
}

fn encode_index(index: &str) -> String {
    index.replace(',', "%2C")
}

#[cfg(test)]
mod bulk_tests {
    use super::parse_bulk_response;
    use serde_json::json;

    #[test]
    fn missing_items_are_counted_as_failed() {
        let resp = json!({
            "errors": false,
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 400, "error": {"type": "mapper_parsing_exception"}}}
            ]
        });
        let out = parse_bulk_response(&resp, 3);
        assert_eq!(out.ok, 1);
        assert_eq!(out.failed, 2); // 1 条 error + 1 条缺失
        assert!(out.first_error.is_some());
    }

    #[test]
    fn extra_items_are_clamped_to_docs_len() {
        let resp = json!({
            "errors": true,
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 400, "error": {"type": "x"}}},
                {"index": {"status": 400, "error": {"type": "y"}}}
            ]
        });
        let out = parse_bulk_response(&resp, 2);
        assert_eq!(out.ok + out.failed, 2);
        assert_eq!(out.ok, 1);
        assert_eq!(out.failed, 1);
    }

    #[test]
    fn extra_failed_items_are_not_clamped_to_zero() {
        // items(3) > docs(2)：2 条成功占满 cap，若只钳 ok 会把 failed 钳成 0，
        // 调用方会误以为整批成功。必须至少保留 1 条失败。
        let resp = json!({
            "errors": true,
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 201}},
                {"index": {"status": 400, "error": {"type": "x"}}}
            ]
        });
        let out = parse_bulk_response(&resp, 2);
        assert_eq!(out.ok, 2);
        assert_eq!(out.failed, 1);
        assert!(!out.is_all_ok());
    }

    #[test]
    fn errors_flag_with_all_items_ok_fails_whole_batch() {
        // 真正覆盖 `errors=true && failed==0` 分支：items 数与 docs_len 相同、
        // 每一条都没有 error 字段。上一版用 {"errors": true}（items 缺失），
        // 失败数由"缺少 items"分支写入，这个分支根本没被执行。
        let resp = json!({
            "errors": true,
            "items": [
                {"index": {"status": 200}},
                {"index": {"status": 201}},
                {"index": {"status": 200}},
                {"index": {"status": 200}}
            ]
        });
        let out = parse_bulk_response(&resp, 4);
        assert_eq!(out.ok, 0);
        assert_eq!(out.failed, 4);
        assert!(out.first_error.is_some());
    }
}
