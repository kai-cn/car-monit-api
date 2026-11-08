#include "http/cors.h"

#include "common/utils.h"

#include <algorithm>
#include <cctype>
#include <optional>
#include <regex>
#include <vector>

namespace cm::http {
namespace {

struct Origin {
  bool valid = false;
  std::string scheme;
  std::string host;  // 小写
  std::string port;  // 规范化后的端口（省略时补默认值）
};

Origin parse_origin(const std::string& value) {
  Origin o;
  auto pos = value.find("://");
  if (pos == std::string::npos) return o;
  o.scheme = utils::to_lower(value.substr(0, pos));
  std::string rest = value.substr(pos + 3);
  auto slash = rest.find('/');
  if (slash != std::string::npos) rest = rest.substr(0, slash);
  auto at = rest.rfind('@');
  if (at != std::string::npos) rest = rest.substr(at + 1);
  std::string host;
  std::string port;
  if (!rest.empty() && rest.front() == '[') { // IPv6
    auto close = rest.find(']');
    if (close == std::string::npos) return o;
    host = rest.substr(1, close - 1);
    if (close + 1 < rest.size() && rest[close + 1] == ':') port = rest.substr(close + 2);
  } else {
    auto colon = rest.rfind(':');
    if (colon != std::string::npos) {
      host = rest.substr(0, colon);
      port = rest.substr(colon + 1);
    } else {
      host = rest;
    }
  }
  if (host.empty()) return o;
  o.host = utils::to_lower(host);
  if (port.empty()) port = (o.scheme == "https" ? "443" : "80");
  o.port = port;
  o.valid = true;
  return o;
}

Origin request_origin(const Request& req) {
  Origin o;
  // 本服务只监听 HTTP，scheme 固定为 http；host/port 来自 Host 头（与 Tomcat 一致）。
  o.scheme = "http";
  std::string host_header = req.header("host");
  if (host_header.empty()) return o;
  Origin parsed = parse_origin("http://" + host_header);
  if (!parsed.valid) return o;
  o.host = parsed.host;
  o.port = parsed.port;
  o.valid = true;
  return o;
}

bool is_cors_request(const Request& req) {
  std::string origin = req.header("origin");
  if (origin.empty()) return false;
  Origin req_o = request_origin(req);
  if (!req_o.valid) return true;
  Origin o = parse_origin(origin);
  if (!o.valid) return true; // "null" 等不透明 origin：按跨域处理
  return !(o.scheme == req_o.scheme && o.host == req_o.host && o.port == req_o.port);
}

bool is_preflight(const Request& req) {
  return utils::equals_ignore_case(req.method, "OPTIONS") &&
         !req.header("origin").empty() &&
         !req.header("access-control-request-method").empty();
}

std::string glob_to_regex(const std::string& pattern) {
  std::string re = "^";
  for (char c : pattern) {
    if (c == '*') {
      re += ".*";
    } else if (std::string(".+()[]{}^$|\\").find(c) != std::string::npos) {
      re += '\\';
      re += c;
    } else {
      re += c;
    }
  }
  re += "$";
  return re;
}

bool match_pattern(const std::string& pattern, const std::string& value) {
  if (pattern == "*") return true;
  try {
    return std::regex_match(value, std::regex(glob_to_regex(pattern), std::regex::icase));
  } catch (...) {
    return false;
  }
}

bool contains_ci(const std::vector<std::string>& list, const std::string& value) {
  return std::any_of(list.begin(), list.end(), [&](const std::string& s) {
    return utils::equals_ignore_case(s, value);
  });
}

// 响应头注入防护：拒绝含 CR/LF/控制字符的 origin 与原样回显的请求头名。
bool has_control_chars(const std::string& s) {
  for (unsigned char c : s) {
    if (c < 0x20 || c == 0x7f) return true;
  }
  return false;
}

// RFC 7230 token：请求头名只能包含 tchar。
bool valid_header_token(const std::string& s) {
  if (s.empty() || s.size() > 256) return false;
  for (unsigned char c : s) {
    const bool ok = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                    (c >= '0' && c <= '9') || c == '!' || c == '#' || c == '$' || c == '%' ||
                    c == '&' || c == '\'' || c == '*' || c == '+' || c == '-' || c == '.' ||
                    c == '^' || c == '_' || c == '`' || c == '|' || c == '~';
    if (!ok) return false;
  }
  return true;
}

// CorsConfiguration#checkOrigin：返回 nullopt 表示 origin 不被允许。
// wildcard 且 allowCredentials=true 时 Spring 抛 IllegalArgumentException，这里映射为 ConfigError。
struct OriginCheck {
  bool config_error = false;
  std::optional<std::string> allow_origin;
};

OriginCheck check_origin(const config::Config::CorsCfg& cfg, const std::string& origin) {
  OriginCheck r;
  // 防止把含 CR/LF 或超长的 Origin 回显到响应头（响应头注入）。
  if (origin.size() > 2048 || has_control_chars(origin)) return r;
  if (contains_ci(cfg.allowed_origins, "*")) {
    if (cfg.allow_credentials) r.config_error = true;
    r.allow_origin = "*";
    return r;
  }
  if (contains_ci(cfg.allowed_origins, origin)) {
    r.allow_origin = origin;
    return r;
  }
  for (const auto& pattern : cfg.allowed_origin_patterns) {
    if (match_pattern(pattern, origin)) {
      r.allow_origin = origin;
      return r;
    }
  }
  return r;
}

std::vector<std::string> split_headers(const std::string& value) {
  std::vector<std::string> out;
  for (auto& part : utils::split(value, ',')) {
    auto t = utils::trim(part);
    if (!t.empty()) out.push_back(t);
  }
  return out;
}

// CorsConfiguration#checkHeaders：返回 nullopt 表示“没有可允许的请求头”。
std::optional<std::vector<std::string>> check_headers(const config::Config::CorsCfg& cfg,
                                                      const std::vector<std::string>& requested) {
  if (cfg.allowed_headers.empty()) return std::nullopt;
  if (contains_ci(cfg.allowed_headers, "*")) {
    // 原样回显前过滤非法头名（含 CR/LF、非 token 字符、超长）。
    std::vector<std::string> echoed;
    for (const auto& h : requested) {
      if (valid_header_token(h)) echoed.push_back(h);
    }
    if (echoed.empty()) return std::nullopt;
    return echoed;
  }
  std::vector<std::string> allowed;
  for (const auto& h : requested) {
    if (contains_ci(cfg.allowed_headers, h)) allowed.push_back(h);
  }
  if (allowed.empty()) return std::nullopt;
  return allowed;
}

void write_headers(const config::Config::CorsCfg& cfg, const std::optional<std::string>& allow_origin,
                   const std::optional<std::vector<std::string>>& allow_methods,
                   const std::optional<std::vector<std::string>>& allow_headers, bool preflight,
                   Response& out) {
  if (allow_origin) out.add_header("Access-Control-Allow-Origin", *allow_origin);
  if (preflight && allow_methods) {
    out.add_header("Access-Control-Allow-Methods", utils::join(*allow_methods, ","));
  }
  if (preflight && allow_headers && !allow_headers->empty()) {
    out.add_header("Access-Control-Allow-Headers", utils::join(*allow_headers, ","));
  }
  if (!cfg.exposed_headers.empty()) {
    out.add_header("Access-Control-Expose-Headers", utils::join(cfg.exposed_headers, ","));
  }
  if (cfg.allow_credentials) out.add_header("Access-Control-Allow-Credentials", "true");
  if (preflight && cfg.max_age >= 0) {
    out.add_header("Access-Control-Max-Age", std::to_string(cfg.max_age));
  }
}

} // namespace

bool cors_path_matches(const std::string& pattern, const std::string& path) {
  if (pattern.empty() || pattern == "/**" || pattern == "/*") return true;
  if (utils::ends_with(pattern, "/**")) {
    std::string prefix = pattern.substr(0, pattern.size() - 3);
    if (prefix.empty() || prefix == "/") return true;
    return path == prefix || utils::starts_with(path, prefix + "/");
  }
  if (pattern.find('*') != std::string::npos) return match_pattern(pattern, path);
  return path == pattern;
}

CorsDecision apply_cors(const config::Config::CorsCfg& cfg, const Request& req, Response& out) {
  if (!cfg.enabled || !cors_path_matches(cfg.path, req.path)) return CorsDecision::NotCors;

  std::string origin = req.header("origin");
  bool preflight = is_preflight(req);
  if (origin.empty() && !preflight) return CorsDecision::NotCors;
  if (origin.empty()) return CorsDecision::NotCors;

  // Spring DefaultCorsProcessor 会对 CORS 响应追加 Vary，保证代理缓存正确。
  out.add_header("Vary", "Origin");
  out.add_header("Vary", "Access-Control-Request-Method");
  out.add_header("Vary", "Access-Control-Request-Headers");

  if (!is_cors_request(req)) return CorsDecision::NotCors;

  OriginCheck oc = check_origin(cfg, origin);
  if (oc.config_error) return CorsDecision::ConfigError;
  if (!oc.allow_origin) {
    return preflight ? CorsDecision::PreflightRejected : CorsDecision::ActualRejected;
  }

  // CorsConfiguration#checkMethods
  std::vector<std::string> resolved = cfg.allowed_methods;
  std::optional<std::vector<std::string>> allow_methods = resolved;
  std::string request_method =
      preflight ? req.header("access-control-request-method") : req.method;
  if (resolved.empty()) {
    allow_methods = std::vector<std::string>{request_method};
  } else if (!contains_ci(resolved, "*")) {
    if (!contains_ci(resolved, request_method)) {
      return preflight ? CorsDecision::PreflightRejected : CorsDecision::ActualRejected;
    }
    if (preflight) allow_methods = resolved;
  } else {
    allow_methods = std::vector<std::string>{"*"};
  }

  std::optional<std::vector<std::string>> allow_headers;
  if (preflight) {
    allow_headers = check_headers(cfg, split_headers(req.header("access-control-request-headers")));
    if (!allow_headers) return CorsDecision::PreflightRejected;
  }

  write_headers(cfg, oc.allow_origin, allow_methods, allow_headers, preflight, out);
  return preflight ? CorsDecision::PreflightAllowed : CorsDecision::ActualAllowed;
}

} // namespace cm::http
