#include "service/optimization.h"

#include "common/error.h"
#include "common/logging.h"
#include "common/result.h"
#include "common/utils.h"
#include "http/server.h"

#include <string>
#include <thread>
#include <vector>

namespace cm::handler {
namespace {

std::string required_param(const http::Request& req, const std::string& name) {
  auto v = req.get(name);
  if (!v) {
    throw BindError(400, "Required request parameter '" + name +
                             "' for method parameter type String is not present");
  }
  return *v;
}

// LargeScaleQueryController.extractFuzzyFields
service::FuzzyFields fuzzy_from_query(const http::Request& req) {
  service::FuzzyFields out;
  for (const auto& kv : req.params_all) {
    if (!cm::utils::starts_with(kv.first, "fuzzyFields.")) continue;
    std::string name = kv.first.substr(12);
    std::string value = kv.second.empty() ? "" : kv.second.back();
    if (value.empty()) continue;
    out[name] = value;
  }
  return out;
}

// @RequestBody(required=false) Map<String,String>
service::FuzzyFields fuzzy_from_body(const http::Request& req, bool strip_prefix) {
  service::FuzzyFields out;
  Json body = req.json();
  if (!body.is_object()) return out;
  for (auto it = body.begin(); it != body.end(); ++it) {
    if (!it.value().is_string()) continue;
    std::string value = it.value().get<std::string>();
    if (value.empty()) continue;
    std::string key = it.key();
    if (strip_prefix) {
      if (!cm::utils::starts_with(key, "fuzzyFields.")) continue;
      key = key.substr(12);
    }
    out[key] = value;
  }
  return out;
}

Json error_body(int code, const std::string& message) {
  Json out = Json::object();
  out["code"] = code;
  out["message"] = message;
  return out;
}

} // namespace

void register_optimization(http::Router& r) {
  // -------------------------------------------------------------------------
  // UnifiedQueryController  (/api/v1/unified)
  // -------------------------------------------------------------------------

  r.add("GET", "/api/v1/unified/{ds}/list", [](http::Request& req) {
    std::string ds_raw = req.path_param("ds").value_or("");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    int page_num = req.int_or("pageNum", 1);
    int page_size = req.int_or("pageSize", 20);
    service::FuzzyFields fuzzy = fuzzy_from_query(req);

    try {
      service::DataSource ds = service::parse_data_source(ds_raw);
      Json data = service::unified_query().query(ds, start, end, fuzzy, page_num, page_size);
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "ok";
      out["dataSource"] = ds_raw;
      out["pageNum"] = page_num;
      out["pageSize"] = page_size;
      out["data"] = data;
      return http::Response::ok(out);
    } catch (const std::invalid_argument& e) {
      return http::Response::ok(error_body(400, e.what()));
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("POST", "/api/v1/unified/{ds}/export/submit", [](http::Request& req) {
    std::string ds_raw = req.path_param("ds").value_or("");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    service::FuzzyFields fuzzy = fuzzy_from_body(req, false);

    try {
      service::DataSource ds = service::parse_data_source(ds_raw);
      std::string task_id = service::unified_export().submit_export_task(ds, start, end, fuzzy);
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "导出任务已提交, 请用 taskId 轮询状态";
      out["taskId"] = task_id;
      return http::Response::ok(out);
    } catch (const std::invalid_argument& e) {
      return http::Response::ok(error_body(400, e.what()));
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("GET", "/api/v1/unified/export/status/{taskId}", [](http::Request& req) {
    std::string task_id = req.path_param("taskId").value_or("");
    Json status = service::unified_export().export_status(task_id);
    if (status.is_null()) {
      Json out = Json::object();
      out["code"] = 404;
      out["message"] = "task not found";
      return http::Response::ok(out);
    }
    return http::Response::ok(status);
  });

  // -------------------------------------------------------------------------
  // LargeScaleQueryController  (/api/v1/large)
  // -------------------------------------------------------------------------

  auto large_list_handler = [](std::string type) -> http::Handler {
    return [type](http::Request& req) {
      std::string start = required_param(req, "startTime");
      std::string end = required_param(req, "endTime");
      int page_num = req.int_or("pageNum", 1);
      int page_size = req.int_or("pageSize", 20);
      service::FuzzyFields fuzzy = fuzzy_from_query(req);

      service::DataSource ds = service::resolve_data_source(type);
      try {
        Json data = service::large_scale_query().fuzzy_query(type, start, end, fuzzy, page_num,
                                                             page_size);
        Json out = Json::object();
        out["code"] = 200;
        out["message"] = "ok";
        out["dataSource"] = service::data_source_name(ds);
        out["pageNum"] = page_num;
        out["pageSize"] = page_size;
        out["data"] = data;
        return http::Response::ok(out);
      } catch (const std::exception& e) {
        return http::Response::ok(error_body(500, e.what()));
      }
    };
  };

  r.add("GET", "/api/v1/large/snapshot", large_list_handler("snapshot"));
  r.add("GET", "/api/v1/large/fee", large_list_handler("fee"));
  r.add("GET", "/api/v1/large/trail", large_list_handler("trail"));

  r.add("GET", "/api/v1/large/carTrackQueryByCarNo", [](http::Request& req) {
    auto car_no = req.get("carNo");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    int page_num = req.int_or("pageNum", 1);
    int page_size = req.int_or("pageSize", 20);
    service::FuzzyFields fuzzy;
    if (car_no && !car_no->empty()) fuzzy["platenumber"] = *car_no;

    try {
      Json data = service::large_scale_query().fuzzy_query(
          "trail", start, end, fuzzy, page_num, page_size);
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "ok";
      out["dataSource"] = service::data_source_name(service::DataSource::Trail);
      out["pageNum"] = page_num;
      out["pageSize"] = page_size;
      out["data"] = data;
      return http::Response::ok(out);
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("GET", "/api/v1/large/stats/group", [](http::Request& req) {
    std::string type = req.str("type", "snapshot");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    std::string group_by = required_param(req, "groupBy");
    std::optional<std::string> count_field = req.get("countField");
    int top_n = req.int_or("topN", 100);
    service::FuzzyFields fuzzy = fuzzy_from_query(req);

    try {
      Json data = service::large_scale_query().aggregation_stats(
          type, start, end, group_by, count_field, fuzzy, top_n);
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "ok";
      out["type"] = type;
      out["groupBy"] = group_by;
      out["topN"] = top_n;
      out["data"] = data;
      return http::Response::ok(out);
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("POST", "/api/v1/large/export/submit", [](http::Request& req) {
    std::string type = req.str("type", "snapshot");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    service::FuzzyFields fuzzy = fuzzy_from_body(req, true);

    try {
      std::string task_id =
          service::large_scale_query().submit_export_task(type, start, end, fuzzy);
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "导出任务已提交";
      out["taskId"] = task_id;
      return http::Response::ok(out);
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("GET", "/api/v1/large/export/status/{taskId}", [](http::Request& req) {
    std::string task_id = req.path_param("taskId").value_or("");
    try {
      Json status = service::large_scale_query().export_status(task_id);
      if (status.is_null()) {
        Json out = Json::object();
        out["code"] = 404;
        out["message"] = "task not found";
        return http::Response::ok(out);
      }
      return http::Response::ok(status);
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("POST", "/api/v1/large/sync/full", [](http::Request&) {
    std::thread([] {
      try {
        service::data_sync().full_sync_one_year();
      } catch (const std::exception& e) {
        CM_LOG_ERROR("optimization.sync") << "全量同步失败: " << e.what();
      }
    }).detach();
    Json out = Json::object();
    out["code"] = 200;
    out["message"] = "全量同步任务已提交";
    return http::Response::ok(out);
  });

  r.add("POST", "/api/v1/large/sync/incremental", [](http::Request&) {
    try {
      service::data_sync().incremental_sync();
      Json out = Json::object();
      out["code"] = 200;
      out["message"] = "增量同步完成";
      return http::Response::ok(out);
    } catch (const std::exception& e) {
      return http::Response::ok(error_body(500, e.what()));
    }
  });

  r.add("POST", "/api/v1/large/sync/repair", [](http::Request& req) {
    std::string type = req.str("type", "snapshot");
    std::string start = required_param(req, "startTime");
    std::string end = required_param(req, "endTime");
    service::DataSource ds = service::resolve_data_source(type);

    std::thread([ds, start, end] {
      try {
        service::data_sync().repair_sync(ds, start, end);
      } catch (const std::exception& e) {
        CM_LOG_ERROR("optimization.sync") << "修复同步失败: " << e.what();
      }
    }).detach();

    Json out = Json::object();
    out["code"] = 200;
    out["message"] = "修复同步任务已提交";
    return http::Response::ok(out);
  });

  // -------------------------------------------------------------------------
  // ProgressiveQueryController  (/progressive)
  // -------------------------------------------------------------------------

  auto progressive_request = [](http::Request& req) {
    service::ProgressiveQueryRequest out;
    out.start_time = req.get("startTime");
    out.end_time = req.get("endTime");
    out.platenumber = req.get("platenumber");
    out.gantryname = req.get("gantryname");
    out.roadname = req.get("roadname");
    out.sectionname = req.get("sectionname");
    out.orgname = req.get("orgname");
    out.tollname = req.get("tollname");
    out.cursor = req.get("cursor");
    out.page_size = req.int_or("pageSize", 20);
    return out;
  };

  r.add("GET", "/progressive/snapshotflow/list", [progressive_request](http::Request& req) {
    service::ProgressiveQueryRequest q = progressive_request(req);
    service::ProgressiveQueryResult result =
        service::progressive_query().query_snapshot_flow(q);
    return http::Response::ok(
        table_data(result.data, result.total, 200, "策略: " + result.strategy));
  });

  r.add("GET", "/progressive/feerecords/list", [progressive_request](http::Request& req) {
    service::ProgressiveQueryRequest q = progressive_request(req);
    service::ProgressiveQueryResult result = service::progressive_query().query_fee_records(q);
    return http::Response::ok(
        table_data(result.data, result.total, 200, "策略: " + result.strategy));
  });

  r.add("GET", "/progressive/trailfitting/list", [progressive_request](http::Request& req) {
    service::ProgressiveQueryRequest q = progressive_request(req);
    service::ProgressiveQueryResult result = service::progressive_query().query_trail_fitting(q);
    return http::Response::ok(
        table_data(result.data, result.total, 200, "策略: " + result.strategy));
  });

  r.add("GET", "/progressive/scale-level", [](http::Request&) {
    Json levels = Json::object();
    levels["ods_rt_szdn_snapshot_flow_addcode"] =
        service::progressive_query().detect_scale_level("ods_rt_szdn_snapshot_flow_addcode");
    levels["ods_lwzxsfsj_fee_records_01"] =
        service::progressive_query().detect_scale_level("ods_lwzxsfsj_fee_records_01");
    levels["zdata_trail_fitting"] =
        service::progressive_query().detect_scale_level("zdata_trail_fitting");
    return http::Response::ok(ajax_ok_data(levels));
  });

  // 启动 GaussDB/ES 一致性对账定时线（等价 Quartz，仅在配置开启时执行）。
  service::ensure_consistency_scheduler();
}

} // namespace cm::handler
