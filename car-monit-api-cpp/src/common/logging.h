#pragma once
// SLF4J / Logback 的最小替代：
//   logback-spring.xml 的 pattern 为 "%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{50} - %msg%n"
//   C++ 侧保持同样的行格式，日志同时写 stdout 与 logs/car-monit-api.log。
#include <sstream>
#include <string>

namespace cm::log {

enum class Level { Trace = 0, Debug = 1, Info = 2, Warn = 3, Error = 4 };

void set_level(Level level);
Level level();
void set_file(const std::string& path);
// 按大小轮转：max_bytes=0 关闭；keep_files 为保留的历史文件数（log.1 ... log.N）。
void set_rotation(long long max_bytes, int keep_files);
void write(Level level, const std::string& logger, const std::string& msg);

// 结构化日志（JSON）开关：logging.json=true 或 CM_LOG_JSON=true 时生效。
void set_json(bool enabled);
bool json_enabled();
// 当前线程的 requestId（由 HTTP 层每个请求设置，日志行自动携带）。
void set_request_id(const std::string& id);
const std::string& request_id();

// RAII：设置当前线程 requestId，析构时恢复上一个值（线程池复用线程时避免串号）。
class RequestIdScope {
public:
  explicit RequestIdScope(std::string id);
  ~RequestIdScope();
  RequestIdScope(const RequestIdScope&) = delete;
  RequestIdScope& operator=(const RequestIdScope&) = delete;

private:
  std::string previous_;
};

std::string thread_name();

class Line {
public:
  Line(Level level, const std::string& logger)
      : level_(level), logger_(logger) {}
  ~Line() { write(level_, logger_, ss_.str()); }
  template <typename T>
  Line& operator<<(const T& v) {
    ss_ << v;
    return *this;
  }

private:
  Level level_;
  std::string logger_;
  std::ostringstream ss_;
};

} // namespace cm::log

#define CM_LOG_DEBUG(logger) cm::log::Line(cm::log::Level::Debug, logger)
#define CM_LOG_INFO(logger) cm::log::Line(cm::log::Level::Info, logger)
#define CM_LOG_WARN(logger) cm::log::Line(cm::log::Level::Warn, logger)
#define CM_LOG_ERROR(logger) cm::log::Line(cm::log::Level::Error, logger)
