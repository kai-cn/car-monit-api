#pragma once
#include "http/server.h"

namespace cm::handler {

// 19 个只读实体控制器（共 48 个端点）。
void register_base(http::Router& r);

// /{id} 详情端点的返回形态（对齐 Java 控制器 getInfo 的返回类型，唯一权威映射）：
// 仅 /base/feeGantry、/base/feerecords、/base/snapshotflow 三个控制器直接返回
// 实体本身（OdsLwzxsfsjFeeGantryFusion01/OdsLwzxsfsjFeeRecords01/
// OdsRtSzdnSnapshotFlowAddcode），其余 16 个返回 AjaxResult.success(entity) 信封；
// 信封形态查不到时返回 {"msg":"操作成功","code":200}（data 键省略，非空 body）。
bool info_returns_raw_entity(const std::string& base_path);
// SysUtilController（/base/sysutil）
void register_sysutil(http::Router& r);
// SysTestController（/base/sysutilTest）
void register_systest(http::Router& r);
// LargeScaleQueryController + UnifiedQueryController + ProgressiveQueryController
void register_optimization(http::Router& r);
// 定时任务（10 个）
void start_schedulers();

} // namespace cm::handler
