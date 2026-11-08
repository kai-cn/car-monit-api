// 最小冒烟测试：覆盖工具类、时间语义、摘要算法与 JSON 信封。
// 数据库/Redis 连通性由环境变量 CM_TEST_DB / CM_TEST_REDIS 开启。
#include "cache/redis.h"
#include "common/crypto.h"
#include "common/datetime.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/result.h"
#include "common/utils.h"
#include "common/worker_pool.h"
#include "config/config.h"
#include "db/auth_guard.h"
#include "db/dao.h"
#include "db/pg.h"
#include "handler/handlers.h"
#include "http/cors.h"
#include "http/server.h"
#include "mq/kafka_producer.h"
#include "meta/entities_generated.h"
#include "router/routes.h"
#include "scheduler/cron.h"
#include "service/dict.h"
#include "service/optimization.h"
#include "service/snapshot_flow_sync.h"

#include <atomic>
#include <cassert>
#include <cctype>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <optional>
#include <thread>

static int g_fail = 0;

#define CHECK(cond)                                                    \
  do {                                                                 \
    if (!(cond)) {                                                     \
      std::cerr << "FAIL " << __FILE__ << ":" << __LINE__ << " " #cond \
                << std::endl;                                          \
      ++g_fail;                                                        \
    }                                                                  \
  } while (0)

static void test_utils() {
  using namespace cm::utils;
  CHECK(trim("  a b  ") == "a b");
  CHECK(is_blank("   "));
  CHECK(!is_blank("x"));
  CHECK(repalace_szdn_toll_name("江西南昌收费站") == "南昌");
  CHECK(delete_end("abc,") == "abc");
  CHECK(split_csv("a, b ,c") == std::vector<std::string>({"a", "b", "c"}));
  CHECK(to_under_score("orderByColumn") == "order_by_column");
  CHECK(format_double(1.5) == "1.5");
  CHECK(sql_quote("O'Neil") == "'O''Neil'");
}

static void test_datetime() {
  using namespace cm::timeutil;
  auto tp = parse_naive("2025-08-29 10:00:00");
  CHECK(tp.has_value());
  if (tp) {
    CHECK(format_datetime(*tp) == "2025-08-29 02:00:00");
    CHECK(format_naive_plus8(*tp) == "2025-08-29 10:00:00");
    CHECK(format_day(*tp) == "2025-08-29");
    CHECK(format_timestamp(*tp).rfind("2025-08-29T02:00:00", 0) == 0);
  }
}

static void test_crypto() {
  namespace c = cm::crypto;
  CHECK(c::md5_hex("") == "d41d8cd98f00b204e9800998ecf8427e");
  CHECK(c::md5_hex("abc") == "900150983cd24fb0d6963f7d28e17f72");
  // PostgreSQL MD5 认证路径（与 pgjdbc 相同的两级摘要）；用虚构口令做向量，避免真实凭据入库。
  CHECK(c::md5_hex("dummy-password-123gaussdb") == "6de93907abf6eb7acae74f4b728f0537");
  {
    std::string salt;
    salt.push_back(char(1));
    salt.push_back(char(2));
    salt.push_back(char(3));
    salt.push_back(char(4));
    CHECK(c::md5_hex("md56de93907abf6eb7acae74f4b728f0537" + salt) ==
          "6f9f9a135e0e8ae020b4c188507b227b");
  }
  CHECK(c::sha1_hex("abc") == "a9993e364706816aba3e25717850c26c9cd0d89d");
  CHECK(c::sha256_hex("abc") ==
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  // RFC 4231 Test Case 2 (HMAC-SHA-256)
  std::vector<uint8_t> key{'J', 'e', 'f', 'e'};
  std::vector<uint8_t> data{'w', 'h', 'a', 't', 's', ' ', 'u', 'p', ' ', 'd', 'o', 'c'};
  auto mac = c::hmac_sha256(key, data);
  std::string mac_hex;
  {
    const char* hx = "0123456789abcdef";
    for (auto b : mac) {
      mac_hex.push_back(hx[b >> 4]);
      mac_hex.push_back(hx[b & 0xF]);
    }
  }
  CHECK(c::sha256_hex(std::string(64, 'a')) ==
        "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb");
  CHECK(mac_hex == "86c17054fadfe00c967a6b07dd0a98a72d49d73fb0d9a9b79c998e1a60f45ddf");
  // PBKDF2-HMAC-SHA256("password","salt",1,32)
  auto dk = c::pbkdf2_sha256("password", std::vector<uint8_t>{'s','a','l','t'}, 1, 32);
  std::string dk_hex;
  {
    const char* hx = "0123456789abcdef";
    for (auto b : dk) {
      dk_hex.push_back(hx[b >> 4]);
      dk_hex.push_back(hx[b & 0xF]);
    }
  }
  CHECK(dk_hex == "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b");
}

// PG 连接串构造与建连错误归类（不涉及真实数据库）。
static void test_pg_conninfo_and_error_mapping() {
  using namespace cm::db;
  PgConnOptions o;
  o.host = "db.example";
  o.port = 15432;
  o.user = "gaussdb";
  o.password = "p'w\\x";
  o.database = "RuoYi";
  o.sslmode = "verify-full";
  o.sslrootcert = "C:\\certs\\ca.pem";
  o.connect_timeout_ms = 4500;
  const std::string ci = build_conninfo(o);
  CHECK(ci.find("host='db.example'") != std::string::npos);
  CHECK(ci.find("port=15432") != std::string::npos);
  CHECK(ci.find("user='gaussdb'") != std::string::npos);
  // 单引号与反斜杠按 libpq conninfo 规则转义。
  CHECK(ci.find("password='p\\'w\\\\x'") != std::string::npos);
  CHECK(ci.find("dbname='RuoYi'") != std::string::npos);
  CHECK(ci.find("sslmode='verify-full'") != std::string::npos);
  CHECK(ci.find("sslrootcert='C:\\\\certs\\\\ca.pem'") != std::string::npos);
  CHECK(ci.find("connect_timeout=5") != std::string::npos); // 4.5s 向上取整

  // SQLSTATE 归类：认证/锁定/网络失败。
  CHECK(classify_connect_error("FATAL:  password authentication failed for user \"gaussdb\"") ==
        "28P01");
  CHECK(classify_connect_error("FATAL: The account has been locked.") == "28000");
  CHECK(classify_connect_error("FATAL: no pg_hba.conf entry for host \"127.0.0.1\"") == "28000");
  CHECK(classify_connect_error("could not connect to server: Connection refused") == "08001");
}


static void test_result() {
  cm::Json ok = cm::ajax_ok();
  CHECK(ok.contains("code") && ok.contains("msg"));
  CHECK(!ok.contains("data"));
  cm::Json data = cm::ajax_ok_data(cm::Json::array());
  CHECK(data.contains("data"));
  cm::Json table = cm::table_data(cm::Json::array(), 5);
  CHECK(table["total"] == 5);
}

static void test_router() {
  auto router = cm::router::build_routes();
  CHECK(router.route_count() >= 40);

  cm::http::Request req;
  req.method = "GET";
  req.path = "/health";
  cm::http::Response res;
  CHECK(router.dispatch(req, res));
  CHECK(res.status == 200);
  // /health 现在汇总依赖连接状态（不再恒 UP）：测试环境无 Redis/Kafka 时为
  // DEGRADED，全部组件可用时为 UP；components 结构必须完整。
  CHECK(res.json.contains("status"));
  CHECK(res.json["status"] == "UP" || res.json["status"] == "DEGRADED");
  CHECK(res.json.contains("components") && res.json["components"].contains("database"));

  // 未注册的路径必须返回 false（由 server 层转成 Spring 风格 404 错误体）。
  cm::http::Request missing;
  missing.method = "GET";
  missing.path = "/not-exists";
  cm::http::Response out;
  CHECK(!router.dispatch(missing, out));
}

static cm::http::Request make_request(const std::string& method, const std::string& path,
                                      const std::string& host, const std::string& origin = "",
                                      const std::string& acrm = "",
                                      const std::string& acrh = "") {
  cm::http::Request req;
  req.method = method;
  req.path = path;
  req.headers_lower["host"] = host;
  if (!origin.empty()) req.headers_lower["origin"] = origin;
  if (!acrm.empty()) req.headers_lower["access-control-request-method"] = acrm;
  if (!acrh.empty()) req.headers_lower["access-control-request-headers"] = acrh;
  return req;
}

static std::string header_value(const cm::http::Response& res, const std::string& name) {
  auto it = res.headers.find(name);
  if (it == res.headers.end()) return "";
  return cm::utils::join(it->second, ",");
}

static void test_cors() {
  cm::config::Config::CorsCfg cfg;  // 默认值与 config.yaml / Spring 默认一致

  // 1) 非 CORS 请求：不产生任何 CORS 头
  {
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cfg, req, out) == cm::http::CorsDecision::NotCors);
    CHECK(header_value(out, "Access-Control-Allow-Origin").empty());
  }

  // 2) 同源请求（Origin == Host）不是 CORS，Spring 也不加 ACAO
  {
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901", "http://127.0.0.1:9901");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cfg, req, out) == cm::http::CorsDecision::NotCors);
    CHECK(header_value(out, "Access-Control-Allow-Origin").empty());
  }

  // 3) 普通跨域 GET：默认 allowed-origins=*，返回 ACAO: *
  {
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901", "http://example.com");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cfg, req, out) == cm::http::CorsDecision::ActualAllowed);
    CHECK(header_value(out, "Access-Control-Allow-Origin") == "*");
    CHECK(header_value(out, "Access-Control-Allow-Credentials").empty());
    CHECK(header_value(out, "Vary").find("Origin") != std::string::npos);
  }

  // 4) 预检通过：白名单 origin + 方法 + 请求头 + max-age 全部回显
  {
    cm::config::Config::CorsCfg c = cfg;
    c.allowed_origins = {"http://localhost:3000"};
    c.allowed_methods = {"GET", "POST"};
    c.allowed_headers = {"*"};
    c.exposed_headers = {"X-Request-Id"};
    c.allow_credentials = true;
    c.max_age = 1800;
    auto req = make_request("OPTIONS", "/api/x", "127.0.0.1:9901", "http://localhost:3000",
                            "POST", "Content-Type, X-Token");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::PreflightAllowed);
    CHECK(header_value(out, "Access-Control-Allow-Origin") == "http://localhost:3000");
    CHECK(header_value(out, "Access-Control-Allow-Methods") == "GET,POST");
    CHECK(header_value(out, "Access-Control-Allow-Headers") == "Content-Type,X-Token");
    CHECK(header_value(out, "Access-Control-Allow-Credentials") == "true");
    CHECK(header_value(out, "Access-Control-Expose-Headers") == "X-Request-Id");
    CHECK(header_value(out, "Access-Control-Max-Age") == "1800");
  }

  // 5) 预检被拒：origin 不在白名单
  {
    cm::config::Config::CorsCfg c = cfg;
    c.allowed_origins = {"http://localhost:3000"};
    auto req = make_request("OPTIONS", "/api/x", "127.0.0.1:9901", "http://evil.example.com",
                            "POST", "Content-Type");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::PreflightRejected);
    CHECK(out.status == 200);  // 由 server 层改写成 403
  }

  // 6) 预检被拒：方法不在白名单
  {
    cm::config::Config::CorsCfg c = cfg;
    c.allowed_origins = {"http://localhost:3000"};
    c.allowed_methods = {"GET"};
    auto req = make_request("OPTIONS", "/api/x", "127.0.0.1:9901", "http://localhost:3000",
                            "DELETE", "");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::PreflightRejected);
  }

  // 7) Spring 规则：allowedOrigins=* 且 allowCredentials=true → IllegalArgumentException(500)
  {
    cm::config::Config::CorsCfg c = cfg;
    c.allow_credentials = true;
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901", "http://example.com");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::ConfigError);
  }

  // 8) allowCredentials + 显式白名单：回显 origin 并带 ACAC
  {
    cm::config::Config::CorsCfg c = cfg;
    c.allowed_origins = {"http://localhost:3000"};
    c.allow_credentials = true;
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901", "http://localhost:3000");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::ActualAllowed);
    CHECK(header_value(out, "Access-Control-Allow-Origin") == "http://localhost:3000");
    CHECK(header_value(out, "Access-Control-Allow-Credentials") == "true");
  }

  // 9) 关闭 CORS 后完全不处理
  {
    cm::config::Config::CorsCfg c = cfg;
    c.enabled = false;
    auto req = make_request("GET", "/api/x", "127.0.0.1:9901", "http://example.com");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::NotCors);
    CHECK(header_value(out, "Access-Control-Allow-Origin").empty());
  }

  // 10) 路径匹配：仅生效路径返回 CORS 头
  {
    cm::config::Config::CorsCfg c = cfg;
    c.path = "/api/**";
    auto req = make_request("GET", "/other/x", "127.0.0.1:9901", "http://example.com");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(c, req, out) == cm::http::CorsDecision::NotCors);
    auto req2 = make_request("GET", "/api/x", "127.0.0.1:9901", "http://example.com");
    cm::http::Response out2;
    CHECK(cm::http::apply_cors(c, req2, out2) == cm::http::CorsDecision::ActualAllowed);
  }
}

static void test_kafka_no_broker() {
  auto& cfg = cm::config::Config::instance();
  bool old_enabled = cfg.kafka.enabled;
  std::string old_bootstrap = cfg.kafka.bootstrap_servers;
  int old_request_timeout = cfg.kafka.request_timeout_ms;
  int old_delivery_timeout = cfg.kafka.delivery_timeout_ms;

  // 127.0.0.1:1 上没有 broker：验证连通性失败路径不会崩溃、不会抛异常。
  cfg.kafka.enabled = true;
  cfg.kafka.bootstrap_servers = "127.0.0.1:1";
  cfg.kafka.request_timeout_ms = 1000;
  cfg.kafka.delivery_timeout_ms = 4000;

  auto& producer = cm::mq::KafkaProducer::instance();
  producer.stop();
  CHECK(producer.start(false));
  std::string error;
  long long offset = -1;
  bool ok = producer.send_sync("ods-rt-szdn-snapshot-flow", "data-1",
                               R"({"dataId":"data-1","value":1})", 8000, &error, &offset);
  CHECK(!ok);
  CHECK(!error.empty());
  std::cout << "Kafka 无 broker 失败路径: " << error << std::endl;
  producer.stop();

  cfg.kafka.enabled = old_enabled;
  cfg.kafka.bootstrap_servers = old_bootstrap;
  cfg.kafka.request_timeout_ms = old_request_timeout;
  cfg.kafka.delivery_timeout_ms = old_delivery_timeout;
}

static void test_auth_guard() {
  using Outcome = cm::db::AuthGuard::Outcome;
  auto& guard = cm::db::AuthGuard::instance();

  // 1) 凭据校验：空口令 / 全空白 / 未展开占位都不通过，真实口令通过。
  CHECK(!cm::db::check_password("").ok);
  CHECK(!cm::db::check_password("   ").ok);
  CHECK(!cm::db::check_password("${CM_PG_PASSWORD}").ok);
  CHECK(cm::db::check_password("dummy-secret").ok);

  // 校验不通过时调用方（main）直接退出，不会进入 attempt：断言“未发起连接”。
  guard.reset();
  int calls = 0;
  guard.set_connector([&]() {
    ++calls;
    return Outcome::Ok;
  });
  CHECK(guard.attempts() == 0);
  CHECK(!guard.blocked());
  CHECK(calls == 0);

  // 2) 口令错误：只尝试一次即熔断，第二次不再触碰连接工厂。
  guard.reset();
  calls = 0;
  guard.set_connector([&]() {
    ++calls;
    return Outcome::AuthFailed;
  });
  CHECK(guard.attempt() == Outcome::AuthFailed);
  guard.mark_auth_failure("28P01", "口令被拒绝");
  CHECK(guard.attempt() == Outcome::Blocked);
  CHECK(calls == 1);
  CHECK(guard.attempts() == 1);
  CHECK(guard.blocked());

  // 3) 正常路径不受影响。
  guard.reset();
  calls = 0;
  guard.set_connector([&]() {
    ++calls;
    return Outcome::Ok;
  });
  CHECK(guard.attempt() == Outcome::Ok);
  CHECK(calls == 1);
  CHECK(!guard.blocked());

  // 4) 显式配置重连上限时，熔断后最多再尝试 N 次（默认 0 次）。
  guard.reset();
  calls = 0;
  guard.set_connector([&]() {
    ++calls;
    return Outcome::Ok;
  });
  guard.mark_auth_failure("28P01", "口令被拒绝");
  guard.set_max_attempts_after_failure(1);
  CHECK(guard.attempt() == Outcome::Ok);
  CHECK(guard.attempt() == Outcome::Blocked);
  CHECK(calls == 1);

  guard.reset();
}

static void test_local_config_override() {
  // configs/config.local.yaml 覆盖 configs/config.yaml（口令等敏感值放本地文件，已 gitignore）。
  namespace fs = std::filesystem;
  fs::path dir = fs::temp_directory_path() / "cm_cfg_test";
  fs::create_directories(dir);
  {
    std::ofstream f(dir / "config.yaml");
    f << "server:\n  port: 9901\nspring:\n  datasource:\n    dynamic:\n      druid:\n"
         "        maxActive: 20\n        maxWait: 60000\n        connect-timeout-ms: 7000\n"
         "      datasource:\n"
         "        master:\n          url: jdbc:postgresql://127.0.0.1:5432/RuoYi\n"
         "          username: gaussdb\n          password: ${CM_PG_PASSWORD}\n";
  }
  {
    std::ofstream f(dir / "config.local.yaml");
    f << "spring:\n  datasource:\n    dynamic:\n      datasource:\n        master:\n"
         "          password: local-secret\n";
  }
  auto& cfg = cm::config::Config::instance();
  cfg.load((dir / "config.yaml").string());
  CHECK(cfg.pg().password == "local-secret");
  CHECK(cfg.local_override_path().find("config.local.yaml") != std::string::npos);
  // Druid maxWait（借出等待）与 connect-timeout-ms（建连超时）分开解析，
  // 不再把 maxWait 误当 connect 超时（审阅 §3.3 R8）。
  CHECK(cfg.pg().max_conns == 20);
  CHECK(cfg.pg().max_wait_ms == 60000);
  CHECK(cfg.pg().connect_timeout_ms == 7000);
  fs::remove_all(dir);
}

static void test_db_optional() {
  if (!cm::utils::get_env("CM_TEST_DB")) return;
  auto& cfg = cm::config::Config::instance();
  cfg.load("configs/config.yaml");
  cfg.apply_env_overrides();
  // 凭据缺失时绝不建连：避免把一次冒烟变成真实失败登录。
  auto credential = cm::db::check_password(cfg.pg().password);
  if (!credential.ok) {
    std::cout << "跳过 DB 冒烟：" << credential.problem << std::endl;
    return;
  }
  cm::db::PgConnOptions pg_options;
  pg_options.host = cfg.pg().host;
  pg_options.port = cfg.pg().port;
  pg_options.user = cfg.pg().user;
  pg_options.password = cfg.pg().password;
  pg_options.database = cfg.pg().database;
  pg_options.sslmode = cfg.pg().sslmode;
  pg_options.sslrootcert = cfg.pg().sslrootcert;
  pg_options.connect_timeout_ms = cfg.pg().connect_timeout_ms;
  pg_options.statement_timeout_ms = cfg.pg().statement_timeout_ms;
  cm::db::PgPool::instance().init(pg_options, cfg.pg().max_conns, cfg.pg().min_idle,
                                  cfg.pg().max_wait_ms);
  try {
    auto r = cm::db::PgPool::instance().query("SELECT 1 AS one");
    CHECK(!r.rows.empty());
  } catch (const std::exception& e) {
    std::cerr << "DB 冒烟失败: " << e.what() << std::endl;
    ++g_fail;
  }
}

static void test_decimal() {
  // Java BigDecimal 序列化保留标度与尾零（Jackson/fastjson2 都基于 toString）。
  CHECK(cm::json_dump(cm::json_raw_decimal("1.50")) == "1.50");
  CHECK(cm::json_dump(cm::json_raw_decimal("1.5")) == "1.5");
  CHECK(cm::json_dump(cm::json_raw_decimal("-2.500")) == "-2.500");
  CHECK(cm::json_dump(cm::json_raw_decimal("0")) == "0");
  CHECK(cm::json_dump(cm::json_raw_decimal("0.00")) == "0.00");
  CHECK(cm::json_dump(cm::json_raw_decimal("-0.00")) == "-0.00");
  CHECK(cm::json_dump(cm::json_raw_decimal("123456789.1200")) == "123456789.1200");
  CHECK(cm::json_dump(cm::json_raw_decimal("1.5E+3")) == "1.5E+3");
  // 非数字字面量按 Jackson QUOTE_NON_NUMERIC_NUMBERS 语义写成字符串。
  CHECK(cm::json_dump(cm::json_raw_decimal("NaN")) == "\"NaN\"");
  CHECK(cm::json_dump(cm::json_raw_decimal("Infinity")) == "\"Infinity\"");
  // 嵌套在响应对象中同样保持标度，且不影响其它字段。
  cm::Json obj = cm::Json::object();
  obj["lon"] = cm::json_raw_decimal("113.50");
  obj["total"] = 2;
  CHECK(cm::json_dump(obj) == "{\"lon\":113.50,\"total\":2}");
}

static void test_query_field_whitelist() {
  // SQL 注入防护（审阅报告 §3.3 R3）：fuzzyFields key / groupBy / countField
  // 只能取实体已知列，未命中必须抛 BindError(400)，不得进入 SQL 标识符位置。
  using cm::service::DataSource;
  auto guard = [](DataSource ds, const std::string& f, bool t) {
    return cm::service::guard_query_field(ds, f, t);
  };
  auto throws_bind_400 = [](DataSource ds, const std::string& f, bool t) {
    try {
      cm::service::guard_query_field(ds, f, t);
      return false;
    } catch (const cm::BindError& e) {
      return e.status() == 400;
    } catch (...) {
      return false;
    }
  };

  // translate=true（UnifiedQueryService 路径）：逻辑字段按数据源翻译为物理列。
  CHECK(guard(DataSource::Snapshot, "platenumber", true) == "platenumber");
  CHECK(guard(DataSource::Fee, "platenumber", true) == "vehicleplate");
  CHECK(guard(DataSource::Trail, "platenumber", true) == "envehicleid");
  CHECK(guard(DataSource::Snapshot, "orgname", true) == "orgname");
  CHECK(guard(DataSource::Snapshot, "gantryname", true) == "gantryname");
  // 已知物理列/JSON 属性名同样放行（等价 Java getOrDefault 透传后命中列）。
  CHECK(guard(DataSource::Fee, "vehicleplate", true) == "vehicleplate");
  CHECK(guard(DataSource::Fee, "bigId", false) == "big_id");

  // translate=false（LargeScaleQueryService 路径）：必须是实体已知列。
  CHECK(guard(DataSource::Fee, "vehicleplate", false) == "vehicleplate");
  CHECK(guard(DataSource::Trail, "envehicleid", false) == "envehicleid");

  // 未命中白名单 -> BindError(400)。
  CHECK(throws_bind_400(DataSource::Fee, "orgname", true));        // fee 无 orgname 列
  CHECK(throws_bind_400(DataSource::Trail, "platenumber", false)); // large 路径不接受逻辑名
  CHECK(throws_bind_400(DataSource::Snapshot, "", true));
  // 典型注入载荷必须被拒（不能再拼进 LIKE/GROUP BY/ORDER BY）。
  CHECK(throws_bind_400(DataSource::Snapshot, "platenumber; DROP TABLE x", true));
  CHECK(throws_bind_400(DataSource::Snapshot, "1=1) UNION SELECT 1--", true));
  CHECK(throws_bind_400(DataSource::Fee, "vehicleplate' --", false));
  CHECK(throws_bind_400(DataSource::Snapshot, "datauuid\" ASC", false));
  CHECK(throws_bind_400(DataSource::Snapshot, "(SELECT pg_sleep(10))", false));
}

static void test_info_envelope_contract() {
  // Java 19 个实体控制器的 getInfo 返回形态（审阅报告 §3.3 R1）：
  // 仅 feeGantry/feerecords/snapshotflow 直接返回实体，其余 16 个为
  // AjaxResult.success(entity) 信封；信封查不到时返回 {"msg","code"}（data 省略），
  // 不能是空 body。
  using cm::handler::info_returns_raw_entity;
  CHECK(info_returns_raw_entity("/base/feeGantry"));
  CHECK(info_returns_raw_entity("/base/feerecords"));
  CHECK(info_returns_raw_entity("/base/snapshotflow"));
  const char* envelope_paths[] = {
      "/base/fwqjcxx",   "/base/sfsjcxx",
      "/base/sfzjcxx",   "/manager/fwqclls",
      "/base/feeStationEnter", "/base/feestationexit",
      "/base/provcapture",     "/base/stationcapture",
      "/base/gantry",   "/base/gantryIp",
      "/base/vehicleweight",   "/base/section",
      "/base/toll",     "/base/tollStationIp",
      "/base/org",      "/base/trailtracks"};
  for (const char* p : envelope_paths) {
    if (info_returns_raw_entity(p)) {
      std::cerr << "FAIL /{id} 信封端点被误判为裸实体: " << p << std::endl;
      ++g_fail;
    }
  }
  CHECK(!info_returns_raw_entity("/base/unknown"));
  CHECK(!info_returns_raw_entity("/base/sysutil"));
  // 信封语义：查不到 -> ajax_ok()（无 data 键、code=200、msg=操作成功）；
  // 查到 -> ajax_ok_data(row)（data 为实体）。
  cm::Json notfound = cm::ajax_ok();
  CHECK(!notfound.contains("data"));
  CHECK(notfound["code"] == 200);
  CHECK(notfound["msg"] == "操作成功");
  cm::Json entity = cm::Json::object();
  entity["id"] = "x1";
  cm::Json found = cm::ajax_ok_data(entity);
  CHECK(found.contains("data") && found["data"]["id"] == "x1");
  CHECK(found["code"] == 200);
}

static void test_cron_spring_semantics() {
  // Spring @Scheduled cron 语义（以 Java 侧 spring-context 5.3.6 实证行为为准，
  // 审阅报告 §3.3 R4：0/3 步进被忽略、周字段口径、日/周组合语义）。
  using cm::scheduler::WallTime;
  auto wt = [](int mon, int day, int h, int m, int s, int wday) {
    WallTime t;
    t.year = 2026;
    t.month = mon;
    t.day = day;
    t.hour = h;
    t.minute = m;
    t.second = s;
    t.wday = wday;
    return t;
  };
  auto m = [](const char* e, WallTime t) { return cm::scheduler::cron_match(e, t); };

  // 实际任务表达式：syncCurrentTrack "0 0/3 * * * ?" 每 3 分钟（修复前只在第 0 分）。
  CHECK(m("0 0/3 * * * ?", wt(11, 7, 10, 0, 0, 6)));
  CHECK(m("0 0/3 * * * ?", wt(11, 7, 10, 3, 0, 6)));
  CHECK(m("0 0/3 * * * ?", wt(11, 7, 10, 57, 0, 6)));
  CHECK(!m("0 0/3 * * * ?", wt(11, 7, 10, 1, 0, 6)));
  CHECK(!m("0 0/3 * * * ?", wt(11, 7, 10, 2, 0, 6)));
  CHECK(!m("0 0/3 * * * ?", wt(11, 7, 10, 4, 0, 6)));
  CHECK(!m("0 0/3 * * * ?", wt(11, 7, 10, 0, 1, 6))); // 秒必须为 0
  // */N 等价 0/N：processPendingQueue 每分钟、syncGantryCaptureData 每 5 分钟。
  CHECK(m("0 */1 * * * ?", wt(11, 7, 10, 7, 0, 6)));
  CHECK(m("0 */5 * * * ?", wt(11, 7, 10, 25, 0, 6)));
  CHECK(!m("0 */5 * * * ?", wt(11, 7, 10, 26, 0, 6)));
  // 区间 + 步进（实证 "1-5/2" = 1,3,5）。
  CHECK(m("0 1-5/2 * * * ?", wt(11, 7, 10, 1, 0, 6)));
  CHECK(m("0 1-5/2 * * * ?", wt(11, 7, 10, 3, 0, 6)));
  CHECK(m("0 1-5/2 * * * ?", wt(11, 7, 10, 5, 0, 6)));
  CHECK(!m("0 1-5/2 * * * ?", wt(11, 7, 10, 2, 0, 6)));
  CHECK(!m("0 1-5/2 * * * ?", wt(11, 7, 10, 4, 0, 6)));
  CHECK(!m("0 1-5/2 * * * ?", wt(11, 7, 10, 7, 0, 6)));
  // 纯数字头 + 步进（实证 "5/15" = 5,20,35,50）。
  CHECK(m("0 5/15 * * * ?", wt(11, 7, 10, 5, 0, 6)));
  CHECK(m("0 5/15 * * * ?", wt(11, 7, 10, 20, 0, 6)));
  CHECK(m("0 5/15 * * * ?", wt(11, 7, 10, 35, 0, 6)));
  CHECK(m("0 5/15 * * * ?", wt(11, 7, 10, 50, 0, 6)));
  CHECK(!m("0 5/15 * * * ?", wt(11, 7, 10, 6, 0, 6)));
  CHECK(!m("0 5/15 * * * ?", wt(11, 7, 10, 15, 0, 6)));
  // 单值精确 / 逗号列表 / 秒字段。
  CHECK(m("0 5 * * * ?", wt(11, 7, 10, 5, 0, 6)));
  CHECK(!m("0 5 * * * ?", wt(11, 7, 10, 6, 0, 6)));
  CHECK(m("0 5,10,15 * * * ?", wt(11, 7, 10, 10, 0, 6)));
  CHECK(!m("0 5,10,15 * * * ?", wt(11, 7, 10, 11, 0, 6)));
  CHECK(m("30 * * * * ?", wt(11, 7, 10, 0, 30, 6)));
  CHECK(!m("30 * * * * ?", wt(11, 7, 10, 0, 29, 6)));
  // 日/时/月：syncBaseInfo 每天 0 点；syncHistroyTrack 每天 4 点；含月字段。
  CHECK(m("0 0 0 * * ?", wt(11, 7, 0, 0, 0, 6)));
  CHECK(!m("0 0 0 * * ?", wt(11, 7, 1, 0, 0, 6)));
  CHECK(m("0 0 4 1 1 ?", wt(1, 1, 4, 0, 0, 4)));
  CHECK(!m("0 0 4 1 1 ?", wt(2, 1, 4, 0, 0, 4)));
  // 周字段（实证：0 与 7 均为周日、1=周一、6=周六）。
  CHECK(m("* * * * * 0", wt(11, 1, 10, 0, 0, 0)));
  CHECK(m("* * * * * 7", wt(11, 1, 10, 0, 0, 0)));
  CHECK(m("* * * * * 6", wt(11, 7, 10, 0, 0, 6)));
  CHECK(m("* * * * * 1", wt(11, 2, 10, 0, 0, 1)));
  CHECK(!m("* * * * * 1", wt(11, 1, 10, 0, 0, 0)));
  // 周区间 6-7 = 周六与周日；周列表。
  CHECK(m("* * * * * 6-7", wt(11, 7, 10, 0, 0, 6)));
  CHECK(m("* * * * * 6-7", wt(11, 1, 10, 0, 0, 0)));
  CHECK(!m("* * * * * 6-7", wt(11, 2, 10, 0, 0, 1)));
  CHECK(m("* * * * * 1,3,5", wt(11, 4, 10, 0, 0, 3)));
  CHECK(!m("* * * * * 1,3,5", wt(11, 3, 10, 0, 0, 2)));
  // 日与周同时受限为 AND（实证 "0 0 0 1 * 1" 仅在"1 号且周一"触发，
  // 如 2027-02-01；审阅报告称 Spring 为 OR，实证为 AND，以实证为准）。
  CHECK(m("0 0 0 1 * 1", WallTime{2027, 2, 1, 0, 0, 0, 1}));  // 1 号 + 周一
  CHECK(!m("0 0 0 1 * 1", wt(11, 2, 0, 0, 0, 1)));             // 周一但非 1 号
  CHECK(!m("0 0 0 1 * 1", wt(11, 1, 0, 0, 0, 0)));             // 1 号但周日
  // 第 7 段（年）在 Spring 中非法。
  CHECK(!m("0 0/3 * * * ? 2026", wt(11, 7, 10, 6, 0, 6)));
  // 字段数不足 / 空表达式。
  CHECK(!m("0 0 * * *", wt(11, 7, 10, 0, 0, 6)));
  CHECK(!m("", wt(11, 7, 10, 0, 0, 6)));
  // 结构校验。
  CHECK(cm::scheduler::cron_validate("0 0/3 * * * ?"));
  CHECK(cm::scheduler::cron_validate("0 30 2 * * ?"));
  CHECK(!cm::scheduler::cron_validate("0 1-5/2,10 8-18 * * MON-FRI")); // 不支持英文名
  CHECK(!cm::scheduler::cron_validate("0 0 * * *"));
  CHECK(!cm::scheduler::cron_validate("0 0/0 * * * ?"));
  CHECK(!cm::scheduler::cron_validate("0 60 * * * ?"));
  CHECK(!cm::scheduler::cron_validate("0 0 0 32 * ?"));
  CHECK(!cm::scheduler::cron_validate("* * * * * * *"));
}

static void test_reliability_timeout() {
  // Java DataReliabilityService.scheduleTimeoutCheck 的超时判定（审阅 §3.3 R9）：
  // 状态缺失（键过期）、PENDING/SENT/DEAD/未知值均视为超时；仅 CONFIRMED 不超时。
  CHECK(cm::mq::reliability_timed_out(std::nullopt));
  CHECK(cm::mq::reliability_timed_out(std::optional<std::string>("PENDING")));
  CHECK(cm::mq::reliability_timed_out(std::optional<std::string>("SENT")));
  CHECK(cm::mq::reliability_timed_out(std::optional<std::string>("DEAD")));
  CHECK(cm::mq::reliability_timed_out(std::optional<std::string>("GARBAGE")));
  CHECK(!cm::mq::reliability_timed_out(std::optional<std::string>("CONFIRMED")));

  // 超时检测线程生命周期冒烟：把 message-timeout-ms 调到 100ms，
  // 发送一条可靠消息（kafka 关闭走 Redis 降级路径，本机无 Redis/Kafka 也只产生
  // 日志不崩溃），等超时到期被扫描处理后 stop() 必须能干净 join。
  auto& cfg = cm::config::Config::instance();
  int old_timeout = cfg.reliability.message_timeout_ms;
  bool old_enabled = cfg.kafka.enabled;
  cfg.reliability.message_timeout_ms = 100;
  cfg.kafka.enabled = false;
  auto& producer = cm::mq::KafkaProducer::instance();
  cm::Json data = cm::Json::object();
  data["bigId"] = "reliability-smoke-1";
  std::string id = producer.send_reliable_message(data, "reliability-smoke-1", "");
  CHECK(!id.empty());
  std::this_thread::sleep_for(std::chrono::milliseconds(1200)); // 100ms 到期 + 500ms 扫描周期
  producer.stop(); // 超时线程必须可回收，不得死锁/崩溃
  CHECK(true);
  cfg.reliability.message_timeout_ms = old_timeout;
  cfg.kafka.enabled = old_enabled;
}

static void test_worker_pool() {
  // 受控线程池（审阅 §4.2 #15）：固定 worker + 有界队列 + 满载拒绝 + shutdown join。
  constexpr int kWorkers = 2, kQueue = 3;
  cm::WorkerPool pool(kWorkers, kQueue);
  std::atomic<int> done{0};
  std::atomic<int> running{0};
  std::atomic<bool> gate{false};
  auto wait_for = [&](auto&& pred, int timeout_ms) {
    for (int t = 0; t < timeout_ms && !pred(); t += 5)
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    return pred();
  };
  auto submit_blocked = [&] {
    return pool.submit([&] {
      running.fetch_add(1);
      while (!gate.load()) std::this_thread::sleep_for(std::chrono::milliseconds(5));
      done.fetch_add(1);
    });
  };

  // 逐个提交并确认 worker 已开跑（避免与队列容量判断竞态），占满 2 个 worker。
  CHECK(submit_blocked());
  CHECK(wait_for([&] { return running.load() >= 1; }, 5000));
  CHECK(submit_blocked());
  CHECK(wait_for([&] { return running.load() >= 2; }, 5000));
  // 两个 worker 都被 gate 挡住：再灌满队列（容量 3），下一个提交应被拒绝。
  CHECK(submit_blocked());
  CHECK(submit_blocked());
  CHECK(submit_blocked());
  CHECK(!submit_blocked());
  gate.store(true);
  CHECK(wait_for([&] { return done.load() >= 5; }, 5000));

  // 排空后可继续提交；shutdown 后拒绝且不崩溃。
  CHECK(pool.submit([&] { done.fetch_add(1); }));
  CHECK(wait_for([&] { return done.load() >= 6; }, 5000));
  pool.shutdown();
  CHECK(!pool.submit([] {}));
}

static void test_pg_pool_connect_breaker() {
  // 连接池"锁外建连 + 网络故障熔断"（审阅 §3.3 R8）：
  // 连一个必然拒绝的本地端口（127.0.0.1:1，无监听、不涉及真实数据库认证，
  // 不会产生失败登录）。连续 3 次建连失败后进入 30s 熔断，快速失败。
  auto& pool = cm::db::PgPool::instance();
  cm::db::PgConnOptions options;
  options.host = "127.0.0.1";
  options.port = 1;
  options.user = "probe-user";
  options.password = "probe-password-not-a-real-login";
  options.database = "probe";
  options.connect_timeout_ms = 500;
  options.statement_timeout_ms = 0;
  pool.init(options, 2, 0, 2000);
  auto expect_db_error = [&](const char* needle) {
    try {
      pool.query("SELECT 1");
      std::cerr << "FAIL 连接池应抛 DbError: " << needle << std::endl;
      ++g_fail;
      return;
    } catch (const cm::DbError& e) {
      if (std::string(e.message()).find(needle) == std::string::npos) {
        std::cerr << "FAIL DbError 消息不含预期关键字 '" << needle << "': " << e.message()
                  << std::endl;
        ++g_fail;
      }
    } catch (const std::exception& e) {
      std::cerr << "FAIL 应为 DbError 而非: " << e.what() << std::endl;
      ++g_fail;
    }
  };
  expect_db_error("无法连接数据库");
  expect_db_error("无法连接数据库");
  expect_db_error("无法连接数据库");
  // 第 4 次：熔断冷却中（不真正发起建连，立即失败）。
  expect_db_error("熔断冷却");
  pool.shutdown();
}

static void test_pg_pool_config_bounds() {
  // 池上限/懒建连/空口令拒绝初始化：均不发起真实连接。
  auto& pool = cm::db::PgPool::instance();
  cm::db::PgConnOptions options;
  options.host = "127.0.0.1";
  options.user = "u";
  options.password = "non-empty-placeholder";
  options.database = "d";
  pool.init(options, 2, 0, 500);
  CHECK(pool.available());
  CHECK(pool.max_connections() == 2);
  CHECK(pool.live_connections() == 0); // init 不建立物理连接
  options.password = "   ";            // 空白口令：拒绝初始化
  pool.init(options, 2, 0, 500);
  CHECK(!pool.available());
  pool.shutdown();
}

static void test_dao_param_binding() {
  // 通用查询层不再把用户输入拼进 SQL：值走 $1..$n 绑定。
  cm::meta::EntityMeta m;
  m.name = "probe";
  m.table = "jl_data01.t";
  m.select_sql = "id";
  m.filters.push_back({"carNo", "envehicleid", cm::meta::FOp::Eq});
  m.filters.push_back({"section", "sectioncode", cm::meta::FOp::In});
  m.filters.push_back({"name", "stationname", cm::meta::FOp::Like});
  cm::http::Request req;
  req.params_all["carNo"] = {"A' OR 1=1 --"};
  req.params_all["section"] = {"S1,S2"};
  req.params_all["name"] = {"50%_off"};
  auto f = cm::repo::where_from_filters(m, req);
  CHECK(f.sql.find("envehicleid = $1") != std::string::npos);
  CHECK(f.sql.find("sectioncode IN ($2,$3)") != std::string::npos);
  CHECK(f.sql.find("stationname LIKE $4") != std::string::npos);
  CHECK(f.sql.find("A' OR 1=1") == std::string::npos); // SQL 文本不含用户值
  CHECK(f.params.size() == 4);
  CHECK(f.params[0].value_or("") == "A' OR 1=1 --");
  CHECK(f.params[1].value_or("") == "S1");
  CHECK(f.params[2].value_or("") == "S2");
  CHECK(f.params[3].value_or("") == "%50\\%_off%"); // % 已转义

  // 编号随 params 连续递增；空 IN 列表退化为 NULL。
  CHECK(cm::repo::bind_param(f.params, std::string("x")) == "$5");
  cm::db::PgParams empty;
  CHECK(cm::repo::bind_in(empty, {}) == "(NULL)");
}

static bool contains_column_token(const std::string& list, const std::string& col) {
  std::size_t pos = 0;
  while ((pos = list.find(col, pos)) != std::string::npos) {
    const bool left_ok =
        pos == 0 || !(std::isalnum(static_cast<unsigned char>(list[pos - 1])) || list[pos - 1] == '_');
    const std::size_t end = pos + col.size();
    const bool right_ok = end >= list.size() ||
                          !(std::isalnum(static_cast<unsigned char>(list[end])) || list[end] == '_');
    if (left_ok && right_ok) return true;
    pos = end;
  }
  return false;
}

static void test_entity_select_columns() {
  // P4：20 个 * 的实体必须展开为显式列清单，且包含 resultMap 的全部物理列。
  using namespace cm::meta;
  const std::vector<const EntityMeta*> all = {
      &dwdLcztFwqjcxx,
      &dwdLcztSfsjcxx,
      &dwdLcztSfzjcxx,
      &odsCxztFwqclls,
      &odsLwzxsfsjFeeGantryFusion01,
      &odsLwzxsfsjFeeRecords01,
      &odsLwzxsfsjFeeStationEnter01,
      &odsLwzxsfsjFeeStationExit01,
      &odsRtSzdnSnapshotFlowAddcode,
      &odsRtSzdnSnapshotFlowProvcaptureAddcode,
      &odsRtSzdnSnapshotFlowStationcaptureAddcode,
      &odsSzdnGantry,
      &odsSzdnGantryIp,
      &odsSzdnProvinceBorderVehicleWeightNewstructure,
      &odsSzdnSection,
      &odsSzdnToll,
      &odsSzdnTollStationIp,
      &odsYhglVBaseOrg,
      &zdataTrailTracks,
      &zdataTrailFitting,
      &zdataLocationDict,
      &kafkaMessageRecord,
  };
  int wildcard = 0;
  for (const auto* m : all) {
    if (m->select_sql != "*") continue;
    ++wildcard;
    const std::string cols = select_columns(*m);
    CHECK(cols != "*");
    CHECK(cols.find("SELECT") == std::string::npos);
    for (const auto& f : m->fields) {
      if (f.column.empty()) continue;
      if (!contains_column_token(cols, f.column)) {
        std::cerr << "FAIL 实体 " << m->name << " 漏列: " << f.column << std::endl;
        ++g_fail;
      }
    }
  }
  CHECK(wildcard == 20);
  cm::service::invalidate_dict_cache();
}

static std::string endpoint_kind(const std::string& path) {
  auto ends = [&](const char* suffix) {
    return path.size() >= std::strlen(suffix) &&
           path.compare(path.size() - std::strlen(suffix), std::strlen(suffix), suffix) == 0;
  };
  if (ends("/list") || ends("/listToExport") || ends("/listAll")) return "table";
  const auto pos = path.find("/{");
  if (pos != std::string::npos) {
    const std::string base = path.substr(0, pos);
    return cm::handler::info_returns_raw_entity(base) ? "raw_entity" : "ajax_entity";
  }
  if (path == "/health" || path == "/metrics") return "diagnostic";
  return "ajax";
}

static void test_contract_routes_golden() {
  // P5：85 个端点的请求契约基线（method/path/响应形态）。
  // 更新基线：设置 CM_UPDATE_CONTRACT_GOLDEN=1 运行测试。
  auto router = cm::router::build_routes();
  auto routes = router.routes();
  std::sort(routes.begin(), routes.end(),
            [](const std::pair<std::string, std::string>& a,
               const std::pair<std::string, std::string>& b) {
              if (a.second != b.second) return a.second < b.second;
              return a.first < b.first;
            });
  cm::Json endpoints = cm::Json::array();
  for (const auto& r : routes) {
    cm::Json e = cm::Json::object();
    e["method"] = r.first;
    e["path"] = r.second;
    e["kind"] = endpoint_kind(r.second);
    endpoints.push_back(e);
  }
  cm::Json golden = cm::Json::object();
  golden["generated_by"] = "carmonit_tests::test_contract_routes_golden";
  golden["endpoints"] = endpoints;

  const std::string file = std::string(CM_SOURCE_DIR) + "/contracts/endpoints.golden.json";
  const auto update = cm::utils::get_env("CM_UPDATE_CONTRACT_GOLDEN");
  if (update && (*update == "1" || *update == "true")) {
    std::filesystem::create_directories(std::string(CM_SOURCE_DIR) + "/contracts");
    std::ofstream out(file);
    out << golden.dump(2) << "\n";
    std::cout << "已写入契约基线: " << file << " (" << endpoints.size() << " 端点)" << std::endl;
    return;
  }

  std::ifstream in(file);
  if (!in) {
    std::cerr << "FAIL 缺少契约基线: " << file
              << "（可设置 CM_UPDATE_CONTRACT_GOLDEN=1 重新生成）" << std::endl;
    ++g_fail;
    return;
  }
  cm::Json expected;
  in >> expected;
  const auto& exp = expected["endpoints"];
  CHECK(!exp.is_null());
  CHECK(exp.size() == endpoints.size());
  for (std::size_t i = 0; i < endpoints.size() && i < exp.size(); ++i) {
    if (endpoints[i]["method"] != exp[i]["method"] || endpoints[i]["path"] != exp[i]["path"] ||
        endpoints[i]["kind"] != exp[i]["kind"]) {
      std::cerr << "FAIL 端点契约漂移 #" << i << ": expected " << exp[i]["method"] << " "
                << exp[i]["path"] << " (" << exp[i]["kind"] << "), got "
                << endpoints[i]["method"] << " " << endpoints[i]["path"] << " ("
                << endpoints[i]["kind"] << ")" << std::endl;
      ++g_fail;
    }
  }
  CHECK(endpoints.size() >= 80); // 当前 85 个端点
}

static void test_background_pool_batch() {
  // syncSuspiciousCar1..10 已改为提交到进程后台池：10 个任务必须全部执行、队列排空。
  std::atomic<int> done{0};
  for (int i = 0; i < 10; ++i) {
    CHECK(cm::background_pool().submit([&done] { done.fetch_add(1); }));
  }
  for (int t = 0; t < 5000 && done.load() < 10; t += 5)
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  CHECK(done.load() == 10);
  CHECK(cm::background_pool().pending() == 0);
}

static void test_pagination_bounds() {
  using cm::repo::resolve_page;
  cm::http::Request req;
  // 越界值收敛：负页码 -> 1，超大 pageSize -> 500。
  req.params_all["pageNum"] = {"-5"};
  req.params_all["pageSize"] = {"999999"};
  auto p = resolve_page(req);
  CHECK(p.paged);
  CHECK(p.page_num == 1);
  CHECK(p.page_size == 500);

  // 超大页码 -> 10000；pageSize<=0 -> 默认 10。
  req.params_all["pageNum"] = {"99999"};
  req.params_all["pageSize"] = {"0"};
  p = resolve_page(req);
  CHECK(p.paged);
  CHECK(p.page_num == 10000);
  CHECK(p.page_size == 10);

  // 非数字/超出 int 范围：直接 400（不退化成全表/默认值）。
  req.params_all["pageNum"] = {"999999999999999999999999"};
  bool threw = false;
  try {
    (void)resolve_page(req);
  } catch (const cm::BindError&) {
    threw = true;
  }
  CHECK(threw);

  // 只给 pageNum 也视为分页（避免退化成全表返回）。
  req = cm::http::Request();
  req.params_all["pageNum"] = {"3"};
  p = resolve_page(req);
  CHECK(p.paged);
  CHECK(p.page_num == 3);
  CHECK(p.page_size == 10);

  // 两者都不给：不分页。
  req = cm::http::Request();
  p = resolve_page(req);
  CHECK(!p.paged);

  // orderByColumn 注入/非法值必须被忽略。
  req.params_all["pageNum"] = {"1"};
  req.params_all["pageSize"] = {"10"};
  req.params_all["orderByColumn"] = {"id; DROP TABLE t"};
  p = resolve_page(req);
  CHECK(p.order_by.empty());
  req.params_all["orderByColumn"] = {"envehicleid"};
  req.params_all["isAsc"] = {"desc"};
  p = resolve_page(req);
  CHECK(p.order_by == "envehicleid desc");
}

static void test_dict_cache_boundaries() {
  using namespace cm::service;
  set_dict_local_ttl_ms(300000);
  invalidate_dict_cache();

  // 命中：同 key 第二次不再构建，且返回同一份只读快照。
  int builds = 0;
  auto p1 = memoize_dict_map("unit:key1", [&](DictMap& m) {
    ++builds;
    m["a"] = cm::Json(1);
  });
  auto p2 = memoize_dict_map("unit:key1", [&](DictMap&) { ++builds; });
  CHECK(builds == 1);
  CHECK(p1 == p2);
  CHECK(p1->count("a") == 1);

  // TTL=0：立即过期，每次都重新构建。
  set_dict_local_ttl_ms(0);
  builds = 0;
  memoize_dict_map("unit:key2", [&](DictMap&) { ++builds; });
  memoize_dict_map("unit:key2", [&](DictMap&) { ++builds; });
  CHECK(builds == 2);

  // 显式失效：失效后重新构建。
  set_dict_local_ttl_ms(300000);
  invalidate_dict_cache();
  builds = 0;
  memoize_dict_map("unit:key3", [&](DictMap&) { ++builds; });
  invalidate_dict_cache();
  memoize_dict_map("unit:key3", [&](DictMap&) { ++builds; });
  CHECK(builds == 2);

  // 构建抛异常不得写入缓存，后续请求可重试成功。
  invalidate_dict_cache();
  builds = 0;
  bool threw = false;
  try {
    memoize_dict_map("unit:bad", [&](DictMap&) {
      ++builds;
      throw std::runtime_error("boom");
    });
  } catch (const std::runtime_error&) {
    threw = true;
  }
  CHECK(threw);
  auto ok = memoize_dict_map("unit:bad", [&](DictMap& m) {
    ++builds;
    m["ok"] = true;
  });
  CHECK(builds == 2);
  CHECK(ok && ok->count("ok") == 1);

  // 并发未命中：允许重复构建，但不得崩溃/数据竞争，所有调用拿到一致结果。
  invalidate_dict_cache();
  std::atomic<int> concurrent_builds{0};
  std::atomic<bool> all_ok{true};
  std::vector<std::thread> threads;
  threads.reserve(8);
  for (int i = 0; i < 8; ++i) {
    threads.emplace_back([&] {
      auto m = memoize_dict_map("unit:conc", [&](DictMap& out) {
        concurrent_builds.fetch_add(1);
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        out["v"] = 1;
      });
      if (!m || m->count("v") != 1) all_ok.store(false);
    });
  }
  for (auto& t : threads) t.join();
  CHECK(concurrent_builds.load() >= 1);
  CHECK(all_ok.load());

  // 批量回源失败降级：Redis/DB 均不可用时返回空对象而不是抛异常。
  auto empty = weight_capture_map("uuid-a,uuid-b");
  CHECK(empty.is_object());
  CHECK(empty.empty());

  set_dict_local_ttl_ms(300000);
  invalidate_dict_cache();
}

static void test_redis_reconnect_no_deadlock() {
  // Redis 重连路径（审阅 §3.3 R7 + 代码复查，改用 hiredis 后保持覆盖）：
  // 1) 连接失败后不得泄漏 fd（hiredis redisFree 负责关闭）；
  // 2) 失败后的命令必须快速返回而不是挂死（旧实现在持锁重连时自锁）。
  // 连必然拒绝的 127.0.0.1:1，不涉及真实 Redis。
  auto& redis = cm::cache::Redis::instance();
  CHECK(!redis.connect("127.0.0.1", 1, "", 0, 300));
  CHECK(!redis.connected());
  // 反复失败-重连路径：每次都应快速失败，不允许挂死或泄漏。
  for (int i = 0; i < 3; ++i) {
    auto v = redis.get("cm-test-reconnect-probe");
    CHECK(!v.has_value());
    CHECK(!redis.connected());
  }
  bool threw = false;
  try {
    redis.cmd({"PING"});
  } catch (const cm::RedisError&) {
    threw = true;
  }
  CHECK(threw);
}

static void test_server_security() {
  // 安全加固（审阅 §5.1 #6）：鉴权与限流为新增能力（默认关闭，对齐 Java 生产
  // 实例——SecurityInterceptor 被整体注释）；开启后的判定逻辑在此覆盖。
  cm::http::Request req;
  auto key_ok = [&](const std::string& key) { return cm::http::check_api_key(req, key); };
  // 未配置密钥：fail-closed。
  CHECK(!key_ok(""));
  // X-API-Key 命中/不命中。
  req.headers_lower["x-api-key"] = "secret-1";
  CHECK(key_ok("secret-1"));
  CHECK(!key_ok("secret-2"));
  // Authorization: Bearer（scheme 大小写不敏感）。
  req.headers_lower.clear();
  req.headers_lower["authorization"] = "Bearer secret-1";
  CHECK(key_ok("secret-1"));
  req.headers_lower["authorization"] = "bearer secret-1";
  CHECK(key_ok("secret-1"));
  // 非 Bearer scheme / 无凭证。
  req.headers_lower["authorization"] = "Basic secret-1";
  CHECK(!key_ok("secret-1"));
  req.headers_lower.clear();
  CHECK(!key_ok("secret-1"));

  // 固定窗口限流：同一 IP 每分钟 3 次，第 4 次拒绝；其它 IP 独立计数。
  cm::http::RateLimiter limiter;
  CHECK(limiter.allow("10.0.0.1", 3));
  CHECK(limiter.allow("10.0.0.1", 3));
  CHECK(limiter.allow("10.0.0.1", 3));
  CHECK(!limiter.allow("10.0.0.1", 3));
  CHECK(limiter.allow("10.0.0.2", 3));
  CHECK(!limiter.allow("10.0.0.1", 0)); // limit<=0 视为全拒

  // 配置解析：安全键与默认值。
  auto& cfg = cm::config::Config::instance();
  CHECK(!cfg.server_security().auth_enabled);      // 默认关闭（对齐 Java）
  CHECK(!cfg.server_security().rate_limit_enabled);
  CHECK(cfg.server_security().max_payload_bytes == 1048576); // config.yaml 1MB
  CHECK(cfg.server_security().read_timeout_ms == 30000);
  CHECK(cfg.server_security().write_timeout_ms == 30000);
}

static void test_negative_inputs() {
  // 1) SQL 标识符白名单：超长/内嵌 NUL/非法 UTF-8/关键字/带引号/CRLF 全部拒绝。
  using cm::service::DataSource;
  auto rejected = [](const std::string& f) {
    try {
      cm::service::guard_query_field(DataSource::Snapshot, f, true);
      return false;
    } catch (const cm::BindError& e) {
      return e.status() == 400;
    } catch (...) {
      return false;
    }
  };
  CHECK(rejected(std::string(10000, 'a')));
  CHECK(rejected(std::string("envehicleid\0", 13)));
  CHECK(rejected("\xFF\xFE"));
  CHECK(rejected("select"));
  CHECK(rejected("\"envehicleid\""));
  CHECK(rejected("envehicleid --"));
  CHECK(rejected("envehicleid\r\n"));

  // 2) 请求体解析：非法 JSON 返回 400；超深嵌套/超长字符串不应崩溃。
  cm::http::Request req;
  req.body = "{invalid";
  bool threw = false;
  try {
    (void)req.json();
  } catch (const cm::BindError& e) {
    threw = e.status() == 400;
  }
  CHECK(threw);
  req.body = "null";
  CHECK(req.json().is_null());
  req.body = std::string(1000, '[') + std::string(1000, ']');
  try {
    auto deep = req.json();
    CHECK(deep.is_array());
  } catch (...) {
    std::cerr << "FAIL 合法深嵌套 JSON 被拒绝" << std::endl;
    ++g_fail;
  }
  req.body = "{\"s\":\"" + std::string(200000, 'x') + "\"}";
  try {
    auto big = req.json();
    CHECK(big["s"].get<std::string>().size() == 200000);
  } catch (...) {
    std::cerr << "FAIL 超长字符串 JSON 被拒绝" << std::endl;
    ++g_fail;
  }

  // 3) CORS：头部注入/超长/不透明 origin 不得回显到响应头。
  cm::config::Config::CorsCfg cors;
  cors.allowed_origins = {"http://localhost:3000"};
  cors.allowed_methods = {"GET", "POST"};
  cors.allowed_headers = {"*"};
  {
    auto r = make_request("OPTIONS", "/api/x", "127.0.0.1:9901", "http://localhost:3000",
                          "POST", "Content-Type\r\nX-Evil: 1");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cors, r, out) == cm::http::CorsDecision::PreflightRejected);
    CHECK(header_value(out, "Access-Control-Allow-Headers").empty());
  }
  {
    auto r = make_request("GET", "/api/x", "127.0.0.1:9901",
                          std::string("http://localhost:3000\r\nX-Evil: 1"));
    cm::http::Response out;
    auto d = cm::http::apply_cors(cors, r, out);
    CHECK(d == cm::http::CorsDecision::ActualRejected || d == cm::http::CorsDecision::NotCors);
    CHECK(header_value(out, "Access-Control-Allow-Origin").empty());
  }
  {
    auto r = make_request("OPTIONS", "/api/x", "127.0.0.1:9901", "null", "GET", "X-Token");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cors, r, out) == cm::http::CorsDecision::PreflightRejected);
  }
  {
    auto r = make_request("GET", "/api/x", "127.0.0.1:9901",
                          "http://" + std::string(5000, 'a') + ".example.com");
    cm::http::Response out;
    CHECK(cm::http::apply_cors(cors, r, out) == cm::http::CorsDecision::ActualRejected);
  }

  // 4) 认证头边界：超长/缺 token/多空格/CRLF 注入均不得通过。
  cm::http::Request areq;
  auto key_ok = [&](const std::string& key) { return cm::http::check_api_key(areq, key); };
  areq.headers_lower["x-api-key"] = std::string(100000, 'a');
  CHECK(!key_ok("secret-1"));
  areq.headers_lower.clear();
  areq.headers_lower["authorization"] = "Bearer";
  CHECK(!key_ok("secret-1"));
  areq.headers_lower["authorization"] = "Bearer  secret-1";
  CHECK(!key_ok("secret-1"));
  areq.headers_lower["authorization"] = "Bearer secret-1\r\nX-Evil: 1";
  CHECK(!key_ok("secret-1"));
}

static void test_health_and_metrics() {
  // /health 汇总各依赖连接状态（不主动建连/认证——探活不得变成失败登录）。
  auto router = cm::router::build_routes();
  cm::http::Request req;
  req.method = "GET";
  req.path = "/health";
  cm::http::Response res;
  CHECK(router.dispatch(req, res));
  CHECK(res.json.contains("status"));
  CHECK(res.json["status"] == "UP" || res.json["status"] == "DEGRADED");
  CHECK(res.json.contains("components"));
  for (const char* comp : {"database", "redis", "kafka", "elasticsearch"}) {
    if (!res.json["components"].contains(comp)) {
      std::cerr << "FAIL /health 缺少组件: " << comp << std::endl;
      ++g_fail;
    }
  }
  // /metrics 指标快照结构。
  req.path = "/metrics";
  res = cm::http::Response();
  CHECK(router.dispatch(req, res));
  for (const char* key : {"requestsTotal", "errorsTotal", "inFlight", "avgLatencyMs",
                          "p50LatencyMs", "p95LatencyMs", "p99LatencyMs", "errorRate",
                          "status2xx", "status5xx", "dependencies"}) {
    if (!res.json.contains(key)) {
      std::cerr << "FAIL /metrics 缺少字段: " << key << std::endl;
      ++g_fail;
    }
  }
  CHECK(res.json["dependencies"].contains("db"));
  CHECK(res.json["dependencies"].contains("redis"));
  CHECK(res.json["dependencies"].contains("workerPool"));
  CHECK(cm::http::metrics_snapshot()["requestsTotal"].is_number());

  // Prometheus 文本格式（?format=prometheus）。
  req.params_all["format"] = {"prometheus"};
  res = cm::http::Response();
  CHECK(router.dispatch(req, res));
  CHECK(res.use_raw);
  CHECK(res.content_type.find("text/plain") != std::string::npos);
  CHECK(res.raw_body.find("carmonit_requests_total") != std::string::npos);
  CHECK(res.raw_body.find("carmonit_dependency_up{component=\"db\"}") != std::string::npos);
  CHECK(res.raw_body.find("carmonit_worker_pool_pending") != std::string::npos);

  // 优雅停机接口幂等：未启动时调用不崩溃。
  cm::router::stop_schedulers();
  cm::router::stop_schedulers();
  cm::service::stop_snapshot_flow_sync();
}

static void test_log_json_and_request_id() {
  // 结构化日志（JSON）+ requestId 贯穿：每行都是合法 JSON，且包含 requestId。
  namespace fs = std::filesystem;
  const fs::path dir = fs::temp_directory_path() / "cm_log_json_test";
  fs::remove_all(dir);
  fs::create_directories(dir);
  const std::string file = (dir / "json.log").string();
  cm::log::set_file(file);
  cm::log::set_level(cm::log::Level::Info);
  cm::log::set_json(true);
  {
    cm::log::RequestIdScope scope("req-abc-123");
    CM_LOG_INFO("json-test") << "hello \"quoted\"\nline2";
  }
  cm::log::set_json(false);
  std::ifstream in(file);
  std::string line;
  std::getline(in, line);
  try {
    auto j = cm::Json::parse(line);
    CHECK(j["level"] == "INFO");
    CHECK(j["logger"] == "json-test");
    CHECK(j["requestId"] == "req-abc-123");
    CHECK(j["msg"].get<std::string>().find("\"quoted\"") != std::string::npos);
  } catch (...) {
    std::cerr << "FAIL JSON 日志行无法解析: " << line << std::endl;
    ++g_fail;
  }
  // 关闭日志文件；不删除临时目录（Windows 上杀软/索引可能短暂占用，保留在 temp 无害）。
  cm::log::set_file("");
}

static void test_log_rotation() {
  // 按大小轮转（审阅 §4.1：原实现文件无限增长）。
  namespace fs = std::filesystem;
  fs::path dir = fs::temp_directory_path() / "cm_log_rotate_test";
  fs::remove_all(dir);
  fs::create_directories(dir);
  const fs::path log = dir / "app.log";
  cm::log::set_file(log.string());
  cm::log::set_rotation(512, 3); // 512 字节轮转，保留 3 个历史文件
  for (int i = 0; i < 60; ++i) {
    cm::log::write(cm::log::Level::Info, "rotate-test",
                   "这是一行用于触发轮转的日志 " + std::to_string(i));
  }
  CHECK(fs::exists(log));
  CHECK(fs::exists(dir / "app.log.1"));
  // 恢复：关闭轮转并停写文件（后续测试日志只上 stdout）。
  cm::log::set_rotation(0, 1);
  cm::log::set_file("");
  fs::remove_all(dir);
}

int main() {
  test_utils();
  test_datetime();
  test_crypto();
  test_pg_conninfo_and_error_mapping();
  test_result();
  test_decimal();
  test_router();
  test_cors();
  test_kafka_no_broker();
  test_reliability_timeout();
  test_worker_pool();
  test_background_pool_batch();
  test_pg_pool_config_bounds();
  test_dao_param_binding();
  test_pagination_bounds();
  test_dict_cache_boundaries();
  test_entity_select_columns();
  test_contract_routes_golden();
  test_pg_pool_connect_breaker();
  test_redis_reconnect_no_deadlock();
  test_auth_guard();
  test_local_config_override();
  test_query_field_whitelist();
  test_info_envelope_contract();
  test_cron_spring_semantics();
  test_server_security();
  test_negative_inputs();
  test_health_and_metrics();
  test_log_json_and_request_id();
  test_log_rotation();
  test_db_optional();
  if (g_fail == 0) {
    std::cout << "ALL TESTS PASSED" << std::endl;
    return 0;
  }
  std::cout << g_fail << " TEST(S) FAILED" << std::endl;
  return 1;
}
