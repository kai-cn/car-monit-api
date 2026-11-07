#include "router/routes.h"

#include "cache/redis.h"
#include "common/logging.h"
#include "db/pg.h"
#include "handler/handlers.h"
#include "http/server.h"
#include "mq/kafka_producer.h"
#include "service/optimization.h"

namespace cm::router {

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
  // 运行指标（本工程新增端点）：请求计数 / 错误计数 / 在途数 / 平均时延。
  router.add("GET", "/metrics", [](http::Request&) {
    return http::Response::ok(cm::http::metrics_snapshot());
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
