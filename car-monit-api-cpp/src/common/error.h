#pragma once
// Error types mirror the Java exception families used by the original service:
//  - BizError       -> com.ruoyi.common.exception.ServiceException (HTTP 200 + business code)
//  - BindError      -> Spring MVC TypeMismatchException / MissingServletRequestParameterException
//  - DbError        -> DataAccessException
#include <stdexcept>
#include <string>
#include <utility>

namespace cm {

class BizError : public std::runtime_error {
public:
  BizError(int code, std::string msg)
      : std::runtime_error(msg), code_(code), msg_(std::move(msg)) {}
  int code() const noexcept { return code_; }
  const std::string& message() const noexcept { return msg_; }

private:
  int code_;
  std::string msg_;
};

// Spring-style binding failure: the HTTP status is not 200 and the body is the
// default Spring error envelope (timestamp/status/error/message/path).
class BindError : public std::runtime_error {
public:
  BindError(int status, std::string reason)
      : std::runtime_error(reason), status_(status), reason_(std::move(reason)) {}
  int status() const noexcept { return status_; }
  const std::string& reason() const noexcept { return reason_; }

private:
  int status_;
  std::string reason_;
};

class DbError : public std::runtime_error {
public:
  DbError(std::string sqlstate, std::string msg)
      : std::runtime_error(msg), sqlstate_(std::move(sqlstate)), msg_(std::move(msg)) {}
  const std::string& sqlstate() const noexcept { return sqlstate_; }
  const std::string& message() const noexcept { return msg_; }

private:
  std::string sqlstate_;
  std::string msg_;
};

class RedisError : public std::runtime_error {
public:
  explicit RedisError(const std::string& msg) : std::runtime_error(msg) {}
};

class EsError : public std::runtime_error {
public:
  explicit EsError(const std::string& msg) : std::runtime_error(msg) {}
};

} // namespace cm
