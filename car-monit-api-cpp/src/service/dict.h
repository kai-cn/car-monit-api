#pragma once
// 字典缓存（对应 ZdataLocationDictServiceImpl / OdsSzdnGantryServiceImpl(ip) /
// OdsSzdnTollServiceImpl / OdsSzdnSectionServiceImpl 中的 updateRedis/getRedisMap）。
//
// Java 侧把整张表以 JDK 序列化写入 Redis，再由 getXxxRedis()/getRedisMap() 读回。
// C++ 侧写入的是同一批行的 JSON 数组（键名 camelCase，与 Jackson 输出一致），
// 键名与 Constants.java 保持一致。缓存未命中/损坏时回源数据库并重建。
#include "common/json.h"
#include "meta/entity_meta.h"

#include <functional>
#include <map>
#include <memory>
#include <string>

namespace cm::service {

using DictMap = std::map<std::string, Json>;

// 常量（Constants.java）
inline constexpr const char* kCarListJC = "car_list_jc";
inline constexpr const char* kCarHistoryTrail = "car_history_trail:";
inline constexpr const char* kCarSyncTime = "car_sync_time:";
inline constexpr const char* kGantryList = "gantry_list";
inline constexpr const char* kGantryListData = "gantry_list_data:";
inline constexpr const char* kDevPost = "dev_post";
inline constexpr const char* kGantryIp = "gantry_ip";
inline constexpr const char* kStationIp = "station_ip";
inline constexpr const char* kStationInfo = "station_info";
inline constexpr const char* kSectionRoadMap = "section_road_map";
inline constexpr const char* kBorderWeighingCapture = "DATE_BorderWeighingCapture:";

// 读缓存（JSON 数组），未命中则全表查询并写回。
Json dict_list_cached(const std::string& key, const meta::EntityMeta& m);

// 清空进程内字典缓存（TTL 之外的显式失效入口；测试/运维重载使用）。
void invalidate_dict_cache();

// 进程内字典 memo（P4）：同 key 在 TTL 内复用；build 抛异常不会写入缓存。
// 并发未命中时允许重复构建（结果一致），构建完成后以最后一次为准。
std::shared_ptr<const DictMap> memoize_dict_map(
    const std::string& cache_id, const std::function<void(DictMap&)>& build);

// 覆盖进程内字典缓存 TTL（毫秒），返回旧值；0 表示立即过期（测试/运维使用）。
int set_dict_local_ttl_ms(int ttl_ms);

std::map<std::string, Json> gantry_map();        // key = gantryCode
std::map<std::string, Json> toll_map();          // key = tollCode / stateCodeMerge
std::map<std::string, Json> section_map();       // key = sectionCode
std::map<std::string, Json> location_dict_map(); // key = rawCode
std::map<std::string, Json> gantry_ip_map();     // key = id/code + 业务前缀
std::map<std::string, Json> station_ip_map();    // key = ip/tollCode/站名 + 前缀

// 对应 OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl#selectByQueryUuids
Json weight_capture_map(const std::string& query_uuids);

} // namespace cm::service
