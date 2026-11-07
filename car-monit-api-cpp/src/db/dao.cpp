#include "db/dao.h"

#include "common/datetime.h"
#include "common/logging.h"
#include "common/utils.h"

#include <algorithm>
#include <cctype>

namespace cm::repo {
namespace {

std::string to_under_score(const std::string& s) {
  std::string out;
  for (std::size_t i = 0; i < s.size(); ++i) {
    char c = s[i];
    if (std::isupper(static_cast<unsigned char>(c))) {
      if (i > 0 && out.back() != '_') out.push_back('_');
      out.push_back(char(std::tolower(static_cast<unsigned char>(c))));
    } else {
      out.push_back(c);
    }
  }
  return out;
}

bool valid_order_column(const std::string& col) {
  if (col.empty()) return false;
  for (char c : col)
    if (!std::isalnum(static_cast<unsigned char>(c)) && c != '_' && c != '.') return false;
  return true;
}

Json convert_value(meta::FType type, const std::optional<std::string>& raw) {
  if (!raw) return Json(nullptr);
  const std::string& v = *raw;
  switch (type) {
    case meta::FType::Str:
      return Json(v);
    case meta::FType::Int:
    case meta::FType::JavaLong: {
      if (v.empty()) return Json(nullptr);
      try {
        long long n = std::stoll(v);
        return Json(n);
      } catch (...) {
        return Json(v);
      }
    }
    case meta::FType::Double:
    case meta::FType::Decimal:
      // Java 域类里没有 Double 字段，元数据中标为 Double 的列实际都是 BigDecimal
      // （lon/lat、各种 fee/weight 等）；Java BigDecimal 序列化会保留标度与尾零
      // （1.50 不能变成 1.5），因此统一按 BigDecimal 文本字面量输出。
      if (v.empty()) return Json(nullptr);
      return json_raw_decimal(v);
    case meta::FType::Timestamp: {
      auto tp = timeutil::from_db_text(v);
      return tp ? Json(timeutil::format_timestamp(*tp)) : Json(v);
    }
    case meta::FType::DateTime: {
      auto tp = timeutil::from_db_text(v);
      return tp ? Json(timeutil::format_datetime(*tp)) : Json(v);
    }
    case meta::FType::Day: {
      auto tp = timeutil::from_db_text(v);
      return tp ? Json(timeutil::format_day(*tp)) : Json(v);
    }
    case meta::FType::Json: {
      if (v.empty()) return Json(nullptr);
      try {
        return Json::parse(v);
      } catch (...) {
        return Json(v);
      }
    }
  }
  return Json(v);
}

std::optional<std::string> lookup(const db::PgResult& r, std::size_t row,
                                  const std::string& column) {
  if (column.empty()) return std::nullopt;
  auto v = r.get(row, column);
  if (v) return v;
  // 大小写不敏感回退（PG 未加引号的标识符统一小写）。
  for (std::size_t i = 0; i < r.columns.size(); ++i) {
    if (utils::equals_ignore_case(r.columns[i], column)) {
      if (i < r.rows[row].size()) return r.rows[row][i];
      break;
    }
  }
  return std::nullopt;
}

} // namespace

std::string quote(const std::string& value) {
  return "'" + utils::replace_all(value, "'", "''") + "'";
}

std::string in_list(const std::vector<std::string>& values) {
  std::string out;
  for (std::size_t i = 0; i < values.size(); ++i) {
    std::string v = utils::trim(values[i]);
    if (v.empty()) continue;
    if (!out.empty()) out += ",";
    out += quote(v);
  }
  if (out.empty()) out = "''";
  return "(" + out + ")";
}

PageInfo resolve_page(const http::Request& req) {
  PageInfo p;
  auto page_num = req.get_int("pageNum");
  auto page_size = req.get_int("pageSize");
  if (page_num && page_size && *page_size > 0) {
    p.paged = true;
    p.page_num = *page_num;
    p.page_size = *page_size;
  }
  std::string col = req.str("orderByColumn");
  if (!col.empty()) {
    std::string under = to_under_score(utils::trim(col));
    if (valid_order_column(under) && under != "orderby") {
      std::string asc = req.str("isAsc", "asc");
      std::string dir = utils::equals_ignore_case(utils::trim(asc), "desc") ? "desc" : "asc";
      p.order_by = under + " " + dir;
    }
  }
  return p;
}

Json project_row(const meta::EntityMeta& meta, const db::PgResult& result, std::size_t row) {
  Json obj = Json::object();
  for (const auto& f : meta.fields) {
    obj[f.json] = convert_value(f.type, lookup(result, row, f.column));
  }
  return obj;
}

std::string where_from_filters(const meta::EntityMeta& meta, const http::Request& req,
                               const std::vector<std::pair<std::string, std::string>>& extra) {
  std::string where;
  for (const auto& f : meta.filters) {
    auto v = req.get(f.json);
    if (!v || v->empty()) continue;
    std::string value = *v;
    switch (f.op) {
      case meta::FOp::Eq:
        where += " AND " + f.column + " = " + quote(value);
        break;
      case meta::FOp::Like: {
        std::string esc = utils::replace_all(value, "'", "''");
        esc = utils::replace_all(esc, "%", "\\%");
        where += " AND " + f.column + " LIKE '%" + esc + "%'";
        break;
      }
      case meta::FOp::ILike:
        where += " AND " + f.column + " ILIKE '%" + utils::replace_all(value, "'", "''") + "%'";
        break;
      case meta::FOp::In:
        where += " AND " + f.column + " IN " + in_list(utils::split_csv(value));
        break;
      case meta::FOp::Gte:
        where += " AND " + f.column + " >= " + quote(value);
        break;
      case meta::FOp::Lte:
        where += " AND " + f.column + " <= " + quote(value);
        break;
      case meta::FOp::Gt:
        where += " AND " + f.column + " > " + quote(value);
        break;
      case meta::FOp::Lt:
        where += " AND " + f.column + " < " + quote(value);
        break;
    }
  }
  for (const auto& kv : extra) where += " AND " + kv.first + " " + kv.second;
  return where;
}

Json select_list_raw(const std::string& base_sql, const http::Request& req) {
  PageInfo page = resolve_page(req);
  std::string sql = base_sql;
  if (page.paged) {
    long long cnt = count_rows(sql);
    long long pages = page.page_size > 0 ? (cnt + page.page_size - 1) / page.page_size : 0;
    if (page.page_num < 1) page.page_num = 1;
    if (page.page_num > pages && pages > 0) page.page_num = int(pages);
  }
  if (!page.order_by.empty()) sql += " ORDER BY " + page.order_by;
  else {
    // 保留原 SQL 中已有的 ORDER BY，不做改动。
  }
  if (page.paged) {
    long long offset = static_cast<long long>(page.page_num - 1) * page.page_size;
    sql += " LIMIT " + std::to_string(page.page_size) + " OFFSET " + std::to_string(offset);
  }
  CM_LOG_DEBUG("db.dao") << "SQL: " << sql;
  auto result = db::PgPool::instance().query(sql);
  Json rows = Json::array();
  for (std::size_t i = 0; i < result.rows.size(); ++i) {
    Json obj = Json::object();
    for (std::size_t c = 0; c < result.columns.size(); ++c) {
      const auto& v = result.rows[i][c];
      obj[result.columns[c]] = v ? Json(*v) : Json(nullptr);
    }
    rows.push_back(obj);
  }
  return rows; // 调用方自行处理 total
}

long long count_rows(const std::string& from_and_where) {
  std::string body = from_and_where;
  // 去掉已有的 limit/offset 和 order by，用子查询计数最稳妥。
  std::string sql = "SELECT count(1) AS cnt FROM (" + body + ") _c";
  try {
    auto r = db::PgPool::instance().query(sql);
    if (!r.rows.empty() && r.rows[0][0]) return std::stoll(*r.rows[0][0]);
  } catch (const std::exception& e) {
    CM_LOG_WARN("db.dao") << "count 失败: " << e.what();
  }
  return 0;
}

Json select_list(const meta::EntityMeta& meta, const http::Request& req,
                 const std::string& extra_where,
                 const std::optional<std::string>& columns_override) {
  std::string columns = columns_override ? *columns_override : meta.select_sql;
  std::string sql = "SELECT " + columns + " FROM " + meta.table + " WHERE 1=1";
  sql += where_from_filters(meta, req);
  sql += extra_where;
  if (!meta.order_sql.empty()) sql += " ORDER BY " + meta.order_sql;

  PageInfo page = resolve_page(req);
  long long total = 0;
  if (page.paged) {
    total = count_rows(sql);
    long long pages = page.page_size > 0 ? (total + page.page_size - 1) / page.page_size : 0;
    if (page.page_num < 1) page.page_num = 1;
    if (page.page_num > pages && pages > 0) page.page_num = int(pages);
    if (!page.order_by.empty()) {
      // 覆盖 mapper 的默认排序（PageHelper 的 orderBy 会追加，这里保持追加语义）
      sql += ", " + page.order_by;
    }
    long long offset = static_cast<long long>(page.page_num - 1) * page.page_size;
    sql += " LIMIT " + std::to_string(page.page_size) + " OFFSET " + std::to_string(offset);
  } else if (!page.order_by.empty()) {
    if (meta.order_sql.empty()) sql += " ORDER BY " + page.order_by;
    else sql += ", " + page.order_by;
  }

  CM_LOG_DEBUG("db.dao") << "SQL: " << sql;
  auto result = db::PgPool::instance().query(sql);
  Json rows = Json::array();
  for (std::size_t i = 0; i < result.rows.size(); ++i)
    rows.push_back(project_row(meta, result, i));
  Json envelope = Json::object();
  envelope["rows"] = rows;
  envelope["total"] = page.paged ? total : static_cast<long long>(rows.size());
  return envelope;
}

// SELECT 子句里的主分别名（如 `id AS agent_pk`）不能用于 WHERE；当实体过滤条件给出了
// 同一 JSON 名对应的物理列时，以物理列为准（对应 Java XML 中 `where t.id = #{agentPk}`）。
static std::string physical_pk_column(const meta::EntityMeta& meta) {
  for (const auto& f : meta.fields) {
    if (!f.pk) continue;
    for (const auto& flt : meta.filters)
      if (flt.json == f.json && !flt.column.empty()) return flt.column;
    if (!f.column.empty()) return f.column;
  }
  return "";
}

Json select_by_id(const meta::EntityMeta& meta, const std::string& id) {
  std::string pk_column = physical_pk_column(meta);
  if (pk_column.empty()) return Json(nullptr);
  std::string sql = "SELECT " + meta.select_sql + " FROM " + meta.table + " WHERE " + pk_column +
                    " = " + quote(id);
  CM_LOG_DEBUG("db.dao") << "SQL: " << sql;
  auto result = db::PgPool::instance().query(sql);
  if (result.rows.empty()) return Json(nullptr);
  return project_row(meta, result, 0);
}

Json select_by_ids(const meta::EntityMeta& meta, const std::string& ids) {
  std::string pk_column = physical_pk_column(meta);
  Json rows = Json::array();
  if (pk_column.empty()) return rows;
  auto values = utils::split_csv(ids);
  if (values.empty()) return rows;
  std::string sql = "SELECT " + meta.select_sql + " FROM " + meta.table + " WHERE " + pk_column +
                    " IN " + in_list(values);
  CM_LOG_DEBUG("db.dao") << "SQL: " << sql;
  auto result = db::PgPool::instance().query(sql);
  for (std::size_t i = 0; i < result.rows.size(); ++i)
    rows.push_back(project_row(meta, result, i));
  return rows;
}

} // namespace cm::repo
