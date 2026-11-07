#pragma once
#include "http/server.h"

namespace cm::handler {

// 17 个只读实体控制器（共 46 个端点）。
void register_base(http::Router& r);
// SysUtilController（/base/sysutil）
void register_sysutil(http::Router& r);
// SysTestController（/base/sysutilTest）
void register_systest(http::Router& r);
// LargeScaleQueryController + UnifiedQueryController + ProgressiveQueryController
void register_optimization(http::Router& r);
// 定时任务（10 个）
void start_schedulers();

} // namespace cm::handler
