#include "handler/handlers.h"

#include "common/datetime.h"
#include "common/logging.h"
#include "common/result.h"
#include "common/utils.h"
#include "db/dao.h"
#include "meta/entities_generated.h"
#include "service/dict.h"

#include <functional>
#include <optional>
#include <string>

namespace cm::handler {
namespace {

using http::Request;
using http::Response;

// 对应 BaseController#getDataTable / startPage。
Json list_response(const meta::EntityMeta& m, const Request& req, const std::string& extra_where,
                   const std::function<void(Json&, bool)>& decorate, bool for_export) {
  Json env = repo::select_list(m, req, extra_where);
  Json& rows = env["rows"];
  if (decorate) decorate(rows, for_export);
  if (for_export) return rows;
  return table_data(rows, env["total"].get<long long>());
}

bool numeric_id(const std::string& s) { return utils::is_integer(s); }

void bad_id(const std::string& name) {
  throw BindError(400, "参数 '" + name + "' 类型不匹配: 不是合法数字");
}

// 去掉分页/排序参数（BaseController#startPage 未提供 pageNum/pageSize 时行为，
// listAll 接口不接受分页）。
Request without_paging(const Request& req) {
  Request copy = req;
  copy.params_all.erase("pageNum");
  copy.params_all.erase("pageSize");
  copy.params_all.erase("orderByColumn");
  copy.params_all.erase("isAsc");
  return copy;
}

std::optional<std::string> time_text(const Json& row, const char* key) {
  auto it = row.find(key);
  if (it == row.end() || it->is_null() || !it->is_string()) return std::nullopt;
  return it->get<std::string>();
}

// Java: DateUtils.parseDateToStr("yyyy-MM-dd HH:mm:ss", date)，JVM 默认时区 +08:00。
std::string date_time_str(const std::string& iso_utc) {
  auto tp = timeutil::parse_any(iso_utc);
  return tp ? timeutil::format_naive_plus8(*tp) : iso_utc;
}

struct Spec {
  const meta::EntityMeta* meta = nullptr;
  std::string base;
  std::string id_param;
  bool numeric = false;    // @PathVariable Long
  bool list_all = false;
  bool exportable = false;
  std::function<std::string(const Request&)> prepare;
  std::function<void(Json&, bool)> decorate;
};

void register_spec(http::Router& r, const Spec& s) {
  // /list
  r.add("GET", s.base + "/list", [s](Request& req) -> Response {
    std::string extra = s.prepare ? s.prepare(req) : "";
    return Response::ok(list_response(*s.meta, req, extra, s.decorate, false));
  });

  // /listToExport
  if (s.exportable) {
    r.add("GET", s.base + "/listToExport", [s](Request& req) -> Response {
      std::string extra = s.prepare ? s.prepare(req) : "";
      return Response::ok(list_response(*s.meta, req, extra, s.decorate, true));
    });
  }

  // /listAll
  if (s.list_all) {
    r.add("GET", s.base + "/listAll", [s](Request& req) -> Response {
      Request clean = without_paging(req);
      return Response::ok(list_response(*s.meta, clean, "", s.decorate, true));
    });
  }

  // /{id}
  if (!s.id_param.empty()) {
    std::string pattern = s.base + "/{" + s.id_param + "}";
    // getInfo 返回形态以 info_returns_raw_entity 为唯一权威：16 个控制器是
    // AjaxResult.success(entity) 信封（查不到时 {"msg":"操作成功","code":200}，
    // data 键省略），仅 feeGantry/feerecords/snapshotflow 直接返回实体。
    const bool raw = info_returns_raw_entity(s.base);
    r.add("GET", pattern, [s, raw](Request& req) -> Response {
      auto id = req.path_param(s.id_param);
      if (!id) throw BindError(400, "缺少路径参数 " + s.id_param);
      if (s.numeric && !numeric_id(*id)) bad_id(s.id_param);
      Json row = repo::select_by_id(*s.meta, *id);
      if (raw) {
        // Java 直接 return entity：查不到时 Spring 输出空 body（HTTP 200）。
        if (row.is_null()) return Response::raw(200, "", "application/json;charset=UTF-8");
        return Response::ok(row);
      }
      if (row.is_null()) return Response::ok(ajax_ok());
      return Response::ok(ajax_ok_data(row));
    });
  }
}

// ---------------------------------------------------------------- decorations

void decorate_fee_gantry(Json& rows, bool) {
  for (auto& row : rows) row["id"] = utils::uuid32();
}

std::string fee_records_prepare(const Request& req) {
  // 对应 OdsLwzxsfsjFeeRecords01Controller#list 的 JiAnDong / 区间逻辑：
  // Java 里这些条件被塞进实体的 sectionList/codeList，但 Mapper XML 并未使用，
  // 因此这里只保留“未带车牌时告警”的日志行为，不生成额外 SQL 条件。
  const bool query_all = req.get_bool("queryAll").value_or(false);
  if (!query_all && utils::is_blank(req.str("vehicleplate"))) {
    CM_LOG_INFO("feeRecords") << "查询未指定车牌，返回全部车牌数据（与 Java 行为一致）";
  }
  return "";
}

void decorate_fee_records(Json& rows, bool) {
  const auto gantry = service::gantry_map();
  for (auto& row : rows) {
    std::string plate;
    auto it = row.find("vehicleplate");
    if (it != row.end() && it->is_string()) plate = it->get<std::string>();
    if (plate.find('_') != std::string::npos)
      row["vehicleplate"] = plate.substr(0, plate.find('_'));

    if (auto t = time_text(row, "transtime")) row["transtimeStr"] = date_time_str(*t);
    if (auto t = time_text(row, "lastgantrytime"))
      row["lastgantrytimeStr"] = date_time_str(*t);

    std::string gantry_id;
    if (auto it2 = row.find("gantryid"); it2 != row.end() && it2->is_string())
      gantry_id = it2->get<std::string>();
    auto g = gantry.find(gantry_id);
    if (g != gantry.end()) {
      auto name = g->second.find("gantryName");
      row["gantryName"] = (name != g->second.end()) ? *name : Json(nullptr);
      auto sec = g->second.find("sectionCode");
      row["sectionCodeStr"] = (sec != g->second.end()) ? *sec : Json(nullptr);
    }
  }
}

std::string snapshotflow_prepare(const Request& req) {
  std::string extra;
  // OdsRtSzdnSnapshotFlowAddcodeMapper.xml: flag=JiAnDong -> orgcode = '030000011'
  if (req.str("flag") == "JiAnDong") extra += " AND orgcode = '030000011'";

  std::string sections = utils::delete_end(req.str("sectionCodeStr"));
  if (!sections.empty()) extra += " AND sectioncode IN " + repo::in_list(utils::split_csv(sections));

  std::string codes = utils::delete_end(req.str("code"));
  if (!codes.empty()) extra += " AND gantrycode IN " + repo::in_list(utils::split_csv(codes));
  return extra;
}

void decorate_snapshotflow(Json& rows, bool for_export) {
  for (auto& row : rows) {
    row["id"] = utils::uuid32();
    if (auto t = time_text(row, "snapshottime")) row["snapshottimeStr"] = date_time_str(*t);
    if (!for_export) {
      auto it = row.find("snappicturepath");
      if (it != row.end() && it->is_string()) {
        std::string path = utils::repalace_pic_url(utils::delete_end(it->get<std::string>()));
        row["snappicturepath"] = path;
      }
    }
  }
}

} // namespace

bool info_returns_raw_entity(const std::string& base_path) {
  // Java 19 个实体控制器中仅 3 个 getInfo 直接 return entity：
  //   OdsLwzxsfsjFeeGantryFusion01Controller（/base/feeGantry）
  //   OdsLwzxsfsjFeeRecords01Controller（/base/feerecords）
  //   OdsRtSzdnSnapshotFlowAddcodeController（/base/snapshotflow）
  // 其余 16 个返回 AjaxResult.success(entity) 信封（审阅报告 §3.3 R1）。
  return base_path == "/base/feeGantry" || base_path == "/base/feerecords" ||
         base_path == "/base/snapshotflow";
}

void register_base(http::Router& r) {
  // 1. /base/fwqjcxx
  Spec fwqjcxx;
  fwqjcxx.meta = &meta::dwdLcztFwqjcxx;
  fwqjcxx.base = "/base/fwqjcxx";
  fwqjcxx.id_param = "agentPk";
  fwqjcxx.numeric = true;
  fwqjcxx.list_all = true;
  register_spec(r, fwqjcxx);

  // 2. /base/sfsjcxx
  Spec sfsjcxx = fwqjcxx;
  sfsjcxx.meta = &meta::dwdLcztSfsjcxx;
  sfsjcxx.base = "/base/sfsjcxx";
  register_spec(r, sfsjcxx);

  // 3. /base/sfzjcxx
  Spec sfzjcxx = fwqjcxx;
  sfzjcxx.meta = &meta::dwdLcztSfzjcxx;
  sfzjcxx.base = "/base/sfzjcxx";
  register_spec(r, sfzjcxx);

  // 4. /manager/fwqclls
  Spec fwqclls;
  fwqclls.meta = &meta::odsCxztFwqclls;
  fwqclls.base = "/manager/fwqclls";
  fwqclls.id_param = "bigId";
  fwqclls.numeric = true;
  register_spec(r, fwqclls);

  // 5. /base/feeGantry
  Spec fee_gantry;
  fee_gantry.meta = &meta::odsLwzxsfsjFeeGantryFusion01;
  fee_gantry.base = "/base/feeGantry";
  fee_gantry.id_param = "bigId";
  fee_gantry.numeric = true;
  fee_gantry.decorate = decorate_fee_gantry;
  register_spec(r, fee_gantry);

  // 6. /base/feerecords
  Spec fee_records;
  fee_records.meta = &meta::odsLwzxsfsjFeeRecords01;
  fee_records.base = "/base/feerecords";
  fee_records.id_param = "bigId";
  fee_records.numeric = true;
  fee_records.exportable = true;
  fee_records.prepare = fee_records_prepare;
  fee_records.decorate = decorate_fee_records;
  register_spec(r, fee_records);

  // 7. /base/feeStationEnter
  Spec enter;
  enter.meta = &meta::odsLwzxsfsjFeeStationEnter01;
  enter.base = "/base/feeStationEnter";
  enter.id_param = "bigId";
  enter.numeric = true;
  register_spec(r, enter);

  // 8. /base/feestationexit
  Spec exit;
  exit.meta = &meta::odsLwzxsfsjFeeStationExit01;
  exit.base = "/base/feestationexit";
  exit.id_param = "bigId";
  exit.numeric = true;
  register_spec(r, exit);

  // 9. /base/snapshotflow
  Spec snapshot;
  snapshot.meta = &meta::odsRtSzdnSnapshotFlowAddcode;
  snapshot.base = "/base/snapshotflow";
  snapshot.id_param = "bigId";
  snapshot.numeric = true;
  snapshot.exportable = true;
  snapshot.prepare = snapshotflow_prepare;
  snapshot.decorate = decorate_snapshotflow;
  register_spec(r, snapshot);

  // 10. /base/provcapture
  Spec prov;
  prov.meta = &meta::odsRtSzdnSnapshotFlowProvcaptureAddcode;
  prov.base = "/base/provcapture";
  prov.id_param = "bigId";
  prov.numeric = true;
  register_spec(r, prov);

  // 11. /base/stationcapture
  Spec station;
  station.meta = &meta::odsRtSzdnSnapshotFlowStationcaptureAddcode;
  station.base = "/base/stationcapture";
  station.id_param = "bigId";
  station.numeric = true;
  register_spec(r, station);

  // 12. /base/gantry
  Spec gantry;
  gantry.meta = &meta::odsSzdnGantry;
  gantry.base = "/base/gantry";
  gantry.id_param = "id";
  gantry.numeric = true;
  gantry.list_all = true;
  register_spec(r, gantry);

  // 13. /base/gantryIp
  Spec gantry_ip;
  gantry_ip.meta = &meta::odsSzdnGantryIp;
  gantry_ip.base = "/base/gantryIp";
  gantry_ip.id_param = "id";
  gantry_ip.numeric = true;
  register_spec(r, gantry_ip);

  // 14. /base/vehicleweight
  Spec weight;
  weight.meta = &meta::odsSzdnProvinceBorderVehicleWeightNewstructure;
  weight.base = "/base/vehicleweight";
  weight.id_param = "dataSource"; // 方法名 selectById(dataSource)，传入的是主键
  register_spec(r, weight);
  r.add("GET", "/base/vehicleweight/map", [](Request& req) -> Response {
    return Response::ok(service::weight_capture_map(req.str("queryUuids")));
  });

  // 15. /base/section
  Spec section;
  section.meta = &meta::odsSzdnSection;
  section.base = "/base/section";
  section.id_param = "id";
  section.numeric = true;
  section.list_all = true;
  register_spec(r, section);

  // 16. /base/toll
  Spec toll;
  toll.meta = &meta::odsSzdnToll;
  toll.base = "/base/toll";
  toll.id_param = "id";
  toll.numeric = true;
  toll.list_all = true;
  register_spec(r, toll);

  // 17. /base/tollStationIp
  Spec toll_ip;
  toll_ip.meta = &meta::odsSzdnTollStationIp;
  toll_ip.base = "/base/tollStationIp";
  toll_ip.id_param = "id";
  toll_ip.numeric = true;
  register_spec(r, toll_ip);

  // 18. /base/org
  Spec org;
  org.meta = &meta::odsYhglVBaseOrg;
  org.base = "/base/org";
  org.id_param = "bigId";
  org.numeric = true;
  org.list_all = true;
  register_spec(r, org);

  // 19. /base/trailtracks
  Spec trail;
  trail.meta = &meta::zdataTrailTracks;
  trail.base = "/base/trailtracks";
  trail.id_param = "uuid";
  register_spec(r, trail);
}

} // namespace cm::handler
