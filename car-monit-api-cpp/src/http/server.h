#pragma once
// 基于 vendored cpp-httplib 的 HTTP 服务，承担 Spring MVC + Tomcat 的角色。
//
// 路由表用 Spring 风格路径（如 "/base/dwdLcztFwqjcxx/{id}"），内部转换为
// 正则并抽取 @PathVariable。上下文路径（server.servlet.context-path）在
// 注册时统一加前缀。
#include "http/ctx.h"

#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace cm::http {

using Handler = std::function<Response(Request&)>;

// ---------------------------------------------------------------------------
// 安全加固（审阅 §5.1 #6，均为新增能力、默认关闭以对齐 Java 生产行为——
// Java 的 SecurityInterceptor 在 WebConfig.java 中被整体注释，运行实例无鉴权）。
// ---------------------------------------------------------------------------

// API-Key 校验（server.auth.enabled 开启时生效）：
// 接受 X-API-Key: <key> 或 Authorization: Bearer <key>。
// api_key 为空时返回 false（fail-closed：开启鉴权但未配置密钥 = 全部拒绝）。
bool check_api_key(const Request& req, const std::string& api_key);

// 按客户端 IP 的固定窗口限流器（server.rate-limit.enabled 开启时生效）。
class RateLimiter {
public:
  // limit_per_minute <= 0 视为全部拒绝。
  bool allow(const std::string& ip, int limit_per_minute);

private:
  std::mutex mu_;
  std::unordered_map<std::string, std::pair<long long, int>> windows_; // ip -> {分钟, 计数}
};

class Router {
public:
  void set_context_path(const std::string& prefix) { prefix_ = prefix; }
  void add(const std::string& method, const std::string& pattern, Handler handler);
  // 合并另一个路由表（模块化注册用）。
  void merge(const Router& other);

  bool dispatch(Request& req, Response& out) const;
  std::size_t route_count() const { return routes_.size(); }
  std::vector<std::pair<std::string, std::string>> routes() const;
  // Spring HttpOptionsHandler 的 Allow 列表（无匹配路径时返回空）。
  std::vector<std::string> methods_for_path(const std::string& path) const;

private:
  struct Route {
    std::string method;
    std::string pattern;
    std::vector<std::string> segments;
    Handler handler;
  };
  std::string prefix_ = "/";
  std::vector<Route> routes_;
};

int run_server(int port, const Router& router, int thread_count);

} // namespace cm::http
