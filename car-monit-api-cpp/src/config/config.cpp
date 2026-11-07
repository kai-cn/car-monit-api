#include "config/config.h"

#include "common/logging.h"
#include "common/utils.h"

#include <cstdlib>
#include <fstream>
#include <sstream>

namespace cm::config {
namespace {

std::string strip_comment(const std::string& line) {
  // YAML 注释：行内 # 前必须有空白；本项目配置里值不含 #，按首次出现截断即可。
  bool in_quote = false;
  for (std::size_t i = 0; i < line.size(); ++i) {
    char c = line[i];
    if (c == '"' || c == '\'') in_quote = !in_quote;
    if (c == '#' && !in_quote && (i == 0 || line[i - 1] == ' ' || line[i - 1] == '\t'))
      return line.substr(0, i);
  }
  return line;
}

std::string trim_str(const std::string& s) {
  std::size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  std::size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}

std::string unquote(const std::string& s) {
  if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') ||
                        (s.front() == '\'' && s.back() == '\'')))
    return s.substr(1, s.size() - 2);
  return s;
}

// ${ENV_NAME} / ${ENV_NAME:-default} 展开。
// 用于把 configs/config.yaml 中的口令等敏感值改为环境变量占位，
// 避免明文写进仓库。
std::string expand_env(const std::string& s) {
  if (s.find("${") == std::string::npos) return s;
  std::string out;
  std::size_t i = 0;
  while (i < s.size()) {
    if (s[i] == '$' && i + 1 < s.size() && s[i + 1] == '{') {
      std::size_t end = s.find('}', i + 2);
      if (end != std::string::npos) {
        std::string name = s.substr(i + 2, end - i - 2);
        std::string def;
        std::size_t sep = name.find(":-");
        if (sep != std::string::npos) {
          def = name.substr(sep + 2);
          name = name.substr(0, sep);
        }
        const char* v = std::getenv(name.c_str());
        if (v && *v) {
          out += v;
        } else if (!def.empty()) {
          out += def;
        } else {
          // 保留原占位，让启动校验能识别“未展开的 ${...}”，而不是退化成空口令去连接。
          out += "${" + name + "}";
        }
        i = end + 1;
        continue;
      }
    }
    out.push_back(s[i++]);
  }
  return out;
}

} // namespace

Yaml Yaml::parse(const std::string& text) {
  Yaml y;
  std::vector<std::pair<int, std::string>> stack; // (indent, key)
  std::istringstream in(text);
  std::string raw;
  while (std::getline(in, raw)) {
    std::string line = strip_comment(raw);
    if (trim_str(line).empty()) continue;
    int indent = 0;
    while (indent < int(line.size()) && line[std::size_t(indent)] == ' ') ++indent;
    std::size_t pos = line.find(':', std::size_t(indent));
    if (pos == std::string::npos) continue;
    std::string key = trim_str(line.substr(std::size_t(indent), pos - std::size_t(indent)));
    std::string value = trim_str(line.substr(pos + 1));
    while (!stack.empty() && stack.back().first >= indent) stack.pop_back();
    std::string full;
    for (const auto& kv : stack) {
      if (!full.empty()) full += ".";
      full += kv.second;
    }
    if (!full.empty()) full += ".";
    full += key;
    if (value.empty()) {
      stack.emplace_back(indent, key);
    } else {
      y.flat_[full] = expand_env(unquote(value));
    }
  }
  return y;
}

bool Yaml::has(const std::string& dotted) const { return flat_.count(dotted) > 0; }

std::optional<std::string> Yaml::get(const std::string& dotted) const {
  auto it = flat_.find(dotted);
  if (it == flat_.end()) return std::nullopt;
  return it->second;
}

std::string Yaml::get_str(const std::string& dotted, const std::string& def) const {
  auto v = get(dotted);
  return v ? *v : def;
}

int Yaml::get_int(const std::string& dotted, int def) const {
  auto v = get(dotted);
  if (!v) return def;
  try { return std::stoi(*v); } catch (...) { return def; }
}

long long Yaml::get_long(const std::string& dotted, long long def) const {
  auto v = get(dotted);
  if (!v) return def;
  try { return std::stoll(*v); } catch (...) { return def; }
}

double Yaml::get_double(const std::string& dotted, double def) const {
  auto v = get(dotted);
  if (!v) return def;
  try { return std::stod(*v); } catch (...) { return def; }
}

bool Yaml::get_bool(const std::string& dotted, bool def) const {
  auto v = get(dotted);
  if (!v) return def;
  std::string s = utils::to_lower(*v);
  return s == "true" || s == "yes" || s == "on" || s == "1";
}

void Yaml::set(const std::string& dotted, const std::string& value) { flat_[dotted] = value; }

Config& Config::instance() {
  static Config cfg;
  return cfg;
}

bool Config::load(const std::string& path) {
  std::ifstream f(path);
  if (!f) {
    CM_LOG_WARN("config") << "配置文件不存在，使用内置默认值: " << path;
    refresh_business();
    return false;
  }
  std::stringstream ss;
  ss << f.rdbuf();
  yaml_ = Yaml::parse(ss.str());
  CM_LOG_INFO("config") << "已加载配置文件: " << path;

  // 本地覆盖配置：configs/config.local.yaml（同目录下的 config.local.yaml）。
  // 用于放真实口令等敏感值，已在 .gitignore 中忽略，不会入库。
  std::size_t slash = path.find_last_of("/\\");
  std::string dir = slash == std::string::npos ? "" : path.substr(0, slash + 1);
  local_override_path_ = dir + "config.local.yaml";
  std::ifstream local(local_override_path_);
  if (local) {
    std::stringstream lss;
    lss << local.rdbuf();
    Yaml overlay = Yaml::parse(lss.str());
    for (const auto& kv : overlay.flat()) yaml_.set(kv.first, kv.second);
    CM_LOG_INFO("config") << "已加载本地覆盖配置: " << local_override_path_;
  }

  refresh_business();
  return true;
}

void Config::refresh_business() {
  server_port_ = yaml_.get_int("server.port", 9901);
  context_path_ = yaml_.get_str("server.servlet.context-path", "/");

  std::string url = yaml_.get_str("spring.datasource.dynamic.datasource.master.url", "");
  if (!url.empty()) {
    // jdbc:postgresql://host:port/db?...
    std::string prefix = "jdbc:postgresql://";
    if (utils::starts_with(url, prefix)) {
      std::string rest = url.substr(prefix.size());
      std::size_t q = rest.find('?');
      if (q != std::string::npos) rest = rest.substr(0, q);
      std::size_t slash = rest.find('/');
      std::string hp = slash == std::string::npos ? rest : rest.substr(0, slash);
      if (slash != std::string::npos) pg_.database = rest.substr(slash + 1);
      std::size_t colon = hp.find(':');
      if (colon != std::string::npos) {
        pg_.host = hp.substr(0, colon);
        try { pg_.port = std::stoi(hp.substr(colon + 1)); } catch (...) {}
      } else {
        pg_.host = hp;
      }
    }
  }
  pg_.user = yaml_.get_str("spring.datasource.dynamic.datasource.master.username", pg_.user);
  pg_.password =
      yaml_.get_str("spring.datasource.dynamic.datasource.master.password", pg_.password);
  pg_.max_conns = yaml_.get_int("spring.datasource.dynamic.druid.maxActive", pg_.max_conns);
  pg_.min_idle = yaml_.get_int("spring.datasource.dynamic.druid.min-idle", pg_.min_idle);
  // Druid maxWait 是"借出连接的等待超时"；TCP 建连超时是另一个参数
  // （pgjdbc connectTimeout，默认 10s）。此前两者混用同一个值。
  pg_.max_wait_ms = yaml_.get_int("spring.datasource.dynamic.druid.maxWait", pg_.max_wait_ms);
  pg_.connect_timeout_ms = yaml_.get_int("spring.datasource.dynamic.druid.connect-timeout-ms",
                                         pg_.connect_timeout_ms);
  pg_.auth_mode =
      yaml_.get_str("spring.datasource.dynamic.datasource.master.auth-mode", pg_.auth_mode);
  pg_.reconnect_after_auth_failure = yaml_.get_int(
      "spring.datasource.dynamic.druid.reconnect-after-auth-failure",
      pg_.reconnect_after_auth_failure);

  redis_.host = yaml_.get_str("spring.redis.host", redis_.host);
  redis_.port = yaml_.get_int("spring.redis.port", redis_.port);
  redis_.password = yaml_.get_str("spring.redis.password", redis_.password);
  redis_.database = yaml_.get_int("spring.redis.database", redis_.database);

  es_.host = yaml_.get_str("elasticsearch.host", es_.host);
  es_.port = yaml_.get_int("elasticsearch.port", es_.port);
  es_.scheme = yaml_.get_str("elasticsearch.scheme", es_.scheme);
  es_.username = yaml_.get_str("elasticsearch.username", es_.username);
  es_.password = yaml_.get_str("elasticsearch.password", es_.password);
  es_.connection_timeout_ms =
      yaml_.get_int("elasticsearch.connection-timeout", es_.connection_timeout_ms);
  es_.socket_timeout_ms = yaml_.get_int("elasticsearch.socket-timeout", es_.socket_timeout_ms);

  optimization.query_timeout_ms =
      yaml_.get_int("optimization.query.timeout-ms", optimization.query_timeout_ms);
  optimization.max_window = yaml_.get_int("optimization.query.max-window", optimization.max_window);
  optimization.es_force_days =
      yaml_.get_int("optimization.query.es-force-days", optimization.es_force_days);
  optimization.export_scroll_batch =
      yaml_.get_int("optimization.export.scroll-batch", optimization.export_scroll_batch);
  optimization.export_file_batch =
      yaml_.get_int("optimization.export.file-batch", optimization.export_file_batch);
  optimization.export_dir = yaml_.get_str("optimization.export.dir", optimization.export_dir);
  optimization.scroll_keepalive_min = yaml_.get_int("optimization.export.scroll-keepalive-min",
                                                   optimization.scroll_keepalive_min);

  mq.snapshot_flow_topic = yaml_.get_str("mq.topic.snapshot-flow", mq.snapshot_flow_topic);
  mq.dlx_exchange = yaml_.get_str("mq.dead-letter.exchange", mq.dlx_exchange);
  mq.dlx_queue = yaml_.get_str("mq.dead-letter.queue", mq.dlx_queue);
  mq.dlx_routing_key = yaml_.get_str("mq.dead-letter.routing-key", mq.dlx_routing_key);
  mq.bootstrap_servers = yaml_.get_str("spring.kafka.bootstrap-servers", mq.bootstrap_servers);

  sync.batch_size = yaml_.get_int("sync.batch-size", sync.batch_size);
  sync.full_sync_enabled = yaml_.get_bool("sync.full-sync-enabled", sync.full_sync_enabled);
  sync.incremental_sync_interval =
      yaml_.get_int("sync.incremental-sync-interval", sync.incremental_sync_interval);

  consistency.reconcile_enabled =
      yaml_.get_bool("consistency.reconcile.enabled", consistency.reconcile_enabled);
  consistency.lookback_months =
      yaml_.get_int("consistency.reconcile.lookback-months", consistency.lookback_months);
  consistency.drift_ratio =
      yaml_.get_double("consistency.reconcile.drift-ratio", consistency.drift_ratio);
  consistency.cron = yaml_.get_str("consistency.reconcile.cron", consistency.cron);

  reliability.message_timeout_ms =
      yaml_.get_int("reliability.message-timeout-ms", reliability.message_timeout_ms);
  reliability.max_retry_count =
      yaml_.get_int("reliability.max-retry-count", reliability.max_retry_count);
  reliability.compensation_interval_seconds = yaml_.get_int(
      "reliability.compensation-interval-seconds", reliability.compensation_interval_seconds);
  reliability.alert_threshold_ms =
      yaml_.get_int("reliability.alert-threshold-ms", reliability.alert_threshold_ms);

  detection.window_size_minutes =
      yaml_.get_int("detection.window-size-minutes", detection.window_size_minutes);
  detection.interval_minutes =
      yaml_.get_int("detection.interval-minutes", detection.interval_minutes);
  detection.loss_threshold_percent =
      yaml_.get_int("detection.loss-threshold-percent", detection.loss_threshold_percent);

  monitoring.device_report_threshold_ms = yaml_.get_int(
      "monitoring.device-report-threshold-ms", monitoring.device_report_threshold_ms);
  monitoring.message_transfer_threshold_ms = yaml_.get_int(
      "monitoring.message-transfer-threshold-ms", monitoring.message_transfer_threshold_ms);
  monitoring.data_process_threshold_ms = yaml_.get_int(
      "monitoring.data-process-threshold-ms", monitoring.data_process_threshold_ms);
  monitoring.end_to_end_threshold_ms = yaml_.get_int(
      "monitoring.end-to-end-threshold-ms", monitoring.end_to_end_threshold_ms);
  monitoring.stats_window_minutes =
      yaml_.get_int("monitoring.stats-window-minutes", monitoring.stats_window_minutes);

  pulsar.service_url = yaml_.get_str("spring.pulsar.service-url", pulsar.service_url);
  pulsar.topic = yaml_.get_str("spring.pulsar.topic", pulsar.topic);
  pulsar.producer_name = yaml_.get_str("spring.pulsar.producer-name", pulsar.producer_name);
  pulsar.subscription_name =
      yaml_.get_str("spring.pulsar.subscription-name", pulsar.subscription_name);
  pulsar.send_timeout_ms = yaml_.get_int("spring.pulsar.send-timeout-ms", pulsar.send_timeout_ms);
  pulsar.batch_max_messages =
      yaml_.get_int("spring.pulsar.batch-max-messages", pulsar.batch_max_messages);
  pulsar.batch_max_publish_delay_ms = yaml_.get_int("spring.pulsar.batch-max-publish-delay-ms",
                                                    pulsar.batch_max_publish_delay_ms);
  pulsar.max_pending_messages =
      yaml_.get_int("spring.pulsar.max-pending-messages", pulsar.max_pending_messages);
  pulsar.receiver_queue_size =
      yaml_.get_int("spring.pulsar.receiver-queue-size", pulsar.receiver_queue_size);
  pulsar.ack_timeout_ms = yaml_.get_int("spring.pulsar.ack-timeout-ms", pulsar.ack_timeout_ms);
  pulsar.max_retry_times = yaml_.get_int("spring.pulsar.max-retry-times", pulsar.max_retry_times);
  pulsar.idempotent_ttl_seconds =
      yaml_.get_int("spring.pulsar.idempotent-ttl-seconds", pulsar.idempotent_ttl_seconds);
  pulsar.max_retry_count = yaml_.get_int("spring.pulsar.max-retry-count", pulsar.max_retry_count);

  kafka.snapshot_flow_topic =
      yaml_.get_str("kafka.topic.snapshot-flow", kafka.snapshot_flow_topic);
  kafka.enabled = yaml_.get_bool("kafka.enabled", kafka.enabled);
  kafka.fallback_redis = yaml_.get_bool("kafka.fallback-redis", kafka.fallback_redis);
  kafka.bootstrap_servers =
      yaml_.get_str("kafka.bootstrap-servers",
                    yaml_.get_str("spring.kafka.bootstrap-servers", kafka.bootstrap_servers));
  kafka.client_id = yaml_.get_str("kafka.client-id", kafka.client_id);
  kafka.acks = yaml_.get_str("kafka.acks", kafka.acks);
  kafka.retries = yaml_.get_long("kafka.retries", kafka.retries);
  kafka.enable_idempotence =
      yaml_.get_bool("kafka.enable-idempotence", kafka.enable_idempotence);
  kafka.max_in_flight = yaml_.get_int("kafka.max-in-flight", kafka.max_in_flight);
  kafka.batch_size = yaml_.get_int("kafka.batch-size", kafka.batch_size);
  kafka.linger_ms = yaml_.get_int("kafka.linger-ms", kafka.linger_ms);
  kafka.buffer_memory = yaml_.get_long("kafka.buffer-memory", kafka.buffer_memory);
  kafka.compression_type = yaml_.get_str("kafka.compression-type", kafka.compression_type);
  kafka.delivery_timeout_ms =
      yaml_.get_int("kafka.delivery-timeout-ms", kafka.delivery_timeout_ms);
  kafka.request_timeout_ms = yaml_.get_int("kafka.request-timeout-ms", kafka.request_timeout_ms);
  kafka.max_retry_count = yaml_.get_int("kafka.max-retry-count", kafka.max_retry_count);
  kafka.retry_interval_ms = yaml_.get_int("kafka.retry-interval-ms", kafka.retry_interval_ms);
  kafka.retry_error_interval_ms =
      yaml_.get_int("kafka.retry-error-interval-ms", kafka.retry_error_interval_ms);

  cors.enabled = yaml_.get_bool("cors.enabled", cors.enabled);
  cors.path = yaml_.get_str("cors.path", cors.path);
  if (auto v = yaml_.get("cors.allowed-origins")) cors.allowed_origins = utils::split_csv(*v);
  if (auto v = yaml_.get("cors.allowed-origin-patterns"))
    cors.allowed_origin_patterns = utils::split_csv(*v);
  if (auto v = yaml_.get("cors.allowed-methods")) cors.allowed_methods = utils::split_csv(*v);
  if (auto v = yaml_.get("cors.allowed-headers")) cors.allowed_headers = utils::split_csv(*v);
  if (auto v = yaml_.get("cors.exposed-headers")) cors.exposed_headers = utils::split_csv(*v);
  cors.allow_credentials = yaml_.get_bool("cors.allow-credentials", cors.allow_credentials);
  cors.max_age = yaml_.get_long("cors.max-age", cors.max_age);


  is_localhost = yaml_.get_str("isLocalhost", is_localhost);
  sysbase_url = yaml_.get_str("sysbaseUrl", sysbase_url);
  rediscluster_nodes = yaml_.get_str("rediscluster.clusterNodes", rediscluster_nodes);
  rediscluster_refresh_ms =
      yaml_.get_int("rediscluster.refresh-interval-ms", rediscluster_refresh_ms);
}

void Config::apply_env_overrides() {
  auto env = [](const char* name) -> std::optional<std::string> {
    const char* v = std::getenv(name);
    if (!v || !*v) return std::nullopt;
    return std::string(v);
  };
  if (auto v = env("CM_SERVER_PORT")) server_port_ = std::stoi(*v);
  if (auto v = env("CM_PG_HOST")) pg_.host = *v;
  if (auto v = env("CM_PG_PORT")) pg_.port = std::stoi(*v);
  if (auto v = env("CM_PG_USER")) pg_.user = *v;
  if (auto v = env("CM_PG_PASSWORD")) pg_.password = *v;
  if (auto v = env("CM_PG_DATABASE")) pg_.database = *v;
  if (auto v = env("CM_PG_AUTH_MODE")) pg_.auth_mode = *v;
  if (auto v = env("CM_REDIS_HOST")) redis_.host = *v;
  if (auto v = env("CM_REDIS_PORT")) redis_.port = std::stoi(*v);
  if (auto v = env("CM_REDIS_PASSWORD")) redis_.password = *v;
  if (auto v = env("CM_ES_HOST")) es_.host = *v;
  if (auto v = env("CM_ES_PORT")) es_.port = std::stoi(*v);
  if (auto v = env("CM_KAFKA_ENABLED")) {
    std::string s = utils::to_lower(*v);
    kafka.enabled = !(s == "false" || s == "0" || s == "no" || s == "off");
  }
  if (auto v = env("CM_KAFKA_BOOTSTRAP")) kafka.bootstrap_servers = *v;
  if (auto v = env("CM_KAFKA_FALLBACK_REDIS")) {
    std::string s = utils::to_lower(*v);
    kafka.fallback_redis = s == "true" || s == "1" || s == "yes" || s == "on";
  }
  if (auto v = env("CM_CORS_ENABLED")) {
    std::string s = utils::to_lower(*v);
    cors.enabled = !(s == "false" || s == "0" || s == "no" || s == "off");
  }
  if (auto v = env("CM_CORS_ALLOWED_ORIGINS")) cors.allowed_origins = utils::split_csv(*v);
  if (auto v = env("CM_CORS_ALLOW_CREDENTIALS")) {
    std::string s = utils::to_lower(*v);
    cors.allow_credentials = s == "true" || s == "1" || s == "yes" || s == "on";
  }

  if (auto v = env("CM_LOG_LEVEL")) {
    std::string s = utils::to_lower(*v);
    if (s == "debug") log::set_level(log::Level::Debug);
    else if (s == "warn") log::set_level(log::Level::Warn);
    else if (s == "error") log::set_level(log::Level::Error);
    else log::set_level(log::Level::Info);
  }
}

std::string Config::yml(const std::string& key, const std::string& def) const {
  return yaml_.get_str(key, def);
}

} // namespace cm::config
