// 来源: pro-base-common/src/main/java/com/ruoyi/common/exception/**（BaseException / UtilException）
//       Spring 的 @ControllerAdvice / @ExceptionHandler
// 职责: 统一业务异常；对应 Spring 把异常映射成 HTTP 状态码 + 错误响应体。
//
// DIFF: Java 用 try/catch + 运行时异常 + ControllerAdvice 全局兜底；
// Rust 用 Result<T, AppError> + `?` 传播，由 IntoResponse 统一转 HTTP 响应。
// 所有 handler 的 Err 分支最终都会落到这里，等价于 @ExceptionHandler。

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    /// 对应 new RuntimeException(msg) / IllegalArgumentException
    #[error("{0}")]
    Biz(String),

    /// 带 HTTP 状态码的业务异常（对应 ResponseStatusException）
    #[error("{code}: {msg}")]
    Http { code: u16, msg: String },

    /// 未找到（对应 NotFoundException）
    #[error("资源不存在: {0}")]
    NotFound(String),

    #[error("数据库错误: {0}")]
    Db(#[from] sqlx::Error),

    #[error("Redis 错误: {0}")]
    Redis(#[from] redis::RedisError),

    #[error("HTTP 错误: {0}")]
    HttpReq(#[from] reqwest::Error),

    #[error("序列化错误: {0}")]
    Json(#[from] serde_json::Error),

    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),

    #[error("{0}")]
    Other(#[from] anyhow::Error),
}

impl AppError {
    pub fn biz(msg: impl Into<String>) -> Self {
        Self::Biz(msg.into())
    }

    pub fn bad_request(msg: impl Into<String>) -> Self {
        Self::Http {
            code: 400,
            msg: msg.into(),
        }
    }

    pub fn unauthorized(msg: impl Into<String>) -> Self {
        Self::Http {
            code: 401,
            msg: msg.into(),
        }
    }

    pub fn internal(msg: impl Into<String>) -> Self {
        Self::Http {
            code: 500,
            msg: msg.into(),
        }
    }

    pub fn status(&self) -> StatusCode {
        match self {
            AppError::Http { code, .. } => {
                StatusCode::from_u16(*code).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR)
            }
            AppError::NotFound(_) => StatusCode::NOT_FOUND,
            _ => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    /// 对应 Java 侧异常消息（前端只读 message/msg）。
    pub fn message(&self) -> String {
        match self {
            AppError::Http { msg, .. } => msg.clone(),
            AppError::NotFound(m) => format!("资源不存在: {}", m),
            other => other.to_string(),
        }
    }
}

/// 对应 Spring Boot 未配置 @ControllerAdvice 时的 /error 响应体。
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = self.status();
        if status.is_server_error() {
            // 响应体保持 Spring 的空 message，只把根因写进日志，便于双端比对时定位
            tracing::error!(status = status.as_u16(), error = %self, "接口内部错误");
        }
        let error = match status.as_u16() {
            400 => "Bad Request",
            401 => "Unauthorized",
            403 => "Forbidden",
            404 => "Not Found",
            405 => "Method Not Allowed",
            409 => "Conflict",
            415 => "Unsupported Media Type",
            _ => "Internal Server Error",
        };
        let path = crate::middleware::CURRENT_PATH
            .try_with(|p| p.clone())
            .unwrap_or_default();
        let body = json!({
            "timestamp": chrono::Utc::now().format("%Y-%m-%dT%H:%M:%S%.3f+00:00").to_string(),
            "status": status.as_u16(),
            "error": error,
            "message": "",
            "path": path,
        });
        (status, Json(body)).into_response()
    }
}

pub type AppResult<T> = Result<T, AppError>;
