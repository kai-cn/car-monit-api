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
use tracing::{info, warn};
use uuid::Uuid;

const REQUEST_ID: HeaderName = HeaderName::from_static("x-request-id");

tokio::task_local! {
    /// 当前请求路径：供 AppError → Spring /error 响应体使用（无需在每个 handler 传参）。
    pub static CURRENT_PATH: String;
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
    let path = req.uri().path().to_string();

    let span =
        tracing::info_span!("http.request", request_id = %rid, method = %method, path = %path);
    let _enter = span.enter();

    let mut resp = CURRENT_PATH
        .scope(path.clone(), async move { next.run(req).await })
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
