#include "router/routes.h"

#include "cache/redis.h"
#include "common/logging.h"
#include "db/pg.h"
#include "handler/handlers.h"
#include "http/server.h"
#include "mq/kafka_producer.h"
#include "service/optimization.h"

#include <sstream>

namespace cm::router {
namespace {

// /metrics?format=prometheus：Prometheus 文本格式（JSON 仍为默认，保持兼容）。
std::string prometheus_metrics(const cm::Json& s) {
  std::ostringstream out;
  auto metric = [&](const char* name, const char* help, const char* type,
                    const cm::Json& value) {
    out << "# HELP " << name << " " << help << "\n";
    out << "# TYPE " << name << " " << type << "\n";
    out << name << " " << cm::json_string(value, "0") << "\n";
  };
  metric("carmonit_requests_total", "HTTP 请求总数", "counter", s["requestsTotal"]);
  metric("carmonit_errors_total", "HTTP 5xx 错误总数", "counter", s["errorsTotal"]);
  metric("carmonit_requests_in_flight", "当前在途请求数", "gauge", s["inFlight"]);
  metric("carmonit_request_duration_ms_avg", "平均请求时延（毫秒）", "gauge",
         s["avgLatencyMs"]);
  metric("carmonit_request_duration_ms_p50", "请求时延 P50（毫秒）", "gauge",
         s["p50LatencyMs"]);
  metric("carmonit_request_duration_ms_p95", "请求时延 P95（毫秒）", "gauge",
         s["p95LatencyMs"]);
  metric("carmonit_request_duration_ms_p99", "请求时延 P99（毫秒）", "gauge",
         s["p99LatencyMs"]);
  metric("carmonit_error_rate", "错误率（errors/requests）", "gauge", s["errorRate"]);
  metric("carmonit_responses_total_2xx", "2xx 响应数", "counter", s["status2xx"]);
  metric("carmonit_responses_total_4xx", "4xx 响应数", "counter", s["status4xx"]);
  metric("carmonit_responses_total_5xx", "5xx 响应数", "counter", s["status5xx"]);

  const auto& deps = s["dependencies"];
  if (deps.is_object()) {
    out << "# HELP carmonit_dependency_up 依赖状态（1=UP，0=DOWN/UNKNOWN）\n";
    out << "# TYPE carmonit_dependency_up gauge\n";
    for (const char* name : {"db", "redis", "es", "kafka"}) {
      const auto& d = deps[name];
      if (!d.is_object()) continue;
      const int up = cm::json_string(d["status"]) == "UP" ? 1 : 0;
      out << "carmonit_dependency_up{component=\"" << name << "\"} " << up << "\n";
    }
    out << "# HELP carmonit_dependency_latency_ms 依赖探活时延（毫秒）\n";
    out << "# TYPE carmonit_dependency_latency_ms gauge\n";
    for (const char* name : {"db", "redis", "es", "kafka"}) {
      const auto& d = deps[name];
      if (!d.is_object()) continue;
      out << "carmonit_dependency_latency_ms{component=\"" << name << "\"} "
          << cm::json_string(d["latencyMs"], "0") << "\n";
    }
    const auto& wp = deps["workerPool"];
    if (wp.is_object()) {
      metric("carmonit_worker_pool_pending", "后台线程池队列深度", "gauge", wp["pending"]);
      metric("carmonit_worker_pool_active", "后台线程池在执行任务数", "gauge", wp["active"]);
      metric("carmonit_worker_pool_capacity", "后台线程池队列容量", "gauge", wp["capacity"]);
    }
    const auto& db = deps["db"];
    if (db.is_object()) {
      metric("carmonit_db_pool_live", "数据库池活跃物理连接数", "gauge",
             db["liveConnections"]);
      metric("carmonit_db_pool_max", "数据库池上限", "gauge", db["maxConnections"]);
    }
  }
  return out.str();
}

} // namespace

http::Router build_routes() {
  http::Router router;
  // 健康检查（本工程新增端点，Java 无对应物）：
  // 汇总 DB/Redis/Kafka/ES 的连接状态。刻意**不主动建连/认证**——探活不能
  // 变成一次失败登录（openGauss failed_login_attempts 会锁账号），因此
  // 各组件只报告当前连接状态；整体状态任一 DOWN 即 DEGRADED。
  router.add("GET", "/health", [](http::Request&) {
    auto& pool = cm::db::PgPool::instance();
    auto& redis = cm::cache::Redis::instance();
    auto& kafka = cm::mq::KafkaProducer::instance();

    const std::string db_status = !pool.available() ? "UNKNOWN"
                                  : pool.live_connections() > 0 ? "UP" : "DOWN";
    const std::string redis_status = redis.connected() ? "UP" : "DOWN";
    const std::string kafka_status = kafka.started() ? "UP" : "DOWN";
    const std::string es_status = cm::service::es_health_status(); // UP/DOWN/UNKNOWN

    bool degraded = db_status == "DOWN" || redis_status == "DOWN" || kafka_status == "DOWN" ||
                    es_status == "DOWN";
    cm::Json j = cm::Json::object();
    j["status"] = degraded ? "DEGRADED" : "UP";
    cm::Json components = cm::Json::object();
    cm::Json cdb = cm::Json::object();
    cdb["status"] = db_status;
    cdb["liveConnections"] = pool.live_connections();
    components["database"] = cdb;
    cm::Json credis = cm::Json::object();
    credis["status"] = redis_status;
    components["redis"] = credis;
    cm::Json ckafka = cm::Json::object();
    ckafka["status"] = kafka_status;
    components["kafka"] = ckafka;
    cm::Json ces = cm::Json::object();
    ces["status"] = es_status;
    components["elasticsearch"] = ces;
    j["components"] = components;
    return http::Response::ok(j);
  });
  // 运行指标（本工程新增端点）：默认 JSON；?format=prometheus 返回 Prometheus 文本。
  router.add("GET", "/metrics", [](http::Request& req) {
    auto snapshot = cm::http::metrics_snapshot();
    if (req.str("format") == "prometheus")
      return http::Response::raw(200, prometheus_metrics(snapshot),
                                 "text/plain; version=0.0.4; charset=utf-8");
    return http::Response::ok(snapshot);
  });
  handler::register_base(router);
  handler::register_sysutil(router);
  handler::register_systest(router);
  handler::register_optimization(router);
  return router;
}

void start_schedulers() { handler::start_schedulers(); }
void stop_schedulers() { handler::stop_schedulers(); }

} // namespace cm::router
