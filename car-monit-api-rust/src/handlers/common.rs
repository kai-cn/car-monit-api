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
            (self.page_num - 1).saturating_mul(self.page_size)
        }
    }

    /// PARITY: 实测 Java 的 PageHelper `reasonable=true` 生效——
    /// pageNum < 1 归 1；pageNum 超过总页数时钳位到最后一页（不是返回空行）。
    /// 因为钳位依赖总数，调用方需要先 count 再取 offset（与 PageHelper 先 count 后取数一致）。
    pub fn offset_for(&self, total: i64) -> i64 {
        let mut num = self.page_num.max(1);
        if self.page_size > 0 {
            let pages = (total + self.page_size - 1) / self.page_size;
            if pages > 0 && num > pages {
                num = pages;
            }
        }
        (num - 1).saturating_mul(self.page_size)
    }
}

/// pageNum 上限：防止 (pageNum-1)*pageSize 溢出，也避免下游把 offset 转 i32 时回绕。
pub const MAX_PAGE_NUM: i64 = 10_000_000;
/// pageSize 上限：全局限流式保护，所有列表接口单页最多 1000 行。
pub const MAX_PAGE_SIZE: i64 = 1000;

/// 对应 BaseController.startPage()：默认 pageNum=1、pageSize=10。
pub fn page_params(q: &PageQuery) -> PageParams {
    let page_num = q
        .page_num
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok())
        // PARITY: Java 用 Convert.toInt（Integer），超出 int 范围视为非法 -> 默认 1
        .filter(|n| *n > 0 && *n <= i32::MAX as i64)
        .map(|n| n.min(MAX_PAGE_NUM))
        .unwrap_or(1);
    let parsed_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok());
    let empty = matches!(parsed_size, Some(n) if n <= 0);
    let mut page_size = parsed_size.filter(|n| *n > 0).unwrap_or(10);
    // 统一保护上限：所有列表接口单页最多 1000 行（与 Go 版一致，避免一次拉全表）。
    if page_size > MAX_PAGE_SIZE {
        page_size = MAX_PAGE_SIZE;
    }
    PageParams {
        page_num,
        page_size,
        empty,
    }
}

/// 对应 `@RequestParam String startTime/endTime` 的必填校验。
/// `startTime=+` 会被解码成一个空格：只判 `is_empty` 会放行，随后 `parse_time("")`
/// 返回 epoch 0，查询从 1970 年开始。这里必须按 trim 后是否为空判定。
pub fn require_time_range(start: &str, end: &str) -> AppResult<()> {
    let mut missing = Vec::new();
    if start.trim().is_empty() {
        missing.push("startTime");
    }
    if end.trim().is_empty() {
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

// ============================================================
// Java 的日期参数白名单绑定
// ============================================================

/// `DateUtils.parsePatterns`（pro-base-common/DateUtils.java:28-31）。
/// Java 的 `BaseController.initBinder` 用这 12 种模式解析所有 `java.util.Date` 查询参数，
/// 且要求整串匹配；不匹配时 `parseDate` 返回 null，对应的 `<if test="x != null">` 条件
/// 根本不会拼进 SQL —— 也就是「过滤条件被静默忽略」，HTTP 仍然 200。
const JAVA_DATE_PATTERNS: &[&str] = &[
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%Y.%m.%d",
];

/// 对应 `DateUtils.parseDate(String)` 的成功/失败判定（不做时区换算，只判断能否解析）。
pub fn java_date_parseable(s: &str) -> bool {
    use chrono::{NaiveDate, NaiveDateTime};
    let s = s.trim();
    if s.is_empty() {
        return false;
    }
    for f in JAVA_DATE_PATTERNS {
        if NaiveDateTime::parse_from_str(s, f).is_ok() || NaiveDate::parse_from_str(s, f).is_ok() {
            return true;
        }
    }
    // yyyy-MM / yyyy/MM / yyyy.MM：只到年份+月份
    for sep in ['-', '/', '.'] {
        if let Some(pos) = s.find(sep) {
            let (y, m) = (&s[..pos], &s[pos + 1..]);
            if y.len() == 4
                && matches!(m.len(), 1 | 2)
                && y.parse::<i32>().is_ok()
                && m.parse::<u32>()
                    .map(|v| (1..=12).contains(&v))
                    .unwrap_or(false)
            {
                return true;
            }
        }
    }
    false
}

fn percent_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut i = 0usize;
    while i < bytes.len() {
        match bytes[i] {
            b'%' if i + 2 < bytes.len() => {
                let hex = &bytes[i + 1..i + 3];
                match u8::from_str_radix(std::str::from_utf8(hex).unwrap_or(""), 16) {
                    Ok(b) => {
                        out.push(b);
                        i += 3;
                    }
                    Err(_) => {
                        out.push(b'%');
                        i += 1;
                    }
                }
            }
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            b => {
                out.push(b);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// 对应 Spring `MethodArgumentTypeMismatchException` → `/error` 的 400 JSON 错误体。
/// PARITY: Axum 默认的 Query 拒绝返回纯文本 `Failed to deserialize query string: ...`，
/// Java 返回的是 `{timestamp,status,error,message,path}`；这里统一成 Java 的形状。
#[derive(Debug)]
pub struct SpringQueryRejection(pub axum::extract::rejection::QueryRejection);

impl IntoResponse for SpringQueryRejection {
    fn into_response(self) -> Response {
        let path = crate::middleware::CURRENT_PATH
            .try_with(|p| p.clone())
            .unwrap_or_default();
        json_status(
            StatusCode::BAD_REQUEST,
            crate::router::spring_error(StatusCode::BAD_REQUEST, "Bad Request", &path),
        )
    }
}

/// 与 `axum::extract::Query<T>` 等价，但先按 Java 的规则丢弃解析失败的日期参数。
/// 只用于绑定实体（19 张基础表的 list/listToExport、feeGantry、snapshotflow 等）。
pub struct JavaQuery<T>(pub T);

impl<T, S> axum::extract::FromRequestParts<S> for JavaQuery<T>
where
    T: serde::de::DeserializeOwned + crate::models::JavaDateFields,
    S: Send + Sync,
{
    type Rejection = SpringQueryRejection;

    async fn from_request_parts(
        parts: &mut axum::http::request::Parts,
        state: &S,
    ) -> Result<Self, Self::Rejection> {
        let raw = parts.uri.query().unwrap_or_default().to_string();
        // PARITY: 绑定前做两件事，都与 Java 对齐
        //  1) 同名参数重复出现时，Spring 把它们用逗号拼成一个值再绑定
        //     （实测 `platenumber=%&platenumber=%` 在 Java 变成 `%,%` → LIKE 不命中；
        //      Rust 走 serde_urlencoded 会当重复字段直接 400）；
        //  2) Date 字段只认 DateUtils.parseDate 的 12 种模式，解析失败要像 Spring 的
        //     PropertyEditor 那样把参数丢掉（条件不生效），而不是报错。
        let mut kept: Vec<(String, String)> = Vec::new(); // (原始键, 已拼接的值)
        for pair in raw.split('&').filter(|p| !p.is_empty()) {
            let (k, v) = match pair.split_once('=') {
                Some(kv) => kv,
                None => (pair, ""),
            };
            let key = percent_decode(k);
            let date_field = <T as crate::models::JavaDateFields>::JAVA_DATE_FIELDS
                .contains(&key.as_str());
            if date_field && !java_date_parseable(&percent_decode(v)) {
                continue;
            }
            if let Some(slot) = kept.iter_mut().find(|(ek, _)| ek == k) {
                slot.1.push(',');
                slot.1.push_str(v);
            } else {
                kept.push((k.to_string(), v.to_string()));
            }
        }
        let kept: Vec<String> = kept
            .into_iter()
            .map(|(k, v)| {
                if v.is_empty() && !k.contains('=') {
                    k
                } else {
                    format!("{}={}", k, v)
                }
            })
            .collect();
        if let Ok(uri) = axum::http::Uri::builder()
            .path_and_query(format!("{}?{}", parts.uri.path(), kept.join("&")))
            .build()
        {
            parts.uri = uri;
        }
        let q = axum::extract::Query::<T>::from_request_parts(parts, state)
            .await
            .map_err(SpringQueryRejection)?;
        Ok(JavaQuery(q.0))
    }
}

#[cfg(test)]
mod tests {
    use super::{page_params, require_time_range, PageQuery, MAX_PAGE_NUM};

    #[test]
    fn require_time_range_rejects_whitespace_only() {
        // `startTime=+` 解码成空格：不能当成"已提供"。
        assert!(require_time_range(" ", "2026-01-01 00:00:00").is_err());
        assert!(require_time_range("2026-01-01 00:00:00", "\t").is_err());
        assert!(require_time_range("2026-01-01 00:00:00", "2026-01-02 00:00:00").is_ok());
    }

    #[test]
    fn page_params_clamps_page_num_above_cap() {
        // i32 范围以内但超过 MAX_PAGE_NUM：钳到上限。
        let q = PageQuery {
            page_num: Some("2000000000".to_string()),
            page_size: Some("20".into()),
        };
        let p = page_params(&q);
        assert_eq!(p.page_num, MAX_PAGE_NUM);
        assert_eq!(p.offset(), (MAX_PAGE_NUM - 1).saturating_mul(20));
        assert!(!p.empty);
    }

    #[test]
    fn page_params_falls_back_for_int_overflow_page_num() {
        // 超过 i32::MAX 与 Java Convert.toInt 一致：视为非法，回退第 1 页。
        let q = PageQuery {
            page_num: Some(i64::MAX.to_string()),
            page_size: Some("20".into()),
        };
        assert_eq!(page_params(&q).page_num, 1);
    }
}
