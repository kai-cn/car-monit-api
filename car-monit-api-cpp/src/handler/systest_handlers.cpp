#include "handler/handlers.h"

#include "common/logging.h"
#include "service/track.h"

#include <exception>
#include <string>
#include <thread>

namespace cm::handler {
namespace {

using http::Request;
using http::Response;

// Java 的 void 控制器方法：HTTP 200 + 空响应体。
Response empty_ok() { return Response::raw(200, "", "application/json;charset=UTF-8"); }

// Java 用 CompletableFuture.runAsync + 线程池异步执行；C++ 用 detached 线程等价实现。
void async_suspicious(int from, int to) {
  for (int i = from; i <= to; ++i) {
    std::thread([i] {
      try {
        service::sync_suspicious_car(i);
      } catch (const std::exception& e) {
        CM_LOG_ERROR("sysutil") << "syncSuspiciousCar" << i << " 失败: " << e.what();
      }
    }).detach();
  }
}

} // namespace

// SysTestController (/base/sysutilTest)：15 个 GET 端点。
void register_systest(http::Router& r) {
  r.add("GET", "/base/sysutilTest/syncCurrentTrack", [](Request&) {
    service::sync_current_track();
    return empty_ok();
  });

  r.add("GET", "/base/sysutilTest/syncBaseInfo", [](Request&) {
    service::sync_base_info();
    return empty_ok();
  });

  r.add("GET", "/base/sysutilTest/syncHistroyTrack", [](Request&) {
    service::sync_histroy_track();
    return empty_ok();
  });

  // /syncSuspiciousCar1..10：第 N 个端点处理 ((N-1)*10+1 .. N*10) 这 10 个下标。
  for (int n = 1; n <= 10; ++n) {
    const std::string pattern = "/base/sysutilTest/syncSuspiciousCar" + std::to_string(n);
    const int from = (n - 1) * 10 + 1;
    const int to = n * 10;
    r.add("GET", pattern, [from, to](Request&) {
      async_suspicious(from, to);
      return empty_ok();
    });
  }

  r.add("GET", "/base/sysutilTest/syncOdsSzdnGantry", [](Request&) {
    service::sync_ods_szdn_gantry();
    return empty_ok();
  });

  r.add("GET", "/base/sysutilTest/separateSnapshotFlowTimeList", [](Request& req) {
    service::separate_snapshot_flow_time_list(req);
    return empty_ok();
  });
}

} // namespace cm::handler
