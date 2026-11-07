#include "db/auth_guard.h"

#include "common/logging.h"

#include <cctype>

namespace cm::db {
namespace {

const char* kStopRetry = "已停止重试，避免触发账号锁定";

std::string trim_copy(const std::string& s) {
  std::size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  std::size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}

} // namespace

CredentialCheck check_password(const std::string& password) {
  CredentialCheck r;
  const std::string v = trim_copy(password);
  if (v.empty()) {
    r.ok = false;
    r.problem =
        "数据库口令为空：configs/config.yaml 使用 ${CM_PG_PASSWORD} 占位，但环境变量未设置，"
        "且 configs/config.local.yaml 未提供口令";
    return r;
  }
  if (v.find("${") != std::string::npos) {
    r.ok = false;
    r.problem = "数据库口令仍是未展开的 ${...} 占位（形如 " + v.substr(0, 32) +
                "），说明环境变量未注入";
    return r;
  }
  r.ok = true;
  return r;
}

AuthGuard& AuthGuard::instance() {
  static AuthGuard guard;
  return guard;
}

void AuthGuard::reset() {
  std::lock_guard<std::mutex> lock(mu_);
  blocked_ = false;
  attempts_ = 0;
  extra_after_failure_ = 0;
  used_after_failure_ = 0;
  injected_ = nullptr;
}

void AuthGuard::set_connector(Connector connector) {
  std::lock_guard<std::mutex> lock(mu_);
  injected_ = std::move(connector);
}

void AuthGuard::clear_connector() {
  std::lock_guard<std::mutex> lock(mu_);
  injected_ = nullptr;
}

void AuthGuard::set_max_attempts_after_failure(int n) {
  std::lock_guard<std::mutex> lock(mu_);
  extra_after_failure_ = n < 0 ? 0 : n;
}

bool AuthGuard::blocked() const {
  std::lock_guard<std::mutex> lock(mu_);
  return blocked_;
}

int AuthGuard::attempts() const {
  std::lock_guard<std::mutex> lock(mu_);
  return attempts_;
}

AuthGuard::Outcome AuthGuard::attempt(const Connector& real) {
  Connector fn;
  {
    std::lock_guard<std::mutex> lock(mu_);
    if (blocked_ && used_after_failure_ >= extra_after_failure_) {
      // 熔断分支：不触碰 socket，也不发送任何认证消息。
      CM_LOG_ERROR("db.pg") << kStopRetry;
      return Outcome::Blocked;
    }
    if (blocked_) ++used_after_failure_;
    ++attempts_;
    fn = injected_ ? injected_ : real;
  }
  if (!fn) return Outcome::OtherError;
  return fn();
}

AuthGuard::Outcome AuthGuard::attempt() { return attempt(Connector()); }

void AuthGuard::mark_auth_failure(const std::string& sqlstate, const std::string& message) {
  std::lock_guard<std::mutex> lock(mu_);
  if (blocked_) return;
  blocked_ = true;
  used_after_failure_ = 0;
  CM_LOG_ERROR("db.pg") << "认证失败 [" << sqlstate << "] " << message;
  CM_LOG_ERROR("db.pg") << kStopRetry
                        << "（认证失败后默认不自动重连，避免继续消耗 failed_login_attempts）。"
                           "修正口令或在 DB 侧解锁后请重启进程。";
}

} // namespace cm::db
