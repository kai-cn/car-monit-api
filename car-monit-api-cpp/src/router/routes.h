#pragma once
// 路由装配入口：对应 Spring 的组件扫描 + @RequestMapping 注册。
#include "http/server.h"

namespace cm::router {

http::Router build_routes();
void start_schedulers();

} // namespace cm::router
