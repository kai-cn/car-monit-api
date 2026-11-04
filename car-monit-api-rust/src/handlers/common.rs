// 来源: pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java:60-140
//       pro-base-common/src/main/java/com/ruoyi/common/core/page/TableSupport.java
// 职责: 分页参数解析、统一响应构造、时间范围必填校验、fuzzyFields 提取。
// 对应关系:
//   startPage() 读 pageNum/pageSize ↔ PageQuery
//   getDataTable(list)             ↔ TableDataInfo::new
//   @RequestParam 必填校验          ↔ require_time_range

use std::collections::HashMap;

use axum::extract::Request;
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
    /// 对应 TableSupport.ORDER_BY_COLUMN
    #[serde(rename = "orderByColumn")]
    pub order_by_column: Option<String>,
    /// 对应 TableSupport.IS_ASC
    #[serde(rename = "isAsc")]
    pub is_asc: Option<String>,
    /// 对应 TableSupport.REASONABLE（PageDomain#getReasonable 把 null 当 true）
    pub reasonable: Option<String>,
}

/// `StringUtils.toUnderScoreCase`（pro-base-common/StringUtils.java:453-496）的逐行等价实现。
/// 注意 Java 的 `nexteCharIsUpperCase` 在最后一个字符处不更新，沿用上一轮的值，
/// 这里保留同样的「尾巴」语义。
pub fn to_under_score_case(s: &str) -> String {
    let cs: Vec<char> = s.chars().collect();
    let mut sb = String::with_capacity(s.len() + 4);
    // Java 里 nexteCharIsUpperCase 在最后一个字符处不更新，沿用上一轮的值，所以它必须活在循环外
    let mut next = true;
    for i in 0..cs.len() {
        let c = cs[i];
        let pre = if i > 0 { cs[i - 1].is_uppercase() } else { false };
        let cur = c.is_uppercase();
        if i + 1 < cs.len() {
            next = cs[i + 1].is_uppercase();
        }
        if pre && cur && !next {
            sb.push('_');
        } else if i != 0 && !pre && cur {
            sb.push('_');
        }
        sb.extend(c.to_lowercase());
    }
    sb
}

/// `SqlUtil.isValidOrderBySql` 的 `[a-zA-Z0-9_ .,]+`（Java 用 `String.matches`，即全串匹配）。
fn is_valid_order_by(v: &str) -> bool {
    !v.is_empty()
        && v.chars().all(|c| {
            c.is_ascii_alphanumeric() || matches!(c, '_' | ' ' | ',' | '.')
        })
}

/// `PageDomain#setIsAsc`：空值不覆盖默认 "asc"，并兼容前端写的 ascending/descending。
fn normalize_is_asc(raw: Option<&str>) -> String {
    match raw {
        None => "asc".to_string(),
        Some(v) if v.trim().is_empty() => "asc".to_string(),
        Some("ascending") => "asc".to_string(),
        Some("descending") => "desc".to_string(),
        Some(v) => v.to_string(),
    }
}

/// `Convert.toBool` + `PageDomain#getReasonable`：解析不出来（含缺省）一律按 true。
fn reasonable_on(raw: Option<&str>) -> bool {
    let v = match raw {
        None => return true,
        Some(v) => v.trim().to_ascii_lowercase(),
    };
    match v.as_str() {
        "" => true,
        "false" | "off" | "no" | "n" | "0" => false,
        "true" | "on" | "yes" | "y" | "1" => true,
        other => other.parse::<f64>().map(|x| x != 0.0).unwrap_or(true),
    }
}

/// 对应 `PageDomain#getOrderBy()` + `SqlUtil#escapeOrderBySql()`（PageUtils.java:1-40）。
/// 返回的是「不含 ORDER BY 关键字」的排序片段，由仓库层拼进 SQL。
/// - orderByColumn 为空/全空格 → None（Java 走 `StringUtils.isEmpty` 分支，返回 ""）
/// - 非法字符或超过 500 字符 → UtilException，Spring 侧表现为 HTTP 500
pub fn order_by_clause(q: &PageQuery) -> AppResult<Option<String>> {
    let col = q.order_by_column.clone().unwrap_or_default();
    if col.trim().is_empty() {
        return Ok(None);
    }
    let asc = normalize_is_asc(q.is_asc.as_deref());
    let composed = format!("{} {}", to_under_score_case(col.trim()), asc);
    if !is_valid_order_by(&composed) {
        return Err(AppError::internal("参数不符合规范，不能进行查询"));
    }
    if composed.chars().count() > 500 {
        return Err(AppError::internal("参数已超过最大限制，不能进行查询"));
    }
    Ok(Some(composed))
}

#[derive(Debug, Clone, Copy)]
pub struct PageParams {
    pub page_num: i64,
    pub page_size: i64,
    /// PageHelper 语义：pageSize <= 0 时 rows 为空（total 仍为匹配总数）。
    pub empty: bool,
    /// PageHelper `reasonable`：false 时不做页码归一/钳位。
    pub reasonable: bool,
}

impl PageParams {
    pub fn offset(&self) -> i64 {
        if self.page_num <= 1 {
            0
        } else {
            (self.page_num - 1) * self.page_size
        }
    }

    /// PARITY: 实测 Java 的 PageHelper `reasonable=true` 生效——
    /// pageNum < 1 归 1；pageNum 超过总页数时钳位到最后一页（不是返回空行）。
    /// 因为钳位依赖总数，调用方需要先 count 再取 offset（与 PageHelper 先 count 后取数一致）。
    pub fn offset_for(&self, total: i64) -> i64 {
        if !self.reasonable {
            return self.offset();
        }
        let mut num = self.page_num.max(1);
        if self.page_size > 0 {
            let pages = (total + self.page_size - 1) / self.page_size;
            if pages > 0 && num > pages {
                num = pages;
            }
        }
        (num - 1) * self.page_size
    }
}

/// 对应 BaseController.startPage()：默认 pageNum=1、pageSize=10。
pub fn page_params(q: &PageQuery) -> PageParams {
    let raw_num = q.page_num.as_deref().and_then(|v| v.trim().parse::<i64>().ok());
    let page_num = raw_num.filter(|n| *n > 0).unwrap_or(1);
    let parsed_size = q
        .page_size
        .as_deref()
        .and_then(|v| v.trim().parse::<i64>().ok());
    let reasonable = reasonable_on(q.reasonable.as_deref());
    // PageHelper 语义（实测）：pageSize<=0 → 空行；
    // reasonable=false 且 pageNum<1 → 也是空行（total 仍为匹配总数），
    // 而 reasonable=true（默认）会把 pageNum<1 归一到第 1 页。
    let empty = matches!(parsed_size, Some(n) if n <= 0)
        || (!reasonable && matches!(raw_num, Some(n) if n < 1));
    let page_size = parsed_size.filter(|n| *n > 0).unwrap_or(10);
    // 注意：Java 侧 PageHelper 对 pageSize 没有上限（只有 reasonable 归一化），
    // 曾在此处加过 1000 的保护钳位，导致 pageSize=2000 时双端行数不同，已移除。
    PageParams {
        page_num,
        page_size,
        empty,
        reasonable,
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

// ============================================================
// Java 的日期参数白名单绑定
// ============================================================

/// `DateUtils.parsePatterns`（pro-base-common/DateUtils.java:28-31）的等价实现见
/// `crate::java_date`：12 种模式、SimpleDateFormat 的宽松进位、贪婪数字段、整串消费，
/// 且**不做 trim**（`"  2025-09-10  "` 在 Java 是解析失败，条件不生效）。
///
/// Java 的 `BaseController.initBinder` 用这 12 种模式解析所有 `java.util.Date` 查询参数；
/// 不匹配时 `parseDate` 返回 null，对应的 `<if test="x != null">` 条件根本不会拼进 SQL
/// —— 也就是「过滤条件被静默忽略」，HTTP 仍然 200。
pub fn java_date_parseable(s: &str) -> bool {
    crate::java_date::parseable(s)
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
    T: serde::de::DeserializeOwned + crate::models::JavaDateFields + crate::models::JavaIndexedFields,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(
        parts: &mut axum::http::request::Parts,
        state: &S,
    ) -> Result<Self, Self::Rejection> {
        let raw = parts.uri.query().unwrap_or_default().to_string();
        // PARITY: 绑定前先按 Java 的规则整理查询串
        //  1) 同名参数重复出现时，Spring 的 WebDataBinder 用逗号拼成一个值再交给编辑器
        //     （实测 `platenumber=%&platenumber=%` 在 Java 变成 `%,%` → LIKE 不命中；
        //      Rust 走 serde_urlencoded 会当重复字段直接 400）；
        //  2) Date 字段只认 DateUtils.parseDate 的 12 种模式，解析失败要像 Spring 的
        //     PropertyEditor 那样把参数丢掉（条件不生效），而不是报错。
        //     判定必须发生在拼接**之后**：`f=2025-09-01&f=2025-09-30&f=zzz` 交给编辑器的
        //     是 `2025-09-01,2025-09-30,zzz` 这一整串，Java 解析失败 → 条件不生效 → 200。
        let mut kept: Vec<(String, String)> = Vec::new(); // (原始键, 已拼接的值)
        for pair in raw.split('&').filter(|p| !p.is_empty()) {
            let (k, v) = match pair.split_once('=') {
                Some(kv) => kv,
                None => (pair, ""),
            };
            let key = percent_decode(k);
            // Spring 的 BeanWrapper：`x[y]=v` 只有当 x 是 Map/List/数组才合法，
            // 否则 InvalidPropertyException → 500；x 完全不存在时才是「未知属性」→ 忽略。
            if let Some(pos) = key.find('[') {
                let root = &key[..pos];
                if <T as crate::models::JavaIndexedFields>::JAVA_INDEXED_FIELDS
                    .iter()
                    .any(|f| *f == root)
                {
                    return Err(AppError::internal(format!(
                        "Invalid property '{}' of bean class",
                        key
                    )));
                }
            }
            if let Some(slot) = kept.iter_mut().find(|(ek, _)| ek == k) {
                slot.1.push(',');
                slot.1.push_str(v);
            } else {
                kept.push((k.to_string(), v.to_string()));
            }
        }
        kept.retain(|(k, v)| {
            let name = percent_decode(k);
            let date_field = <T as crate::models::JavaDateFields>::JAVA_DATE_FIELDS
                .iter()
                .any(|f| *f == name.as_str());
            !date_field || java_date_parseable(&percent_decode(v))
        });
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
            .map_err(|e| AppError::bad_request(e.to_string()))?;
        Ok(JavaQuery(q.0))
    }
}

// ============================================================
// 请求体绑定：对应 Spring 的 HttpMessageNotReadableException
// ============================================================

/// Spring 侧请求体不可读时的响应：HTTP 400 + `/error` 的 JSON 体（message 为空串）。
/// axum 默认给 `text/plain` 的 "Failed to parse the request body as JSON: ..."，
/// 且类型不符时是 422，两处都会让契约比对失败。
fn body_not_readable() -> Response {
    spring_body_error(StatusCode::BAD_REQUEST)
}

/// 状态码跟随 Spring：请求体类型不符 400、Content-Type 不支持 415。
fn spring_body_error(status: StatusCode) -> Response {
    let path = crate::middleware::CURRENT_PATH
        .try_with(|p| p.clone())
        .unwrap_or_default();
    let error = status.canonical_reason().unwrap_or("Bad Request");
    json_status(
        status,
        crate::router::spring_error(status, error, &path),
    )
}

/// Spring 的 `@RequestBody` 允许「不带 Content-Type」（此时按可读性挑转换器），
/// 但显式的非 JSON 类型一定 415。
fn content_type_accepts_json(req: &Request) -> bool {
    match req
        .headers()
        .get(axum::http::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
    {
        None => true,
        Some(raw) => {
            let t = raw
                .split(';')
                .next()
                .unwrap_or("")
                .trim()
                .to_ascii_lowercase();
            t.is_empty()
                || t == "application/json"
                || t == "application/*+json"
                || t.ends_with("+json")
        }
    }
}

/// 对应 `@RequestBody T x`（required = true）：缺失/空/非法/类型不符都按 Spring 走 400。
pub struct SpringJson<T>(pub T);

impl<T, S> axum::extract::FromRequest<S> for SpringJson<T>
where
    T: serde::de::DeserializeOwned + Send,
    S: Send + Sync,
{
    type Rejection = Response;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let expect = if content_type_accepts_json(&req) {
            StatusCode::BAD_REQUEST
        } else {
            StatusCode::UNSUPPORTED_MEDIA_TYPE
        };
        let bad = |e: axum::extract::rejection::JsonRejection| {
            spring_body_error(if e.status() == StatusCode::UNSUPPORTED_MEDIA_TYPE {
                StatusCode::UNSUPPORTED_MEDIA_TYPE
            } else {
                expect
            })
        };
        // Jackson 只把 JSON **对象**绑定成 bean；`[]`/`{}` 之外的标量、数组都会
        // HttpMessageNotReadableException(400)。serde 默认允许「用数组按顺序填结构体字段」，
        // 所以这里先落到 Value 再把非对象拒掉（实测 Java `[]` → 400，Rust 修复前 → 200）。
        let Json(value) = axum::extract::Json::<serde_json::Value>::from_request(req, state)
            .await
            .map_err(bad)?;
        if !value.is_object() {
            return Err(spring_body_error(StatusCode::BAD_REQUEST));
        }
        let v: T = serde_json::from_value(value).map_err(|_| spring_body_error(StatusCode::BAD_REQUEST))?;
        Ok(SpringJson(v))
    }
}

/// 对应 `@RequestBody(required = false) Map<String, String> fuzzyFields`：
/// 无请求体或空体 → 空 Map；JSON 非对象 / 值非标量 → 400。
/// 数字与布尔按 Jackson 的宽松标量强转成字符串，null 值在 Java 侧会被 isNotBlank 跳过，
/// 这里等价地丢弃。
pub struct SpringStringMap(pub HashMap<String, String>);

impl<S> axum::extract::FromRequest<S> for SpringStringMap
where
    S: Send + Sync,
{
    type Rejection = Response;

    async fn from_request(req: Request, _state: &S) -> Result<Self, Self::Rejection> {
        if !content_type_accepts_json(&req) {
            return Err(spring_body_error(StatusCode::UNSUPPORTED_MEDIA_TYPE));
        }
        let bytes = axum::body::Bytes::from_request(req, _state)
            .await
            .map_err(|_| body_not_readable())?;
        if String::from_utf8_lossy(&bytes).trim().is_empty() {
            return Ok(SpringStringMap(HashMap::new()));
        }
        let value: serde_json::Value =
            serde_json::from_slice(&bytes).map_err(|_| body_not_readable())?;
        let serde_json::Value::Object(map) = value else {
            return Err(body_not_readable());
        };
        let mut out = HashMap::new();
        for (k, v) in map {
            match v {
                Value::String(s) => {
                    out.insert(k, s);
                }
                Value::Number(n) => {
                    out.insert(k, n.to_string());
                }
                Value::Bool(b) => {
                    out.insert(k, b.to_string());
                }
                Value::Null => {}
                _ => return Err(body_not_readable()),
            }
        }
        Ok(SpringStringMap(out))
    }
}
