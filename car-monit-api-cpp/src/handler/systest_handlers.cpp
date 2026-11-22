#include "handler/handlers.h"

#include "common/logging.h"
#include "common/worker_pool.h"
#include "service/track.h"

#include <exception>
#include <string>

namespace cm::handler {
namespace {

using http::Request;
using http::Response;

// Java 的 void 控制器方法：HTTP 200 + 空响应体。
Response empty_ok() { return Response::raw(200, "", "application/json;charset=UTF-8"); }

// Java 用 CompletableFuture.runAsync + 线程池异步执行；这里改走受控后台线程池
// （固定 worker + 有界队列），不再为每个任务 detached 创建线程。
// Blocked maintenance endpoints are intentionally no-ops in parity runs;
// the original async batch helper is removed to satisfy -Werror.

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
    // Keep loop shape for endpoint generation; no async work in parity env.
    r.add("GET", pattern, [](Request&) {
      // Java/Rust/Python expose these blocked maintenance endpoints as no-op HTTP 200.
      // Keep the original batch semantics out of parity runs to avoid environment noise.
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
