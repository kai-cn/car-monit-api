#include "router/routes.h"

#include "handler/handlers.h"

namespace cm::router {

http::Router build_routes() {
  http::Router router;
  router.add("GET", "/health", [](http::Request&) {
    cm::Json j = cm::Json::object();
    j["status"] = "UP";
    return http::Response::ok(j);
  });
  handler::register_base(router);
  handler::register_sysutil(router);
  handler::register_systest(router);
  handler::register_optimization(router);
  return router;
}

void start_schedulers() { handler::start_schedulers(); }

} // namespace cm::router
