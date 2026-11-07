#pragma once
// RuoYi 返回信封：
//   AjaxResult    -> HashMap，键序为 msg, code, data；data 为 null 时该键不存在
//   TableDataInfo -> {total, rows, code, msg}
//   Result<T>     -> {success, message, code, result, timestamp}
#include "common/json.h"

#include <string>
#include <vector>

namespace cm {

namespace http_status {
inline constexpr int SUCCESS = 200;
inline constexpr int WARN = 601;
inline constexpr int ERROR = 500;
inline constexpr int UNAUTHORIZED = 401;
inline constexpr int BAD_REQUEST = 400;
} // namespace http_status

Json ajax_result(int code, const std::string& msg, const Json& data = Json(nullptr),
                 bool has_data = false);
inline Json ajax_ok() { return ajax_result(http_status::SUCCESS, "操作成功"); }
inline Json ajax_ok_data(const Json& data) {
  return ajax_result(http_status::SUCCESS, "操作成功", data, true);
}
inline Json ajax_ok_msg(const std::string& msg) {
  return ajax_result(http_status::SUCCESS, msg);
}
inline Json ajax_error() { return ajax_result(http_status::ERROR, "操作失败"); }
inline Json ajax_error_msg(const std::string& msg) {
  return ajax_result(http_status::ERROR, msg);
}
inline Json ajax_error_code(int code, const std::string& msg) {
  return ajax_result(code, msg);
}

// TableDataInfo(list, total) + setCode/setMsg.
Json table_data(const Json& rows, long long total, int code = http_status::SUCCESS,
                const std::string& msg = "查询成功");

// Result<T>（少数接口使用，如未授权响应）。
Json result_envelope(bool success, const std::string& message, int code,
                     const Json& data = Json(nullptr), bool has_data = false);

// Spring 默认错误体：timestamp/status/error/message/path。
Json spring_error(int status, const std::string& error, const std::string& message,
                  const std::string& path);

} // namespace cm
