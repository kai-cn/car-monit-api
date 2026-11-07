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
void write(Level level, const std::string& logger, const std::string& msg);

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
