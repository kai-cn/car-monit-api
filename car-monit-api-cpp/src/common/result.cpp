#include "common/result.h"

#include "common/datetime.h"

namespace cm {

Json ajax_result(int code, const std::string& msg, const Json& data, bool has_data) {
  Json j = Json::object();
  j["msg"] = msg;
  j["code"] = code;
  if (has_data && !data.is_null()) j["data"] = data;
  return j;
}

Json table_data(const Json& rows, long long total, int code, const std::string& msg) {
  Json j = Json::object();
  j["total"] = total;
  j["rows"] = rows;
  j["code"] = code;
  j["msg"] = msg;
  return j;
}

Json result_envelope(bool success, const std::string& message, int code, const Json& data,
                     bool has_data) {
  Json j = Json::object();
  j["success"] = success;
  j["message"] = message;
  j["code"] = code;
  if (has_data && !data.is_null()) j["result"] = data;
  j["timestamp"] = timeutil::to_millis(timeutil::now());
  return j;
}

Json spring_error(int status, const std::string& error, const std::string& message,
                  const std::string& path) {
  Json j = Json::object();
  j["timestamp"] = timeutil::format_timestamp(timeutil::now());
  j["status"] = status;
  j["error"] = error;
  j["message"] = message;
  j["path"] = path;
  return j;
}

} // namespace cm
