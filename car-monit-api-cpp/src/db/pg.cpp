#include "db/pg.h"

#include "common/error.h"
#include "common/logging.h"
#include "common/utils.h"
#include "db/auth_guard.h"

#include <libpq-fe.h>
#include <pqxx/pqxx>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <sstream>
#include <utility>

namespace cm::db {
namespace {

std::string conn_value(const std::string& v) {
  std::string out;
  out.reserve(v.size() + 2);
  out.push_back('\'');
  for (char c : v) {
    if (c == '\\' || c == '\'') out.push_back('\\');
    out.push_back(c);
  }
  out.push_back('\'');
  return out;
}

std::string lower_copy(const std::string& s) {
  std::string out = s;
  std::transform(out.begin(), out.end(), out.begin(), [](unsigned char c) {
    return static_cast<char>(std::tolower(c));
  });
  return out;
}

bool contains_any(const std::string& haystack, const std::vector<std::string>& needles) {
  for (const auto& n : needles) {
    if (haystack.find(n) != std::string::npos) return true;
  }
  return false;
}

pqxx::params to_params(const PgParams& params) {
  pqxx::params p;
  p.reserve(params.size());
  for (const auto& v : params) p.append(v);
  return p;
}

PgResult map_result(const pqxx::result& r) {
  PgResult out;
  const pqxx::row_size_type cols = r.columns();
  out.columns.reserve(static_cast<std::size_t>(cols));
  out.fields.reserve(static_cast<std::size_t>(cols));
  for (pqxx::row_size_type c = 0; c < cols; ++c) {
    PgField f;
    f.name = r.column_name(c);
    f.type_oid = static_cast<int>(r.column_type(c));
    f.format = 0;
    out.columns.push_back(f.name);
    out.fields.push_back(std::move(f));
  }
  out.rows.reserve(static_cast<std::size_t>(r.size()));
  for (const auto& row : r) {
    std::vector<std::optional<std::string>> values;
    values.reserve(static_cast<std::size_t>(row.size()));
    for (pqxx::row::size_type c = 0; c < row.size(); ++c) {
      const auto& field = row[c];
      if (field.is_null())
        values.emplace_back(std::nullopt);
      else
        values.emplace_back(field.as<std::string>());
    }
    out.rows.push_back(std::move(values));
  }
  out.affected = static_cast<long long>(r.affected_rows());
  return out;
}

} // namespace

std::string build_conninfo(const PgConnOptions& o) {
  std::ostringstream out;
  out << "host=" << conn_value(o.host) << " port=" << o.port << " user=" << conn_value(o.user)
      << " password=" << conn_value(o.password) << " dbname=" << conn_value(o.database)
      << " sslmode=" << conn_value(o.sslmode.empty() ? "prefer" : o.sslmode)
      << " client_encoding=" << conn_value("UTF8")
      << " application_name=" << conn_value("car-monit-api-cpp");
  if (!o.sslrootcert.empty()) out << " sslrootcert=" << conn_value(o.sslrootcert);
  const int seconds = std::max(1, (o.connect_timeout_ms + 999) / 1000);
  out << " connect_timeout=" << seconds;
  return out.str();
}

std::string classify_connect_error(const std::string& message) {
  const std::string m = lower_copy(message);
  // 先判口令类：openGauss / PostgreSQL 的失败登录文本。
  if (contains_any(m, {"password authentication failed", "authentication failed",
                       "invalid password", "password authentication"}))
    return "28P01";
  // 账号锁定 / 认证规格不允许（pg_hba 拒绝、失败次数超限、账号被锁）。
  if (contains_any(m, {"locked", "too many authentication failures", "no pg_hba.conf entry",
                       "pg_hba.conf rejects", "invalid authorization"}))
    return "28000";
  return "08001";
}

struct PgConn::Impl {
  explicit Impl(pqxx::connection c) : conn(std::move(c)) {}
  pqxx::connection conn;
};

PgConn::PgConn() = default;
PgConn::~PgConn() = default;

void PgConn::close() { impl_.reset(); }

bool PgConn::alive() const { return impl_ && impl_->conn.is_open(); }

const std::string& PgConn::last_sqlstate() const { return last_sqlstate_; }

bool PgConn::connect(const PgConnOptions& options) {
  close();
  last_sqlstate_.clear();

  auto& guard = AuthGuard::instance();
  const auto outcome = guard.attempt([&]() -> AuthGuard::Outcome {
    const std::string conninfo = build_conninfo(options);
    PGconn* raw = PQconnectdb(conninfo.c_str());
    if (raw == nullptr) {
      last_sqlstate_ = "08001";
      CM_LOG_ERROR("db.pg") << "PQconnectdb 返回空连接";
      return AuthGuard::Outcome::OtherError;
    }
    if (PQstatus(raw) != CONNECTION_OK) {
      std::string msg = PQerrorMessage(raw) ? PQerrorMessage(raw) : "";
      const std::string state = classify_connect_error(msg);
      PQfinish(raw);
      last_sqlstate_ = state;
      if (state == "28P01" || state == "28000") {
        CM_LOG_ERROR("db.pg") << "认证失败 [" << state << "] " << msg;
        guard.mark_auth_failure(state, state == "28000" ? "账号被锁定或认证被拒" : "口令被拒绝");
        return AuthGuard::Outcome::AuthFailed;
      }
      CM_LOG_ERROR("db.pg") << "建连失败 [" << state << "] " << msg;
      return AuthGuard::Outcome::OtherError;
    }

    try {
      impl_ = std::make_unique<Impl>(pqxx::connection::seize_raw_connection(raw));
      // 会话参数：与 Java 数据源/驱动保持一致的文本格式与标度。
      pqxx::nontransaction setup(impl_->conn);
      setup.exec("SET client_encoding TO 'UTF8'");
      setup.exec("SET datestyle TO 'ISO'");
      setup.exec("SET extra_float_digits = 3");
      if (options.statement_timeout_ms > 0) {
        setup.exec("SET statement_timeout = " +
                   std::to_string(options.statement_timeout_ms));
      }
      return AuthGuard::Outcome::Ok;
    } catch (const pqxx::sql_error& e) {
      last_sqlstate_ = e.sqlstate();
      CM_LOG_ERROR("db.pg") << "会话初始化失败 [" << e.sqlstate() << "] " << e.what();
    } catch (const std::exception& e) {
      last_sqlstate_ = "08001";
      CM_LOG_ERROR("db.pg") << "会话初始化异常: " << e.what();
    }
    impl_.reset();
    return AuthGuard::Outcome::OtherError;
  });
  return outcome == AuthGuard::Outcome::Ok;
}

PgResult PgConn::query(const std::string& sql) { return query(sql, {}); }

PgResult PgConn::query(const std::string& sql, const PgParams& params) {
  if (!alive()) throw DbError("08003", "数据库连接已关闭");
  try {
    pqxx::nontransaction tx(impl_->conn);
    if (params.empty()) return map_result(tx.exec(sql));
    return map_result(tx.exec(sql, to_params(params)));
  } catch (const pqxx::sql_error& e) {
    throw DbError(e.sqlstate().empty() ? "42601" : e.sqlstate(), e.what());
  } catch (const pqxx::broken_connection& e) {
    close();
    throw DbError("08006", e.what());
  } catch (const pqxx::failure& e) {
    throw DbError("HY000", e.what());
  }
}

long long PgConn::execute(const std::string& sql) { return execute(sql, {}); }

long long PgConn::execute(const std::string& sql, const PgParams& params) {
  if (!alive()) throw DbError("08003", "数据库连接已关闭");
  try {
    pqxx::nontransaction tx(impl_->conn);
    pqxx::result r = params.empty() ? tx.exec(sql) : tx.exec(sql, to_params(params));
    return static_cast<long long>(r.affected_rows());
  } catch (const pqxx::sql_error& e) {
    throw DbError(e.sqlstate().empty() ? "42601" : e.sqlstate(), e.what());
  } catch (const pqxx::broken_connection& e) {
    close();
    throw DbError("08006", e.what());
  } catch (const pqxx::failure& e) {
    throw DbError("HY000", e.what());
  }
}

std::string PgConn::version() {
  try {
    auto r = query("SELECT version()");
    if (!r.rows.empty() && r.rows[0][0]) return *r.rows[0][0];
  } catch (...) {
  }
  return "";
}

std::vector<PgResult> PgConn::transaction(
    const std::vector<std::pair<std::string, bool>>& stmts) {
  if (!alive()) throw DbError("08003", "数据库连接已关闭");
  try {
    pqxx::work tx(impl_->conn);
    std::vector<PgResult> out;
    out.reserve(stmts.size());
    for (const auto& st : stmts) {
      auto r = tx.exec(st.first);
      if (st.second) {
        out.push_back(map_result(r));
      } else {
        PgResult p;
        p.affected = static_cast<long long>(r.affected_rows());
        out.push_back(std::move(p));
      }
    }
    tx.commit();
    return out;
  } catch (const pqxx::sql_error& e) {
    throw DbError(e.sqlstate().empty() ? "42601" : e.sqlstate(), e.what());
  } catch (const pqxx::broken_connection& e) {
    close();
    throw DbError("08006", e.what());
  } catch (const pqxx::failure& e) {
    throw DbError("HY000", e.what());
  }
}

std::optional<std::string> PgResult::get(std::size_t row, const std::string& column) const {
  auto it = std::find(columns.begin(), columns.end(), column);
  if (it == columns.end()) return std::nullopt;
  std::size_t idx = std::size_t(it - columns.begin());
  if (row >= rows.size() || idx >= rows[row].size()) return std::nullopt;
  return rows[row][idx];
}

// ---------------- PgPool ----------------

PgPool& PgPool::instance() {
  static PgPool pool;
  return pool;
}

void PgPool::init(const PgConnOptions& options, int max_conns, int min_idle, int max_wait_ms) {
  std::lock_guard<std::mutex> lock(mu_);
  // 二次防线：即便调用方没做启动校验，口令不合法时也不初始化连接池（不发起连接）。
  auto check = check_password(options.password);
  if (!check.ok) {
    CM_LOG_ERROR("db.pg") << "拒绝初始化连接池：" << check.problem;
    inited_ = false;
    return;
  }
  options_ = options;
  options_.sslmode = options.sslmode.empty() ? "prefer" : options.sslmode;
  max_ = max_conns > 0 ? max_conns : 20;
  min_ = min_idle > 0 ? min_idle : 5;
  wait_ms_ = max_wait_ms > 0 ? max_wait_ms : 60000;
  slots_.clear();
  ++generation_;
  consecutive_connect_failures_ = 0;
  breaker_until_epoch_ms_ = 0;
  inited_ = true;
}

void PgPool::shutdown() {
  std::lock_guard<std::mutex> lock(mu_);
  for (auto& slot : slots_) slot.conn.reset();
  slots_.clear();
  ++generation_;
  inited_ = false;
  cv_.notify_all();
}

bool PgPool::available() { return inited_; }

int PgPool::max_connections() {
  std::lock_guard<std::mutex> guard(mu_);
  return max_;
}

int PgPool::live_connections() {
  std::lock_guard<std::mutex> guard(mu_);
  int live = 0;
  for (const auto& slot : slots_) {
    if (slot.conn && slot.conn->alive()) ++live;
  }
  return live;
}

void PgPool::note_connect_result_locked(bool ok) {
  if (ok) {
    consecutive_connect_failures_ = 0;
    breaker_until_epoch_ms_ = 0;
    return;
  }
  if (++consecutive_connect_failures_ >= kConnectFailureThreshold) {
    breaker_until_epoch_ms_ =
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count() +
        kConnectCooldownMs;
    consecutive_connect_failures_ = 0;
    CM_LOG_ERROR("db.pg") << "连续 " << kConnectFailureThreshold << " 次建连失败，进入 "
                          << kConnectCooldownMs / 1000
                          << "s 熔断冷却（认证失败由 AuthGuard 单独熔断）";
  }
}

PgPool::Borrowed PgPool::acquire() {
  std::unique_lock<std::mutex> lock(mu_);
  if (!inited_) throw DbError("08003", "数据库连接池未初始化");
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(wait_ms_);
  while (true) {
    // 网络故障熔断：冷却期内快速失败，不再每次请求都等满建连超时。
    if (breaker_until_epoch_ms_ > 0) {
      long long now = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::system_clock::now().time_since_epoch())
                          .count();
      if (now < breaker_until_epoch_ms_) {
        throw DbError("08001", "数据库连接连续失败，熔断冷却中（约 " +
                                   std::to_string((breaker_until_epoch_ms_ - now + 999) / 1000) +
                                   "s 后允许重试）");
      }
      breaker_until_epoch_ms_ = 0; // 冷却结束，放行一次探测
    }
    // 1) 锁内取空闲健康连接。
    for (std::size_t i = 0; i < slots_.size(); ++i) {
      if (!slots_[i].in_use && !slots_[i].reserved && slots_[i].conn && slots_[i].conn->alive()) {
        slots_[i].in_use = true;
        return Borrowed{i, slots_[i].conn.get()};
      }
    }
    // 2) 未达上限：优先复用空槽，否则追加新槽做预留，然后锁外建连。
    std::size_t reserved_index = std::string::npos;
    for (std::size_t i = 0; i < slots_.size(); ++i) {
      if (!slots_[i].in_use && !slots_[i].reserved && !slots_[i].conn) {
        slots_[i].reserved = true;
        slots_[i].reserve_gen = generation_;
        reserved_index = i;
        break;
      }
    }
    if (reserved_index == std::string::npos && slots_.size() < std::size_t(max_)) {
      ConnSlot slot;
      slot.reserved = true;
      slot.reserve_gen = generation_;
      slots_.push_back(std::move(slot));
      reserved_index = slots_.size() - 1;
    }
    if (reserved_index != std::string::npos) {
      const long long gen = generation_;
      // 锁外建连：连接参数先拷贝到栈上，避免与 init()/shutdown() 竞争。
      const PgConnOptions options = options_;
      lock.unlock();
      auto conn = std::make_unique<PgConn>();
      const bool ok = conn->connect(options);
      const std::string state = conn->last_sqlstate();
      lock.lock();
      // 池在锁外建连期间被 shutdown/re-init：丢弃本连接（gen 不匹配）。
      if (!inited_ || reserved_index >= slots_.size() || !slots_[reserved_index].reserved ||
          slots_[reserved_index].reserve_gen != gen) {
        cv_.notify_all();
        throw DbError("08003", "数据库连接池已关闭");
      }
      note_connect_result_locked(ok);
      if (!ok) {
        // 回收占位（保留空槽供下次复用，槽位总数不增长）。
        slots_[reserved_index].reserved = false;
        cv_.notify_all();
        if (state == "28P01" || state == "28000") {
          throw DbError(state, state == "28000" ? "数据库账号被锁定或认证被拒"
                                               : "数据库口令被拒绝");
        }
        throw DbError("08001", "无法连接数据库 " + options_.host + ":" +
                                   std::to_string(options_.port));
      }
      slots_[reserved_index].conn = std::move(conn);
      slots_[reserved_index].reserved = false;
      slots_[reserved_index].in_use = true;
      return Borrowed{reserved_index, slots_[reserved_index].conn.get()};
    }
    // 3) 达到上限：条件变量等待空闲（maxWait 超时），替代原 10ms 轮询。
    if (cv_.wait_until(lock, deadline) == std::cv_status::timeout) {
      for (std::size_t i = 0; i < slots_.size(); ++i) {
        if (!slots_[i].in_use && !slots_[i].reserved && slots_[i].conn && slots_[i].conn->alive()) {
          slots_[i].in_use = true;
          return Borrowed{i, slots_[i].conn.get()};
        }
      }
      throw DbError("08001", "等待数据库连接超时（maxWait=" + std::to_string(wait_ms_) + "ms）");
    }
  }
}

void PgPool::release(std::size_t index, bool broken) {
  {
    std::lock_guard<std::mutex> guard(mu_);
    if (index < slots_.size()) {
      if (broken) slots_[index].conn.reset(); // 空槽保留复用
      slots_[index].in_use = false;
    }
  }
  cv_.notify_all();
}

PgResult PgPool::query(const std::string& sql) { return query(sql, {}); }

PgResult PgPool::query(const std::string& sql, const PgParams& params) {
  Borrowed b = acquire();
  try {
    PgResult result = b.raw->query(sql, params);
    release(b.index, false);
    return result;
  } catch (const DbError& e) {
    release(b.index, e.sqlstate().rfind("08", 0) == 0);
    throw;
  } catch (...) {
    release(b.index, true);
    throw;
  }
}

long long PgPool::execute(const std::string& sql) { return execute(sql, {}); }

long long PgPool::execute(const std::string& sql, const PgParams& params) {
  Borrowed b = acquire();
  try {
    long long affected = b.raw->execute(sql, params);
    release(b.index, false);
    return affected;
  } catch (const DbError& e) {
    release(b.index, e.sqlstate().rfind("08", 0) == 0);
    throw;
  } catch (...) {
    release(b.index, true);
    throw;
  }
}

long long PgPool::execute_in_tx(const std::vector<std::string>& sqls) {
  std::vector<std::pair<std::string, bool>> stmts;
  stmts.reserve(sqls.size());
  for (const auto& s : sqls) stmts.emplace_back(s, false);
  auto results = transaction(stmts);
  long long total = 0;
  for (const auto& r : results) total += r.affected;
  return total;
}

std::vector<PgResult> PgPool::transaction(
    const std::vector<std::pair<std::string, bool>>& stmts) {
  Borrowed b = acquire();
  bool broken = false;
  try {
    auto out = b.raw->transaction(stmts);
    release(b.index, false);
    return out;
  } catch (const DbError& e) {
    broken = e.sqlstate().rfind("08", 0) == 0;
    release(b.index, broken);
    throw;
  } catch (...) {
    release(b.index, true);
    throw;
  }
}

} // namespace cm::db
