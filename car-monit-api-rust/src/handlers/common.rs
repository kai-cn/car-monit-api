// 来源: pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java:60-140
//       pro-base-common/src/main/java/com/ruoyi/common/core/page/TableSupport.java
// 职责: 分页参数解析、统一响应构造、时间范围必填校验、fuzzyFields 提取。
// 对应关系:
//   startPage() 读 pageNum/pageSize ↔ PageQuery
//   getDataTable(list)             ↔ TableDataInfo::new
//   @RequestParam 必填校验          ↔ require_time_range

use std::collections::HashMap;

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::error::{AppError, AppResult};

#[derive(Debug, Clone, Default, Deserialize)]
pub struct PageQuery {
    // 用 String 接收，再宽松解析：对应 Java `Convert.toInt(param, 1)` 的容错语义
    #[serde(rename = "pageNum")]
    pub page_num: Option<String>,
    #[serde(rename = "pageSize")]
    pub page_size: Option<String>,
}

#[derive(Debug, Clone, Copy)]
pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
    /// PageHelper 语义：pageSize <= 0 时 rows 为空（total 仍为匹配总数）。
    pub empty: bool,
}

impl PageParams {
    pub fn offset(&self) -> i64 {
        if self.page_num <= 1 {
            0
        } else {
            (self.page_num - 1) * self.page_size
        }
    }
}

/// 对应 BaseController.startPage()：默认 pageNum=1、pageSize=10。
pub fn page_params(q: &PageQuery) -> PageParams {
    let page_num = q
        .page_num
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(1);
    let parsed_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok());
    let empty = matches!(parsed_size, Some(n) if n <= 0);
    let mut page_size = parsed_size.filter(|n| *n > 0).unwrap_or(10);
    // 与 Go 版一致的保护上限：8 亿级表不允许一次拉太多
    if page_size > 1000 {
        page_size = 1000;
    }
    PageParams {
        page_num,
        page_size,
        empty,
    }
}

/// 对应 `@RequestParam String startTime/endTime` 的必填校验。
pub fn require_time_range(start: &str, end: &str) -> AppResult<()> {
    let mut missing = Vec::new();
    if start.is_empty() {
        missing.push("startTime");
    }
    if end.is_empty() {
        missing.push("endTime");
    }
    if missing.is_empty() {
        Ok(())
    } else {
        Err(AppError::bad_request(format!(
            "缺少必填参数: {}",
            missing.join(", ")
        )))
    }
}

/// 提取 `fuzzyFields.xxx` 形式的查询参数（对应 extractFuzzyFields）。
pub fn fuzzy_fields(raw: &HashMap<String, String>) -> HashMap<String, String> {
    raw.iter()
        .filter_map(|(k, v)| {
            k.strip_prefix("fuzzyFields.")
                .filter(|_| !v.is_empty())
                .map(|name| (name.to_string(), v.clone()))
        })
        .collect()
}

/// 把 `fuzzyFields.` 前缀也应用到请求体（large 导出接口的原始行为）。
pub fn prefixed_fields(raw: &HashMap<String, String>) -> HashMap<String, String> {
    raw.iter()
        .filter_map(|(k, v)| {
            k.strip_prefix("fuzzyFields.")
                .filter(|_| !v.is_empty())
                .map(|name| (name.to_string(), v.clone()))
        })
        .collect()
}

/// 直接以 HTTP 200 返回 JSON。
pub fn json_ok(v: impl serde::Serialize) -> Response {
    (StatusCode::OK, Json(v)).into_response()
}

/// 以指定 HTTP 状态码返回 JSON。
pub fn json_status(status: StatusCode, v: impl serde::Serialize) -> Response {
    (status, Json(v)).into_response()
}

pub fn empty_ok() -> Response {
    StatusCode::OK.into_response()
}

/// 对应 Java 的 `Map<String,Object> result`：字段顺序与 put 顺序一致（serde_json preserve_order）。
pub fn map_response(pairs: Vec<(&str, Value)>) -> Response {
    let mut m = serde_json::Map::new();
    for (k, v) in pairs {
        m.insert(k.to_string(), v);
    }
    json_ok(Value::Object(m))
}

/// 对应 `/api/v1/large|unified` 的错误信封：HTTP 仍为 200，body.code=500。
pub fn biz_map_error(message: impl Into<String>) -> Response {
    json_ok(json!({ "code": 500, "message": message.into() }))
}
