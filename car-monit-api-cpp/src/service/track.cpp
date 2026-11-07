#include "service/track.h"

#include "cache/redis.h"
#include "common/datetime.h"
#include "common/logging.h"
#include "common/result.h"
#include "common/utils.h"
#include "db/dao.h"
#include "db/pg.h"
#include "meta/entities_generated.h"
#include "service/dict.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace cm::service {
namespace {

using Json = cm::Json;
using MapJson = std::map<std::string, Json>;

// Java Constants.BORDER_WEIGHING_CAPTURE 的 stateType 值；dict.h 中的同名常量是 Redis
// 键前缀（DATE_BorderWeighingCapture:），两者语义不同，这里单独命名避免混用。
constexpr const char* kStateBorderWeighing = "BorderWeighingCapture";

// getByTrailBo 的 Redis 键前缀（Constants.java）。Java 用 FastJson2 写 Redis，
// C++ 侧写同键名的 JSON（Date 为 Jackson(UTC) 格式），键结构保持一致。
constexpr const char* kDateGantryCapture = "DATE_GANTRY_CAPTURE:";
constexpr const char* kDateProvCapture = "DATE_PROV_CAPTURE:";
constexpr const char* kDateServiceAreaCapture = "DATE_SERVICE_AREA_CAPTURE:";
constexpr const char* kDateStationCapture = "DATE_STATION_CAPTURE:";

constexpr const char* kIndexSectionCode = "200R500450649000";
constexpr const char* kIndexSectionName = "泰赣路段";

// ---------------------------------------------------------------------------
// JSON 取值辅助（对应 CommonUtil.isNull / getXxx）
// ---------------------------------------------------------------------------
std::string jstr(const Json& o, const char* key) {
  if (!o.is_object()) return "";
  auto it = o.find(key);
  if (it == o.end() || it->is_null()) return "";
  if (it->is_string()) return it->get<std::string>();
  if (it->is_boolean()) return it->get<bool>() ? "true" : "false";
  if (it->is_number_integer()) return std::to_string(it->get<long long>());
  if (it->is_number_unsigned()) return std::to_string(it->get<unsigned long long>());
  if (it->is_number_float()) return it->dump();
  return "";
}

bool jblank(const Json& o, const char* key) { return cm::utils::is_blank(jstr(o, key)); }

Json jget(const Json& o, const char* key) {
  if (!o.is_object()) return Json(nullptr);
  auto it = o.find(key);
  return it == o.end() ? Json(nullptr) : *it;
}

Json json_number_or_null(const std::string& text) {
  const std::string v = cm::utils::trim(text);
  if (v.empty()) return Json(nullptr);
  try {
    return Json::parse(v);
  } catch (...) {
    return Json(v);
  }
}

// 数字/字符串值 -> 文本（对应 Java 的 String.valueOf / toPlainString）
std::string json_text(const Json& v) {
  if (v.is_null()) return "";
  if (v.is_string()) return v.get<std::string>();
  if (v.is_number_integer()) return std::to_string(v.get<long long>());
  if (v.is_number_unsigned()) return std::to_string(v.get<unsigned long long>());
  if (v.is_number_float()) return v.dump();
  return "";
}

void set_null(Json& o, const char* key) { o[key] = nullptr; }
void set_str(Json& o, const char* key, const std::string& v) { o[key] = v; }
void set_str_if(Json& o, const char* key, const std::string& v) {
  if (!v.empty()) o[key] = v;
}

void set_dec_from(Json& o, const char* dec_key, const char* src_key) {
  Json v = jget(o, src_key);
  if (v.is_null()) {
    set_null(o, dec_key);
    return;
  }
  if (v.is_string()) {
    o[dec_key] = json_number_or_null(v.get<std::string>());
    return;
  }
  o[dec_key] = v;
}

std::optional<cm::timeutil::TimePoint> parse_time(const std::string& s) {
  if (cm::utils::is_blank(s) || s == "null") return std::nullopt;
  if (auto t = cm::timeutil::parse_any(s)) return t;
  return cm::timeutil::from_db_text(s);
}

// Java SimpleDateFormat("yyyy-MM-dd HH:mm:ss")（JVM 本地时区 +08:00）。
std::string local_datetime_text(const std::string& s) {
  auto tp = parse_time(s);
  return tp ? cm::timeutil::format_naive_plus8(*tp) : "";
}

std::string today_day() {
  return cm::timeutil::format_naive_plus8(cm::timeutil::now()).substr(0, 10);
}

std::string today_compact() {
  return cm::utils::replace_all(today_day(), "-", "");
}

// ---------------------------------------------------------------------------
// TrailBo / ZdataTrailTracks / TrailInfo 的空对象（Jackson 默认输出 null 字段）
// ---------------------------------------------------------------------------
Json empty_trail_bo() {
  Json o = Json::object();
  for (const char* k : {"pointUuid", "stateType", "pointFlag", "pointJosn",
                        "borderWeighingCaptureBO", "gantryCaptureBO", "provCaptureBO",
                        "stationCapture", "feeRecord", "feeStationEnter", "feeStationExit",
                        "captureTime", "directionIn", "locationCode", "locationName",
                        "standardCode", "longitude", "latitude", "locationFlag", "ipType",
                        "locationJosn", "gantryIpBO", "stationIpBO", "devCode", "devName",
                        "imagesArry", "lon", "lat", "roadCode", "sectionCode", "orgCode",
                        "direction", "pileno", "preCaptureTime", "countNum", "platenumber",
                        "locationId", "isQuery", "platecolor", "isVirtual"}) {
    o[k] = nullptr;
  }
  return o;
}

Json empty_tracks() {
  Json o = Json::object();
  for (const char* k :
       {"uuid", "type", "pointCount", "plateKey", "enterTime", "exitTime", "trailPoints",
        "enterLocationcode", "exitLocationcode", "trackJosn", "enaxlecount", "entolllaneid",
        "entollstationid", "entollstationname", "envehicleclass", "envehicleid", "envehicletype",
        "enweight", "extolllaneid", "extollstationid", "extollstationname", "exvehicleclass",
        "exvehicleid", "exvehicletype", "exweight", "startLon", "stratLat", "endLon", "endLat",
        "firtStationCode", "firtStationName", "firtStationTime", "plateColor", "carType", "carNo",
        "carVehicle", "carNum", "passType", "escapedType", "escapedTypeRemark", "applyTime1",
        "applyTime2", "flag", "startLonDec", "stratLatDec", "endLonDec", "endLatDec", "escapedTfcj",
        "trailtype"}) {
    o[k] = nullptr;
  }
  return o;
}

Json empty_trail_info() {
  Json o = Json::object();
  o["trailUuid"] = nullptr;
  o["enterTime"] = nullptr;
  o["tracks"] = nullptr;
  o["trailList"] = nullptr;
  return o;
}

// ---------------------------------------------------------------------------
// getTrailBoListString：还原 Java 对被转义 json[] 文本的替换
// ---------------------------------------------------------------------------
std::string trail_points_json_text(const std::string& raw) {
  std::string s = cm::utils::replace_all(raw, "\\", "");
  s = cm::utils::replace_all(s, "{\"{", "[{");
  s = cm::utils::replace_all(s, "}\"}", "}]");
  s = cm::utils::replace_all(s, "\",\"{", ",{");
  s = cm::utils::replace_all(s, "ZdTrails:", "");
  return s;
}

// SysUtilServiceImpl#mapTrailBoList：同名（stateType+locationCode）在 4 分钟内合并图片。
// Java 变量名为 threeMinutesInMillis，但实际取值为 4 分钟。
std::vector<Json> map_trail_bo_list(std::vector<Json> list) {
  std::vector<Json> out;
  std::map<std::string, std::size_t> latest;
  const long long merge_ms = 4LL * 60 * 1000;

  for (auto& tb : list) {
    const std::string type = jstr(tb, "stateType");
    const std::string key = type + jstr(tb, "locationCode");
    const bool mergeable = (type == kGantryCapture || type == kStationCapture);
    auto found = mergeable ? latest.find(key) : latest.end();

    if (found == latest.end()) {
      out.push_back(tb);
      if (mergeable) latest[key] = out.size() - 1;
      continue;
    }

    Json& prev = out[found->second];
    auto t1 = parse_time(jstr(prev, "captureTime"));
    auto t2 = parse_time(jstr(tb, "captureTime"));
    bool split = (!t1 || !t2);
    if (!split) {
      long long diff = cm::timeutil::to_millis(*t2) - cm::timeutil::to_millis(*t1);
      if (std::llabs(diff) > merge_ms) split = true;
    }
    if (split) {
      out.push_back(tb);
      latest[key] = out.size() - 1;
    } else {
      // deleteEnd 后逗号拼接图片
      std::string merged = cm::utils::delete_end(jstr(prev, "imagesArry"));
      std::string add = cm::utils::delete_end(jstr(tb, "imagesArry"));
      if (!add.empty()) merged = merged.empty() ? add : merged + "," + add;
      prev["imagesArry"] = merged;
    }
  }
  return out;
}

// SysUtilServiceImpl#getTrailBoList
std::vector<Json> get_trail_bo_list(const std::string& raw) {
  std::vector<Json> out;
  if (cm::utils::is_blank(raw)) return out;

  Json arr;
  try {
    arr = Json::parse(trail_points_json_text(raw));
  } catch (const std::exception& e) {
    CM_LOG_ERROR("sysutil") << "getTrailBoList parse failed: " << e.what();
    return out;
  }
  if (!arr.is_array()) return out;

  std::vector<Json> parsed;
  parsed.reserve(arr.size());
  try {
    for (const auto& elem : arr) {
      Json tb = empty_trail_bo();
      if (!elem.is_object()) {
        parsed.push_back(std::move(tb));
        continue;
      }
      std::string capture = jstr(elem, "captureTime");
      if (!capture.empty()) {
        if (capture.size() > 10 && capture[10] == 'T') capture[10] = ' ';
        if (capture.size() > 19) capture = capture.substr(0, 19);
        set_str(tb, "captureTime", capture);
      }
      for (const char* k : {"stateType", "platenumber", "locationId", "locationCode",
                            "pointUuid", "sectionCode", "orgCode", "pileNo", "devCode",
                            "devName", "imagesArry", "preCaptureTime", "isVirtual",
                            "direction", "directionIn", "pileno", "platecolor", "roadCode"}) {
        if (elem.contains(k) && !elem[k].is_null()) tb[k] = elem[k];
      }
      for (const char* k : {"lon", "lat"}) {
        if (elem.contains(k) && !elem[k].is_null()) {
          tb[k] = elem[k].is_string() ? json_number_or_null(elem[k].get<std::string>()) : elem[k];
        }
      }
      if (elem.contains("countNum") && !elem["countNum"].is_null()) tb["countNum"] = elem["countNum"];
      parsed.push_back(std::move(tb));
    }
  } catch (const std::exception& e) {
    CM_LOG_ERROR("sysutil") << "getTrailBoList field convert failed: " << e.what();
  }
  out = map_trail_bo_list(std::move(parsed));
  return out;
}

// ---------------------------------------------------------------------------
// 图片辅助（CommonUtil.deleteEnd / deleteStart / repalacePicUrl）
// ---------------------------------------------------------------------------
std::string delete_start(const std::string& s) {
  if (cm::utils::is_blank(s)) return "";
  std::string v = cm::utils::replace_all(s, "\\/", "/");
  auto idx = v.find_first_of(',');
  if (idx != std::string::npos && idx > 0) return v.substr(idx + 1);
  return v;
}

const Json* map_get(const MapJson& m, const std::string& key) {
  if (key.empty()) return nullptr;
  auto it = m.find(key);
  return it == m.end() ? nullptr : &it->second;
}

const Json* nested(const Json& o, const char* key) {
  auto it = o.find(key);
  if (it == o.end() || !it->is_object()) return nullptr;
  return &*it;
}

// ---------------------------------------------------------------------------
// changeData 的经纬度赋值：照搬 Java 原代码
//   BigDecimal lat = trailBo.getLon();  // 原代码 bug，纬度实际取经度
// 分支内只更新 lon，最终 setLat(lat)，因此 lat 等于该轨迹点原来的 lon。
// ---------------------------------------------------------------------------
void set_lon_with_lat_bug(Json& tb, const Json& lon_val, const Json& lat_var) {
  if (lon_val.is_null() || json_text(lon_val).empty()) return;
  tb["lon"] = lon_val;
  tb["lat"] = lat_var;
}

// ---------------------------------------------------------------------------
// changeData（SysUtilServiceImpl#changeData）
// ---------------------------------------------------------------------------
Json change_data(Json tracks, std::vector<Json> trail_list) {
  const MapJson gantry_dict = gantry_map();
  const MapJson gantry_ip_dict = gantry_ip_map();
  const MapJson toll_dict = toll_map();
  const MapJson station_ip_dict = station_ip_map();
  const MapJson location_dict = location_dict_map();
  const MapJson section_dict = section_map();

  Json jwd_list = Json::array();

  for (auto& tb : trail_list) {
    const std::string type = jstr(tb, "stateType");
    const std::string location_code = jstr(tb, "locationCode");

    // sectionCode -> roadCode
    const std::string section_code = jstr(tb, "sectionCode");
    if (!section_code.empty()) {
      if (const Json* sec = map_get(section_dict, section_code)) {
        set_str_if(tb, "roadCode", jstr(*sec, "roadCode"));
      }
    }

    // Java bug：lat 取自 trailBo.getLon()
    const Json lat_var = jget(tb, "lon");

    if (type == kStateBorderWeighing) {
      Json wm = weight_capture_map(jstr(tb, "pointUuid"));
      const std::string uuid = jstr(tb, "pointUuid");
      if (!uuid.empty() && wm.is_object() && wm.contains(uuid)) {
        const Json& rec = wm[uuid];
        std::string capture = jstr(rec, "snapshottime");
        if (capture.empty()) capture = jstr(rec, "checkTime");
        if (!capture.empty()) set_str(tb, "captureTime", local_datetime_text(capture));

        std::string gantry_code = jstr(rec, "gantrycode");
        if (gantry_code.empty()) gantry_code = jstr(rec, "siteId");
        if (const Json* g = map_get(gantry_dict, gantry_code)) {
          set_str_if(tb, "devName", jstr(*g, "gantryName"));
        }
        // 称重照片
        if (jblank(tb, "imagesArry")) {
          std::string imgs = jstr(rec, "weighingImagesArry");
          if (!imgs.empty()) set_str(tb, "imagesArry", cm::utils::delete_end(imgs));
        }
      }
    } else if (type == kGantryCapture) {
      if (const Json* ip = map_get(gantry_ip_dict, location_code)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          set_str_if(tb, "devName", jstr(*g, "gantryName"));
          set_str_if(tb, "isVirtual", jstr(*g, "isVirtual"));
          set_str_if(tb, "direction", jstr(*g, "direction"));
          Json direction_in = jget(*ip, "directionIn");
          if (!direction_in.is_null()) tb["directionIn"] = direction_in;
          set_lon_with_lat_bug(tb, jget(*g, "lon"), lat_var);
        }
      }
    } else if (type == kProvCapture) {
      if (const Json* ip = map_get(gantry_ip_dict, location_code)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          set_str_if(tb, "isVirtual", jstr(*g, "isVirtual"));
          set_str_if(tb, "direction", jstr(*g, "direction"));
        }
        Json direction_in = jget(*ip, "directionIn");
        if (!direction_in.is_null()) tb["directionIn"] = direction_in;
      }
    } else if (type == kStationCapture) {
      if (const Json* ip = map_get(station_ip_dict, location_code)) {
        set_str_if(tb, "devCode", jstr(*ip, "tollCode"));
        set_str_if(tb, "devName", jstr(*ip, "tollName"));
        if (const Json* toll = nested(*ip, "odsSzdnToll")) {
          set_lon_with_lat_bug(tb, json_number_or_null(jstr(*toll, "longitude")), lat_var);
        }
      }
    } else if (type == kFeeRecord) {
      set_str(tb, "locationName", jstr(tb, "devName"));
    } else if (type == kFeeStationEnter || type == kFeeStationExit) {
      if (const Json* toll = map_get(toll_dict, location_code)) {
        set_str_if(tb, "devName", jstr(*toll, "tollName"));
        set_str_if(tb, "orgCode", jstr(*toll, "orgCode"));
        set_lon_with_lat_bug(tb, json_number_or_null(jstr(*toll, "longitude")), lat_var);
      }
    } else if (type == kServiceAreaCapture) {
      const std::string code = cm::utils::replace_all(location_code, "devip:", "serviceip:");
      if (const Json* loc = map_get(location_dict, code)) {
        set_str_if(tb, "devCode", jstr(*loc, "rawCode"));
        set_str_if(tb, "devName", jstr(*loc, "name"));
        set_str_if(tb, "roadCode", jstr(*loc, "roadcode"));
        set_str_if(tb, "sectionCode", jstr(*loc, "sectioncode"));
        set_str_if(tb, "direction", jstr(*loc, "direction"));
        set_str_if(tb, "pileno", jstr(*loc, "pileNo"));
        set_lon_with_lat_bug(tb, json_number_or_null(jstr(*loc, "longitude")), lat_var);
      }
    }

    // Java 在所有分支末尾统一执行
    if (jblank(tb, "devName")) {
      set_str(tb, "devName", cm::utils::replace_all(location_code, "serviceip:", ""));
    }

    Json lon_now = jget(tb, "lon");
    Json lat_now = jget(tb, "lat");
    if (!lon_now.is_null() && !lat_now.is_null()) {
      Json p = Json::object();
      p["lon"] = lon_now;
      p["lat"] = lat_now;
      p["stateType"] = jstr(tb, "stateType");
      p["locationCode"] = jstr(tb, "locationCode");
      jwd_list.push_back(std::move(p));
    }
  }

  // Java 无条件覆盖的字段
  set_str(tracks, "plateColor", "");
  set_str(tracks, "carType", "");
  set_str(tracks, "carVehicle", "");
  set_str(tracks, "passType", "");
  set_null(tracks, "carNum");

  const std::string flag = jstr(tracks, "flag");
  if (flag == "currentTrack") {
    if (!jwd_list.empty()) {
      const Json& front = jwd_list.front();
      const Json& back = jwd_list.back();
      set_str(tracks, "startLon", json_text(jget(front, "lon")));
      set_str(tracks, "stratLat", json_text(jget(front, "lat")));
      set_dec_from(tracks, "startLonDec", "startLon");
      set_dec_from(tracks, "stratLatDec", "stratLat");
      set_str(tracks, "endLon", json_text(jget(back, "lon")));
      set_str(tracks, "endLat", json_text(jget(back, "lat")));
      set_dec_from(tracks, "endLonDec", "endLon");
      set_dec_from(tracks, "endLatDec", "endLat");
    }
  } else {
    const std::string first_code = jstr(tracks, "entollstationid");
    const std::string first_name =
        cm::utils::repalace_szdn_toll_name(jstr(tracks, "entollstationname"));
    const std::string end_code = jstr(tracks, "extollstationid");
    const std::string end_name =
        cm::utils::repalace_szdn_toll_name(jstr(tracks, "extollstationname"));

    if (!first_code.empty()) {
      if (const Json* toll = map_get(toll_dict, first_code)) {
        if (!jblank(*toll, "longitude")) set_str(tracks, "startLon", jstr(*toll, "longitude"));
        if (!jblank(*toll, "latitude")) set_str(tracks, "stratLat", jstr(*toll, "latitude"));
        set_str(tracks, "entollstationid", first_code);
      } else if (const Json* ip = map_get(gantry_ip_dict, first_code)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          if (!jblank(*g, "lon")) set_str(tracks, "startLon", jstr(*g, "lon"));
          if (!jblank(*g, "lat")) set_str(tracks, "stratLat", jstr(*g, "lat"));
          set_str(tracks, "entollstationid", jstr(*g, "gantryCode"));
        }
      }
    }
    if (!end_code.empty()) {
      if (const Json* toll = map_get(toll_dict, end_code)) {
        if (!jblank(*toll, "longitude")) set_str(tracks, "endLon", jstr(*toll, "longitude"));
        if (!jblank(*toll, "latitude")) set_str(tracks, "endLat", jstr(*toll, "latitude"));
        set_str(tracks, "extollstationid", end_code);
      } else if (const Json* ip = map_get(gantry_ip_dict, end_code)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          if (!jblank(*g, "lon")) set_str(tracks, "endLon", jstr(*g, "lon"));
          if (!jblank(*g, "lat")) set_str(tracks, "endLat", jstr(*g, "lat"));
          set_str(tracks, "extollstationid", jstr(*g, "gantryCode"));
        }
      }
    }
    if (jblank(tracks, "startLon") && !first_name.empty()) {
      if (const Json* st = map_get(station_ip_dict, first_name)) {
        if (const Json* toll = nested(*st, "odsSzdnToll")) {
          if (!jblank(*toll, "longitude")) set_str(tracks, "startLon", jstr(*toll, "longitude"));
          if (!jblank(*toll, "latitude")) set_str(tracks, "stratLat", jstr(*toll, "latitude"));
        }
        set_str_if(tracks, "entollstationid", jstr(*st, "tollCode"));
      } else if (const Json* ip = map_get(gantry_ip_dict, first_name)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          if (!jblank(*g, "lon")) set_str(tracks, "startLon", jstr(*g, "lon"));
          if (!jblank(*g, "lat")) set_str(tracks, "stratLat", jstr(*g, "lat"));
          set_str(tracks, "entollstationid", jstr(*g, "gantryCode"));
        }
      }
    }
    if (jblank(tracks, "endLon") && !end_name.empty()) {
      if (const Json* st = map_get(station_ip_dict, end_name)) {
        if (const Json* toll = nested(*st, "odsSzdnToll")) {
          if (!jblank(*toll, "longitude")) set_str(tracks, "endLon", jstr(*toll, "longitude"));
          if (!jblank(*toll, "latitude")) set_str(tracks, "endLat", jstr(*toll, "latitude"));
        }
        set_str_if(tracks, "extollstationid", jstr(*st, "tollCode"));
      } else if (const Json* ip = map_get(gantry_ip_dict, end_name)) {
        if (const Json* g = nested(*ip, "odsSzdnGantry")) {
          if (!jblank(*g, "lon")) set_str(tracks, "endLon", jstr(*g, "lon"));
          if (!jblank(*g, "lat")) set_str(tracks, "endLat", jstr(*g, "lat"));
          set_str(tracks, "extollstationid", jstr(*g, "gantryCode"));
        }
      }
    }
    if (!jblank(tracks, "startLon")) {
      set_dec_from(tracks, "startLonDec", "startLon");
      set_dec_from(tracks, "stratLatDec", "stratLat");
    }
    if (!jblank(tracks, "endLon")) {
      set_dec_from(tracks, "endLonDec", "endLon");
      set_dec_from(tracks, "endLatDec", "endLat");
    }
  }

  Json info = empty_trail_info();
  info["tracks"] = std::move(tracks);
  info["trailList"] = Json(std::move(trail_list));
  return info;
}

// ---------------------------------------------------------------------------
// getByTrailBo 依赖的缓存查询（对应 *ServiceImpl#selectByQueryUuids）
// ---------------------------------------------------------------------------
Json load_record(const std::string& redis_key, const cm::meta::EntityMeta& m,
                 const std::string& table, const std::string& id_col, const std::string& uuid,
                 const std::string& time_col, const std::string& apply1, const std::string& apply2,
                 const std::string& id_field) {
  auto& redis = cm::cache::Redis::instance();
  auto cached = redis.get(redis_key);
  if (cached && !cached->empty()) {
    try {
      Json j = Json::parse(*cached);
      if (j.is_object()) return j;
    } catch (...) {
      // Java 缓存为 FastJson2/JDK 序列化格式时无法直接解析，回源数据库并覆盖为 JSON。
      CM_LOG_WARN("sysutil") << "缓存不是 JSON，回源查询: " << redis_key;
    }
  }

  std::string sql = "SELECT * FROM " + table + " WHERE " + id_col + " = " + cm::repo::quote(uuid);
  if (!time_col.empty() && !apply1.empty() && !apply2.empty()) {
    sql += " AND " + time_col + " >= to_timestamp(" + cm::repo::quote(apply1) +
           ",'YYYY-MM-DD HH24:MI:SS') AND " + time_col +
           " <= to_timestamp(" + cm::repo::quote(apply2) + ",'YYYY-MM-DD HH24:MI:SS')";
  }
  sql += " LIMIT 1";

  Json obj;
  auto r = cm::db::PgPool::instance().query(sql);
  if (r.rows.empty()) {
    // Java 未命中时缓存一个只带查询键的占位对象
    obj = Json::object();
    obj[id_field] = uuid;
  } else {
    obj = cm::repo::project_row(m, r, 0);
  }
  redis.set(redis_key, json_dump(obj));
  return obj;
}

// SysUtilServiceImpl#getByTrailBo
Json get_by_trail_bo_impl(const Json& input) {
  Json tb = empty_trail_bo();
  if (input.is_object()) {
    for (auto it = input.begin(); it != input.end(); ++it) tb[it.key()] = it.value();
  }

  const std::string state = jstr(tb, "stateType");
  const std::string uuid = jstr(tb, "pointUuid");
  std::string day = jstr(tb, "captureTime").substr(0, 10);

  // STATION_CAPTURE 且 preCaptureTime 非空时，以该日期重算查询时间范围
  if (state == kStationCapture && !jblank(tb, "preCaptureTime")) {
    day = jstr(tb, "preCaptureTime").substr(0, 10);
  }
  const std::string apply1 = day.size() >= 10 ? day + " 00:00:00" : "";
  const std::string apply2 = day.size() >= 10 ? day + " 23:59:59" : "";

  std::string images_prefix;
  Json rec = Json(nullptr);

  if (uuid.empty()) {
    // 无 pointUuid 时不查任何流水，直接返回入参对象
  } else if (state == kStateBorderWeighing) {
    Json wm = weight_capture_map(uuid);
    if (wm.is_object() && wm.contains(uuid)) {
      rec = wm[uuid];
      std::string img = jstr(rec, "weighingImagesArry");
      if (!img.empty()) images_prefix = "\"" + cm::utils::delete_end(img);
      set_str_if(tb, "platecolor", jstr(rec, "plateColor"));
    }
  } else if (state == kGantryCapture) {
    rec = load_record(std::string(kDateGantryCapture) + uuid,
                      cm::meta::odsRtSzdnSnapshotFlowAddcode,
                      "jl_data01.ods_rt_szdn_snapshot_flow_addcode", "datauuid", uuid,
                      "snapshottime", apply1, apply2, "datauuid");
    set_str_if(tb, "locationCode", jstr(rec, "gantrycode"));
    set_str_if(tb, "longitude", json_text(jget(rec, "lon")));
    set_str_if(tb, "latitude", json_text(jget(rec, "lat")));
    set_str_if(tb, "platecolor", jstr(rec, "platecolor"));
    std::string img = jstr(rec, "snappicturepath");
    if (!img.empty()) images_prefix = "\"" + cm::utils::delete_end(img);
  } else if (state == kProvCapture) {
    rec = load_record(std::string(kDateProvCapture) + uuid,
                      cm::meta::odsRtSzdnSnapshotFlowProvcaptureAddcode,
                      "jl_data01.ods_rt_szdn_snapshot_flow_provcapture_addcode", "datauuid",
                      uuid, "", "", "", "datauuid");
    set_str_if(tb, "locationCode", jstr(rec, "gantryid"));
    set_str_if(tb, "platecolor", jstr(rec, "platecolor"));
    std::string merged;
    for (const char* k : {"headimage", "sideimage", "plateimage", "tailimage"}) {
      std::string v = jstr(rec, k);
      if (v.empty()) continue;
      merged += "\"" + v;
    }
    if (!merged.empty()) images_prefix = "\"" + delete_start(merged);
  } else if (state == kServiceAreaCapture) {
    rec = load_record(std::string(kDateServiceAreaCapture) + uuid, cm::meta::odsCxztFwqclls,
                      "jl_data01.ods_cxzt_fwqclls", "datauuid", uuid, "", "", "", "datauuid");
    set_str_if(tb, "platecolor", jstr(rec, "platecolor"));
    std::string img = jstr(rec, "platepicurl");
    if (img.empty()) img = jstr(rec, "targetpicurl");
    if (!img.empty()) images_prefix = "\"" + cm::utils::delete_end(img);
  } else if (state == kStationCapture) {
    rec = load_record(std::string(kDateStationCapture) + uuid,
                      cm::meta::odsRtSzdnSnapshotFlowStationcaptureAddcode,
                      "jl_data01.ods_rt_szdn_snapshot_flow_stationcapture_addcode", "datauuid",
                      uuid, "snapshottime", apply1, apply2, "datauuid");
    set_str_if(tb, "locationCode", jstr(rec, "tollcode"));
    set_str_if(tb, "locationName", jstr(rec, "tollname"));
    set_str_if(tb, "platecolor", jstr(rec, "platecolor"));
    std::string img = jstr(rec, "snappicturepath");
    if (!img.empty()) images_prefix = "\"" + cm::utils::delete_end(img);
  }

  const std::string images = jstr(tb, "imagesArry");
  std::string images_new = images_prefix + images;
  set_str(tb, "imagesArry", cm::utils::repalace_pic_url(cm::utils::delete_end(images_new)));
  return tb;
}

// 统计指定 stateType 的数量
int count_state(const std::vector<Json>& list, const char* type) {
  int n = 0;
  for (const auto& b : list) {
    if (jstr(b, "stateType") == type) ++n;
  }
  return n;
}

bool code_in(const std::vector<std::string>& codes, const std::string& value) {
  if (value.empty()) return false;
  return std::find(codes.begin(), codes.end(), value) != codes.end();
}

// 存在虚拟门架时返回 false（对应 getIsVirtualFlag 的返回语义为 true 表示全部真实）
bool is_virtual_ok(const std::vector<Json>& list) {
  for (const auto& b : list) {
    if (jstr(b, "stateType") == kGantryCapture && jstr(b, "isVirtual") == "1") return false;
  }
  return true;
}

// getPlateColor：取第一个门架抓拍（countNum==0）的 platecolor 后 break
std::string plate_color_of(const std::vector<Json>& list) {
  for (const auto& b : list) {
    if (jstr(b, "stateType") != kGantryCapture) continue;
    std::string count = jstr(b, "countNum");
    if (count.empty() || count == "0") return jstr(get_by_trail_bo_impl(b), "platecolor");
    break;
  }
  return "";
}

// ---------------------------------------------------------------------------
// 轨迹查询参数（CarParaVO）与 SQL
// ---------------------------------------------------------------------------
struct Para {
  std::string car_no;
  std::string apply1;
  std::string apply2;
  std::string flag;
  std::vector<std::string> car_no_list;
  std::vector<std::string> section_list;
};

struct PageReq {
  long long num = 1;
  long long size = 10;
  std::string order_by;
};

PageReq page_of(const cm::http::Request& req) {
  PageReq p;
  p.num = req.int_or("pageNum", 1);
  p.size = req.int_or("pageSize", 10);
  if (p.num < 1) p.num = 1;
  if (p.size < 1) p.size = 10;
  p.order_by = cm::repo::resolve_page(req).order_by;
  return p;
}

Para para_from_req(const cm::http::Request& req) {
  Para p;
  p.car_no = req.str("carNo");
  p.apply1 = req.str("applyTime1");
  p.apply2 = req.str("applyTime2");
  p.flag = req.str("flag");
  return p;
}

std::string history_select() {
  return "SELECT t.cid AS uuid, t.envehicleid AS platekey, t.enaxlecount AS enaxlecount,"
         " t.entime AS entertime, t.entolllaneid AS entolllaneid,"
         " t.entollstationid AS entollstationid, t.entollstationname AS entollstationname,"
         " t.envehicleclass AS envehicleclass, t.envehicleid AS envehicleid,"
         " t.envehicletype AS envehicletype, t.enweight AS enweight,"
         " t.extime AS exittime, t.extolllaneid AS extolllaneid,"
         " t.extollstationid AS extollstationid, t.extollstationname AS extollstationname,"
         " t.exvehicleclass AS exvehicleclass, t.exvehicleid AS exvehicleid,"
         " t.exvehicletype AS exvehicletype, t.exweight AS exweight,"
         " t.trailpoints AS trailpoints FROM jl_data01.zdata_trail_fitting t";
}

std::string history_where(const Para& p) {
  std::string w = " WHERE 1=1";
  if (!p.car_no.empty()) w += " AND t.envehicleid = " + cm::repo::quote(p.car_no);
  if (!p.apply1.empty())
    w += " AND t.extime >= to_timestamp(" + cm::repo::quote(p.apply1) +
         ",'YYYY-MM-DD HH24:MI:SS')";
  if (!p.apply2.empty())
    w += " AND t.extime <= to_timestamp(" + cm::repo::quote(p.apply2) +
         ",'YYYY-MM-DD HH24:MI:SS')";
  if (p.flag == "bannian") w += " AND t.extime >= now()-180 AND t.extime <= now()";
  if (p.flag == "yiyue") w += " AND t.extime >= now()-3 AND t.extime <= now()";
  if (!p.car_no_list.empty()) w += " AND t.envehicleid IN " + cm::repo::in_list(p.car_no_list);
  return w;
}

std::string latest_select() {
  return history_select() + ", t.trailtype AS trailtype";
}

std::string latest_where(const Para& p) {
  std::string w = " WHERE 1=1";
  if (p.flag == "jiandong") {
    w += " AND EXISTS (SELECT 1 FROM jl_data01.ods_szdn_toll sip WHERE (sip.toll_code ="
         " t.entollstationid OR sip.toll_code = t.extollstationid)"
         " AND sip.org_code = '030000011')";
  }
  if (p.flag == "ksqcpb") w += " AND t.trailtype = 0";
  if (p.flag == "ldtf") {
    w += " AND t.trailtype = 1";
    if (!p.section_list.empty()) {
      w += " AND EXISTS (SELECT 1 FROM UNNEST(t.trailpoints) AS elem"
           " WHERE (elem::json->>'sectionCode') IN " + cm::repo::in_list(p.section_list) + ")";
    }
  }
  if (!p.apply1.empty())
    w += " AND t.extime >= to_timestamp(" + cm::repo::quote(p.apply1) +
         ",'YYYY-MM-DD HH24:MI:SS')";
  if (!p.apply2.empty())
    w += " AND t.extime <= to_timestamp(" + cm::repo::quote(p.apply2) +
         ",'YYYY-MM-DD HH24:MI:SS')";
  return w;
}

Json num_or_null_from_row(const cm::db::PgResult& r, std::size_t row, const char* col) {
  auto v = r.get(row, col);
  if (!v || v->empty()) return Json(nullptr);
  return json_number_or_null(*v);
}

// mapper 列 -> ZdataTrailTracks JSON（字段顺序与 Java 实体一致）
Json tracks_from_row(const cm::db::PgResult& r, std::size_t row) {
  Json o = empty_tracks();
  set_str(o, "uuid", r.get(row, "uuid").value_or(""));
  set_str(o, "plateKey", r.get(row, "platekey").value_or(""));

  o["enaxlecount"] = num_or_null_from_row(r, row, "enaxlecount");
  for (const char* c : {"entolllaneid", "entollstationid", "entollstationname", "envehicleclass",
                        "envehicleid", "envehicletype", "extolllaneid", "extollstationid",
                        "extollstationname", "exvehicleclass", "exvehicleid", "exvehicletype"}) {
    set_str(o, c, r.get(row, c).value_or(""));
  }
  o["enweight"] = num_or_null_from_row(r, row, "enweight");
  o["exweight"] = num_or_null_from_row(r, row, "exweight");

  auto et = parse_time(r.get(row, "entertime").value_or(""));
  if (et) set_str(o, "enterTime", cm::timeutil::format_datetime(*et)); else set_null(o, "enterTime");
  auto xt = parse_time(r.get(row, "exittime").value_or(""));
  if (xt) set_str(o, "exitTime", cm::timeutil::format_datetime(*xt)); else set_null(o, "exitTime");

  set_str(o, "trailPoints", r.get(row, "trailpoints").value_or(""));
  if (r.get(row, "trailtype") && !r.get(row, "trailtype")->empty()) {
    set_str(o, "trailtype", *r.get(row, "trailtype"));
  }
  return o;
}

std::vector<Json> query_tracks(const std::string& select, const std::string& where,
                               const std::string& order, long long limit, long long offset) {
  std::string sql = select + where;
  if (!order.empty()) sql += " ORDER BY " + order;
  sql += " LIMIT " + std::to_string(limit) + " OFFSET " + std::to_string(offset);
  auto r = cm::db::PgPool::instance().query(sql);
  std::vector<Json> out;
  out.reserve(r.rows.size());
  for (std::size_t i = 0; i < r.rows.size(); ++i) out.push_back(tracks_from_row(r, i));
  return out;
}

long long count_history(const Para& p) {
  auto r = cm::db::PgPool::instance().query(
      "SELECT count(1) AS c FROM jl_data01.zdata_trail_fitting t" + history_where(p));
  if (r.rows.empty()) return 0;
  try {
    return std::stoll(r.rows[0][0].value_or("0"));
  } catch (...) {
    return 0;
  }
}

std::vector<Json> history_tracks(const Para& p, const PageReq& page, long long& total) {
  total = count_history(p);
  long long pages = page.size > 0 ? (total + page.size - 1) / page.size : 0;
  long long num = page.num;
  if (pages > 0 && num > pages) num = pages; // 与项目 PageHelper reasonable 语义一致

  std::string sql = history_select() + history_where(p);
  if (!page.order_by.empty()) sql += " ORDER BY " + page.order_by;
  long long offset = (num - 1) * page.size;
  sql += " LIMIT " + std::to_string(page.size) + " OFFSET " + std::to_string(offset);

  auto r = cm::db::PgPool::instance().query(sql);
  std::vector<Json> out;
  out.reserve(r.rows.size());
  for (std::size_t i = 0; i < r.rows.size(); ++i) out.push_back(tracks_from_row(r, i));
  return out;
}

// SysUtilController#carTrackQueryByCarNo / carTrackQueryByTime 的公共转换
std::vector<Json> decorate_tracks(const std::vector<Json>& list, bool clear_points) {
  std::vector<Json> out;
  out.reserve(list.size());
  for (auto tracks : list) {
    const std::string car_no = jstr(tracks, "plateKey");
    const std::string points = jstr(tracks, "trailPoints");
    if (cm::utils::is_blank(points)) continue;
    auto trail_list = get_trail_bo_list(points);
    if (clear_points) set_str(tracks, "trailPoints", "");
    Json info = change_data(tracks, trail_list);
    set_str(info, "trailUuid", car_no);
    out.push_back(std::move(info));
  }
  return out;
}

// ---------------------------------------------------------------------------
// Redis 列表辅助（对应 RedisCache.getCacheObject/setCacheObject）
// ---------------------------------------------------------------------------
Json read_array(const std::string& key) {
  auto v = cm::cache::Redis::instance().get(key);
  if (!v || v->empty()) return Json::array();
  try {
    Json j = Json::parse(*v);
    if (j.is_array()) return j;
  } catch (...) {
    // Java 写入的是 FastJson2/JDK 序列化数据，键名相同但值格式不同。
    CM_LOG_WARN("sysutil") << "Redis 值不是 JSON 数组: " << key;
  }
  return Json::array();
}

void append_array_item(const std::string& key, const Json& item) {
  Json arr = read_array(key);
  arr.push_back(item);
  cm::cache::Redis::instance().set(key, json_dump(arr));
}

std::string cached_scalar(const std::string& key, const std::string& def) {
  auto v = cm::cache::Redis::instance().get(key);
  if (!v || v->empty()) return def;
  std::string s = *v;
  if (s.size() >= 2 && s.front() == '"' && s.back() == '"') {
    try {
      return Json::parse(s).get<std::string>();
    } catch (...) {
    }
  }
  return s;
}

int cached_int(const std::string& key, int def) {
  std::string s = cached_scalar(key, "");
  if (s.empty()) return def;
  try {
    return std::stoi(s);
  } catch (...) {
    return def;
  }
}

void delete_keys(const std::string& pattern) {
  auto& redis = cm::cache::Redis::instance();
  for (const auto& key : redis.keys(pattern)) redis.del(key);
}

// ---------------------------------------------------------------------------
// isFeeRecordsExist：门架牌识连续轨迹判定为“路段全程屏蔽”
// ---------------------------------------------------------------------------
void is_fee_records_exist(const std::string& key, const std::vector<Json>& snapshot_list,
                          int road_supoer_mjnum, const std::string& redis_date) {
  if (cm::utils::is_blank(key) || snapshot_list.empty()) return;
  if (static_cast<int>(snapshot_list.size()) < road_supoer_mjnum) return;
  if (snapshot_list.size() < 2) return;

  auto parts = cm::utils::split(key, ':');
  if (parts.size() <= 1) return;

  const Json& first = snapshot_list.front();
  const Json& last = snapshot_list.back();
  auto start_tp = parse_time(jstr(first, "snapshottime"));
  auto end_tp = parse_time(jstr(last, "snapshottime"));
  if (!start_tp || !end_tp) return;

  const std::string start_time = cm::timeutil::format_naive_plus8(*start_tp);
  const std::string end_time = cm::timeutil::format_naive_plus8(*end_tp);
  const long long start_long = cm::timeutil::to_millis(*start_tp);
  const long long end_long = cm::timeutil::to_millis(*end_tp);

  const std::string road_car_key = parts[1];
  const std::string section_code = jstr(first, "sectioncode");
  std::string section_name;
  std::string road_code;
  if (const Json* sec = map_get(section_map(), section_code)) {
    section_name = jstr(*sec, "sectionName");
    road_code = jstr(*sec, "roadCode");
  }

  // 该路段当天已有成功交易则跳过
  Json old_fee = read_array(std::string(kFeeRecordsList) + redis_date + ":" + road_car_key);
  bool add = true;
  if (!old_fee.empty()) {
    int free_count = 0;
    for (const auto& fee : old_fee) {
      auto tp = parse_time(jstr(fee, "transtime"));
      if (!tp) continue;
      long long m = cm::timeutil::to_millis(*tp);
      if (m < start_long || m > end_long) continue;
      double fee_value = 0;
      try {
        fee_value = std::stod(jstr(fee, "fee"));
      } catch (...) {
        fee_value = 0;
      }
      if (fee_value > 0) ++free_count;
    }
    add = free_count == 0;
  }
  if (!add) return;

  const std::string car_no = jstr(first, "platenumber");

  // 已生成过轨迹则跳过
  Json old_fitting = read_array(std::string(kTrailFittingList) + redis_date + ":" + car_no);
  int trail_fitting = 0;
  for (const auto& fit : old_fitting) {
    auto in = parse_time(jstr(fit, "enterTime"));
    auto out = parse_time(jstr(fit, "exitTime"));
    if (!in || !out) continue;
    long long in_ms = cm::timeutil::to_millis(*in);
    long long out_ms = cm::timeutil::to_millis(*out);
    if (end_long >= in_ms && end_long <= out_ms) ++trail_fitting;
  }
  if (trail_fitting != 0) return;

  const std::string start_gantry = jstr(first, "gantrycode");
  const std::string end_gantry = jstr(last, "gantrycode");
  const std::string platecolor = jstr(first, "platecolor");

  Json tracks = empty_tracks();
  set_str(tracks, "uuid", cm::utils::uuid32());
  set_str(tracks, "plateKey", car_no);
  set_str(tracks, "enterTime", start_time);
  set_str(tracks, "entollstationid", start_gantry);
  if (const Json* g = map_get(gantry_map(), start_gantry))
    set_str(tracks, "entollstationname", jstr(*g, "gantryName"));
  if (!jstr(first, "lon").empty()) set_str(tracks, "startLon", jstr(first, "lon"));
  if (!jstr(first, "lat").empty()) set_str(tracks, "stratLat", jstr(first, "lat"));
  set_str(tracks, "envehicletype", jstr(first, "cartypecode"));
  set_str(tracks, "envehicleid", car_no);
  set_str(tracks, "exitTime", end_time);
  set_str(tracks, "extollstationid", end_gantry);
  if (const Json* g = map_get(gantry_map(), end_gantry))
    set_str(tracks, "extollstationname", jstr(*g, "gantryName"));
  if (!jstr(last, "lon").empty()) set_str(tracks, "endLon", jstr(last, "lon"));
  if (!jstr(last, "lat").empty()) set_str(tracks, "endLat", jstr(last, "lat"));
  set_str(tracks, "exvehicleid", car_no);
  if (!jblank(tracks, "startLon")) {
    set_dec_from(tracks, "startLonDec", "startLon");
    set_dec_from(tracks, "stratLatDec", "stratLat");
  }
  if (!jblank(tracks, "endLon")) {
    set_dec_from(tracks, "endLonDec", "endLon");
    set_dec_from(tracks, "endLatDec", "endLat");
  }

  std::vector<Json> trail_list;
  trail_list.reserve(snapshot_list.size());
  const MapJson gantry_dict = gantry_map();
  for (const auto& snapshot_bo : snapshot_list) {
    Json tb = empty_trail_bo();
    const std::string gantry_code = jstr(snapshot_bo, "gantrycode");
    set_str(tb, "stateType", kGantryCapture);
    set_str(tb, "platenumber", jstr(snapshot_bo, "platenumber"));
    set_str(tb, "locationId", gantry_code);
    set_str(tb, "locationCode", gantry_code);
    set_str(tb, "pointUuid", jstr(snapshot_bo, "datauuid"));
    set_str(tb, "sectionCode", jstr(snapshot_bo, "sectioncode"));
    std::string capture = local_datetime_text(jstr(snapshot_bo, "snapshottime"));
    if (!capture.empty()) set_str(tb, "captureTime", capture);
    set_str(tb, "devCode", gantry_code);
    if (const Json* g = map_get(gantry_dict, gantry_code)) {
      set_str_if(tb, "pileno", jstr(*g, "pileNo"));
      set_lon_with_lat_bug(tb, jget(*g, "lon"), jget(*g, "lat"));
      set_str_if(tb, "devName", jstr(*g, "gantryName"));
    }
    if (jblank(tb, "devName")) set_str(tb, "devName", gantry_code);
    set_str_if(tb, "roadCode", road_code);
    trail_list.push_back(std::move(tb));
  }

  const std::string remark = section_name + "路段全程屏蔽：其中门架牌识流水数量:" +
                             std::to_string(snapshot_list.size()) +
                             "，门架交易成功流水数量:0。";
  set_str(tracks, "escapedTypeRemark", remark);
  set_str(tracks, "escapedType", kEscapedType20);
  set_str(tracks, "escapedTfcj", "3");
  set_str(tracks, "plateColor", platecolor);

  Json info = empty_trail_info();
  info["trailUuid"] = car_no;
  info["tracks"] = tracks;
  info["trailList"] = Json(trail_list);

  if (is_virtual_ok(trail_list)) {
    const std::string suspicious_key = std::string(kCarSuspicious) + redis_date + ":" + car_no;
    if (!cm::cache::Redis::instance().exists(suspicious_key)) {
      cm::cache::Redis::instance().set(suspicious_key, info.dump());
    }
  }
}

// getSuspiciousKey(redisDate, carNo)
std::string suspicious_key(const std::string& redis_date, const std::string& car_no) {
  return std::string(kCarSuspicious) + redis_date + ":" + car_no;
}

// ---------------------------------------------------------------------------
// syncTrack / syncHistroyTrack 的公共实现
// ---------------------------------------------------------------------------
void sync_trail_from_keys(const std::string& prefix, const std::string& flag, bool clear_points,
                          bool reset_enter_time, bool write_sync_time) {
  auto& redis = cm::cache::Redis::instance();
  for (const auto& key : redis.keys(prefix + "*")) {
    const std::string car_no = key.substr(prefix.size());
    if (car_no.empty()) continue;
    auto raw = redis.get(key);
    if (!raw || raw->empty()) continue;

    Json arr;
    try {
      arr = Json::parse(*raw);
    } catch (...) {
      // Java 侧为 FastJson2/JDK 序列化，无法解析时保留原键并跳过
      CM_LOG_WARN("sysutil") << "轨迹缓存不是 JSON，跳过: " << key;
      continue;
    }
    if (!arr.is_array()) continue;

    Json result = Json::array();
    for (auto& elem : arr) {
      if (!elem.is_object()) continue;
      Json tracks = elem;
      set_str(tracks, "plateKey", car_no);
      set_str(tracks, "uuid", cm::utils::uuid32());
      set_str(tracks, "flag", flag);
      if (reset_enter_time) set_null(tracks, "enterTime");

      std::string points = jstr(tracks, "trailPoints");
      std::vector<Json> trail_list;
      if (!cm::utils::is_blank(points)) {
        trail_list = get_trail_bo_list(points);
        if (clear_points) set_str(tracks, "trailPoints", "");
      }
      Json info = change_data(tracks, trail_list);

      // Java 写入的是 Map<ZdataTrailTracks, List<TrailBo>>（FastJson2 序列化）；
      // C++ 侧用数组 [{tracks, trailList}] 表达同样内容，键名保持一致。
      Json item = Json::object();
      item["tracks"] = info["tracks"];
      item["trailList"] = info["trailList"];
      result.push_back(std::move(item));
    }
    redis.set(std::string(kCarCurrentTrail) + car_no, json_dump(result));
    if (write_sync_time) {
      redis.set(std::string(kCarSyncTime) + car_no,
                cm::timeutil::format_naive_plus8(cm::timeutil::now()));
    }
    CM_LOG_INFO("sysutil") << "同步轨迹完成: " << car_no << " count=" << result.size();
  }
}

std::string pending_plate(const Json& event) {
  if (!event.is_object()) return "";
  for (const char* k : {"plate", "plateNo", "plateKey", "vehicleplate", "carNo"}) {
    std::string v = jstr(event, k);
    if (!v.empty()) return v;
  }
  Json inner = jget(event, "event");
  if (inner.is_object()) {
    for (const char* k : {"plate", "plateNo", "plateKey", "vehicleplate", "carNo"}) {
      std::string v = jstr(inner, k);
      if (!v.empty()) return v;
    }
  }
  return "";
}

std::string pending_time(const Json& event) {
  if (!event.is_object()) return "";
  for (const char* k : {"time", "captureTime", "snapshottime", "createTime"}) {
    std::string v = jstr(event, k);
    if (!v.empty()) return v;
  }
  return "";
}

} // namespace

// ===========================================================================
// TrackTask#syncBaseInfo：重建 7 类基础信息缓存
// ===========================================================================
void sync_base_info() {
  delete_keys(kGantryList);
  delete_keys(kGantryIp);
  delete_keys(kStationIp);
  delete_keys(kStationInfo);
  delete_keys(kSectionRoadMap);
  delete_keys(kDevPost);

  gantry_map();
  toll_map();
  section_map();
  location_dict_map();
  gantry_ip_map();
  station_ip_map();
  CM_LOG_INFO("sysutil") << "syncBaseInfo 完成";
}

// ===========================================================================
// TrackTask#syncCurrentTrack -> SysUtilServiceImpl#syncTrack
// ===========================================================================
void sync_current_track() {
  sync_trail_from_keys(kTrailPrefix, "currentTrack", true, true, false);
}

// ===========================================================================
// DataFlowTask#syncHistroyTrack
// ===========================================================================
void sync_histroy_track() {
  sync_trail_from_keys(kCarHistoryTrail, "yiyue", false, false, true);
}

// ===========================================================================
// MultiSourceDataFlowService#processPendingQueue
//
// Java 侧用 RedisTemplate（JDK 序列化）保存 dataflow:pending:* 与
// dataflow:trail:<plate>，C++ 无法反序列化 JDK 流；此处要求生产者写同键名 JSON，
// PendingEvent 字段（event/retryCount/createTime）保持不变。读不出来的键原样保留，
// 不会静默丢弃数据。
// ===========================================================================
void process_pending_queue() {
  auto& redis = cm::cache::Redis::instance();
  const std::string prefix = "dataflow:pending:";
  const std::string trail_prefix = "dataflow:trail:";
  const long long split_ms = 4LL * 60 * 60 * 1000; // needSplitTrail：4 小时切分

  for (const auto& key : redis.keys(prefix + "*")) {
    auto raw = redis.get(key);
    if (!raw || raw->empty()) continue;

    Json event;
    try {
      event = Json::parse(*raw);
    } catch (...) {
      CM_LOG_WARN("sysutil") << "pending 事件不是 JSON，保留待处理: " << key;
      continue;
    }

    const std::string plate = pending_plate(event);
    if (plate.empty()) {
      CM_LOG_WARN("sysutil") << "pending 事件缺少车牌，保留待处理: " << key;
      continue;
    }

    const std::string trail_key = trail_prefix + plate;
    Json trail = read_array(trail_key);

    if (!trail.empty()) {
      auto first_tp = parse_time(pending_time(trail.front()));
      auto now_tp = parse_time(pending_time(event));
      if (first_tp && now_tp &&
          cm::timeutil::to_millis(*now_tp) - cm::timeutil::to_millis(*first_tp) > split_ms) {
        // 超过 4 小时：归档旧轨迹段，开始新段（数据不丢）
        const std::string archive = trail_key + ":closed:" +
                                    std::to_string(cm::timeutil::to_millis(*first_tp));
        redis.set(archive, json_dump(trail));
        trail = Json::array();
      }
    }

    trail.push_back(event);
    redis.set(trail_key, json_dump(trail));
    redis.del(key);
  }
}

// ===========================================================================
// DataFlowTask#syncGantryCaptureData
// Java 方法体整体被注释，仅保留日志。
// ===========================================================================
void sync_gantry_capture_data() {
  CM_LOG_INFO("sysutil") << "syncGantryCaptureData：Java 方法体已注释，C++ 仅记录日志";
}

// ===========================================================================
// SysUtilServiceImpl#syncSuspiciousCarQutaz(index, index)
// ===========================================================================
void sync_suspicious_car(int index) {
  const int supoer_mjnum = cached_int(kSupoerMjnum, 5);
  const int road_supoer_mjnum = cached_int(kRoadSupoerMjnum, 3);
  int star_time = cached_int(kRedisTimeKey, 2);
  if (star_time <= 0) star_time = 2;

  const auto now = cm::timeutil::now();
  const std::string today = cm::timeutil::format_naive_plus8(now).substr(0, 10);
  const std::string query_date =
      cm::timeutil::format_naive_plus8(cm::timeutil::add_days(now, -star_time)).substr(0, 10);
  const std::string formatted_date = cm::utils::replace_all(today, "-", "");
  const std::string query_start = query_date + " 00:00:00";
  const std::string query_end = query_date + " 23:59:59";

  // Java 仅用 indexOf 判断节假日是否配置
  const std::string holiday = cached_scalar(kJholidayTime, "");
  const bool not_holiday = holiday.find(query_date) == std::string::npos;

  std::vector<std::string> section_list;
  for (const auto& kv : section_map()) {
    if (jstr(kv.second, "sectionCode") == kIndexSectionCode) section_list.push_back(kIndexSectionCode);
  }

  const std::string date_filter =
      " AND t.snapshottime >= to_timestamp(" + cm::repo::quote(query_start) +
      ",'YYYY-MM-DD HH24:MI:SS') AND t.snapshottime <= to_timestamp(" +
      cm::repo::quote(query_end) + ",'YYYY-MM-DD HH24:MI:SS')";

  auto save_suspicious = [&](Json tracks, const std::string& remark,
                             const std::string& escaped_tfcj) {
    const std::string car_no = jstr(tracks, "plateKey");
    std::vector<Json> trail_list = get_trail_bo_list(jstr(tracks, "trailPoints"));
    set_str(tracks, "trailPoints", "");

    Json info = change_data(tracks, trail_list);
    Json info_tracks = info["tracks"];
    if (is_virtual_ok(trail_list)) set_str(info_tracks, "plateColor", plate_color_of(trail_list));
    set_str(info_tracks, "escapedType", kEscapedType20);
    set_str(info_tracks, "escapedTypeRemark", remark);
    set_str(info_tracks, "escapedTfcj", escaped_tfcj);
    info["tracks"] = std::move(info_tracks);
    set_str(info, "trailUuid", car_no);
    cm::cache::Redis::instance().set(suspicious_key(formatted_date, car_no), info.dump());
  };

  for (int i = index; i <= index; ++i) {
    if (i <= 0) continue;

    // ---- 门架牌识流水 -> js_car_snapshot<date>:<sectioncode>@@<plate>
    std::string snapshot_sql =
        "SELECT * FROM jl_data01.ods_rt_szdn_snapshot_flow_addcode t WHERE 1=1" + date_filter;
    if (!section_list.empty()) snapshot_sql += " AND t.sectioncode IN " + cm::repo::in_list(section_list);
    snapshot_sql += " ORDER BY t.snapshottime LIMIT 2000 OFFSET " + std::to_string((i - 1) * 2000);

    auto snapshot_result = cm::db::PgPool::instance().query(snapshot_sql);
    for (std::size_t row = 0; row < snapshot_result.rows.size(); ++row) {
      Json rowj = cm::repo::project_row(cm::meta::odsRtSzdnSnapshotFlowAddcode, snapshot_result, row);
      if (jblank(rowj, "platenumber") || jstr(rowj, "snapshottime").empty()) continue;
      const std::string key = std::string(kSnapshotFlowList) + formatted_date + ":" +
                              jstr(rowj, "sectioncode") + "@@" + jstr(rowj, "platenumber");
      append_array_item(key, rowj);
    }

    // ---- 门架交易流水 -> js_car_reerecords<date>:<sectioncode>@@<plate>
    std::string fee_sql =
        "SELECT * FROM jl_data01.ods_lwzxsfsj_fee_records_01 t WHERE t.transtime >= to_timestamp(" +
        cm::repo::quote(query_start) +
        ",'YYYY-MM-DD HH24:MI:SS') AND t.transtime <= to_timestamp(" +
        cm::repo::quote(query_end) + ",'YYYY-MM-DD HH24:MI:SS')";
    if (!section_list.empty()) {
      fee_sql += " AND t.gantryid IN (SELECT g.gantry_code FROM jl_data01.ods_szdn_gantry g"
                 " WHERE g.section_code IN " +
                 cm::repo::in_list(section_list) + ")";
    }
    // Java 侧 feeRecords.setPlateColor("_1")：车牌字段带颜色后缀
    fee_sql += " AND t.vehicleplate LIKE '%_1' ORDER BY t.transtime LIMIT 2000 OFFSET " +
               std::to_string((i - 1) * 2000);

    auto fee_result = cm::db::PgPool::instance().query(fee_sql);
    for (std::size_t row = 0; row < fee_result.rows.size(); ++row) {
      Json rowj = cm::repo::project_row(cm::meta::odsLwzxsfsjFeeRecords01, fee_result, row);
      const std::string plate = jstr(rowj, "vehicleplate");
      if (cm::utils::contains(plate, "_")) {
        const std::vector<std::string> parts = cm::utils::split(plate, '_');
        if (!parts.empty() && !cm::utils::is_blank(parts[0])) {
          const std::string key = std::string(kFeeRecordsList) + formatted_date + ":" +
                                  jstr(rowj, "sectioncode") + "@@" + parts[0];
          append_array_item(key, rowj);
        }
      }
    }

    // ---- 当天轨迹 -> 可疑车辆
    Para para;
    para.apply1 = query_start;
    para.apply2 = query_end;
    auto tracks_all = query_tracks(latest_select(), latest_where(para), "t.cid, t.extime", 6000,
                                   (i - 1) * 6000);

    std::vector<Json> qspb;
    std::vector<Json> ldpb;
    for (auto& tracks : tracks_all) {
      const std::string trail_type = jstr(tracks, "trailtype");
      const std::string first_name = jstr(tracks, "entollstationname");
      const std::string end_name = jstr(tracks, "extollstationname");
      const std::string points = jstr(tracks, "trailPoints");

      if (trail_type == "0" && cm::utils::contains(first_name, "门架") &&
          cm::utils::contains(end_name, "门架")) {
        if (not_holiday) qspb.push_back(tracks);
        continue;
      }
      bool hit = false;
      for (const auto& code : section_list) {
        if (cm::utils::contains(points, code)) {
          hit = true;
          break;
        }
      }
      if (!hit) continue;

      if (not_holiday) ldpb.push_back(tracks);
      const std::string car_no = jstr(tracks, "plateKey");
      Json fitting = Json::object();
      fitting["plateKey"] = car_no;
      fitting["enterTime"] = jget(tracks, "enterTime");
      fitting["exitTime"] = jget(tracks, "exitTime");
      append_array_item(std::string(kTrailFittingList) + formatted_date + ":" + car_no, fitting);
    }

    // 跨省全程屏蔽
    for (auto& tracks : qspb) {
      auto trail_list = get_trail_bo_list(jstr(tracks, "trailPoints"));
      const int gantry_count = count_state(trail_list, kGantryCapture);
      const int fee_count = count_state(trail_list, kFeeRecord);
      if (gantry_count > supoer_mjnum && fee_count == 0) {
        const std::string remark = "跨省全程屏蔽：其中门架牌识流水数量:" +
                                   std::to_string(gantry_count) + "，门架交易流水数量:" +
                                   std::to_string(fee_count) + "。";
        save_suspicious(tracks, remark, "1");
      }
    }

    // 关注路段全程屏蔽
    for (auto& tracks : ldpb) {
      auto trail_list = get_trail_bo_list(jstr(tracks, "trailPoints"));
      int gantry_count = 0;
      int fee_count = 0;
      for (const auto& tb : trail_list) {
        if (!code_in(section_list, jstr(tb, "sectionCode"))) continue;
        if (jstr(tb, "stateType") == kGantryCapture) ++gantry_count;
        else if (jstr(tb, "stateType") == kFeeRecord) ++fee_count;
      }
      if (gantry_count > road_supoer_mjnum && fee_count == 0) {
        const std::string remark = std::string(kIndexSectionName) + "全程屏蔽：其中门架牌识流水数量:" +
                                   std::to_string(gantry_count) + "，门架交易流水数量:" +
                                   std::to_string(fee_count) + "。";
        save_suspicious(tracks, remark, "2");
      }
    }
  }
}

// ===========================================================================
// OdsSzdnGantryServiceImpl#saveGantryRedis
// ===========================================================================
void sync_ods_szdn_gantry() {
  auto& redis = cm::cache::Redis::instance();
  delete_keys(kGantryList);
  delete_keys(kGantryIp);

  const MapJson gantries = gantry_map();
  gantry_ip_map();
  for (const auto& kv : gantries) {
    redis.set(std::string(kGantryListData) + kv.first, kv.second.dump());
  }
  CM_LOG_INFO("sysutil") << "saveGantryRedis 完成 count=" << gantries.size();
}

// ===========================================================================
// SysUtilServiceImpl#separateSnapshotFlowTimeList
// ===========================================================================
Json separate_snapshot_flow_time_list(const cm::http::Request& req) {
  (void)req;
  const std::string redis_date = today_compact();
  int road_supoer_mjnum = cached_int(kRoadSupoerMjnum, 3);
  if (road_supoer_mjnum < 0) road_supoer_mjnum = 3;
  const long long one_hour_ms = 60LL * 60 * 1000;

  auto& redis = cm::cache::Redis::instance();
  const std::string pattern = std::string(kSnapshotFlowList) + redis_date + "*";

  for (const auto& key : redis.keys(pattern)) {
    Json raw = read_array(key);
    if (static_cast<int>(raw.size()) < road_supoer_mjnum) continue;

    std::vector<Json> list;
    list.reserve(raw.size());
    for (auto& item : raw) list.push_back(item);

    std::stable_sort(list.begin(), list.end(), [](const Json& a, const Json& b) {
      auto ta = parse_time(jstr(a, "snapshottime"));
      auto tb = parse_time(jstr(b, "snapshottime"));
      const long long ma = ta ? cm::timeutil::to_millis(*ta) : 0;
      const long long mb = tb ? cm::timeutil::to_millis(*tb) : 0;
      return ma < mb;
    });

    std::vector<Json> snapshot_list;
    long long previous = 0;
    for (std::size_t i = 0; i < list.size(); ++i) {
      auto tp = parse_time(jstr(list[i], "snapshottime"));
      const long long current = tp ? cm::timeutil::to_millis(*tp) : 0;
      if (i == 0) {
        snapshot_list.push_back(list[i]);
        previous = current;
        continue;
      }
      if (current - previous > one_hour_ms) {
        is_fee_records_exist(key, snapshot_list, road_supoer_mjnum, redis_date);
        snapshot_list.clear();
      }
      snapshot_list.push_back(list[i]);
      previous = current;
    }
    if (!snapshot_list.empty()) {
      is_fee_records_exist(key, snapshot_list, road_supoer_mjnum, redis_date);
    }
  }

  // 处理完成后清理当天三类临时键
  delete_keys(std::string(kSnapshotFlowList) + redis_date + "*");
  delete_keys(std::string(kFeeRecordsList) + redis_date + "*");
  delete_keys(std::string(kTrailFittingList) + redis_date + "*");

  CM_LOG_INFO("sysutil") << "separateSnapshotFlowTimeList 完成 date=" << redis_date;
  return cm::ajax_ok();
}

// ===========================================================================
// SysUtilController#saveRedis（Java 方法体已注释，直接返回 AjaxResult.success()）
// ===========================================================================
Json save_redis() { return cm::ajax_ok(); }

// ===========================================================================
// SysUtilController#carTrackQueryByCarNo
// ===========================================================================
Json car_track_query_by_car_no(const cm::http::Request& req) {
  const PageReq page = page_of(req);
  Para para = para_from_req(req);

  std::vector<Json> rows;
  long long total = 0;
  if (!cm::utils::is_blank(para.car_no)) {
    para.flag = "bannian";
    auto list = history_tracks(para, page, total);
    rows = decorate_tracks(list, true);
  }
  return cm::table_data(Json(std::move(rows)), total, cm::http_status::SUCCESS, "查询成功");
}

// ===========================================================================
// SysUtilController#carTrackQueryByTime
// ===========================================================================
Json car_track_query_by_time(const cm::http::Request& req) {
  const PageReq page = page_of(req);
  Para para = para_from_req(req);

  std::vector<Json> rows;
  long long total = 0;

  // Java 从 Redis car_list_jc 读取 List<CarVO>（FastJson2）；C++ 读取同键名 JSON。
  auto cached = cm::cache::Redis::instance().get(kCarListJC);
  std::vector<std::string> car_nos;
  if (cached && !cached->empty()) {
    try {
      Json arr = Json::parse(*cached);
      if (arr.is_array()) {
        for (const auto& car : arr) {
          std::string no = jstr(car, "carNo");
          if (!no.empty()) car_nos.push_back(no);
        }
      }
    } catch (...) {
      CM_LOG_WARN("sysutil") << "car_list_jc 不是 JSON（可能是 Java JDK 序列化），忽略";
    }
  }

  if (!car_nos.empty()) {
    para.car_no_list = car_nos;
    auto list = history_tracks(para, page, total);
    rows = decorate_tracks(list, false); // Java 此处未清空 trailPoints
  }
  return cm::table_data(Json(std::move(rows)), total, cm::http_status::SUCCESS, "查询成功");
}

// ===========================================================================
// SysUtilController#changeTrailInfo -> SysUtilServiceImpl#changeData
// ===========================================================================
Json change_trail_info(const Json& trail_info) {
  if (!trail_info.is_object()) return trail_info;

  Json tracks = jget(trail_info, "tracks");
  Json trail_list = jget(trail_info, "trailList");
  if (!tracks.is_object() || !trail_list.is_array() || trail_list.empty()) return trail_info;

  // startLon/stratLat/endLon/endLat 非空则转 BigDecimal 写入 *Dec
  set_dec_from(tracks, "startLonDec", "startLon");
  set_dec_from(tracks, "stratLatDec", "stratLat");
  set_dec_from(tracks, "endLonDec", "endLon");
  set_dec_from(tracks, "endLatDec", "endLat");

  std::vector<Json> list;
  list.reserve(trail_list.size());
  for (auto& item : trail_list) {
    item["isQuery"] = "1";
    list.push_back(item);
  }

  const std::string car_no = jstr(tracks, "plateKey");
  Json info = change_data(tracks, list);
  set_str(info, "trailUuid", car_no);
  return info;
}

// ===========================================================================
// SysUtilController#getByTrailBo
// ===========================================================================
Json get_by_trail_bo(const Json& trail_bo) { return get_by_trail_bo_impl(trail_bo); }

} // namespace cm::service
