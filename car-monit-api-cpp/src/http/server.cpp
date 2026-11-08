#include "http/server.h"

#include "cache/redis.h"
#include "common/datetime.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "common/worker_pool.h"
#include "config/config.h"
#include "db/pg.h"
#include "http/cors.h"
#include "mq/kafka_producer.h"
#include "service/optimization.h"

#include "httplib.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdlib>
#include <mutex>
#include <sstream>

namespace cm::http {
namespace {

// 进程级 IP 限流器（server.rate-limit.enabled 开启时使用）。
// 放在文件作用域：static 局部变量不能被 lambda 简单捕获（C3495）。
RateLimiter g_rate_limiter;

// 运行期指标（审阅 §5.1 #10）：请求计数 / 错误计数 / 在途数 / 时延直方图。
std::atomic<long long> g_requests_total{0};
std::atomic<long long> g_errors_total{0};
std::atomic<long long> g_in_flight{0};
std::atomic<long long> g_total_latency_ms{0};
std::atomic<long long> g_max_latency_ms{0};
std::atomic<long long> g_status_2xx{0};
std::atomic<long long> g_status_4xx{0};
std::atomic<long long> g_status_5xx{0};
// 时延分位（近似）：累积桶计数，边界单位毫秒。最后一桶是溢出桶（>10000ms）。
constexpr std::size_t kLatencyBuckets = 11;
const long long kLatencyBounds[kLatencyBuckets] = {1,   5,   10,  25,  50,  100,
                                                   250, 500, 1000, 2500, 5000};
std::atomic<long long> g_latency_buckets[kLatencyBuckets] = {};
std::atomic<long long> g_latency_overflow{0};
// 优雅停机：信号处理器只置位（async-signal-safe），监视线程负责调 svr.stop()。
std::atomic<bool> g_shutdown_requested{false};

void record_latency(long long ms) {
  g_total_latency_ms.fetch_add(ms);
  long long prev = g_max_latency_ms.load();
  while (ms > prev && !g_max_latency_ms.compare_exchange_weak(prev, ms)) {
  }
  for (std::size_t i = 0; i < kLatencyBuckets; ++i) {
    if (ms <= kLatencyBounds[i]) {
      g_latency_buckets[i].fetch_add(1);
      return;
    }
  }
  g_latency_overflow.fetch_add(1);
}

long long percentile_ms(double p, long long total) {
  if (total <= 0) return 0;
  const long long target = static_cast<long long>(std::ceil(p * static_cast<double>(total)));
  long long cumulative = 0;
  for (std::size_t i = 0; i < kLatencyBuckets; ++i) {
    cumulative += g_latency_buckets[i].load();
    if (cumulative >= target) return kLatencyBounds[i];
  }
  if (g_latency_overflow.load() > 0) return g_max_latency_ms.load();
  return g_max_latency_ms.load();
}

// 依赖探活（5s 缓存）：DB/Redis 只在已有连接上做轻量探测，绝不新建连接
// （避免 /metrics 被频繁抓取时变成反复登录/建连）。ES 为被动状态（不主动请求）。
Json probe_dependencies() {
  static std::mutex mu;
  static Json cached = Json::object();
  static long long cached_at = 0;
  const long long now = std::chrono::duration_cast<std::chrono::milliseconds>(
                            std::chrono::steady_clock::now().time_since_epoch())
                            .count();
  std::lock_guard<std::mutex> lock(mu);
  if (now - cached_at < 5000 && !cached.empty()) return cached;

  Json deps = Json::object();
  auto elapsed = [](std::chrono::steady_clock::time_point t0) {
    return static_cast<long long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - t0)
            .count());
  };

  // DB
  Json db = Json::object();
  auto& pool = cm::db::PgPool::instance();
  db["liveConnections"] = pool.live_connections();
  db["maxConnections"] = pool.max_connections();
  if (!pool.available()) {
    db["status"] = "UNKNOWN";
    db["latencyMs"] = 0;
  } else if (pool.live_connections() > 0) {
    const auto t0 = std::chrono::steady_clock::now();
    try {
      pool.query("SELECT 1");
      db["status"] = "UP";
    } catch (...) {
      db["status"] = "DOWN";
    }
    db["latencyMs"] = elapsed(t0);
  } else {
    // 有池但当前无物理连接：只报告 DOWN/UNKNOWN，不主动建连。
    db["status"] = "DOWN";
    db["latencyMs"] = 0;
  }
  deps["db"] = db;

  // Redis
  Json redis = Json::object();
  auto& rc = cm::cache::Redis::instance();
  if (rc.connected()) {
    const auto t0 = std::chrono::steady_clock::now();
    try {
      auto v = rc.cmd({"PING"});
      redis["status"] = (v && !v->empty()) ? "UP" : "DOWN";
    } catch (...) {
      redis["status"] = "DOWN";
    }
    redis["latencyMs"] = elapsed(t0);
  } else {
    redis["status"] = "DOWN";
    redis["latencyMs"] = 0;
  }
  deps["redis"] = redis;

  // ES（被动状态：不主动发起 HTTP 探测，避免慢请求拖垮 /metrics）
  Json es = Json::object();
  es["status"] = cm::service::es_health_status();
  es["latencyMs"] = 0;
  deps["es"] = es;

  // Kafka（生产者是否已启动；无同步探测接口，延迟不适用）
  Json kafka = Json::object();
  kafka["status"] = cm::mq::KafkaProducer::instance().started() ? "UP" : "DOWN";
  kafka["latencyMs"] = 0;
  deps["kafka"] = kafka;

  Json worker_pool = Json::object();
  worker_pool["pending"] = cm::background_pool().pending();
  worker_pool["active"] = cm::background_pool().active();
  worker_pool["capacity"] = cm::background_pool().capacity();
  deps["workerPool"] = worker_pool;

  cached = deps;
  cached_at = now;
  return deps;
}

} // namespace

Json metrics_snapshot() {
  Json j = Json::object();
  const long long total = g_requests_total.load();
  const long long latency = g_total_latency_ms.load();
  const long long errors = g_errors_total.load();
  j["requestsTotal"] = total;
  j["errorsTotal"] = errors;
  j["errorRate"] = total > 0 ? static_cast<double>(errors) / static_cast<double>(total) : 0.0;
  j["inFlight"] = g_in_flight.load();
  j["avgLatencyMs"] = total > 0 ? (latency / total) : 0;
  j["maxLatencyMs"] = g_max_latency_ms.load();
  j["p50LatencyMs"] = percentile_ms(0.50, total);
  j["p95LatencyMs"] = percentile_ms(0.95, total);
  j["p99LatencyMs"] = percentile_ms(0.99, total);
  j["status2xx"] = g_status_2xx.load();
  j["status4xx"] = g_status_4xx.load();
  j["status5xx"] = g_status_5xx.load();
  j["uptimeSeconds"] = std::chrono::duration_cast<std::chrono::seconds>(
                           std::chrono::steady_clock::now().time_since_epoch())
                           .count();
  j["dependencies"] = probe_dependencies();
  return j;
}

namespace {

std::vector<std::string> split_path(const std::string& path) {
  std::vector<std::string> segs;
  std::size_t pos = 0;
  while (pos < path.size()) {
    if (path[pos] == '/') {
      ++pos;
      continue;
    }
    std::size_t slash = path.find('/', pos);
    segs.push_back(path.substr(pos, slash == std::string::npos ? std::string::npos : slash - pos));
    if (slash == std::string::npos) break;
    pos = slash + 1;
  }
  return segs;
}

std::map<std::string, std::vector<std::string>> parse_urlencoded(const std::string& body) {
  std::map<std::string, std::vector<std::string>> out;
  std::size_t pos = 0;
  while (pos < body.size()) {
    std::size_t amp = body.find('&', pos);
    std::string pair = body.substr(pos, amp == std::string::npos ? std::string::npos : amp - pos);
    std::size_t eq = pair.find('=');
    std::string k = utils::url_decode(eq == std::string::npos ? pair : pair.substr(0, eq));
    std::string v = eq == std::string::npos ? "" : utils::url_decode(pair.substr(eq + 1));
    if (!k.empty()) out[k].push_back(v);
    if (amp == std::string::npos) break;
    pos = amp + 1;
  }
  return out;
}

Response build_error_response(int status, const std::string& error, const std::string& message,
                              const std::string& path) {
  Response out;
  out.status = status;
  Json j = Json::object();
  j["timestamp"] = timeutil::format_timestamp(timeutil::now());
  j["status"] = status;
  j["error"] = error;
  j["message"] = message;
  j["path"] = path;
  out.json = j;
  return out;
}

} // namespace

void Router::add(const std::string& method, const std::string& pattern, Handler handler) {
  Route r;
  r.method = utils::to_upper(method);
  r.pattern = pattern;
  std::string full = pattern;
  if (prefix_ != "/" && utils::starts_with(full, "/")) full = prefix_ + full;
  std::size_t pos = 0;
  while (pos < full.size()) {
    if (full[pos] == '/') {
      ++pos;
      continue;
    }
    std::size_t slash = full.find('/', pos);
    r.segments.push_back(
        full.substr(pos, slash == std::string::npos ? std::string::npos : slash - pos));
    if (slash == std::string::npos) break;
    pos = slash + 1;
  }
  r.handler = std::move(handler);
  routes_.push_back(std::move(r));
}

void Router::merge(const Router& other) {
  routes_.insert(routes_.end(), other.routes_.begin(), other.routes_.end());
}

std::vector<std::pair<std::string, std::string>> Router::routes() const {
  std::vector<std::pair<std::string, std::string>> out;
  for (const auto& r : routes_) out.emplace_back(r.method, r.pattern);
  return out;
}

std::vector<std::string> Router::methods_for_path(const std::string& path) const {
  auto segs = split_path(path);
  std::vector<std::string> out;
  bool has_get = false;
  for (const auto& r : routes_) {
    if (r.segments.size() != segs.size()) continue;
    bool match = true;
    for (std::size_t i = 0; i < segs.size(); ++i) {
      const std::string& pat = r.segments[i];
      bool wildcard = !pat.empty() && pat.front() == '{' && pat.back() == '}';
      if (!wildcard && pat != segs[i]) {
        match = false;
        break;
      }
    }
    if (!match) continue;
    if (std::find(out.begin(), out.end(), r.method) == out.end()) out.push_back(r.method);
    if (r.method == "GET") has_get = true;
  }
  if (out.empty()) return out;
  // Spring 的 GET 隐式支持 HEAD，且 OPTIONS 始终可选。
  if (has_get) {
    auto it = std::find(out.begin(), out.end(), "GET");
    out.insert(it + 1, "HEAD");
  }
  out.push_back("OPTIONS");
  return out;
}

bool Router::dispatch(Request& req, Response& out) const {
  auto segs = split_path(req.path);
  const Route* best = nullptr;
  int best_wild = 1 << 30;
  for (const auto& r : routes_) {
    if (r.method != req.method) continue;
    if (r.segments.size() != segs.size()) continue;
    int wild = 0;
    bool match = true;
    for (std::size_t i = 0; i < segs.size(); ++i) {
      const std::string& pat = r.segments[i];
      if (!pat.empty() && pat.front() == '{' && pat.back() == '}') {
        ++wild;
      } else if (pat != segs[i]) {
        match = false;
        break;
      }
    }
    if (!match) continue;
    if (wild < best_wild) {
      best = &r;
      best_wild = wild;
    }
  }
  if (!best) return false;

  req.path_params.clear();
  for (std::size_t i = 0; i < best->segments.size(); ++i) {
    const std::string& pat = best->segments[i];
    if (!pat.empty() && pat.front() == '{' && pat.back() == '}')
      req.path_params[pat.substr(1, pat.size() - 2)] = segs[i];
  }
  out = best->handler(req);
  return true;
}

bool check_api_key(const Request& req, const std::string& api_key) {
  // fail-closed：开启鉴权但未配置密钥 = 全部拒绝。
  if (api_key.empty()) return false;
  auto it = req.headers_lower.find("x-api-key");
  if (it != req.headers_lower.end() && it->second == api_key) return true;
  auto authz = req.headers_lower.find("authorization");
  if (authz != req.headers_lower.end()) {
    const std::string prefix = "bearer ";
    if (authz->second.size() > prefix.size()) {
      std::string scheme = utils::to_lower(authz->second.substr(0, prefix.size()));
      if (scheme == prefix && authz->second.substr(prefix.size()) == api_key) return true;
    }
  }
  return false;
}

bool RateLimiter::allow(const std::string& ip, int limit_per_minute) {
  if (limit_per_minute <= 0) return false;
  const long long minute = std::chrono::duration_cast<std::chrono::minutes>(
                               std::chrono::system_clock::now().time_since_epoch())
                               .count();
  std::lock_guard<std::mutex> lock(mu_);
  auto it = windows_.find(ip);
  if (it == windows_.end() || it->second.first != minute) {
    // 容量保护：窗口表过大时清理过期项，防止长期运行无界增长。
    if (windows_.size() > 65536) {
      for (auto w = windows_.begin(); w != windows_.end();) {
        if (w->second.first != minute) {
          w = windows_.erase(w);
        } else {
          ++w;
        }
      }
    }
    windows_[ip] = {minute, 1};
    return true;
  }
  if (it->second.second >= limit_per_minute) return false;
  ++it->second.second;
  return true;
}

int run_server(int port, const Router& router, int /*thread_count*/, int shutdown_timeout_ms) {
  httplib::Server svr;
  const auto& sec = config::Config::instance().server_security();
  // 安全加固（审阅 §5.1 #6）：请求体上限（原 64MB）与读写超时（原无超时）。
  svr.set_payload_max_length(static_cast<size_t>(sec.max_payload_bytes > 0
                                                     ? sec.max_payload_bytes
                                                     : 1LL * 1024 * 1024));
  svr.set_read_timeout(std::chrono::milliseconds(sec.read_timeout_ms > 0 ? sec.read_timeout_ms
                                                                         : 30000));
  svr.set_write_timeout(std::chrono::milliseconds(sec.write_timeout_ms > 0 ? sec.write_timeout_ms
                                                                           : 30000));
  if (sec.auth_enabled) {
    if (sec.api_key.empty()) {
      CM_LOG_ERROR("http") << "server.auth.enabled=true 但未配置 server.auth.api-key："
                              "鉴权将以 fail-closed 方式拒绝全部请求";
    }
    CM_LOG_WARN("http") << "API-Key 鉴权已开启（X-API-Key / Authorization: Bearer；"
                           "/health 与 CORS 预检豁免）——新增能力，Java 生产实例无鉴权";
  }
  if (sec.rate_limit_enabled) {
    CM_LOG_WARN("http") << "IP 限流已开启：每分钟 " << sec.requests_per_minute
                        << " 次/客户端——新增能力，Java 生产实例无限流";
  }

  auto handler = [&router, &sec](const httplib::Request& raw, httplib::Response& res) {
    const auto t0 = std::chrono::steady_clock::now();
    // requestId 贯穿：优先复用上游 X-Request-Id，否则生成新值；响应头回写，
    // 日志（尤其 JSON 模式）自动携带该值。RAII 保证线程池复用线程时不串号。
    std::string request_id = raw.get_header_value("X-Request-Id");
    if (request_id.empty()) request_id = utils::uuid32();
    cm::log::RequestIdScope request_scope(request_id);
    g_in_flight.fetch_add(1);
    struct FlightGuard {
      ~FlightGuard() { g_in_flight.fetch_sub(1); }
    } flight_guard;
    Request req;
    req.method = raw.method;
    req.path = raw.path;
    for (const auto& kv : raw.params) req.params_all[kv.first].push_back(kv.second);
    std::string ctype = utils::to_lower(raw.get_header_value("Content-Type"));
    if (utils::contains(ctype, "application/x-www-form-urlencoded")) {
      auto form = parse_urlencoded(raw.body);
      for (auto& kv : form) req.params_all[kv.first].insert(req.params_all[kv.first].end(),
                                                           kv.second.begin(), kv.second.end());
    }
    for (const auto& kv : raw.headers) req.headers_lower[utils::to_lower(kv.first)] = kv.second;
    req.body = raw.body;
    req.remote_addr = raw.remote_addr;

    // CORS 先于业务路由/拦截器执行：预检请求直接返回 200/403，不进入业务逻辑。
    Response out;
    CorsDecision decision = apply_cors(config::Config::instance().cors, req, out);
    auto merge_headers = [](Response& dst, const Response& src) {
      for (const auto& kv : src.headers) {
        dst.headers[kv.first].insert(dst.headers[kv.first].end(), kv.second.begin(),
                                     kv.second.end());
      }
    };
    auto options_response = [&](const std::string& path) {
      Response r;
      auto methods = router.methods_for_path(path);
      if (methods.empty()) return build_error_response(404, "Not Found", "", path);
      r.status = 200;
      r.no_body = true;
      r.add_header("Allow", utils::join(methods, ","));
      return r;
    };

    switch (decision) {
      case CorsDecision::ConfigError: {
        auto r = build_error_response(
            500, "Internal Server Error",
            "When allowCredentials is true, allowedOrigins cannot contain the wildcard '*' since "
            "that cannot be set on the 'Access-Control-Allow-Origin' response header. To allow "
            "credentials to a set of origins, list them explicitly or consider using "
            "'allowedOriginPatterns' instead.",
            raw.path);
        merge_headers(r, out);
        out = std::move(r);
        break;
      }
      case CorsDecision::PreflightRejected: {
        out.status = 403;
        out.use_raw = true;
        out.raw_body = "Invalid CORS request";
        out.content_type = "text/plain;charset=ISO-8859-1";
        out.suppress_disposition = true;
        break;
      }
      case CorsDecision::PreflightAllowed: {
        out.status = 200;
        out.no_body = true;
        auto methods = router.methods_for_path(req.path);
        if (!methods.empty()) out.add_header("Allow", utils::join(methods, ","));
        break;
      }
      default: {
        Response routed;
        // 鉴权与限流（默认关闭；CORS 预检与 /health 探活豁免）。
        const bool exempt = req.method == "OPTIONS" || req.path == "/health";
        if (!exempt && sec.auth_enabled && !check_api_key(req, sec.api_key)) {
          routed = build_error_response(401, "Unauthorized", "Invalid or missing API key",
                                        raw.path);
          merge_headers(routed, out);
          out = std::move(routed);
          break;
        }
        if (!exempt && sec.rate_limit_enabled &&
            !g_rate_limiter.allow(req.remote_addr, sec.requests_per_minute)) {
          routed =
              build_error_response(429, "Too Many Requests", "Rate limit exceeded", raw.path);
          merge_headers(routed, out);
          out = std::move(routed);
          break;
        }
        if (req.method == "OPTIONS") {
          routed = options_response(req.path);
        } else {
          try {
            if (!router.dispatch(req, routed))
              routed = build_error_response(404, "Not Found", "", raw.path);
          } catch (const BizError& e) {
            routed.status = 200;
            routed.json = Json::object();
            routed.json["msg"] = e.message();
            routed.json["code"] = e.code();
          } catch (const BindError& e) {
            routed = build_error_response(e.status(), "Bad Request", e.reason(), raw.path);
          } catch (const DbError& e) {
            CM_LOG_ERROR("http") << "数据库错误 " << raw.method << " " << raw.path << ": "
                                 << e.message();
            routed = build_error_response(500, "Internal Server Error", e.message(), raw.path);
          } catch (const std::exception& e) {
            CM_LOG_ERROR("http") << "未处理异常 " << raw.method << " " << raw.path << ": "
                                 << e.what();
            routed = build_error_response(500, "Internal Server Error", e.what(), raw.path);
          }
        }
        merge_headers(routed, out);
        out = std::move(routed);
        break;
      }
    }

    res.status = out.status;
    if (!out.no_body) {
      res.set_content(out.use_raw ? out.raw_body : cm::json_dump(out.json), out.content_type);
      if (out.use_raw && !out.suppress_disposition)
        res.set_header("Content-Disposition", "attachment");
    }
    for (const auto& kv : out.headers) res.set_header(kv.first, utils::join(kv.second, ","));
    res.set_header("X-Request-Id", request_id);

    // 指标累计（审阅 §5.1 #10）。
    g_requests_total.fetch_add(1);
    if (out.status >= 500) g_errors_total.fetch_add(1);
    if (out.status >= 500)
      g_status_5xx.fetch_add(1);
    else if (out.status >= 400)
      g_status_4xx.fetch_add(1);
    else if (out.status >= 200 && out.status < 300)
      g_status_2xx.fetch_add(1);
    record_latency(std::chrono::duration_cast<std::chrono::milliseconds>(
                       std::chrono::steady_clock::now() - t0)
                       .count());
  };

  svr.Get(R"(.*)", handler);
  svr.Post(R"(.*)", handler);
  svr.Put(R"(.*)", handler);
  svr.Delete(R"(.*)", handler);
  svr.Options(R"(.*)", handler);

  // 优雅停机（审阅 §5.1 #11）：SIGINT/SIGTERM 只置位原子标志（async-signal-safe），
  // 监视线程检测到后调用 svr.stop() 停止接受新连接；run_server 返回后由 main
  // 依次回收调度器/同步线程/后台任务池/Kafka/连接池。
  g_shutdown_requested.store(false);
  std::signal(SIGINT, [](int) { g_shutdown_requested.store(true); });
  std::signal(SIGTERM, [](int) { g_shutdown_requested.store(true); });
  std::thread shutdown_watcher([&svr, shutdown_timeout_ms] {
    while (!g_shutdown_requested.load()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    CM_LOG_INFO("http") << "收到停机信号，停止接受新请求（在途请求最多等待 "
                        << shutdown_timeout_ms << "ms）";
    if (shutdown_timeout_ms > 0) {
      // 硬超时：httplib 的 stop() 会等待线程池任务排空；若慢请求超过该时限，
      // 强制退出（日志为逐行 flush，不会丢失已写内容）。
      // 硬超时看门线程：故意 detach——它必须在主线程被慢请求阻塞时仍能强制退出，
      // 因此不能由任何线程 join。
      std::thread([shutdown_timeout_ms] {
        std::this_thread::sleep_for(std::chrono::milliseconds(shutdown_timeout_ms));
        CM_LOG_WARN("http") << "优雅停机超时（" << shutdown_timeout_ms
                            << "ms），强制退出（在途请求未完成）";
        std::_Exit(1);
      }).detach();
    }
    svr.stop();
  });

  CM_LOG_INFO("http") << "HTTP 服务启动于 0.0.0.0:" << port << "，路由数 "
                     << router.route_count();
  const bool listening = svr.listen("0.0.0.0", port);
  // listen 返回（信号停机或监听失败）：让监视线程退出并 join，
  // 避免其引用已析构的栈上 svr。
  g_shutdown_requested.store(true);
  if (shutdown_watcher.joinable()) shutdown_watcher.join();
  if (!listening) {
    CM_LOG_ERROR("http") << "端口监听失败: " << port;
    return 1;
  }
  CM_LOG_INFO("http") << "HTTP 服务已停止（等待中的请求已全部返回）";
  return 0;
}

} // namespace cm::http
