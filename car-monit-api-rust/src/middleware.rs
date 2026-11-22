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

use axum::extract::Request;
use axum::http::{HeaderName, HeaderValue};
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

pub async fn request_id_and_log(req: Request, next: Next) -> Response {
    let start = Instant::now();
    let method = req.method().clone();
    // Drop guard：客户端断连导致 future 被取消时也能把 in-flight 计数减回去。
    let mut inflight = crate::metrics::InFlightGuard::start(method.as_str());
    let rid = req
        .headers()
        .get(&REQUEST_ID)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string())
        .unwrap_or_else(|| Uuid::new_v4().simple().to_string());
    let path = req.uri().path().to_string();

    // PARITY: Tomcat 的 maxHttpHeaderSize=8192 连请求行一起算，实测 GET 的
    // `path?query` 上限是 8075 字节（8075 → 200，8076 → 400）。Rust 侧用 hyper，
    // 默认上限不同，长参数（例如把整段轨迹 JSON 当过滤值传进来）会在 Java 400 而 Rust 200。
    // 这里补上同样的长度闸门，让状态码一致（Java 的 400 页面是容器 HTML，不属于应用契约，
    // Rust 继续返回应用的 Spring 错误 JSON，差异记录在 README 已知差异表）。
    if req
        .uri()
        .path_and_query()
        .map(|pq| pq.as_str().len())
        .unwrap_or(0)
        > MAX_URI_BYTES
    {
        inflight.finish(
            axum::http::StatusCode::BAD_REQUEST.as_u16(),
            start.elapsed().as_millis() as u64,
        );
        return crate::handlers::common::json_status(
            axum::http::StatusCode::BAD_REQUEST,
            crate::router::spring_error(axum::http::StatusCode::BAD_REQUEST, "Bad Request", &path),
        );
    }

    let span =
        tracing::info_span!("http.request", request_id = %rid, method = %method, path = %path);

    // DIFF: 旧实现用 span.enter() 持有 guard 跨 await，异步任务切换线程时 span 会错位；
    // 改用 Instrument 让 span 随 future 传播，日志里的 request_id/path 才能稳定关联。
    let mut resp = CURRENT_PATH
        .scope(path.clone(), async move { next.run(req).await })
        .instrument(span)
        .await;
    let status = resp.status();
    if let Ok(v) = HeaderValue::from_str(&rid) {
        resp.headers_mut().insert(REQUEST_ID, v);
    }
    let cost = start.elapsed().as_millis();
    inflight.finish(status.as_u16(), cost as u64);
    if status.is_server_error() {
        warn!(status = status.as_u16(), cost_ms = cost, "请求失败");
    } else {
        info!(status = status.as_u16(), cost_ms = cost, "请求完成");
    }
    resp
}
