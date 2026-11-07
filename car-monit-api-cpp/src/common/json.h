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

// BigDecimal 的 JSON 数字字面量。
//
// Java 侧 BigDecimal("1.50") 经 Jackson/fastjson2 序列化后是 1.50（保留标度与
// 尾零），而 nlohmann::json 只能存 double，会被写成 1.5。这里把字面量存成占位
// 字符串，由 json_dump() 在最终序列化时还原成未加引号的数字，从而与 Java 逐字节一致。
// 非数字字面量（NaN/Infinity）按 Jackson 默认的 QUOTE_NON_NUMERIC_NUMBERS 语义写成字符串。
Json json_raw_decimal(const std::string& literal);

// 等价于 Json::dump()，但会把 json_raw_decimal 的占位还原为数字字面量。
std::string json_dump(const Json& j);

// 若 v 是 json_raw_decimal 产生的占位字符串，返回其原始数字字面量（不加引号）。
bool json_raw_decimal_literal(const Json& v, std::string& literal);

} // namespace cm
