#include "service/dict.h"

#include "cache/redis.h"
#include "common/logging.h"
#include "common/utils.h"
#include "db/dao.h"
#include "db/pg.h"
#include "meta/entities_generated.h"

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

} // namespace

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
  std::string sql = "SELECT " + m.select_sql + " FROM " + m.table;
  if (!m.order_sql.empty()) sql += " ORDER BY " + m.order_sql;
  auto result = db::PgPool::instance().query(sql);
  Json arr = Json::array();
  for (std::size_t i = 0; i < result.rows.size(); ++i) arr.push_back(repo::project_row(m, result, i));
  redis.set_json(key, arr.dump());
  CM_LOG_INFO("dict") << "字典缓存已重建: " << key << " count=" << arr.size();
  return arr;
}

std::map<std::string, Json> gantry_map() {
  std::map<std::string, Json> out;
  Json list = dict_list_cached(kGantryList, meta::odsSzdnGantry);
  for (const auto& row : list) out[s(row, "gantryCode")] = row;
  return out;
}

std::map<std::string, Json> toll_map() {
  std::map<std::string, Json> out;
  Json list = dict_list_cached(kStationInfo, meta::odsSzdnToll);
  for (const auto& row : list) {
    out[s(row, "tollCode")] = row;
    out[s(row, "stateCodeMerge")] = row;
  }
  return out;
}

std::map<std::string, Json> section_map() {
  std::map<std::string, Json> out;
  Json list = dict_list_cached(kSectionRoadMap, meta::odsSzdnSection);
  for (const auto& row : list) out[s(row, "sectionCode")] = row;
  return out;
}

std::map<std::string, Json> location_dict_map() {
  std::map<std::string, Json> out;
  Json list = dict_list_cached(kDevPost, meta::zdataLocationDict);
  for (const auto& row : list) out[s(row, "rawCode")] = row;
  return out;
}

std::map<std::string, Json> gantry_ip_map() {
  std::map<std::string, Json> out;
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
  return out;
}

std::map<std::string, Json> station_ip_map() {
  std::map<std::string, Json> out;
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
  return out;
}

Json weight_capture_map(const std::string& query_uuids) {
  Json map = Json::object();
  if (utils::is_blank(query_uuids)) return map;
  auto& redis = cache::Redis::instance();
  for (const auto& uuid : utils::split_csv(query_uuids)) {
    const std::string key = std::string(kBorderWeighingCapture) + uuid;
    auto cached = redis.get(key);
    if (cached && !cached->empty()) {
      try {
        Json j = Json::parse(*cached);
        // Java 未命中时缓存的是一个 datauuid=uuid 的空对象，不会放进返回 Map。
        if (j.is_object()) {
          auto it = j.find("bigId");
          if (it != j.end() && !it->is_null()) {
            map[uuid] = j;
            continue;
          }
        }
      } catch (...) {
        CM_LOG_WARN("dict") << "称重缓存反序列化失败: " << key;
      }
    }
    std::string sql = "SELECT " + meta::odsSzdnProvinceBorderVehicleWeightNewstructure.select_sql +
                      " FROM " + meta::odsSzdnProvinceBorderVehicleWeightNewstructure.table +
                      " WHERE datauuid = " + repo::quote(uuid) + " LIMIT 1";
    auto result = db::PgPool::instance().query(sql);
    if (!result.rows.empty()) {
      Json row = repo::project_row(meta::odsSzdnProvinceBorderVehicleWeightNewstructure, result, 0);
      map[uuid] = row;
      redis.set_json(key, row.dump());
    } else {
      Json empty = Json::object();
      empty["datauuid"] = uuid;
      redis.set_json(key, empty.dump());
    }
  }
  return map;
}

} // namespace cm::service
