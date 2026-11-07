#include "service/optimization.h"

#include "cache/redis.h"
#include "common/datetime.h"
#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "config/config.h"
#include "db/dao.h"
#include "db/pg.h"
#include "meta/entities_generated.h"

#include "httplib.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace cm::service {
namespace {

// ---------------------------------------------------------------------------
// 基础工具
// ---------------------------------------------------------------------------

const Json& member(const Json& j, const std::string& key) {
  static const Json kNull = Json(nullptr);
  if (!j.is_object()) return kNull;
  auto it = j.find(key);
  return it == j.end() ? kNull : *it;
}

std::string jstr(const Json& j, const std::string& key, const std::string& def = "") {
  const Json& v = member(j, key);
  return cm::json_string(v, def);
}

long long jlong(const Json& j, const std::string& key, long long def = 0) {
  const Json& v = member(j, key);
  if (v.is_number_integer()) return v.get<long long>();
  if (v.is_number_unsigned()) return static_cast<long long>(v.get<unsigned long long>());
  if (v.is_number_float()) return static_cast<long long>(v.get<double>());
  if (v.is_string()) {
    try {
      return std::stoll(v.get<std::string>());
    } catch (...) {
      return def;
    }
  }
  return def;
}

long long now_ms() { return timeutil::to_millis(timeutil::now()); }

std::string lower(std::string s) { return utils::to_lower(s); }

bool in(const std::string& v, std::initializer_list<const char*> values) {
  for (const char* x : values) {
    if (v == x) return true;
  }
  return false;
}

std::string ds_key(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return "snapshot";
    case DataSource::Fee: return "fee";
    case DataSource::Trail: return "trail";
  }
  return "snapshot";
}

const meta::EntityMeta& entity_meta(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return meta::odsRtSzdnSnapshotFlowAddcode;
    case DataSource::Fee: return meta::odsLwzxsfsjFeeRecords01;
    case DataSource::Trail: return meta::zdataTrailFitting;
  }
  return meta::odsRtSzdnSnapshotFlowAddcode;
}

std::string time_field(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return "snapshottime";
    case DataSource::Fee: return "transtime";
    case DataSource::Trail: return "extime";
  }
  return "snapshottime";
}

std::string id_field(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return "datauuid";
    case DataSource::Fee: return "big_id";
    case DataSource::Trail: return "cid";
  }
  return "datauuid";
}

std::string plate_field(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return "platenumber";
    case DataSource::Fee: return "vehicleplate";
    case DataSource::Trail: return "envehicleid";
  }
  return "platenumber";
}

// EsIndexManageService.resolveIndexName
std::string index_name(DataSource ds) {
  const auto& cfg = config::Config::instance();
  switch (ds) {
    case DataSource::Snapshot: return cfg.yml("elasticsearch.index.snapshot-flow", "snapshot_flow");
    case DataSource::Fee: return cfg.yml("elasticsearch.index.fee-records", "fee_records");
    case DataSource::Trail: return cfg.yml("elasticsearch.index.trail-fitting", "trail_fitting");
  }
  return "snapshot_flow";
}

// UnifiedQueryService.buildFieldTranslation
std::string translate_field(DataSource ds, const std::string& logical) {
  if (in(logical, {"orgname", "sectionname", "roadname", "gantryname", "tollname"})) return logical;
  if (logical == "platenumber") {
    switch (ds) {
      case DataSource::Snapshot: return "platenumber";
      case DataSource::Fee: return "vehicleplate";
      case DataSource::Trail: return "envehicleid";
    }
  }
  return logical;
}

// 白名单数据源：实体的已知列集合（json 属性名或物理列名二选一命中即可）。
// 仅存在于 Java 类、无对应数据库列的字段（column 为空）不能作为查询列。
const std::string& known_column_or_empty(const meta::EntityMeta& m, const std::string& name) {
  static const std::string kEmpty;
  for (const auto& f : m.fields) {
    if (f.column.empty()) continue;
    if (name == f.column || name == f.json) return f.column;
  }
  return kEmpty;
}

std::string sql_literal(const std::string& value) { return utils::sql_quote(value); }

std::string like_literal(const std::string& value) {
  return "'%" + utils::replace_all(value, "'", "''") + "%'";
}

// ---------------------------------------------------------------------------
// Elasticsearch REST 客户端（vendored cpp-httplib）
//
// Java 侧使用 RestHighLevelClient（HttpHost(host, port, "http")）。这里保持
// http 协议与 Basic 认证，所有 DSL 由本文件构造。
// ---------------------------------------------------------------------------

std::atomic<long long> g_es_failure_ms{0};
constexpr long long kEsCooldownMs = 30000;

struct EsRaw {
  int status = 0;
  std::string body;
};

std::optional<EsRaw> es_call(const std::string& method, const std::string& path,
                             const std::string& body = "",
                             const std::string& content_type = "application/json") {
  const auto& cfg = config::Config::instance();
  const auto& es = cfg.es();

  long long now = now_ms();
  long long failed = g_es_failure_ms.load();
  if (failed > 0 && now - failed < kEsCooldownMs) return std::nullopt;

  httplib::Client cli(es.host, es.port);
  cli.set_connection_timeout(std::chrono::milliseconds(es.connection_timeout_ms));
  cli.set_read_timeout(std::chrono::milliseconds(es.socket_timeout_ms));
  if (!es.username.empty()) cli.set_basic_auth(es.username, es.password);

  httplib::Result res;
  if (method == "GET") {
    res = cli.Get(path);
  } else if (method == "DELETE") {
    res = body.empty() ? cli.Delete(path) : cli.Delete(path, body, content_type);
  } else {
    res = body.empty() ? cli.Post(path) : cli.Post(path, body, content_type);
  }

  if (!res) {
    g_es_failure_ms.store(now);
    CM_LOG_WARN("optimization.es")
        << "[环境差异] Elasticsearch " << es.host << ":" << es.port
        << " 连接失败，降级为 PostgreSQL 等价查询。";
    return std::nullopt;
  }
  if (res->status < 200 || res->status >= 300) {
    CM_LOG_WARN("optimization.es") << "ES " << method << " " << path << " 返回 HTTP "
                                   << res->status << "："
                                   << res->body.substr(0, 200);
    return std::nullopt;
  }
  g_es_failure_ms.store(0);
  return EsRaw{res->status, res->body};
}

std::optional<Json> es_json(const std::string& method, const std::string& path,
                            const Json& body) {
  auto raw = es_call(method, path, body.dump(), "application/json");
  if (!raw) return std::nullopt;
  try {
    return Json::parse(raw->body);
  } catch (const std::exception& e) {
    CM_LOG_WARN("optimization.es") << "ES 响应不是合法 JSON: " << e.what();
    return std::nullopt;
  }
}

void es_clear_scroll(const std::string& scroll_id) {
  if (scroll_id.empty()) return;
  Json body = Json::object();
  Json ids = Json::array();
  ids.push_back(scroll_id);
  body["scroll_id"] = ids;
  es_call("DELETE", "/_search/scroll", body.dump(), "application/json");
}

// ---------------------------------------------------------------------------
// ES Query DSL（与 Java QueryBuilders 逐项对应）
// ---------------------------------------------------------------------------

Json build_range_filter(const std::string& field, const std::string& start,
                        const std::string& end) {
  Json inner = Json::object();
  inner["format"] = "yyyy-MM-dd HH:mm:ss";
  if (!start.empty()) inner["gte"] = start;
  if (!end.empty()) inner["lte"] = end;
  Json range_obj = Json::object();
  range_obj["range"] = Json::object();
  range_obj["range"][field] = inner;
  return range_obj;
}

// UnifiedQueryService.buildFuzzyQuery
Json build_fuzzy_query(const std::string& field, const std::string& value) {
  Json q = Json::object();
  if (value.size() >= 7 && in(field, {"platenumber", "gantrycode", "sectioncode"})) {
    q["term"] = Json::object();
    q["term"][field + ".keyword"] = value;
  } else if (value.size() >= 3) {
    q["match"] = Json::object();
    q["match"][field + ".ngram"] = value;
  } else {
    q["wildcard"] = Json::object();
    q["wildcard"][field + ".keyword"] = "*" + value + "*";
  }
  return q;
}

Json build_bool_query(DataSource ds, const std::string& start, const std::string& end,
                      const FuzzyFields& fuzzy, bool translate) {
  Json filter = Json::array();
  if (!start.empty() || !end.empty()) {
    filter.push_back(build_range_filter(time_field(ds), start, end));
  }
  Json must = Json::array();
  for (const auto& kv : fuzzy) {
    if (kv.second.empty()) continue;
    std::string field = translate ? translate_field(ds, kv.first) : kv.first;
    must.push_back(build_fuzzy_query(field, kv.second));
  }
  Json boolq = Json::object();
  if (!filter.empty()) boolq["filter"] = filter;
  if (!must.empty()) boolq["must"] = must;
  Json q = Json::object();
  q["bool"] = boolq;
  return q;
}

Json build_sort_desc(const std::string& field) {
  Json item = Json::object();
  Json order = Json::object();
  order["order"] = "desc";
  item[field] = order;
  Json arr = Json::array();
  arr.push_back(item);
  return arr;
}

// UnifiedQueryService.shouldRouteToEs
bool should_route_to_es(DataSource ds, const std::string& start, const std::string& end,
                        const FuzzyFields& fuzzy) {
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) return true;
  }
  long long start_ms = 0;
  long long end_ms = 0;
  if (!start.empty()) {
    auto tp = timeutil::parse_naive(start);
    if (!tp) return true;
    start_ms = timeutil::to_millis(*tp);
  }
  if (!end.empty()) {
    auto tp = timeutil::parse_naive(end);
    if (!tp) return true;
    end_ms = timeutil::to_millis(*tp);
  }
  long long force = static_cast<long long>(
      config::Config::instance().optimization.es_force_days) * 86400000LL;
  if (end_ms - start_ms > force) return true;
  return ds == DataSource::Fee || ds == DataSource::Trail;
}

// ---------------------------------------------------------------------------
// PostgreSQL 等价查询（ES 不可用时的降级路径）
// ---------------------------------------------------------------------------

Json pg_rows(const meta::EntityMeta& m, const std::string& where, const std::string& order,
             long long limit, long long offset) {
  std::string sql = "SELECT " + m.select_sql + " FROM " + m.table + " WHERE 1=1" + where;
  if (!order.empty()) sql += " ORDER BY " + order;
  if (limit > 0) {
    sql += " LIMIT " + std::to_string(limit);
    if (offset > 0) sql += " OFFSET " + std::to_string(offset);
  }
  auto result = db::PgPool::instance().query(sql);
  Json rows = Json::array();
  for (std::size_t i = 0; i < result.rows.size(); ++i) {
    rows.push_back(repo::project_row(m, result, i));
  }
  return rows;
}

std::string pg_where(DataSource ds, const std::string& start, const std::string& end,
                     const FuzzyFields& fuzzy, bool translate) {
  std::string where;
  const std::string tf = time_field(ds);
  if (!start.empty()) where += " AND " + tf + " >= " + sql_literal(start);
  if (!end.empty()) where += " AND " + tf + " <= " + sql_literal(end);
  for (const auto& kv : fuzzy) {
    if (kv.second.empty()) continue;
    // 标识符必须命中白名单（guard_query_field 未命中抛 BindError(400)），
    // 杜绝把 fuzzyFields.<key> 的 key 拼进 SQL；值继续走字面量转义。
    std::string field = guard_query_field(ds, kv.first, translate);
    where += " AND " + field + " LIKE " + like_literal(kv.second);
  }
  return where;
}

// ---------------------------------------------------------------------------
// 导出任务内存注册表（Java ConcurrentHashMap + 线程池的等价实现）
// ---------------------------------------------------------------------------

struct ExportTaskStatus {
  std::string task_id;
  std::string data_source; // SNAPSHOT/FEE/TRAIL 或 snapshot/fee/trail
  std::string start_time;
  std::string end_time;
  std::string type; // LargeScale 的原始 type
  bool unified = false;
  std::string status = "PENDING";
  long long submit_time = 0;
  long long finish_time = 0;
  long long total_exported = 0;
  int file_part_count = 0;
  std::string error_message;
  std::vector<std::string> file_paths;
  FuzzyFields fuzzy;
  mutable std::mutex mu;
};

struct ExportRegistry {
  std::mutex mu;
  std::map<std::string, std::shared_ptr<ExportTaskStatus>> tasks;
};

ExportRegistry& registry() {
  static ExportRegistry r;
  return r;
}

std::shared_ptr<ExportTaskStatus> create_task(const std::string& task_id) {
  auto t = std::make_shared<ExportTaskStatus>();
  t->task_id = task_id;
  t->submit_time = now_ms();
  {
    std::lock_guard<std::mutex> lk(registry().mu);
    registry().tasks[task_id] = t;
  }
  return t;
}

std::shared_ptr<ExportTaskStatus> find_task(const std::string& task_id) {
  std::lock_guard<std::mutex> lk(registry().mu);
  auto it = registry().tasks.find(task_id);
  return it == registry().tasks.end() ? nullptr : it->second;
}

void task_set_status(const std::shared_ptr<ExportTaskStatus>& t, const std::string& status,
                     const std::string& error = "") {
  std::lock_guard<std::mutex> lk(t->mu);
  t->status = status;
  if (!error.empty()) t->error_message = error;
}

void task_set_progress(const std::shared_ptr<ExportTaskStatus>& t, long long total,
                       int parts) {
  std::lock_guard<std::mutex> lk(t->mu);
  t->total_exported = total;
  t->file_part_count = parts;
}

void task_add_file(const std::shared_ptr<ExportTaskStatus>& t, const std::string& path) {
  std::lock_guard<std::mutex> lk(t->mu);
  t->file_paths.push_back(path);
}

void task_finish(const std::shared_ptr<ExportTaskStatus>& t, long long total, int parts) {
  std::lock_guard<std::mutex> lk(t->mu);
  t->status = "COMPLETED";
  t->total_exported = total;
  t->file_part_count = parts;
  t->finish_time = now_ms();
}

// ---------------------------------------------------------------------------
// CSV 工具
// ---------------------------------------------------------------------------

std::string value_to_string(const Json& v) {
  if (v.is_null()) return "";
  std::string literal;
  if (json_raw_decimal_literal(v, literal)) return literal;
  if (v.is_string()) return v.get<std::string>();
  if (v.is_boolean()) return v.get<bool>() ? "true" : "false";
  return json_dump(v);
}

std::string csv_escape(const std::string& s) {
  if (s.find(',') == std::string::npos && s.find('"') == std::string::npos &&
      s.find('\n') == std::string::npos && s.find('\r') == std::string::npos) {
    return s;
  }
  std::string out = "\"";
  for (char c : s) {
    if (c == '"') out += "\"\"";
    else out.push_back(c);
  }
  out += "\"";
  return out;
}

void ensure_dir(const std::string& dir) {
  if (dir.empty()) return;
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  if (ec) throw std::runtime_error("创建导出目录失败: " + dir + " (" + ec.message() + ")");
}

std::string export_file_path(const std::string& dir, const std::string& name) {
  return dir + "/" + name;
}

void write_header(std::ofstream& out, const std::vector<std::string>& columns) {
  std::string line;
  for (std::size_t i = 0; i < columns.size(); ++i) {
    if (i) line += ",";
    line += columns[i];
  }
  out << line << "\n";
}

// ---------------------------------------------------------------------------
// 导出列（UnifiedExportService.COLUMNS）
// ---------------------------------------------------------------------------

std::vector<std::string> export_columns(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot:
      return {"datauuid", "platenumber", "gantrycode", "gantryname", "sectioncode",
              "sectionname", "roadcode", "roadname", "orgcode", "orgname", "snapshottime",
              "platecolor"};
    case DataSource::Fee:
      return {"big_id", "vehicleplate", "gantryid", "gantryname", "sectioncode", "sectionname",
              "roadname", "tollname", "orgname", "transtime", "fee", "axlecount", "passstate"};
    case DataSource::Trail:
      return {"cid", "envehicleid", "exvehicleid", "entollstationname", "extollstationname",
              "entime", "extime", "envehicleclass", "exvehicleclass"};
  }
  return {};
}

std::string scroll_keepalive() {
  int minutes = config::Config::instance().optimization.scroll_keepalive_min;
  if (minutes <= 0) minutes = 5;
  return std::to_string(minutes) + "m";
}

// ---------------------------------------------------------------------------
// Unified 导出（ES Scroll，失败时 PostgreSQL）
// ---------------------------------------------------------------------------

bool execute_unified_export_es(const std::shared_ptr<ExportTaskStatus>& task) {
  const auto& opt = config::Config::instance().optimization;
  const DataSource ds = parse_data_source(task->data_source);
  const std::string index = index_name(ds);
  const std::string tf = time_field(ds);
  const std::vector<std::string> columns = export_columns(ds);

  Json body = Json::object();
  body["query"] = build_bool_query(ds, task->start_time, task->end_time, task->fuzzy, true);
  body["size"] = std::max(1, opt.export_scroll_batch);
  body["sort"] = build_sort_desc(tf);
  body["timeout"] = "120s";
  Json includes = Json::array();
  for (const auto& c : columns) includes.push_back(c);
  body["_source"] = Json::object();
  body["_source"]["includes"] = includes;

  const std::string keepalive = scroll_keepalive();
  auto first = es_json("POST", "/" + index + "/_search?scroll=" + keepalive, body);
  if (!first) return false;

  std::string scroll_id = jstr(*first, "_scroll_id");
  long long total = 0;
  int parts = 0;
  std::ofstream out;

  try {
    Json hits = member(*first, "hits");
    while (true) {
      const Json& arr = member(hits, "hits");
      if (!arr.is_array() || arr.empty()) break;

      if (!out.is_open() || total % std::max(1, opt.export_file_batch) == 0) {
        if (out.is_open()) out.close();
        ensure_dir(opt.export_dir);
        ++parts;
        std::string path = export_file_path(
            opt.export_dir, "export_" + task->task_id + "_p" + std::to_string(parts) + ".csv");
        out.open(path, std::ios::out | std::ios::trunc);
        if (!out.is_open()) throw std::runtime_error("无法创建导出文件: " + path);
        write_header(out, columns);
        task_add_file(task, path);
      }

      for (const auto& hit : arr) {
        const Json& src = member(hit, "_source");
        std::string line;
        for (std::size_t i = 0; i < columns.size(); ++i) {
          if (i) line += ",";
          line += csv_escape(value_to_string(member(src, columns[i])));
        }
        out << line << "\n";
        ++total;
      }
      out.flush();
      task_set_progress(task, total, parts);

      if (scroll_id.empty()) break;
      Json scroll_body = Json::object();
      scroll_body["scroll"] = keepalive;
      scroll_body["scroll_id"] = scroll_id;
      auto next = es_json("POST", "/_search/scroll", scroll_body);
      if (!next) throw std::runtime_error("ES scroll 请求失败");
      scroll_id = jstr(*next, "_scroll_id", scroll_id);
      hits = member(*next, "hits");
    }
  } catch (...) {
    if (out.is_open()) out.close();
    es_clear_scroll(scroll_id);
    throw;
  }

  if (out.is_open()) out.close();
  es_clear_scroll(scroll_id);
  task_finish(task, total, parts);
  return true;
}

void execute_unified_export_pg(const std::shared_ptr<ExportTaskStatus>& task) {
  const auto& opt = config::Config::instance().optimization;
  const DataSource ds = parse_data_source(task->data_source);
  const meta::EntityMeta& m = entity_meta(ds);
  const std::vector<std::string> columns = export_columns(ds);
  const long long batch = std::max(1, opt.export_scroll_batch);
  std::string where = pg_where(ds, task->start_time, task->end_time, task->fuzzy, true);

  long long total = 0;
  long long offset = 0;
  int parts = 0;
  std::ofstream out;
  while (true) {
    Json rows = pg_rows(m, where, "", batch, offset);
    if (rows.empty()) break;
    if (!out.is_open() || total % std::max(1, opt.export_file_batch) == 0) {
      if (out.is_open()) out.close();
      ensure_dir(opt.export_dir);
      ++parts;
      std::string path = export_file_path(
          opt.export_dir, "export_" + task->task_id + "_p" + std::to_string(parts) + ".csv");
      out.open(path, std::ios::out | std::ios::trunc);
      if (!out.is_open()) throw std::runtime_error("无法创建导出文件: " + path);
      write_header(out, columns);
      task_add_file(task, path);
    }
    for (const auto& row : rows) {
      std::string line;
      for (std::size_t i = 0; i < columns.size(); ++i) {
        if (i) line += ",";
        line += csv_escape(value_to_string(member(row, columns[i])));
      }
      out << line << "\n";
      ++total;
    }
    out.flush();
    task_set_progress(task, total, parts);
    offset += static_cast<long long>(rows.size());
    if (static_cast<long long>(rows.size()) < batch) break;
  }
  if (out.is_open()) out.close();
  task_finish(task, total, parts);
}

void run_unified_export(const std::shared_ptr<ExportTaskStatus>& task) {
  task_set_status(task, "RUNNING");
  try {
    if (execute_unified_export_es(task)) return;
    CM_LOG_WARN("optimization.export")
        << "[环境差异] ES 不可用，导出任务 " << task->task_id << " 改用 PostgreSQL 等价查询";
    execute_unified_export_pg(task);
  } catch (const std::exception& e) {
    CM_LOG_ERROR("optimization.export") << "导出任务 " << task->task_id << " 失败: " << e.what();
    std::lock_guard<std::mutex> lk(task->mu);
    task->status = "FAILED";
    task->error_message = e.what();
    task->finish_time = now_ms();
  }
}

// ---------------------------------------------------------------------------
// LargeScale 导出（滚动全量文档 + CSV detail）
// ---------------------------------------------------------------------------

bool execute_large_export_es(const std::shared_ptr<ExportTaskStatus>& task) {
  const auto& opt = config::Config::instance().optimization;
  const DataSource ds = resolve_data_source(task->type);
  const std::string index = index_name(ds);
  const std::string tf = time_field(ds);
  const std::string idf = id_field(ds);
  const std::string pf = plate_field(ds);

  Json body = Json::object();
  body["query"] = build_bool_query(ds, task->start_time, task->end_time, task->fuzzy, false);
  body["size"] = std::max(1, opt.export_scroll_batch);
  body["sort"] = build_sort_desc(tf);
  body["timeout"] = "120s";

  const std::string keepalive = scroll_keepalive();
  auto first = es_json("POST", "/" + index + "/_search?scroll=" + keepalive, body);
  if (!first) return false;

  std::string scroll_id = jstr(*first, "_scroll_id");
  long long total = 0;
  int parts = 0;
  std::ofstream out;

  try {
    Json hits = member(*first, "hits");
    while (true) {
      const Json& arr = member(hits, "hits");
      if (!arr.is_array() || arr.empty()) break;

      if (!out.is_open() || total % std::max(1, opt.export_file_batch) == 0) {
        if (out.is_open()) out.close();
        ensure_dir(opt.export_dir);
        ++parts;
        std::string path = export_file_path(
            opt.export_dir,
            "export_" + task->type + "_" + task->task_id + "_p" + std::to_string(parts) + ".csv");
        out.open(path, std::ios::out | std::ios::trunc);
        if (!out.is_open()) throw std::runtime_error("无法创建导出文件: " + path);
        out << idf << "," << pf << "," << tf << ",detail\n";
        task_add_file(task, path);
      }

      for (const auto& hit : arr) {
        const Json& src = member(hit, "_source");
        std::string detail = src.dump();
        detail = utils::replace_all(detail, "\n", " ");
        detail = utils::replace_all(detail, "\r", "");
        out << value_to_string(member(src, idf)) << "," << value_to_string(member(src, pf))
            << "," << value_to_string(member(src, tf)) << ",\"" << detail << "\"\n";
        ++total;
      }
      out.flush();
      task_set_progress(task, total, parts);

      if (scroll_id.empty()) break;
      Json scroll_body = Json::object();
      scroll_body["scroll"] = keepalive;
      scroll_body["scroll_id"] = scroll_id;
      auto next = es_json("POST", "/_search/scroll", scroll_body);
      if (!next) throw std::runtime_error("ES scroll 请求失败");
      scroll_id = jstr(*next, "_scroll_id", scroll_id);
      hits = member(*next, "hits");
    }
  } catch (...) {
    if (out.is_open()) out.close();
    es_clear_scroll(scroll_id);
    throw;
  }

  if (out.is_open()) out.close();
  es_clear_scroll(scroll_id);
  {
    std::lock_guard<std::mutex> lk(task->mu);
    task->status = "COMPLETED";
    task->total_exported = total;
    task->file_part_count = parts;
    task->finish_time = now_ms();
  }
  return true;
}

void execute_large_export_pg(const std::shared_ptr<ExportTaskStatus>& task) {
  const auto& opt = config::Config::instance().optimization;
  const DataSource ds = resolve_data_source(task->type);
  const meta::EntityMeta& m = entity_meta(ds);
  const std::string tf = time_field(ds);
  const std::string idf = id_field(ds);
  const std::string pf = plate_field(ds);
  const long long batch = std::max(1, opt.export_scroll_batch);
  std::string where = pg_where(ds, task->start_time, task->end_time, task->fuzzy, false);
  const std::string order = tf + " DESC";

  long long total = 0;
  long long offset = 0;
  int parts = 0;
  std::ofstream out;
  while (true) {
    Json rows = pg_rows(m, where, order, batch, offset);
    if (rows.empty()) break;
    if (!out.is_open() || total % std::max(1, opt.export_file_batch) == 0) {
      if (out.is_open()) out.close();
      ensure_dir(opt.export_dir);
      ++parts;
      std::string path = export_file_path(
          opt.export_dir,
          "export_" + task->type + "_" + task->task_id + "_p" + std::to_string(parts) + ".csv");
      out.open(path, std::ios::out | std::ios::trunc);
      if (!out.is_open()) throw std::runtime_error("无法创建导出文件: " + path);
      out << idf << "," << pf << "," << tf << ",detail\n";
      task_add_file(task, path);
    }
    for (const auto& row : rows) {
      std::string detail = row.dump();
      detail = utils::replace_all(detail, "\n", " ");
      detail = utils::replace_all(detail, "\r", "");
      out << value_to_string(member(row, idf)) << "," << value_to_string(member(row, pf))
          << "," << value_to_string(member(row, tf)) << ",\"" << detail << "\"\n";
      ++total;
    }
    out.flush();
    task_set_progress(task, total, parts);
    offset += static_cast<long long>(rows.size());
    if (static_cast<long long>(rows.size()) < batch) break;
  }
  if (out.is_open()) out.close();
  {
    std::lock_guard<std::mutex> lk(task->mu);
    task->status = "COMPLETED";
    task->total_exported = total;
    task->file_part_count = parts;
    task->finish_time = now_ms();
  }
}

void run_large_export(const std::shared_ptr<ExportTaskStatus>& task) {
  task_set_status(task, "RUNNING");
  try {
    if (execute_large_export_es(task)) return;
    CM_LOG_WARN("optimization.export")
        << "[环境差异] ES 不可用，大规模导出任务 " << task->task_id << " 改用 PostgreSQL 等价查询";
    execute_large_export_pg(task);
  } catch (const std::exception& e) {
    CM_LOG_ERROR("optimization.export")
        << "大规模导出任务 " << task->task_id << " 失败: " << e.what();
    std::lock_guard<std::mutex> lk(task->mu);
    task->status = "FAILED";
    task->error_message = e.what();
  }
}

// ---------------------------------------------------------------------------
// 同步（full / incremental / repair）
// ---------------------------------------------------------------------------

struct SyncTarget {
  DataSource ds;
  const meta::EntityMeta* meta;
};

SyncTarget sync_target(DataSource ds) {
  return SyncTarget{ds, &entity_meta(ds)};
}

std::string normalize_time(const std::string& value) {
  auto tp = timeutil::parse_naive(value);
  if (!tp) throw std::invalid_argument("时间格式不正确: " + value);
  return timeutil::format_naive_plus8(*tp);
}

Json cursor_batch(const SyncTarget& t, const std::string& start, const std::string& end,
                  const std::string& cursor_time, const std::string& cursor_id, int limit) {
  std::string where = " AND " + time_field(t.ds) + " >= " + sql_literal(start) +
                      " AND " + time_field(t.ds) + " < " + sql_literal(end);
  if (!cursor_time.empty()) {
    where += " AND (" + time_field(t.ds) + " > " + sql_literal(cursor_time) + " OR (" +
             time_field(t.ds) + " = " + sql_literal(cursor_time) + " AND " + id_field(t.ds) +
             " > " + sql_literal(cursor_id) + "))";
  }
  std::string order = time_field(t.ds) + " ASC, " + id_field(t.ds) + " ASC";
  return pg_rows(*t.meta, where, order, limit, 0);
}

struct BulkBuffer {
  std::vector<std::string> lines;
  int count = 0;
};

void bulk_flush(BulkBuffer& buf, const std::string& index, int retries = 0) {
  if (buf.lines.empty()) return;
  std::string ndjson;
  for (const auto& line : buf.lines) ndjson += line + "\n";
  auto raw = es_call("POST", "/_bulk", ndjson, "application/x-ndjson");
  if (!raw) {
    if (retries > 0) {
      std::this_thread::sleep_for(std::chrono::seconds(1));
      bulk_flush(buf, index, retries - 1);
      return;
    }
    CM_LOG_WARN("optimization.sync") << "[环境差异] ES bulk 写入失败（" << index << "，"
                                     << buf.count << " 条），已跳过";
  } else {
    try {
      Json resp = Json::parse(raw->body);
      if (member(resp, "errors").is_boolean() && member(resp, "errors").get<bool>()) {
        CM_LOG_WARN("optimization.sync") << "ES bulk 部分失败（" << index << "）";
      }
    } catch (...) {
      // 忽略解析失败
    }
  }
  buf.lines.clear();
  buf.count = 0;
}

void bulk_add(BulkBuffer& buf, const std::string& index, const std::string& id,
              const Json& source) {
  Json action = Json::object();
  Json meta_obj = Json::object();
  meta_obj["_index"] = index;
  if (!id.empty()) meta_obj["_id"] = id;
  action["index"] = meta_obj;
  buf.lines.push_back(json_dump(action));
  buf.lines.push_back(json_dump(source));
  ++buf.count;
  int batch = config::Config::instance().sync.batch_size;
  if (batch <= 0) batch = 1000;
  if (buf.count >= batch) bulk_flush(buf, index);
}

long long read_and_dispatch(const SyncTarget& t, const std::string& start,
                            const std::string& end) {
  const int scroll_batch = config::Config::instance().optimization.export_scroll_batch > 0
                               ? config::Config::instance().optimization.export_scroll_batch
                               : 2000;
  const std::string index = index_name(t.ds);
  const std::string tf = time_field(t.ds);
  const std::string idf = id_field(t.ds);
  BulkBuffer buf;
  long long total = 0;
  int empties = 0;
  std::string cursor_time;
  std::string cursor_id;

  while (true) {
    Json rows = cursor_batch(t, start, end, cursor_time, cursor_id, scroll_batch);
    if (rows.empty()) {
      if (++empties >= 3) break;
      std::this_thread::sleep_for(std::chrono::seconds(1));
      continue;
    }
    empties = 0;
    for (const auto& row : rows) {
      std::string id = jstr(row, idf);
      bulk_add(buf, index, id, row);
      ++total;
    }
    const Json& last = rows.back();
    cursor_time = normalize_time(jstr(last, tf));
    cursor_id = jstr(last, idf);
    if (static_cast<int>(rows.size()) < scroll_batch) break;
  }
  bulk_flush(buf, index);
  return total;
}

void sync_table(const SyncTarget& t, const std::string& start, const std::string& end) {
  int hours = 1;
  try {
    hours = std::stoi(config::Config::instance().yml("sync.shard.hours", "1"));
  } catch (...) {
    hours = 1;
  }
  if (hours <= 0) hours = 1;

  auto start_tp = timeutil::parse_naive(start);
  auto end_tp = timeutil::parse_naive(end);
  if (!start_tp || !end_tp) throw std::invalid_argument("同步时间范围不合法");

  long long total = 0;
  auto cur = *start_tp;
  while (cur < *end_tp) {
    auto shard_end = std::min(*end_tp, timeutil::add_hours(cur, hours));
    std::string from = timeutil::format_naive_plus8(cur);
    std::string to = timeutil::format_naive_plus8(shard_end);
    total += read_and_dispatch(t, from, to);
    cur = shard_end;
  }
  CM_LOG_INFO("optimization.sync")
      << "同步 " << ds_key(t.ds) << " 完成，范围 [" << start << ", " << end << ")，共 "
      << total << " 条";
}

// ---------------------------------------------------------------------------
// 一致性对账
// ---------------------------------------------------------------------------

long long count_gauss(DataSource ds, const std::string& start, const std::string& end) {
  const meta::EntityMeta& m = entity_meta(ds);
  std::string sql = "SELECT count(1) AS c FROM " + m.table + " WHERE " + time_field(ds) +
                    " >= " + sql_literal(start) + " AND " + time_field(ds) + " <= " +
                    sql_literal(end);
  auto r = db::PgPool::instance().query(sql);
  if (r.empty()) return 0;
  auto v = r.get(0, "c");
  if (!v) return 0;
  try {
    return std::stoll(*v);
  } catch (...) {
    return 0;
  }
}

long long count_es(DataSource ds, const std::string& start, const std::string& end) {
  Json body = Json::object();
  Json filter = Json::array();
  filter.push_back(build_range_filter(time_field(ds), start, end));
  body["query"] = Json::object();
  body["query"]["bool"] = Json::object();
  body["query"]["bool"]["filter"] = filter;
  body["size"] = 0;
  body["track_total_hits"] = true;

  auto resp = es_json("POST", "/" + index_name(ds) + "/_search", body);
  if (!resp) throw std::runtime_error("Elasticsearch 不可用，无法完成一致性对账");
  const Json& total = member(member(*resp, "hits"), "total");
  if (total.is_object()) return jlong(total, "value");
  if (total.is_number_integer()) return total.get<long long>();
  if (total.is_number_unsigned()) return static_cast<long long>(total.get<unsigned long long>());
  if (total.is_number_float()) return static_cast<long long>(total.get<double>());
  return 0;
}

std::vector<DataSource> consistency_datasets() {
  const auto& cfg = config::Config::instance();
  std::string raw = cfg.yml("consistency.reconcile.datasets",
                            cfg.yml("consistency.datasets", "snapshot,fee,trail"));
  std::vector<DataSource> out;
  for (const auto& item : utils::split_csv(raw)) {
    std::string s = lower(utils::trim(item));
    if (s == "snapshot") out.push_back(DataSource::Snapshot);
    else if (s == "fee") out.push_back(DataSource::Fee);
    else if (s == "trail") out.push_back(DataSource::Trail);
  }
  if (out.empty()) {
    out.push_back(DataSource::Snapshot);
    out.push_back(DataSource::Fee);
    out.push_back(DataSource::Trail);
  }
  return out;
}

void wall_clock(int& year, int& month, int& day, int& hour, int& minute, int& second) {
  long long ms = now_ms();
  std::time_t t = static_cast<std::time_t>(ms / 1000 + timeutil::kJavaZoneOffsetMinutes * 60);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  year = tm.tm_year + 1900;
  month = tm.tm_mon + 1;
  day = tm.tm_mday;
  hour = tm.tm_hour;
  minute = tm.tm_min;
  second = tm.tm_sec;
}

std::string month_first_day(int year, int month) {
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-01 00:00:00", year, month);
  return std::string(buf);
}

} // namespace

// ---------------------------------------------------------------------------
// 查询字段白名单（防 SQL 注入，见 optimization.h 注释）
// ---------------------------------------------------------------------------

std::string guard_query_field(DataSource ds, const std::string& field, bool translate) {
  std::string name = translate ? translate_field(ds, field) : field;
  const std::string& column = known_column_or_empty(entity_meta(ds), name);
  if (!column.empty()) return column;
  throw BindError(400, "非法查询字段 '" + field + "'：" + data_source_name(ds) +
                           " 数据源不支持该字段（白名单校验失败）");
}

// ---------------------------------------------------------------------------
// 数据源解析
// ---------------------------------------------------------------------------

std::string data_source_name(DataSource ds) {
  switch (ds) {
    case DataSource::Snapshot: return "SNAPSHOT";
    case DataSource::Fee: return "FEE";
    case DataSource::Trail: return "TRAIL";
  }
  return "SNAPSHOT";
}

DataSource parse_data_source(const std::string& ds) {
  std::string s = lower(ds);
  if (s == "snapshot") return DataSource::Snapshot;
  if (s == "fee") return DataSource::Fee;
  if (s == "trail") return DataSource::Trail;
  throw std::invalid_argument("未知数据源: " + ds + ", 合法取值: snapshot / fee / trail");
}

DataSource resolve_data_source(const std::string& type) {
  std::string s = lower(type);
  if (s == "fee") return DataSource::Fee;
  if (s == "trail") return DataSource::Trail;
  return DataSource::Snapshot;
}

// ---------------------------------------------------------------------------
// UnifiedQueryService
// ---------------------------------------------------------------------------

Json UnifiedQueryService::query(DataSource ds, const std::string& start_time,
                                const std::string& end_time, const FuzzyFields& fuzzy,
                                int page_num, int page_size) {
  // 入口白名单校验：非法字段直接 400，ES 与 PG 降级路径行为一致。
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) guard_query_field(ds, kv.first, true);
  }
  bool use_es = should_route_to_es(ds, start_time, end_time, fuzzy);

  auto query_from_pg = [&]() -> Json {
    Json all = pg_rows(entity_meta(ds), pg_where(ds, start_time, end_time, fuzzy, true), "",
                       1000, 0);
    // QueryWrapper.last("LIMIT 1000") 之后在内存中做 subList
    if (page_size < 0) return Json::array();
    long long from = std::max(0LL, static_cast<long long>(page_num - 1) * page_size);
    long long to = std::min(static_cast<long long>(all.size()), from + page_size);
    Json out = Json::array();
    if (from >= static_cast<long long>(all.size())) return out;
    for (long long i = from; i < to; ++i) out.push_back(all[static_cast<std::size_t>(i)]);
    return out;
  };

  auto query_from_es = [&]() -> std::optional<Json> {
    const auto& opt = config::Config::instance().optimization;
    int from = std::max(0, (page_num - 1) * page_size);
    int size = std::min(page_size, opt.max_window);
    if (from + size > opt.max_window) {
      CM_LOG_WARN("optimization.query")
          << "浅分页超过 max_result_window=" << opt.max_window << "，回退 PostgreSQL";
      return std::nullopt;
    }
    Json body = Json::object();
    body["query"] = build_bool_query(ds, start_time, end_time, fuzzy, true);
    body["from"] = from;
    body["size"] = size;
    body["sort"] = build_sort_desc(time_field(ds));
    body["timeout"] = std::to_string(opt.query_timeout_ms) + "ms";
    auto resp = es_json("POST", "/" + index_name(ds) + "/_search", body);
    if (!resp) return std::nullopt;
    Json out = Json::array();
    const Json& hits = member(member(*resp, "hits"), "hits");
    if (hits.is_array()) {
      for (const auto& hit : hits) out.push_back(member(hit, "_source"));
    }
    return out;
  };

  if (use_es) {
    auto es_result = query_from_es();
    if (es_result) return *es_result;
    CM_LOG_WARN("optimization.query")
        << "[环境差异] 统一查询数据源 " << data_source_name(ds)
        << " 的 ES 调用不可用，降级为 PostgreSQL 等价查询";
  }
  try {
    return query_from_pg();
  } catch (const std::exception& e) {
    CM_LOG_WARN("optimization.query") << "PostgreSQL 降级查询失败: " << e.what();
    return Json::array();
  }
}

// ---------------------------------------------------------------------------
// LargeScaleQueryService（查询 / 统计 / 导出）
// ---------------------------------------------------------------------------

Json LargeScaleQueryService::fuzzy_query(const std::string& type, const std::string& start_time,
                                         const std::string& end_time, const FuzzyFields& fuzzy,
                                         int page_num, int page_size) {
  DataSource ds = resolve_data_source(type);
  // 入口白名单校验：本服务不做逻辑字段翻译，只接受实体已知列。
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) guard_query_field(ds, kv.first, false);
  }

  int from = (page_num - 1) * page_size; // 与 Java 一致，负值交给 ES 报错 / 降级
  Json body = Json::object();
  body["query"] = build_bool_query(ds, start_time, end_time, fuzzy, false);
  body["from"] = from;
  body["size"] = page_size;
  body["sort"] = build_sort_desc(time_field(ds));
  body["terminate_after"] = 1000000;
  body["timeout"] = "30s";

  auto resp = es_json("POST", "/" + index_name(ds) + "/_search", body);
  if (resp) {
    Json out = Json::array();
    const Json& hits = member(member(*resp, "hits"), "hits");
    if (hits.is_array()) {
      for (const auto& hit : hits) out.push_back(member(hit, "_source"));
    }
    return out;
  }

  CM_LOG_WARN("optimization.query")
      << "[环境差异] 大规模查询 " << type << " 的 ES 调用不可用，降级为 PostgreSQL 等价查询";
  long long safe_from = std::max(0, from);
  long long safe_size = std::max(0, page_size);
  return pg_rows(entity_meta(ds), pg_where(ds, start_time, end_time, fuzzy, false),
                 time_field(ds) + " DESC", safe_size, safe_from);
}

Json LargeScaleQueryService::aggregation_stats(const std::string& type,
                                               const std::string& start_time,
                                               const std::string& end_time,
                                               const std::string& group_by,
                                               const std::optional<std::string>& count_field,
                                               const FuzzyFields& fuzzy, int top_n) {
  DataSource ds = resolve_data_source(type);
  // 白名单校验：groupBy/countField/fuzzyFields key 都会进入 ES DSL 或 PG 降级
  // SQL 的标识符位置，必须是实体已知列；countField 为空或 "_id" 时等价 count(1)。
  std::string group_col = guard_query_field(ds, group_by, false);
  std::string count_expr = "count(1)";
  if (count_field.has_value() && !count_field->empty() && *count_field != "_id") {
    count_expr = "count(" + guard_query_field(ds, *count_field, false) + ")";
  }
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) guard_query_field(ds, kv.first, false);
  }

  Json body = Json::object();
  body["query"] = build_bool_query(ds, start_time, end_time, fuzzy, false);
  body["size"] = 0;
  body["timeout"] = "60s";

  const std::string agg_name = "group_by_" + group_by;
  Json count_agg = Json::object();
  count_agg["value_count"] = Json::object();
  count_agg["value_count"]["field"] = count_field.has_value() ? *count_field : "_id";

  Json terms = Json::object();
  terms["field"] = group_by + ".keyword";
  terms["size"] = top_n;
  Json aggs_inner = Json::object();
  aggs_inner["total_count"] = count_agg;
  Json group_agg = Json::object();
  group_agg["terms"] = terms;
  group_agg["aggs"] = aggs_inner;

  body["aggs"] = Json::object();
  body["aggs"][agg_name] = group_agg;

  auto resp = es_json("POST", "/" + index_name(ds) + "/_search", body);
  if (resp) {
    Json out = Json::object();
    const Json& buckets = member(member(member(*resp, "aggregations"), agg_name), "buckets");
    if (buckets.is_array()) {
      for (const auto& b : buckets) {
        std::string key = jstr(b, "key_as_string");
        if (key.empty() && !member(b, "key").is_null()) key = cm::json_string(member(b, "key"));
        out[key] = static_cast<long long>(
            std::llround(member(member(b, "total_count"), "value").is_number()
                             ? member(member(b, "total_count"), "value").get<double>()
                             : 0.0));
      }
    }
    return out;
  }

  CM_LOG_WARN("optimization.query")
      << "[环境差异] 统计查询 " << type << " 的 ES 调用不可用，降级为 PostgreSQL 等价查询";
  // PG 降级路径：group_by/count_field 已在入口过白名单，此处只用解析后的物理列。
  std::string sql = "SELECT " + group_col + " AS k, " + count_expr +
                    " AS c FROM " + entity_meta(ds).table + " WHERE 1=1" +
                    pg_where(ds, start_time, end_time, fuzzy, false) + " GROUP BY " +
                    group_col + " ORDER BY c DESC LIMIT " + std::to_string(top_n);
  auto result = db::PgPool::instance().query(sql);
  Json out = Json::object();
  for (std::size_t i = 0; i < result.rows.size(); ++i) {
    auto k = result.get(i, "k");
    auto c = result.get(i, "c");
    long long count = 0;
    if (c) {
      try {
        count = std::stoll(*c);
      } catch (...) {
        count = 0;
      }
    }
    out[k ? *k : ""] = count;
  }
  return out;
}

std::string LargeScaleQueryService::submit_export_task(const std::string& type,
                                                       const std::string& start_time,
                                                       const std::string& end_time,
                                                       const FuzzyFields& fuzzy) {
  // 提交时即做白名单校验：后台线程里的 BindError 无法转成 400 响应。
  DataSource ds = resolve_data_source(type);
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) guard_query_field(ds, kv.first, false);
  }
  std::string task_id = utils::uuid4();
  auto task = create_task(task_id);
  task->data_source = data_source_name(ds);
  task->type = type.empty() ? "snapshot" : type;
  task->start_time = start_time;
  task->end_time = end_time;
  task->fuzzy = fuzzy;
  task->unified = false;
  std::thread([task] { run_large_export(task); }).detach();
  return task_id;
}

Json LargeScaleQueryService::export_status(const std::string& task_id) {
  auto task = find_task(task_id);
  if (!task) return Json(nullptr);

  Json out = Json::object();
  {
    std::lock_guard<std::mutex> lk(task->mu);
    out["code"] = 200;
    out["status"] = task->status;
    out["totalExported"] = task->total_exported;
    out["filePartCount"] = task->file_part_count;
    out["submitTime"] = task->submit_time;
    out["endTime"] = task->finish_time;
    if (task->status == "FAILED") out["errorMessage"] = task->error_message;
  }
  return out;
}

// ---------------------------------------------------------------------------
// UnifiedExportService
// ---------------------------------------------------------------------------

std::string UnifiedExportService::submit_export_task(DataSource ds, const std::string& start_time,
                                                     const std::string& end_time,
                                                     const FuzzyFields& fuzzy) {
  // 提交时即做白名单校验（translate=true：统一查询逻辑字段翻译语义）。
  for (const auto& kv : fuzzy) {
    if (!kv.second.empty()) guard_query_field(ds, kv.first, true);
  }
  std::string task_id = utils::uuid4();
  auto task = create_task(task_id);
  task->data_source = data_source_name(ds);
  task->start_time = start_time;
  task->end_time = end_time;
  task->fuzzy = fuzzy;
  task->unified = true;
  std::thread([task] { run_unified_export(task); }).detach();
  return task_id;
}

Json UnifiedExportService::export_status(const std::string& task_id) {
  auto task = find_task(task_id);
  if (!task) return Json(nullptr);

  Json out = Json::object();
  {
    std::lock_guard<std::mutex> lk(task->mu);
    out["code"] = 200;
    out["status"] = task->status;
    out["totalExported"] = task->total_exported;
    out["filePartCount"] = task->file_part_count;
    out["submitTime"] = task->submit_time;
    if (task->status == "COMPLETED") {
      out["endTime"] = task->finish_time;
      Json paths = Json::array();
      for (const auto& p : task->file_paths) paths.push_back(p);
      out["filePaths"] = paths;
      out["costSeconds"] = (task->finish_time - task->submit_time) / 1000;
    } else if (task->status == "FAILED") {
      out["errorMessage"] = task->error_message;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// ProgressiveQueryArchitectureService
// ---------------------------------------------------------------------------

std::string ProgressiveQueryArchitectureService::detect_scale_level(
    const std::string& table_name) {
  std::string key = "table:count:" + table_name;
  auto cached = cache::Redis::instance().get(key);
  if (cached) {
    long long count = 0;
    try {
      count = std::stoll(*cached);
    } catch (...) {
      throw std::runtime_error("Redis 表行数缓存不是数字: " + key);
    }
    if (count < 50000000LL) return "LEVEL_10M";
    if (count < 500000000LL) return "LEVEL_100M";
    return "LEVEL_1B";
  }
  std::string configured = config::Config::instance().yml("optimization.scale-level", "LEVEL_10M");
  if (configured == "LEVEL_10M" || configured == "LEVEL_100M" || configured == "LEVEL_1B") {
    return configured;
  }
  return "LEVEL_10M";
}

namespace {

bool any_fuzzy_set(const ProgressiveQueryRequest& req) {
  return req.platenumber.has_value() || req.gantryname.has_value() ||
         req.roadname.has_value() || req.sectionname.has_value() ||
         req.orgname.has_value() || req.tollname.has_value();
}

ProgressiveQueryResult placeholder_result() {
  ProgressiveQueryResult r;
  r.data = Json::array();
  r.total = 0;
  r.strategy = "phase3-elasticsearch";
  return r;
}

std::string snapshot_filters(const ProgressiveQueryRequest& req) {
  std::string where;
  if (req.start_time) where += " AND snapshottime >= " + sql_literal(*req.start_time);
  if (req.end_time) where += " AND snapshottime <= " + sql_literal(*req.end_time);
  auto add_like = [&](const std::optional<std::string>& v, const char* col) {
    if (v && !v->empty()) where += " AND " + std::string(col) + " LIKE " + like_literal(*v);
  };
  add_like(req.platenumber, "platenumber");
  add_like(req.gantryname, "gantryname");
  add_like(req.roadname, "roadname");
  add_like(req.sectionname, "sectionname");
  add_like(req.orgname, "orgname");
  add_like(req.tollname, "tollname");
  return where;
}

ProgressiveQueryResult snapshot_phase1(const ProgressiveQueryRequest& req) {
  const auto& m = meta::odsRtSzdnSnapshotFlowAddcode;
  Json rows = pg_rows(m, snapshot_filters(req), m.order_sql, -1, 0);
  ProgressiveQueryResult r;
  r.data = rows;
  r.total = static_cast<long long>(rows.size());
  r.strategy = "phase1-gaussdb-gin";
  return r;
}

ProgressiveQueryResult snapshot_phase2(const ProgressiveQueryRequest& req) {
  if (!req.cursor || req.cursor->empty()) {
    ProgressiveQueryResult r = snapshot_phase1(req);
    r.strategy = "phase2-partition-prune";
    return r;
  }

  // selectByCursorShard(startTime, endTime, cursor, null, pageSize)
  // mapper 中 to_timestamp(NULL) 的比较结果为 NULL，等价于无结果。
  if (!req.start_time || !req.end_time) {
    ProgressiveQueryResult r;
    r.data = Json::array();
    r.total = 0;
    r.strategy = "phase2-partition-cursor";
    return r;
  }

  const auto& m = meta::odsRtSzdnSnapshotFlowAddcode;
  std::string where = " AND snapshottime >= " + sql_literal(*req.start_time) +
                      " AND snapshottime <= " + sql_literal(*req.end_time) +
                      " AND snapshottime > " + sql_literal(*req.cursor);
  Json rows = pg_rows(m, where, "snapshottime ASC, datauuid ASC", req.page_size, 0);
  ProgressiveQueryResult r;
  r.data = rows;
  r.total = static_cast<long long>(rows.size());
  r.strategy = "phase2-partition-cursor";
  return r;
}

ProgressiveQueryResult fee_phase1(const ProgressiveQueryRequest& req) {
  std::string where;
  if (req.platenumber) where += " AND vehicleplate = " + sql_literal(*req.platenumber);
  Json rows = pg_rows(meta::odsLwzxsfsjFeeRecords01, where, "", -1, 0);
  ProgressiveQueryResult r;
  r.data = rows;
  r.total = static_cast<long long>(rows.size());
  r.strategy = "phase1-gaussdb-gin";
  return r;
}

ProgressiveQueryResult trail_phase1(const ProgressiveQueryRequest& req) {
  std::string where;
  auto check_time = [](const std::string& v) {
    if (v.empty()) throw std::invalid_argument("时间格式不正确: ");
    return v;
  };
  if (req.start_time) where += " AND entime = " + sql_literal(check_time(*req.start_time));
  if (req.end_time) where += " AND extime = " + sql_literal(check_time(*req.end_time));
  Json rows = pg_rows(meta::zdataTrailFitting, where, "", -1, 0);
  ProgressiveQueryResult r;
  r.data = rows;
  r.total = static_cast<long long>(rows.size());
  r.strategy = "phase1-gaussdb-gin";
  return r;
}

} // namespace

ProgressiveQueryResult ProgressiveQueryArchitectureService::query_snapshot_flow(
    const ProgressiveQueryRequest& req) {
  std::string level = detect_scale_level("ods_rt_szdn_snapshot_flow_addcode");
  if (level == "LEVEL_10M") return snapshot_phase1(req);
  ProgressiveQueryResult phased = snapshot_phase2(req);
  if (level == "LEVEL_100M") return phased;
  if (any_fuzzy_set(req) || req.page_size > 100) return placeholder_result();
  return phased;
}

ProgressiveQueryResult ProgressiveQueryArchitectureService::query_fee_records(
    const ProgressiveQueryRequest& req) {
  std::string level = detect_scale_level("ods_lwzxsfsj_fee_records_01");
  if (level == "LEVEL_10M") return fee_phase1(req);
  ProgressiveQueryResult phased = fee_phase1(req);
  if (level == "LEVEL_100M") return phased;
  if (req.platenumber.has_value() || req.page_size > 100) return placeholder_result();
  return phased;
}

ProgressiveQueryResult ProgressiveQueryArchitectureService::query_trail_fitting(
    const ProgressiveQueryRequest& req) {
  std::string level = detect_scale_level("zdata_trail_fitting");
  if (level == "LEVEL_10M") return trail_phase1(req);
  ProgressiveQueryResult phased = trail_phase1(req);
  if (level == "LEVEL_100M") return phased;
  return placeholder_result();
}

// ---------------------------------------------------------------------------
// 同步服务
// ---------------------------------------------------------------------------

void LargeScaleDataSyncService::full_sync_one_year() {
  auto now = timeutil::now();
  auto start = timeutil::add_days(now, -365);
  std::string from = timeutil::format_naive_plus8(start);
  std::string to = timeutil::format_naive_plus8(now);
  CM_LOG_INFO("optimization.sync") << "开始全量同步（一年），范围 [" << from << ", " << to << "]";
  for (DataSource ds : {DataSource::Snapshot, DataSource::Fee, DataSource::Trail}) {
    try {
      sync_table(sync_target(ds), from, to);
    } catch (const std::exception& e) {
      CM_LOG_ERROR("optimization.sync") << "全量同步 " << ds_key(ds) << " 失败: " << e.what();
    }
  }
}

void LargeScaleDataSyncService::incremental_sync() {
  // 上界 = now - 10s，避免读到尚未提交的事务
  auto upper_tp = timeutil::now() - std::chrono::seconds(10);
  std::string upper = timeutil::format_naive_plus8(upper_tp);

  for (DataSource ds : {DataSource::Snapshot, DataSource::Fee, DataSource::Trail}) {
    try {
      std::string key = "es:sync:watermark:" + ds_key(ds);
      auto stored = cache::Redis::instance().get(key);
      timeutil::TimePoint lower_tp;
      if (stored && !stored->empty()) {
        auto parsed = timeutil::parse_any(*stored);
        if (!parsed) parsed = timeutil::parse_naive(*stored);
        if (!parsed) throw std::runtime_error("Redis 水位时间格式不合法: " + *stored);
        lower_tp = *parsed;
      } else {
        lower_tp = timeutil::add_minutes(timeutil::now(), -60);
      }
      std::string lower = timeutil::format_naive_plus8(lower_tp);
      long long total = read_and_dispatch(sync_target(ds), lower, upper);
      if (total > 0) cache::Redis::instance().set(key, upper);
      CM_LOG_INFO("optimization.sync")
          << "增量同步 " << ds_key(ds) << " [" << lower << ", " << upper << ") " << total << " 条";
    } catch (const std::exception& e) {
      CM_LOG_ERROR("optimization.sync") << "增量同步 " << ds_key(ds) << " 失败: " << e.what();
      throw;
    }
  }
}

void LargeScaleDataSyncService::repair_sync(DataSource ds, const std::string& start_time,
                                            const std::string& end_time) {
  std::string start = normalize_time(start_time);
  std::string end = normalize_time(end_time);
  CM_LOG_INFO("optimization.sync")
      << "开始补同步 " << ds_key(ds) << " [" << start << ", " << end << ")";
  sync_table(sync_target(ds), start, end);
}

// ---------------------------------------------------------------------------
// GaussEsConsistencyService
// ---------------------------------------------------------------------------

void GaussEsConsistencyService::consistency_tick() {
  const auto& cfg = config::Config::instance();
  if (!cfg.consistency.reconcile_enabled) return;

  double threshold = cfg.consistency.drift_ratio;
  if (auto pct = cfg.yaml().get("consistency.reconcile.drift_threshold_pct")) {
    try {
      threshold = std::stod(*pct) / 100.0;
    } catch (...) {
      // 保持 drift-ratio
    }
  }

  int lookback = cfg.consistency.lookback_months;
  if (lookback <= 0) lookback = 1;

  std::vector<DataSource> datasets = consistency_datasets();

  for (int i = 0; i < lookback; ++i) {
    int year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0;
    wall_clock(year, month, day, hour, minute, second);
    (void)day;
    (void)hour;
    (void)minute;
    (void)second;
    int start_month = month - (i + 1);
    int start_year = year;
    while (start_month <= 0) {
      start_month += 12;
      --start_year;
    }
    std::string window_start = month_first_day(start_year, start_month);
    std::string window_end = month_first_day(year, month);

    for (DataSource ds : datasets) {
      try {
        long long gauss = count_gauss(ds, window_start, window_end);
        long long es = count_es(ds, window_start, window_end);
        long long diff = std::llabs(gauss - es);
        double base = static_cast<double>(std::max(1LL, std::max(gauss, es)));
        double ratio = static_cast<double>(diff) / base;
        if (ratio > threshold) {
          CM_LOG_WARN("optimization.consistency")
              << "[一致性漂移] dataset=" << ds_key(ds) << " window=[" << window_start << ", "
              << window_end << ") gauss=" << gauss << " es=" << es << " drift=" << diff
              << " ratio=" << ratio << " threshold=" << threshold << "，触发补同步";
          DataSource target = ds;
          std::string s = window_start;
          std::string e = window_end;
          std::thread([target, s, e] {
            try {
              data_sync().repair_sync(target, s, e);
            } catch (const std::exception& ex) {
              CM_LOG_ERROR("optimization.consistency") << "补同步失败: " << ex.what();
            }
          }).detach();
        } else {
          CM_LOG_INFO("optimization.consistency")
              << "[一致性] dataset=" << ds_key(ds) << " window=[" << window_start << ", "
              << window_end << ") gauss=" << gauss << " es=" << es << " consistent";
        }
      } catch (const std::exception& e) {
        CM_LOG_ERROR("optimization.consistency")
            << "[一致性] dataset=" << ds_key(ds) << " 对账失败: " << e.what();
      }
    }
  }
}

void ensure_consistency_scheduler() {
  static std::once_flag once;
  std::call_once(once, [] {
    std::thread([] {
      const auto& cfg = config::Config::instance();
      std::vector<std::string> fields = utils::split(cfg.consistency.cron, ' ');
      if (fields.size() < 3) {
        CM_LOG_WARN("optimization.consistency")
            << "consistency.reconcile.cron 配置不合法: " << cfg.consistency.cron;
        return;
      }
      int second = 0, minute = 30, hour = 2;
      try {
        second = std::stoi(fields[0]);
        minute = std::stoi(fields[1]);
        hour = std::stoi(fields[2]);
      } catch (...) {
        CM_LOG_WARN("optimization.consistency")
            << "consistency.reconcile.cron 仅支持固定时分秒: " << cfg.consistency.cron;
        return;
      }
      int last_day = -1;
      while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        if (!config::Config::instance().consistency.reconcile_enabled) continue;
        int year = 0, month = 0, day = 0, h = 0, m = 0, s = 0;
        wall_clock(year, month, day, h, m, s);
        (void)year;
        (void)month;
        if (h == hour && m == minute && s == second && day != last_day) {
          last_day = day;
          consistency_service().consistency_tick();
        }
      }
    }).detach();
  });
}

// ---------------------------------------------------------------------------
// 单例
// ---------------------------------------------------------------------------

UnifiedQueryService& unified_query() {
  static UnifiedQueryService s;
  return s;
}

LargeScaleQueryService& large_scale_query() {
  static LargeScaleQueryService s;
  return s;
}

UnifiedExportService& unified_export() {
  static UnifiedExportService s;
  return s;
}

ProgressiveQueryArchitectureService& progressive_query() {
  static ProgressiveQueryArchitectureService s;
  return s;
}

LargeScaleDataSyncService& data_sync() {
  static LargeScaleDataSyncService s;
  return s;
}

GaussEsConsistencyService& consistency_service() {
  static GaussEsConsistencyService s;
  return s;
}

} // namespace cm::service
