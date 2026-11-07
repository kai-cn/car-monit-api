#include "service/dict.h"

#include "cache/redis.h"
#include "common/logging.h"
#include "common/utils.h"
#include "db/dao.h"
#include "db/pg.h"
#include "meta/entities_generated.h"

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <functional>
#include <map>
#include <memory>
#include <mutex>

namespace cm::service {
namespace {

// Jackson 输出中为 null 的字段读成空串（对应 CommonUtil.isNull）。
std::string s(const Json& row, const char* key) {
  auto it = row.find(key);
  if (it == row.end() || it->is_null()) return "";
  if (it->is_string()) return it->get<std::string>();
  if (it->is_number_integer()) return std::to_string(it->get<long long>());
  return it->dump();
}

using MapJson = std::map<std::string, Json>;

// 进程内字典缓存（P4：消除按行重复读取字典的 N+1）。
// Java 侧字典由 Redis 缓存；C++ 侧在其上再加一层短 TTL 的进程内缓存，
// 避免 track 处理每个点位时都做一次 Redis GET + JSON 解析 + map 重建。
// 失效策略：TTL 300s；或显式 invalidate_dict_cache()（测试/运维重载）。
// 与 Java 的差异：Java 实例间共享 Redis 缓存，C++ 进程内缓存最多滞后 5 分钟。
std::mutex g_local_mu;
struct LocalEntry {
  std::shared_ptr<const MapJson> map;
  std::chrono::steady_clock::time_point expires;
};
std::map<std::string, LocalEntry> g_local;
constexpr std::chrono::seconds kLocalTtl{300};

std::shared_ptr<const MapJson> memo_map(const std::string& cache_id,
                                        const std::function<void(MapJson&)>& build) {
  {
    std::lock_guard<std::mutex> lock(g_local_mu);
    auto it = g_local.find(cache_id);
    if (it != g_local.end() && it->second.expires > std::chrono::steady_clock::now())
      return it->second.map;
  }
  MapJson built;
  build(built);
  auto shared = std::make_shared<const MapJson>(std::move(built));
  {
    std::lock_guard<std::mutex> lock(g_local_mu);
    g_local[cache_id] = LocalEntry{shared, std::chrono::steady_clock::now() + kLocalTtl};
  }
  return shared;
}

} // namespace

void invalidate_dict_cache() {
  std::lock_guard<std::mutex> lock(g_local_mu);
  g_local.clear();
}

Json dict_list_cached(const std::string& key, const meta::EntityMeta& m) {
  auto& redis = cache::Redis::instance();
  auto cached = redis.get(key);
  if (cached && !cached->empty()) {
    try {
      Json j = Json::parse(*cached);
      if (j.is_array()) return j;
    } catch (...) {
      CM_LOG_WARN("dict") << "字典缓存反序列化失败，回源重建: " << key;
    }
  }
  std::string sql = "SELECT " + meta::select_columns(m) + " FROM " + m.table;
  if (!m.order_sql.empty()) sql += " ORDER BY " + m.order_sql;
  auto result = db::PgPool::instance().query(sql);
  Json arr = Json::array();
  for (std::size_t i = 0; i < result.rows.size(); ++i) arr.push_back(repo::project_row(m, result, i));
  redis.set_json(key, arr.dump());
  CM_LOG_INFO("dict") << "字典缓存已重建: " << key << " count=" << arr.size();
  return arr;
}

std::map<std::string, Json> gantry_map() {
  auto cached = memo_map("gantry", [](MapJson& out) {
    Json list = dict_list_cached(kGantryList, meta::odsSzdnGantry);
    for (const auto& row : list) out[s(row, "gantryCode")] = row;
  });
  return *cached;
}

std::map<std::string, Json> toll_map() {
  auto cached = memo_map("toll", [](MapJson& out) {
    Json list = dict_list_cached(kStationInfo, meta::odsSzdnToll);
    for (const auto& row : list) {
      out[s(row, "tollCode")] = row;
      out[s(row, "stateCodeMerge")] = row;
    }
  });
  return *cached;
}

std::map<std::string, Json> section_map() {
  auto cached = memo_map("section", [](MapJson& out) {
    Json list = dict_list_cached(kSectionRoadMap, meta::odsSzdnSection);
    for (const auto& row : list) out[s(row, "sectionCode")] = row;
  });
  return *cached;
}

std::map<std::string, Json> location_dict_map() {
  auto cached = memo_map("location", [](MapJson& out) {
    Json list = dict_list_cached(kDevPost, meta::zdataLocationDict);
    for (const auto& row : list) out[s(row, "rawCode")] = row;
  });
  return *cached;
}

std::map<std::string, Json> gantry_ip_map() {
  auto cached = memo_map("gantry_ip", [](MapJson& out) {
    Json gantries = dict_list_cached(kGantryList, meta::odsSzdnGantry);
    std::map<std::string, Json> by_code;
    for (const auto& g : gantries) by_code[s(g, "gantryCode")] = g;

    Json list = dict_list_cached(kGantryIp, meta::odsSzdnGantryIp);
    for (const auto& row : list) {
      Json item = row;
      auto it = by_code.find(s(row, "gantryCode"));
      if (it != by_code.end()) item["odsSzdnGantry"] = it->second;
      const std::string id = s(item, "id");
      const std::string code = s(item, "gantryCode");
      for (const char* p : {"gantryip:", "bwlocation:", "gantryid:", "gantry:"}) {
        out[std::string(p) + id] = item;
        out[std::string(p) + code] = item;
      }
      out[id] = item;
      out[code] = item;
    }
  });
  return *cached;
}

std::map<std::string, Json> station_ip_map() {
  auto cached = memo_map("station_ip", [](MapJson& out) {
    Json tolls = dict_list_cached(kStationInfo, meta::odsSzdnToll);
    std::map<std::string, Json> by_code;
    for (const auto& t : tolls) by_code[s(t, "tollCode")] = t;

    Json list = dict_list_cached(kStationIp, meta::odsSzdnTollStationIp);
    for (const auto& row : list) {
      Json item = row;
      auto it = by_code.find(s(row, "tollCode"));
      if (it != by_code.end()) item["odsSzdnToll"] = it->second;
      const std::string ip = s(item, "ip");
      const std::string code = s(item, "tollCode");
      for (const char* p : {"stationip:", "station:"}) {
        out[std::string(p) + ip] = item;
        out[std::string(p) + code] = item;
      }
      out[ip] = item;
      out[code] = item;
      out[utils::repalace_szdn_toll_name(s(item, "tollName"))] = item;
    }
  });
  return *cached;
}

Json weight_capture_map(const std::string& query_uuids) {
  Json map = Json::object();
  if (utils::is_blank(query_uuids)) return map;
  auto& redis = cache::Redis::instance();
  const auto& m = meta::odsSzdnProvinceBorderVehicleWeightNewstructure;

  // 先逐个查 Redis，把未命中/占位对象收集起来，再一次性批量回源（P4：消除 N+1）。
  std::vector<std::string> missing;
  for (const auto& raw : utils::split_csv(query_uuids)) {
    const std::string uuid = utils::trim(raw);
    if (uuid.empty()) continue;
    const std::string key = std::string(kBorderWeighingCapture) + uuid;
    auto cached = redis.get(key);
    if (cached && !cached->empty()) {
      try {
        Json j = Json::parse(*cached);
        if (j.is_object()) {
          auto it = j.find("bigId");
          if (it != j.end() && !it->is_null()) {
            map[uuid] = j;
            continue;
          }
          // Java 未命中时缓存的占位对象（仅含 datauuid）视为“已知不存在”，
          // 占位键有 60s TTL，避免长期挡住后到的真实记录。
          if (j.contains("datauuid")) continue;
        }
      } catch (...) {
        CM_LOG_WARN("dict") << "称重缓存反序列化失败: " << key;
      }
    }
    missing.push_back(uuid);
  }

  constexpr std::size_t kBatch = 100;
  for (std::size_t begin = 0; begin < missing.size(); begin += kBatch) {
    const std::size_t end = std::min(missing.size(), begin + kBatch);
    std::vector<std::string> chunk(missing.begin() + static_cast<std::ptrdiff_t>(begin),
                                   missing.begin() + static_cast<std::ptrdiff_t>(end));
    db::PgParams params;
    std::string sql = "SELECT " + meta::select_columns(m) + " FROM " + m.table +
                      " WHERE datauuid IN " + repo::bind_in(params, chunk);
    auto result = db::PgPool::instance().query(sql, params);
    for (std::size_t i = 0; i < result.rows.size(); ++i) {
      auto uuid = result.get(i, "datauuid");
      if (!uuid) continue;
      Json row = repo::project_row(m, result, i);
      map[*uuid] = row;
      redis.set_json(std::string(kBorderWeighingCapture) + *uuid, row.dump());
    }
    for (const auto& uuid : chunk) {
      if (map.contains(uuid)) continue;
      Json empty = Json::object();
      empty["datauuid"] = uuid;
      redis.set_json(std::string(kBorderWeighingCapture) + uuid, empty.dump(), 60);
    }
  }
  return map;
}

} // namespace cm::service
