#pragma once
// Spring MVC 的 C++ 等价物：Request（参数绑定）+ Response。
//
// 绑定规则与 Spring 一致：
//   * @RequestParam / 实体属性绑定 -> 同名请求参数（query 或 form，重复参数取最后一个）
//   * @PathVariable                -> path_params
//   * @RequestBody                 -> 原始 body 解析为 JSON
// 类型转换失败（如 int 参数为 "abc"）抛出 cm::BindError(400)，对应
// SpringMvc 的 TypeMismatchException 响应体。
#include "common/error.h"
#include "common/json.h"

#include <cstdlib>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace cm::http {

struct Request {
  std::string method;
  std::string path;
  std::map<std::string, std::vector<std::string>> params_all;
  std::map<std::string, std::string> path_params;
  std::map<std::string, std::string> headers_lower;
  std::string body;
  std::string remote_addr;

  bool has(const std::string& name) const { return params_all.count(name) > 0; }

  std::optional<std::string> get(const std::string& name) const {
    auto it = params_all.find(name);
    if (it == params_all.end() || it->second.empty()) return std::nullopt;
    return it->second.back();
  }

  std::string str(const std::string& name, const std::string& def = "") const {
    auto v = get(name);
    return v ? *v : def;
  }

  std::optional<int> get_int(const std::string& name) const {
    auto v = get(name);
    if (!v || v->empty()) return std::nullopt;
    try {
      return std::stoi(*v);
    } catch (...) {
      throw BindError(400, "参数 '" + name + "' 类型不匹配: " + *v);
    }
  }

  int int_or(const std::string& name, int def) const {
    auto v = get_int(name);
    return v ? *v : def;
  }

  std::optional<long long> get_long(const std::string& name) const {
    auto v = get(name);
    if (!v || v->empty()) return std::nullopt;
    try {
      return std::stoll(*v);
    } catch (...) {
      throw BindError(400, "参数 '" + name + "' 类型不匹配: " + *v);
    }
  }

  std::optional<bool> get_bool(const std::string& name) const {
    auto v = get(name);
    if (!v || v->empty()) return std::nullopt;
    std::string s = *v;
    for (auto& c : s) c = char(tolower(c));
    if (s == "true" || s == "1" || s == "yes") return true;
    if (s == "false" || s == "0" || s == "no") return false;
    throw BindError(400, "参数 '" + name + "' 类型不匹配: " + *v);
  }

  Json json() const {
    if (body.empty()) return Json(nullptr);
    try {
      return Json::parse(body);
    } catch (...) {
      throw BindError(400, "请求体不是合法的 JSON");
    }
  }

  std::optional<std::string> path_param(const std::string& name) const {
    auto it = path_params.find(name);
    if (it == path_params.end()) return std::nullopt;
    return it->second;
  }

  std::string header(const std::string& lower_name) const {
    auto it = headers_lower.find(lower_name);
    return it == headers_lower.end() ? "" : it->second;
  }
};

struct Response {
  int status = 200;
  std::string content_type = "application/json;charset=UTF-8";
  cm::Json json = cm::Json(nullptr);
  std::string raw_body;
  bool use_raw = false;
  // 额外响应头（同名多值，输出时以逗号合并，等价于 Spring 的多行 Vary 等）。
  std::map<std::string, std::vector<std::string>> headers;
  // true 时不设置 Content-Type/正文（对应 Spring 预检的空响应体）。
  bool no_body = false;
  // true 时不追加 Content-Disposition: attachment（CORS 403 等文本响应）。
  bool suppress_disposition = false;

  void add_header(const std::string& name, const std::string& value) {
    headers[name].push_back(value);
  }

  static Response ok(const Json& j) {
    Response r;
    r.json = j;
    return r;
  }
  static Response raw(int status, const std::string& body, const std::string& ctype) {
    Response r;
    r.status = status;
    r.raw_body = body;
    r.content_type = ctype;
    r.use_raw = true;
    return r;
  }
};

} // namespace cm::http
