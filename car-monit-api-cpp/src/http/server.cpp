#include "http/server.h"

#include "common/datetime.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "config/config.h"
#include "http/cors.h"

#include "httplib.h"

#include <algorithm>
#include <sstream>

namespace cm::http {
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

int run_server(int port, const Router& router, int /*thread_count*/) {
  httplib::Server svr;
  svr.set_payload_max_length(64LL * 1024 * 1024);

  auto handler = [&router](const httplib::Request& raw, httplib::Response& res) {
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
  };

  svr.Get(R"(.*)", handler);
  svr.Post(R"(.*)", handler);
  svr.Put(R"(.*)", handler);
  svr.Delete(R"(.*)", handler);
  svr.Options(R"(.*)", handler);

  CM_LOG_INFO("http") << "HTTP 服务启动于 0.0.0.0:" << port << "，路由数 "
                     << router.route_count();
  if (!svr.listen("0.0.0.0", port)) {
    CM_LOG_ERROR("http") << "端口监听失败: " << port;
    return 1;
  }
  return 0;
}

} // namespace cm::http
