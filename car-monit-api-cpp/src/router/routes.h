#pragma once
// 路由装配入口：对应 Spring 的组件扫描 + @RequestMapping 注册。
#include "http/server.h"

namespace cm::router {

http::Router build_routes();
void start_schedulers();
// 优雅停机：停止调度循环并 join 执行池（幂等）。
void stop_schedulers();

} // namespace cm::router
