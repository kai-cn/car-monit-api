#include "handler/handlers.h"

#include "common/json.h"
#include "service/track.h"

#include <string>

namespace cm::handler {
namespace {

using http::Request;
using http::Response;

// TrailBo 的标量字段（Spring 按同名请求参数绑定 TrailBo）。
const char* kTrailBoFields[] = {
    "pointUuid",      "stateType",      "pointFlag",     "pointJosn",     "captureTime",
    "directionIn",    "locationCode",   "locationName",  "standardCode",  "longitude",
    "latitude",       "locationFlag",   "ipType",        "locationJosn",  "devCode",
    "devName",        "imagesArry",     "lon",           "lat",           "roadCode",
    "sectionCode",    "orgCode",        "direction",     "pileno",        "preCaptureTime",
    "countNum",       "platenumber",    "locationId",    "isQuery",       "platecolor",
    "isVirtual"};

} // namespace

// SysUtilController (/base/sysutil)：仅注册 Java 中未被注释的 5 个端点。
void register_sysutil(http::Router& r) {
  r.add("GET", "/base/sysutil/saveRedis",
        [](Request&) { return Response::ok(service::save_redis()); });

  r.add("GET", "/base/sysutil/carTrackQueryByCarNo",
        [](Request& req) { return Response::ok(service::car_track_query_by_car_no(req)); });

  r.add("GET", "/base/sysutil/carTrackQueryByTime",
        [](Request& req) { return Response::ok(service::car_track_query_by_time(req)); });

  // @RequestBody TrailInfo
  r.add("POST", "/base/sysutil/changeTrailInfo",
        [](Request& req) { return Response::ok(service::change_trail_info(req.json())); });

  // TrailBo 由查询参数绑定
  r.add("GET", "/base/sysutil/getByTrailBo", [](Request& req) {
    Json trail_bo = Json::object();
    for (const char* field : kTrailBoFields) {
      auto v = req.get(field);
      if (v) trail_bo[field] = *v;
    }
    return Response::ok(service::get_by_trail_bo(trail_bo));
  });
}

} // namespace cm::handler
