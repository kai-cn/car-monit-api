#pragma once
// application.yml 的等价配置读取。
//
// Java 侧通过 @Value / @ConfigurationProperties / yml 层级注入配置。C++ 侧没有
// 依赖注入容器，改由单例 Config 在启动时解析 config.yaml（结构、键名与
// application.yml 完全一致，另支持环境变量覆盖，便于容器化部署）。
//
// YAML 解析器只实现本项目用到的子集：缩进嵌套 + 标量（字符串/数字/布尔），
// 足够覆盖 application.yml 中所有键（不含锚点/多行块/数组）。
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace cm::config {

class Yaml {
public:
  static Yaml parse(const std::string& text);

  bool has(const std::string& dotted) const;
  std::optional<std::string> get(const std::string& dotted) const;
  std::string get_str(const std::string& dotted, const std::string& def) const;
  int get_int(const std::string& dotted, int def) const;
  long long get_long(const std::string& dotted, long long def) const;
  double get_double(const std::string& dotted, double def) const;
  bool get_bool(const std::string& dotted, bool def) const;
  void set(const std::string& dotted, const std::string& value);
  const std::map<std::string, std::string>& flat() const { return flat_; }

private:
  std::map<std::string, std::string> flat_;
};

struct PgOptions {
  std::string host = "127.0.0.1";
  int port = 5432;
  std::string user = "gaussdb";
  std::string password;
  std::string database = "RuoYi";
  int max_conns = 20;
  int min_idle = 5;
  int connect_timeout_ms = 10000;
  // 认证失败后允许连接池重建连接的次数；默认 0 = 关闭自动重连（熔断）。
  int reconnect_after_auth_failure = 0;
  // auto / md5 / opengauss-sha256 / scram-sha-256，对应 openGauss password_encryption_type
  std::string auth_mode = "auto";
};

struct RedisOptions {
  std::string host = "127.0.0.1";
  int port = 6379;
  std::string password;
  int database = 0;
  int timeout_ms = 3000;
};

struct EsOptions {
  std::string scheme = "http";
  std::string host = "localhost";
  int port = 9200;
  std::string username = "elastic";
  std::string password = "changeme";
  int connection_timeout_ms = 30000;
  int socket_timeout_ms = 30000;
};

class Config {
public:
  static Config& instance();

  bool load(const std::string& path);
  void apply_env_overrides();
  // 本地覆盖配置路径（config.yaml 同目录下的 config.local.yaml，已 gitignore）。
  const std::string& local_override_path() const { return local_override_path_; }

  int server_port() const { return server_port_; }
  std::string context_path() const { return context_path_; }

  const PgOptions& pg() const { return pg_; }
  void set_pg(const PgOptions& o) { pg_ = o; }
  const RedisOptions& redis() const { return redis_; }
  const EsOptions& es() const { return es_; }

  const Yaml& yaml() const { return yaml_; }
  std::string yml(const std::string& key, const std::string& def) const;

  // ---- 业务配置（application.yml 中的自定义段落） ----
  struct Optimization {
    int query_timeout_ms = 30000;
    int max_window = 10000;
    int es_force_days = 30;
    int export_scroll_batch = 2000;
    int export_file_batch = 100000;
    std::string export_dir = "/data/export";
    int scroll_keepalive_min = 5;
  } optimization;

  struct Mq {
    std::string snapshot_flow_topic = "topic_snapshot_flow";
    std::string dlx_exchange = "exchange.snapshot.flow.dlx";
    std::string dlx_queue = "queue.snapshot.flow.dlx";
    std::string dlx_routing_key = "snapshot.flow.dlx";
    std::string bootstrap_servers = "localhost:9092";
  } mq;

  struct Sync {
    int batch_size = 1000;
    bool full_sync_enabled = true;
    int incremental_sync_interval = 60000;
  } sync;

  struct Consistency {
    bool reconcile_enabled = false;
    int lookback_months = 3;
    double drift_ratio = 0.01;
    std::string cron = "0 30 2 * * ?";
  } consistency;

  struct Reliability {
    int message_timeout_ms = 30000;
    int max_retry_count = 5;
    int compensation_interval_seconds = 60;
    int alert_threshold_ms = 10000;
  } reliability;

  struct Detection {
    int window_size_minutes = 60;
    int interval_minutes = 30;
    int loss_threshold_percent = 5;
  } detection;

  struct Monitoring {
    int device_report_threshold_ms = 5000;
    int message_transfer_threshold_ms = 3000;
    int data_process_threshold_ms = 10000;
    int end_to_end_threshold_ms = 30000;
    int stats_window_minutes = 10;
  } monitoring;

  struct PulsarCfg {
    std::string service_url = "pulsar://localhost:6650";
    std::string topic = "persistent://public/default/ods-rt-szdn-snapshot-flow";
    std::string producer_name = "car-monit-producer";
    std::string subscription_name = "ods-rt-szdn-snapshot-flow-sub";
    int send_timeout_ms = 30000;
    int batch_max_messages = 1000;
    int batch_max_publish_delay_ms = 10;
    int max_pending_messages = 10000;
    int receiver_queue_size = 1000;
    int ack_timeout_ms = 60000;
    int max_retry_times = 3;
    int idempotent_ttl_seconds = 86400;
    int max_retry_count = 10;
  } pulsar;

  struct KafkaCfg {
    // true = 使用 librdkafka 发送真实 Kafka 消息；false = 退回 Redis 队列。
    bool enabled = true;
    // 可选降级路径：把消息写入 Redis 列表 mq:pending:<topic>（默认关闭）。
    bool fallback_redis = false;
    std::string bootstrap_servers = "localhost:9092";
    std::string client_id = "car-monit-api";
    std::string snapshot_flow_topic = "ods-rt-szdn-snapshot-flow";
    std::string acks = "all";
    long long retries = 2147483647;
    bool enable_idempotence = true;
    int max_in_flight = 5;
    int batch_size = 16384;
    int linger_ms = 10;
    long long buffer_memory = 33554432;
    std::string compression_type = "lz4";
    int delivery_timeout_ms = 120000;
    int request_timeout_ms = 30000;
    int max_retry_count = 10;
    int retry_interval_ms = 30000;
    int retry_error_interval_ms = 60000;
  } kafka;

  // Spring MVC / CorsFilter 的等价配置。Java 源码没有 CORS 配置，这里按 Spring
  // CorsConfiguration.applyPermitDefaultValues() 的默认值实现（可被配置覆盖）。
  struct CorsCfg {
    bool enabled = true;
    std::string path = "/**";
    std::vector<std::string> allowed_origins{"*"};
    std::vector<std::string> allowed_origin_patterns;
    std::vector<std::string> allowed_methods{"GET", "HEAD", "POST"};
    std::vector<std::string> allowed_headers{"*"};
    std::vector<std::string> exposed_headers;
    bool allow_credentials = false;
    long long max_age = 1800;
  } cors;


  std::string is_localhost = "local";
  std::string sysbase_url = "http://223.84.150.189:26066/prod-api";
  std::string rediscluster_nodes = "36.200.31.15:22400";
  int rediscluster_refresh_ms = 300000;

private:
  Config() = default;
  void refresh_business();

  Yaml yaml_;
  std::string local_override_path_;
  int server_port_ = 9901;
  std::string context_path_ = "/";
  PgOptions pg_;
  RedisOptions redis_;
  EsOptions es_;
};

} // namespace cm::config
