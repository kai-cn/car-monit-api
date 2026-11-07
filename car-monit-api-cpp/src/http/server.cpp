#include "http/server.h"

#include "common/datetime.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "config/config.h"
#include "http/cors.h"

#include "httplib.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <sstream>

namespace cm::http {
namespace {

// 进程级 IP 限流器（server.rate-limit.enabled 开启时使用）。
// 放在文件作用域：static 局部变量不能被 lambda 简单捕获（C3495）。
RateLimiter g_rate_limiter;

// 运行期指标（审阅 §5.1 #10）：请求计数 / 错误计数 / 在途数 / 累计时延。
std::atomic<long long> g_requests_total{0};
std::atomic<long long> g_errors_total{0};
std::atomic<long long> g_in_flight{0};
std::atomic<long long> g_total_latency_ms{0};
// 优雅停机：信号处理器只置位（async-signal-safe），监视线程负责调 svr.stop()。
std::atomic<bool> g_shutdown_requested{false};

} // namespace

Json metrics_snapshot() {
  Json j = Json::object();
  long long total = g_requests_total.load();
  long long latency = g_total_latency_ms.load();
  j["requestsTotal"] = total;
  j["errorsTotal"] = g_errors_total.load();
  j["inFlight"] = g_in_flight.load();
  j["avgLatencyMs"] = total > 0 ? (latency / total) : 0;
  j["uptimeSeconds"] = std::chrono::duration_cast<std::chrono::seconds>(
                           std::chrono::steady_clock::now().time_since_epoch())
                           .count();
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

int run_server(int port, const Router& router, int /*thread_count*/) {
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

    // 指标累计（审阅 §5.1 #10）。
    g_requests_total.fetch_add(1);
    if (out.status >= 500) g_errors_total.fetch_add(1);
    g_total_latency_ms.fetch_add(
        std::chrono::duration_cast<std::chrono::milliseconds>(
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
  std::thread shutdown_watcher([&svr] {
    while (!g_shutdown_requested.load()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    CM_LOG_INFO("http") << "收到停机信号，停止接受新请求";
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
