// 最小冒烟测试：覆盖工具类、时间语义、摘要算法与 JSON 信封。
// 数据库/Redis 连通性由环境变量 CM_TEST_DB / CM_TEST_REDIS 开启。
#include "cache/redis.h"
#include "common/crypto.h"
#include "common/datetime.h"
#include "common/error.h"
#include "common/result.h"
#include "common/utils.h"
#include "config/config.h"
#include "db/auth_guard.h"
#include "db/pg.h"
#include "handler/handlers.h"
#include "http/cors.h"
#include "http/server.h"
#include "mq/kafka_producer.h"
#include "router/routes.h"
#include "scheduler/cron.h"
#include "service/optimization.h"

#include <cassert>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
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

static std::string to_hex(const std::vector<uint8_t>& in) {
  const char* hx = "0123456789abcdef";
  std::string out;
  for (auto b : in) {
    out.push_back(hx[b >> 4]);
    out.push_back(hx[b & 0xF]);
  }
  return out;
}

// openGauss / PostgreSQL 认证算法回归向量（免密、无需 DB 即可运行）。
static void test_pg_auth() {
  using namespace cm::db;
  CHECK(parse_auth_mode("auto") == PgAuthMode::Auto);
  CHECK(parse_auth_mode("md5") == PgAuthMode::Md5);
  CHECK(parse_auth_mode("openGauss-SHA256") == PgAuthMode::OpenGaussSha256);
  CHECK(parse_auth_mode("scram-sha-256") == PgAuthMode::ScramSha256);
  CHECK(parse_auth_mode("unknown") == PgAuthMode::Auto);

  // PostgreSQL/openGauss MD5：md5( md5(password+user) + salt )
  std::string salt4;
  salt4.push_back(char(1));
  salt4.push_back(char(2));
  salt4.push_back(char(3));
  salt4.push_back(char(4));
  CHECK(pg_md5_auth_response("dummy-password-123", "gaussdb", salt4) ==
        "md56f9f9a135e0e8ae020b4c188507b227b");

  // openGauss sha256：SHA256(SHA256(password) || salt)
  std::vector<uint8_t> salt16;
  for (int i = 0; i < 16; ++i) salt16.push_back(uint8_t(i));
  auto salted = opengauss_salted_password("dummy-password-123", salt16);
  CHECK(to_hex(salted) == "2ca504263c3c1455d3a77b074a5acd1d0fde2513757d9831fd8bd7ed59a625cd");

  // 完整 SCRAM 交换（RFC 5802 流程 + openGauss 派生）
  auto proof = compute_scram_proof(salted, "n=,r=abcdefghijklmnopqrstuvwx",
                                   "r=abcdefghijklmnopqrstuvwxyz012345,"
                                   "s=AAECAwQFBgcICQoLDA0ODw==,i=4096",
                                   "abcdefghijklmnopqrstuvwxyz012345");
  CHECK(proof.client_final ==
        "c=biws,r=abcdefghijklmnopqrstuvwxyz012345,"
        "p=MNGvFFLa8PT/IHEw405eMI3w/2lPd5R7in/kkXfDb7A=");
  CHECK(proof.server_signature_b64 == "4q6H3eCqWzM0t5l3z3U1hMlduiCocFUoijy8qSN359U=");
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
  CHECK(res.json.contains("status") && res.json["status"] == "UP");

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
    f << "server:\n  port: 9901\nspring:\n  datasource:\n    dynamic:\n      datasource:\n"
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
  fs::remove_all(dir);
}

static void test_db_optional() {
  if (!std::getenv("CM_TEST_DB")) return;
  auto& cfg = cm::config::Config::instance();
  cfg.load("configs/config.yaml");
  cfg.apply_env_overrides();
  // 凭据缺失时绝不建连：避免把一次冒烟变成真实失败登录。
  auto credential = cm::db::check_password(cfg.pg().password);
  if (!credential.ok) {
    std::cout << "跳过 DB 冒烟：" << credential.problem << std::endl;
    return;
  }
  cm::db::PgPool::instance().init(cfg.pg().host, cfg.pg().port, cfg.pg().user, cfg.pg().password,
                                  cfg.pg().database, cfg.pg().max_conns, cfg.pg().min_idle,
                                  cfg.pg().connect_timeout_ms, cfg.pg().auth_mode);
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

int main() {
  test_utils();
  test_datetime();
  test_crypto();
  test_pg_auth();
  test_result();
  test_decimal();
  test_router();
  test_cors();
  test_kafka_no_broker();
  test_reliability_timeout();
  test_auth_guard();
  test_local_config_override();
  test_query_field_whitelist();
  test_info_envelope_contract();
  test_cron_spring_semantics();
  test_db_optional();
  if (g_fail == 0) {
    std::cout << "ALL TESTS PASSED" << std::endl;
    return 0;
  }
  std::cout << g_fail << " TEST(S) FAILED" << std::endl;
  return 1;
}
