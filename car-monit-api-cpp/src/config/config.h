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
  // TCP 建连 + 认证的超时（pgjdbc connectTimeout 默认 10s）。
  int connect_timeout_ms = 10000;
  // 借出连接的等待超时（Druid maxWait，默认 60s）。此前误把 maxWait 当
  // connect 超时使用，两者语义不同，现分开配置。
  int max_wait_ms = 60000;
  // 认证失败后允许连接池重建连接的次数；默认 0 = 关闭自动重连（熔断）。
  int reconnect_after_auth_failure = 0;
  // libpq sslmode：disable / allow / prefer / require / verify-ca / verify-full。
  // 默认 prefer 与 libpq 一致；生产建议 require，内网可 verify-full。
  std::string sslmode = "prefer";
  // verify-ca / verify-full 的 CA 路径；为空使用系统默认 CA。
  std::string sslrootcert;
  // 语句超时（毫秒；0 = 不设置），防止单条慢 SQL 长期占用连接。
  int statement_timeout_ms = 30000;
};

// HTTP 服务安全选项（审阅 §5.1 #6）。鉴权与限流是**新增能力**：Java 的
// SecurityInterceptor 在 WebConfig.java 中被整体注释（生产无鉴权），为保持
// 行为一致两者默认关闭；请求体上限与读写超时为安全收紧（原 64MB 无超时）。
struct ServerSecurityOptions {
  // 鉴权：开启后校验 X-API-Key / Authorization: Bearer <key>（401 拒绝）。
  // api_key 为空时 fail-closed（全部 401）。/health 与 CORS 预检豁免。
  bool auth_enabled = false;
  std::string api_key;
  // 限流：按客户端 IP 的固定窗口（429 拒绝）。0 或负数视为全部拒绝。
  bool rate_limit_enabled = false;
  int requests_per_minute = 600;
  // 请求体上限（默认 1MB；原实现 64MB，DoS 面）。
  long long max_payload_bytes = 1LL * 1024 * 1024;
  // 读写超时（毫秒；原实现无超时，慢客户端可占满线程）。
  int read_timeout_ms = 30000;
  int write_timeout_ms = 30000;
};

struct RedisOptions {
  std::string host = "127.0.0.1";
  int port = 6379;
  std::string password;
  int database = 0;
  int timeout_ms = 3000;
  // TLS：默认关闭，与 Java 侧（未配置 SSL）保持一致。开启后使用 hiredis_ssl。
  bool tls = false;
  std::string tls_cacert; // 为空则使用系统默认 CA
  std::string tls_cert;   // 客户端证书（与 tls_key 成对）
  std::string tls_key;
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

  const ServerSecurityOptions& server_security() const { return server_security_; }
  // 日志轮转：logging.max-file-mb（默认 50，0=不轮转）/ logging.max-files（默认 5）。
  int log_max_file_mb() const { return log_max_file_mb_; }
  int log_max_files() const { return log_max_files_; }
  // 结构化日志（JSON）开关：logging.json。
  bool log_json() const { return log_json_; }
  // 优雅停机超时（毫秒）：超过该时间仍有在途请求则强制退出。
  int shutdown_timeout_ms() const { return shutdown_timeout_ms_; }
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

  // 多实例单活：启动时抢 Redis 分布式锁，只有 leader 执行调度与全量/增量同步。
  // Redis 不可用时的行为由 fail_open 决定（默认 fail-closed：暂停调度，HTTP 继续服务）。
  struct Cluster {
    bool leader_election_enabled = true;
    std::string leader_lock_key = "car-monit:leader";
    int leader_ttl_ms = 30000;
    int leader_renew_ms = 10000;
    bool leader_fail_open = false;
  } cluster;

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
  ServerSecurityOptions server_security_;
  int log_max_file_mb_ = 50;
  int log_max_files_ = 5;
  bool log_json_ = false;
  int shutdown_timeout_ms_ = 30000;
  std::string context_path_ = "/";
  PgOptions pg_;
  RedisOptions redis_;
  EsOptions es_;
};

} // namespace cm::config
