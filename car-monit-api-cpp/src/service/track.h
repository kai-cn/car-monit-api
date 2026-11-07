#pragma once
// 轨迹/可疑车辆相关业务（SysUtilServiceImpl + SysTestController + TrackTask 的 C++ 移植）。
//
// 每个函数上方标注其对应的 Java 方法，键名与 Constants.java 保持一致。
#include "common/json.h"
#include "http/ctx.h"

#include <string>

namespace cm::service {

// SysUtilServiceImpl 中的流水来源类型常量（BorderWeighingCapture 见 service/dict.h）。
inline constexpr const char* kGantryCapture = "GantryCapture";
inline constexpr const char* kProvCapture = "ProvCapture";
inline constexpr const char* kServiceAreaCapture = "ServiceAreaCapture";
inline constexpr const char* kStationCapture = "StationCapture";
inline constexpr const char* kFeeRecord = "FeeRecord";
inline constexpr const char* kFeeStationEnter = "FeeStationEnter";
inline constexpr const char* kFeeStationExit = "FeeStationExit";

// Constants.java 中的缓存键
inline constexpr const char* kCarCurrentTrail = "car_curent_trail:";
inline constexpr const char* kTrailPrefix = "trail:";
inline constexpr const char* kCarSuspicious = "car_uspicious";
inline constexpr const char* kSnapshotFlowList = "js_car_snapshot";
inline constexpr const char* kFeeRecordsList = "js_car_reerecords";
inline constexpr const char* kTrailFittingList = "js_car_trail_fitting";
inline constexpr const char* kEscapedType20 = "20";

// 配置键（SysUtilServiceImpl 顶部常量）
inline constexpr const char* kRedisTimeKey = "sys_config:syncSuspiciousCar_time";
inline constexpr const char* kRedisBiteKey = "sys_config:syncSuspiciousCar_bite";
inline constexpr const char* kSupoerMjnum = "sys_config:supoer_mjnum";
inline constexpr const char* kRoadSupoerMjnum = "sys_config:road_supoer_mjnum";
inline constexpr const char* kJholidayTime = "sys_config:jholiday_time";

// ---------------------------------------------------------------------------
// TrackTask / DataFlowTask
// ---------------------------------------------------------------------------
// TrackTask#syncBaseInfo：重建 7 类基础信息缓存。
void sync_base_info();
// TrackTask#syncCurrentTrack -> SysUtilServiceImpl#syncTrack(new CarParaVO())
void sync_current_track();
// DataFlowTask#syncHistroyTrack（逻辑在 SysTestController 中）
void sync_histroy_track();
// DataFlowTask#processPendingQueue -> MultiSourceDataFlowService#processPendingQueue
void process_pending_queue();
// DataFlowTask#syncGantryCaptureData（Java 方法体整体被注释，仅保留日志）
void sync_gantry_capture_data();

// SysUtilServiceImpl#syncSuspiciousCarQutaz(index, index)
void sync_suspicious_car(int index);

// OdsSzdnGantryServiceImpl#saveGantryRedis + SysTestController#syncOdsSzdnGantry
void sync_ods_szdn_gantry();

// SysUtilServiceImpl#separateSnapshotFlowTimeList
Json separate_snapshot_flow_time_list(const cm::http::Request& req);

// ---------------------------------------------------------------------------
// SysUtilController
// ---------------------------------------------------------------------------
// SysUtilServiceImpl#saveRedis(SysUtil) -> AjaxResult.success()
Json save_redis();

// GET /carTrackQueryByCarNo
Json car_track_query_by_car_no(const cm::http::Request& req);
// GET /carTrackQueryByTime
Json car_track_query_by_time(const cm::http::Request& req);

// SysUtilServiceImpl#changeData(tracks, trailList) 的对外入口（POST changeTrailInfo）
Json change_trail_info(const Json& trail_info);
// SysUtilServiceImpl#getByTrailBo(TrailBo)
Json get_by_trail_bo(const Json& trail_bo);

} // namespace cm::service
