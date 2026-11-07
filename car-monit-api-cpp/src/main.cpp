// car-monit-api 的 C++ 实现入口，对应 Java 的 EcBusinessApiApplication
// + SpringApplication.run：加载配置 -> 初始化连接池 -> 注册路由 -> 启动调度器。
#include "config/config.h"
#include "cache/redis.h"
#include "db/auth_guard.h"
#include "db/pg.h"
#include "common/logging.h"
#include "http/server.h"
#include "mq/kafka_producer.h"
#include "service/snapshot_flow_sync.h"

#include "router/routes.h"

#include <iostream>

int main(int argc, char** argv) {
  std::string config_path = "configs/config.yaml";
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if ((arg == "-c" || arg == "--config") && i + 1 < argc) config_path = argv[++i];
  }

  cm::log::set_level(cm::log::Level::Info);
  cm::log::set_file("logs/car-monit-api.log");

  auto& cfg = cm::config::Config::instance();
  cfg.load(config_path);
  cfg.apply_env_overrides();

  // 凭据守卫：口令未解析/为空/仍是 ${...} 占位时直接退出。
  // 这里刻意放在任何网络动作（DB/Redis/Kafka）之前，避免一次空口令连接变成
  // 真实失败登录，进而触发 openGauss 的 failed_login_attempts 把账号锁死。
  auto credential = cm::db::check_password(cfg.pg().password);
  if (!credential.ok) {
    CM_LOG_ERROR("main") << "数据库凭据校验未通过：" << credential.problem;
    CM_LOG_ERROR("main") << "请设置环境变量 CM_PG_PASSWORD，或把口令写入 "
                            << cfg.local_override_path() << "（该文件已被 .gitignore 忽略）";
    CM_LOG_ERROR("main") << "为避免失败登录触发账号锁定，进程已退出：未发起任何数据库连接";
    std::cerr << "数据库凭据未配置，进程已退出（详见 logs/car-monit-api.log）" << std::endl;
    return 1;
  }
  // 认证失败后默认不再重建连接（0 = 关闭自动重连）。
  cm::db::AuthGuard::instance().set_max_attempts_after_failure(
      cfg.pg().reconnect_after_auth_failure);

  CM_LOG_INFO("main") << "启动 car-monit-api (C++)，端口 " << cfg.server_port();

  // 数据库连接池（Druid 等价物）。连接失败不阻断启动：Java 侧 Druid 也是懒加载，
  // 首次请求时才建立物理连接。
  cm::db::PgPool::instance().init(cfg.pg().host, cfg.pg().port, cfg.pg().user, cfg.pg().password,
                                  cfg.pg().database, cfg.pg().max_conns, cfg.pg().min_idle,
                                  cfg.pg().connect_timeout_ms, cfg.pg().auth_mode);
  try {
    auto& pool = cm::db::PgPool::instance();
    pool.query("SELECT 1");
    CM_LOG_INFO("main") << "数据库连接成功: " << cfg.pg().host << ":" << cfg.pg().port << "/"
                        << cfg.pg().database;
  } catch (const std::exception& e) {
    CM_LOG_WARN("main") << "数据库连接失败（启动继续，请求时重试）: " << e.what();
  }

  if (cm::cache::Redis::instance().connect(cfg.redis().host, cfg.redis().port,
                                           cfg.redis().password, cfg.redis().database,
                                           cfg.redis().timeout_ms)) {
    CM_LOG_INFO("main") << "Redis 连接成功: " << cfg.redis().host << ":" << cfg.redis().port;
  } else {
    CM_LOG_WARN("main") << "Redis 连接失败，缓存相关功能将按 Java 侧降级语义处理";
  }

  // Kafka 生产者（KafkaTemplate 等价物）。broker 不可达不会阻断启动：
  // librdkafka 在首次发送时才建立连接，失败通过 delivery 回调进入重试/死信。
  if (cfg.kafka.enabled) {
    if (cm::mq::KafkaProducer::instance().start()) {
      CM_LOG_INFO("main") << "Kafka 生产者已启动: " << cfg.kafka.bootstrap_servers;
    } else {
      CM_LOG_WARN("main") << "Kafka 生产者启动失败（继续启动）: "
                          << cm::mq::KafkaProducer::instance().last_error();
    }
  } else {
    CM_LOG_WARN("main") << "Kafka 已关闭（kafka.enabled=false），MQ 走 Redis 降级路径";
  }

  auto router = cm::router::build_routes();
  cm::router::start_schedulers();

  // SnapshotFlowSyncService 等价物：对应 Java @PostConstruct 里的全量/增量推送线程。
  // 只在后台线程运行，DB/Kafka 不可达时不会阻塞启动。
  cm::service::start_snapshot_flow_sync();

  int rc = cm::http::run_server(cfg.server_port(), router, 16);
  cm::mq::KafkaProducer::instance().stop();
  return rc;

}
