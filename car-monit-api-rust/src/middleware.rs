// 来源: pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/WebConfig.java（整文件被注释）
//       pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/SecurityInterceptor.java（整文件被注释）
// 职责: 请求 ID、访问日志、panic 兜底、404/405 统一响应。
// 对应关系:
//   WebMvcConfigurer.addInterceptors      ↔ Router::layer(middleware::from_fn(...))
//   @ControllerAdvice + @ExceptionHandler ↔ AppError::into_response + fallback
//   MDC/RequestContextHolder              ↔ request_id 存入 response header 并写入 tracing span
//
// PARITY: SecurityInterceptor 在 Java 源码中整段被块注释（`/* ... */`），WebConfig 同样未启用，
// 因此 Java 服务当前没有任何鉴权拦截；Rust 侧保持一致 —— 不新增鉴权行为，
// 仅在 README 中标注「若恢复拦截器，应在此层实现」。

use std::time::Instant;

use axum::body::Body;
use axum::extract::Request;
use axum::http::header::ACCEPT;
use axum::http::{HeaderName, HeaderValue, StatusCode};
use axum::middleware::Next;
use axum::response::Response;
use tracing::{info, warn, Instrument};
use uuid::Uuid;

const REQUEST_ID: HeaderName = HeaderName::from_static("x-request-id");

/// GET 请求行里 `path?query` 的最大字节数（对齐 Tomcat maxHttpHeaderSize 的实测结果）。
const MAX_URI_BYTES: usize = 8075;

tokio::task_local! {
    /// 当前请求路径：供 AppError → Spring /error 响应体使用（无需在每个 handler 传参）。
    pub static CURRENT_PATH: String;
}

/// 归一化前的原始 requestURI：Spring 的 /error 体里 `path` 用的是它，不是合并斜杠后的路径。
#[derive(Clone)]
pub struct OriginalPath(pub String);

/// 供 404/405 兜底取原始路径。
pub fn error_path_of(req: &Request) -> String {
    req.extensions()
        .get::<OriginalPath>()
        .map(|o| o.0.clone())
        .unwrap_or_else(|| req.uri().path().to_string())
}

/// Spring 的 AntPathMatcher（`spring.mvc.pathmatch.matching-strategy=ant_path_matcher`）
/// 会合并连续斜杠并把结尾斜杠视为可选，实测：
/// `/base/gantry/list/`、`//base/gantry/list`、`/base/gantry//list` 都命中同一个方法。
/// Axum 用 matchit，默认严格匹配，需要在进入路由前做同样的归一化。
pub fn normalize_path(p: &str) -> String {
    // Spring 的 UrlPathHelper#removeSemicolonContent：每个路径段里从 ';' 到下一个 '/'
    // 之前的内容属于矩阵变量，不参与路由匹配（实测 `/base/gantry/list;a=b` 命中 list）。
    let without_matrix = {
        let mut buf = String::with_capacity(p.len());
        let mut skipping = false;
        for c in p.chars() {
            match c {
                ';' => skipping = true,
                '/' => {
                    skipping = false;
                    buf.push('/');
                }
                _ => {
                    if !skipping {
                        buf.push(c);
                    }
                }
            }
        }
        buf
    };
    let mut out = String::with_capacity(without_matrix.len());
    let mut prev_slash = false;
    for c in without_matrix.chars() {
        if c == '/' {
            if prev_slash {
                continue;
            }
            prev_slash = true;
        } else {
            prev_slash = false;
        }
        out.push(c);
    }
    if out.len() > 1 && out.ends_with('/') {
        out.pop();
    }
    out
}

/// Accept 头分类：`(能接受 JSON 族, 显式接受 text/html 或 text/*)`。
/// 实测 Spring 的行为：
///   `*/*`、`application/json`、`application/*`、`application/*+json` → 正常输出 JSON；
///   `text/html`、`text/*` → 正常响应 406，错误响应走 Whitelabel HTML；
///   `application/xml`、`application/xhtml+xml`、畸形值 → 406 且错误响应体为空。
/// `*/*` 只算接受 JSON（否则 `Accept: */*` 的 404 会错成 HTML，实测 Java 给的是 JSON）。
pub fn accept_prefs(raw: &str) -> (bool, bool) {
    let raw = raw.trim();
    if raw.is_empty() {
        return (true, false);
    }
    let mut json = false;
    let mut html = false;
    for part in raw.split(',') {
        let t = part
            .split(';')
            .next()
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        match t.as_str() {
            "*/*" | "application/json" | "application/*" | "application/*+json"
            | "application/cbor" | "application/x-jackson-smile" => json = true,
            "text/html" | "text/*" => html = true,
            _ => {}
        }
    }
    (json, html)
}

/// Whitelabel 页面 `#created` 那行的时间形态。
///
/// 注意来源不是 `java.util.Date#toString()`，而是 Spring Boot 错误视图里的
/// Thymeleaf 表达式 `${#dates.format(#dates.createNow(), 'EEE MMM dd HH:mm:ss zzz yyyy')}`，
/// 所以**日期补零**（实测 11-03 是 `Tue Nov 03 17:11:05 CST 2026`，而 `Date#toString()`
/// 会给出 `Nov  3`）。chrono 的 `%Z` 对固定偏移只给 `+08:00`，JDK 给的是缩写（本机 CST），
/// 因此缩写取 `APP_JAVA_TZ_ABBR`，缺省按偏移推断。
fn java_date_to_string() -> String {
    let now = chrono::Local::now();
    let abbr = match std::env::var("APP_JAVA_TZ_ABBR") {
        Ok(v) => v,
        Err(_) => match now.offset().local_minus_utc() {
            28800 => "CST".to_string(),
            0 => "GMT".to_string(),
            -18000 => "EST".to_string(),
            -28800 => "PST".to_string(),
            32400 => "JST".to_string(),
            secs => format!("GMT{:+}", secs / 3600),
        },
    };
    // %a %b = "Tue Nov"，%d = 补零的日，%Y = 四位年
    format!(
        "{} {} {} {} {}",
        now.format("%a %b"),
        now.format("%d"),
        now.format("%H:%M:%S"),
        abbr,
        now.format("%Y")
    )
}

/// 对应 Spring Boot 的 `WhitelabelErrorView`：`BasicErrorController.errorHtml` 的固定模板，
/// 时间戳见 `java_date_to_string()` 的说明。
fn whitelabel(status: StatusCode) -> Response {
    let created = java_date_to_string();
    let body = format!(
        "<html><body><h1>Whitelabel Error Page</h1><p>This application has no explicit mapping for /error, so you are seeing this as a fallback.</p><div id='created'>{}</div><div>There was an unexpected error (type={}, status={}).</div><div></div></body></html>",
        created,
        status.canonical_reason().unwrap_or("Unknown Status"),
        status.as_u16()
    );
    Response::builder()
        .status(status)
        .header(
            axum::http::header::CONTENT_TYPE,
            HeaderValue::from_static("text/html;charset=UTF-8"),
        )
        .body(Body::from(body))
        .unwrap()
}

fn empty_status(status: StatusCode) -> Response {
    Response::builder()
        .status(status)
        .body(Body::empty())
        .unwrap()
}

/// Tomcat 错误页的固定样式块。
const TOMCAT_CSS: &str = "body {font-family:Tahoma,Arial,sans-serif;} h1, h2, h3, b {color:white;background-color:#525D76;} h1 {font-size:22px;} h2 {font-size:16px;} h3 {font-size:14px;} p {font-size:12px;} a {color:black;} .line {height:1px;background-color:#525D76;border:none;}";

/// 容器级 400：请求行本身被 Tomcat 拒掉（编码斜杠、NUL、超过 maxHttpHeaderSize），
/// 请求根本没进 Spring，所以既不走 Whitelabel 也不看 Accept —— 实测恒为这一页（435 字节）。
fn tomcat_bad_request() -> Response {
    let title = "HTTP Status 400 \u{2013} Bad Request";
    let body = format!(
        "<!doctype html><html lang=\"en\"><head><title>{}</title><style type=\"text/css\">{}</style></head><body><h1>{}</h1></body></html>",
        title, TOMCAT_CSS, title
    );
    Response::builder()
        .status(StatusCode::BAD_REQUEST)
        .header(
            axum::http::header::CONTENT_TYPE,
            HeaderValue::from_static("text/html;charset=utf-8"),
        )
        .body(Body::from(body))
        .unwrap()
}

/// 请求行级的 Tomcat 拒绝条件。
/// `path` 只用于容器安全检查，`request_line`（`path?query`）只用于长度检查。
fn container_rejects(path: &str, request_line: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    // PARITY: Tomcat 拒绝编码后的斜杠与 NUL，但判定范围**只有 path**：
    // 实测 `/base/toll/list?a=%2Fb`、`?a=%00b` → 200（query 不参与路径解码），
    // 而 `/base/toll/list/a%2Fb`、`/base/toll/list%00` → 容器 HTML 400。
    // 图片地址类过滤值（`plateimage=http%3A%2F%2F...`）本身带 %2F，误判成 400 就是回归。
    if lower.contains("%2f") || lower.contains("%00") || path.contains('\u{0}') {
        return true;
    }
    // PARITY: Tomcat 的 maxHttpHeaderSize=8192 连请求行一起算，实测 GET 的
    // `path?query` 上限 8075 字节（8075 → 200，8076 → 400）。长参数（例如把整段轨迹
    // JSON 当过滤值传进来）在 Java 会撞这个闸门，hyper 默认不撞，状态码就差一位。
    request_line.len() > MAX_URI_BYTES
}

/// Spring 的协商与 /error 渲染规则（实测得到）：
///   1. 请求行先过 Tomcat 的容器级闸门（编码斜杠 / NUL / 长度上限）；
///   2. 路径按 AntPathMatcher 归一化；
///   3. 处理器成功返回 2xx 而客户端不接受 JSON → 406；404/405/500 的状态码优先，不被改写成 406；
///   4. 任何 >=400 的响应，体由 Accept 决定：text/html|text/* → Whitelabel；JSON 族或 */* → JSON；
///      两者都不接受 → 空体且不带 Content-Type。
pub async fn spring_negotiation(mut req: Request, next: Next) -> Response {
    let original = req.uri().path().to_string();
    let request_line = match req.uri().query() {
        Some(q) => format!("{}?{}", original, q),
        None => original.clone(),
    };
    if container_rejects(&original, &request_line) {
        return tomcat_bad_request();
    }
    let norm = normalize_path(&original);
    if norm != original {
        // http::Uri 没有 set_path，按 origin-form 重建 path?query
        let rebuilt = match req.uri().query() {
            Some(q) => format!("{}?{}", norm, q),
            None => norm.clone(),
        };
        if let Ok(uri) = rebuilt.parse::<axum::http::Uri>() {
            *req.uri_mut() = uri;
        }
    }
    let accept_raw = req
        .headers()
        .get(ACCEPT)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_string();
    let (json_ok, html_ok) = accept_prefs(&accept_raw);
    req.extensions_mut().insert(OriginalPath(original));

    let mut resp = next.run(req).await;
    let status = resp.status();
    if status.is_success() && !json_ok {
        resp = if html_ok {
            whitelabel(StatusCode::NOT_ACCEPTABLE)
        } else {
            empty_status(StatusCode::NOT_ACCEPTABLE)
        };
    } else if status.is_client_error() || status.is_server_error() {
        if html_ok {
            resp = whitelabel(status);
        } else if !json_ok {
            resp = empty_status(status);
        }
    }
    // 改写过的响应不再带 x-request-id：Java 侧本来就没有这个头，Whitelabel/空体也不应出现它
    resp
}

pub async fn request_id_and_log(req: Request, next: Next) -> Response {
    let start = Instant::now();
    let rid = req
        .headers()
        .get(&REQUEST_ID)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .unwrap_or_else(|| Uuid::new_v4().simple().to_string());
    let method = req.method().clone();
    let path = error_path_of(&req);

    // PARITY: 请求行级闸门（编码斜杠 / NUL / maxHttpHeaderSize）已经在 spring_negotiation
    // 里统一处理，这里不再重复判长度。

    let span =
        tracing::info_span!("http.request", request_id = %rid, method = %method, path = %path);
    // tracing 的 span 不能用 enter() 跨 await 持有（多线程 runtime 下会 panic：
    // "tried to clone a span that already closed"），改用 Instrument。
    let mut resp = CURRENT_PATH
        .scope(path.clone(), async move { next.run(req).await })
        .instrument(span)
        .await;
    let status = resp.status();
    if let Ok(v) = HeaderValue::from_str(&rid) {
        resp.headers_mut().insert(REQUEST_ID, v);
    }
    let cost = start.elapsed().as_millis();
    if status.is_server_error() {
        warn!(status = status.as_u16(), cost_ms = cost, "请求失败");
    } else {
        info!(status = status.as_u16(), cost_ms = cost, "请求完成");
    }
    resp
}
