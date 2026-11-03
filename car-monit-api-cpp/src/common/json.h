#pragma once
// JSON facade. ordered_json is used everywhere because the Java API's field
// order is observable: entity properties follow Java declaration order, and
// AjaxResult follows java.util.HashMap bucket order (msg, code, data).
#include <nlohmann/json.hpp>

#include <optional>
#include <string>

namespace cm {

using Json = nlohmann::ordered_json;

inline Json json_null() { return Json(nullptr); }

inline std::optional<std::string> json_opt_string(const Json& j) {
  if (j.is_null()) return std::nullopt;
  if (j.is_string()) return j.get<std::string>();
  return j.dump();
}

inline std::string json_string(const Json& j, const std::string& def = "") {
  if (j.is_null()) return def;
  if (j.is_string()) return j.get<std::string>();
  if (j.is_boolean()) return j.get<bool>() ? "true" : "false";
  if (j.is_number_integer()) return std::to_string(j.get<long long>());
  if (j.is_number_unsigned()) return std::to_string(j.get<unsigned long long>());
  if (j.is_number_float()) return j.dump();
  return def;
}

} // namespace cm
