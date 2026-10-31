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
        if resp.status().is_success() {
            Ok(())
        } else {
            Err(AppError::biz(format!(
                "Elasticsearch 健康检查失败: HTTP {}",
                resp.status()
            )))
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

    /// 对应 BulkRequest：_id 即主键，实现 upsert（index 动作覆盖同 _id 文档）。
    pub async fn bulk_upsert(&self, index: &str, id_field: &str, docs: &[Value]) -> AppResult<i64> {
        if docs.is_empty() {
            return Ok(0);
        }
        let mut body = String::new();
        for doc in docs {
            let id = doc
                .get(id_field)
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
                .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
            body.push_str(&serde_json::to_string(
                &json!({ "index": { "_index": index, "_id": id } }),
            )?);
            body.push('\n');
            body.push_str(&serde_json::to_string(doc)?);
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
        Ok(v.get("items")
            .and_then(|x| x.as_array())
            .map(|a| a.len() as i64)
            .unwrap_or(0))
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
            Err(AppError::biz(format!(
                "创建索引 {} 失败 HTTP {}: {}",
                index, status, text
            )))
        }
    }
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
