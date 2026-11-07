#pragma once
// Spring 5.3.6 CORS 语义的等价实现（CorsConfiguration + DefaultCorsProcessor）。
// Java 工程源码没有全局 CORS 配置，这里按 Spring 的默认值实现并允许配置覆盖。
#include "config/config.h"
#include "http/ctx.h"

#include <string>

namespace cm::http {

enum class CorsDecision {
  NotCors,            // 无 Origin / 同源 / CORS 关闭 / 路径不匹配：不写任何 CORS 头
  ActualAllowed,      // 实际跨域请求，已写入 CORS 响应头
  ActualRejected,     // 实际跨域请求被拒：不写 CORS 头，但请求继续（Spring 行为）
  PreflightAllowed,   // 预检通过：应返回 200 空响应体
  PreflightRejected,  // 预检被拒：应返回 403 "Invalid CORS request"
  ConfigError,        // allowedOrigins=* 且 allowCredentials=true（Spring 抛 IllegalArgumentException）
};

// 按 Spring DefaultCorsProcessor#processRequest 处理：
//  * 非 CORS 请求直接放行；
//  * 预检请求在业务路由之前返回 200/403；
//  * 实际跨域请求追加 Access-Control-* 响应头后继续业务；
//  * Origin 不在白名单的实际请求继续业务但不加 CORS 头（与 Spring 一致）。
CorsDecision apply_cors(const config::Config::CorsCfg& cfg, const Request& req, Response& out);

// Spring UrlBasedCorsConfigurationSource 的路径匹配（支持 "/**" 与 "/prefix/**"）。
bool cors_path_matches(const std::string& pattern, const std::string& path);

} // namespace cm::http
