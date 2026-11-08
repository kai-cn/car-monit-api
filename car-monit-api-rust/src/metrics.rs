// 职责: 最小可用的 Prometheus 指标端点（S1）。
//
// DIFF: Java 侧没有 Actuator/Micrometer；Rust 侧不引入额外依赖，直接用进程内原子计数
// 输出 Prometheus 文本格式，避免为一个 /metrics 增加 metrics-exporter-prometheus 依赖树。
// 覆盖：请求量（method/status）、延迟总和与次数（method）、在途请求、DB 连接池、消费端开关。
// 未覆盖：Kafka lag（需要 consumer group 查询）、导出队列深度（需跨副本）、分位延迟（需直方图桶）。

use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;

use axum::extract::State;
use axum::response::{IntoResponse, Response};
use dashmap::DashMap;
use once_cell::sync::Lazy;

use crate::state::AppState;

static REQUESTS_TOTAL: Lazy<DashMap<String, u64>> = Lazy::new(DashMap::new);
static DURATION_MS_SUM: Lazy<DashMap<String, u64>> = Lazy::new(DashMap::new);
static DURATION_COUNT: Lazy<DashMap<String, u64>> = Lazy::new(DashMap::new);
static IN_FLIGHT: AtomicI64 = AtomicI64::new(0);

/// 请求进入时调用（在 request_id_and_log 里配对使用）。
pub fn request_started() {
    IN_FLIGHT.fetch_add(1, Ordering::Relaxed);
}

/// 请求完成时调用。
pub fn request_finished(method: &str, status: u16, elapsed_ms: u64) {
    IN_FLIGHT.fetch_sub(1, Ordering::Relaxed);
    *REQUESTS_TOTAL
        .entry(format!("{}|{}", method, status))
        .or_insert(0) += 1;
    *DURATION_MS_SUM.entry(method.to_string()).or_insert(0) += elapsed_ms;
    *DURATION_COUNT.entry(method.to_string()).or_insert(0) += 1;
}

/// 客户端断连/任务被取消时调用：没有响应状态，单独计数为 client_closed。
pub fn request_aborted(method: &str) {
    IN_FLIGHT.fetch_sub(1, Ordering::Relaxed);
    *REQUESTS_TOTAL
        .entry(format!("{}|client_closed", method))
        .or_insert(0) += 1;
}

/// 在途计数守卫：即使 handler future 被客户端断连取消（不会走到收尾代码），
/// Drop 时也会把 in-flight 计数减回去，避免 /metrics 单调泄漏。
pub struct InFlightGuard {
    method: String,
    finished: bool,
}

impl InFlightGuard {
    pub fn start(method: &str) -> Self {
        request_started();
        Self {
            method: method.to_string(),
            finished: false,
        }
    }

    pub fn finish(&mut self, status: u16, elapsed_ms: u64) {
        if !self.finished {
            request_finished(&self.method, status, elapsed_ms);
            self.finished = true;
        }
    }
}

impl Drop for InFlightGuard {
    fn drop(&mut self) {
        if !self.finished {
            request_aborted(&self.method);
        }
    }
}

fn escape_label(v: &str) -> String {
    v.replace('\\', "\\\\").replace('"', "\\\"")
}

/// GET /metrics —— Prometheus 文本格式（text/plain; version=0.0.4）。
pub async fn metrics(State(state): State<Arc<AppState>>) -> Response {
    let mut out = String::with_capacity(2048);

    out.push_str("# HELP http_requests_total 已完成的 HTTP 请求数\n");
    out.push_str("# TYPE http_requests_total counter\n");
    for e in REQUESTS_TOTAL.iter() {
        let (method, status) = e.key().split_once('|').unwrap_or((e.key(), "0"));
        out.push_str(&format!(
            "http_requests_total{{method=\"{}\",status=\"{}\"}} {}\n",
            escape_label(method),
            escape_label(status),
            e.value()
        ));
    }

    out.push_str("# HELP http_request_duration_seconds_sum 请求处理耗时总和\n");
    out.push_str("# TYPE http_request_duration_seconds_sum counter\n");
    out.push_str("# HELP http_request_duration_seconds_count 请求处理次数\n");
    out.push_str("# TYPE http_request_duration_seconds_count counter\n");
    for e in DURATION_MS_SUM.iter() {
        let method = escape_label(e.key());
        let sum = *e.value() as f64 / 1000.0;
        let count = DURATION_COUNT.get(e.key()).map(|v| *v).unwrap_or(0);
        out.push_str(&format!(
            "http_request_duration_seconds_sum{{method=\"{}\"}} {:.3}\n",
            method, sum
        ));
        out.push_str(&format!(
            "http_request_duration_seconds_count{{method=\"{}\"}} {}\n",
            method, count
        ));
    }

    out.push_str("# HELP http_requests_in_flight 当前在途请求数\n");
    out.push_str("# TYPE http_requests_in_flight gauge\n");
    out.push_str(&format!(
        "http_requests_in_flight {}\n",
        IN_FLIGHT.load(Ordering::Relaxed)
    ));

    out.push_str("# HELP db_pool_connections 数据库连接池连接数\n");
    out.push_str("# TYPE db_pool_connections gauge\n");
    out.push_str(&format!(
        "db_pool_connections{{state=\"size\"}} {}\n",
        state.db.pool.size()
    ));
    out.push_str(&format!(
        "db_pool_connections{{state=\"idle\"}} {}\n",
        state.db.pool.num_idle()
    ));

    out.push_str("# HELP app_consumer_enabled 消费端是否启用（1=启用）\n");
    out.push_str("# TYPE app_consumer_enabled gauge\n");
    out.push_str(&format!(
        "app_consumer_enabled {}\n",
        if state.cfg.app.consumer_enabled { 1 } else { 0 }
    ));

    (
        [(
            axum::http::header::CONTENT_TYPE,
            "text/plain; version=0.0.4",
        )],
        out,
    )
        .into_response()
}
