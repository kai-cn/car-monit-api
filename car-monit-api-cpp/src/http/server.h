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
#include <string>
#include <vector>

namespace cm::http {

using Handler = std::function<Response(Request&)>;

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
