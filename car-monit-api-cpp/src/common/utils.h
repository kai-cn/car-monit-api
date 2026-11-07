#pragma once
// Direct ports of com.ruoyi.common.utils.CommonUtil / StringUtils helpers.
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cm::utils {

std::string trim(std::string_view s);
bool is_blank(std::string_view s);
bool is_not_blank(std::string_view s);
std::string is_null(const std::optional<std::string>& s);
std::string is_null(std::string_view s);
bool is_integer(std::string_view s);

// CommonUtil.repalaceSzdnTollName (sic): removes 收费站 / 江西 / 站.
std::string repalace_szdn_toll_name(std::string_view s);
// CommonUtil.deleteEnd: drops one trailing comma.
std::string delete_end(std::string_view s);
// CommonUtil.repalacePicUrl: rewrites the internal image host.
std::string repalace_pic_url(std::string_view s);

std::vector<std::string> split_csv(std::string_view s);
std::vector<std::string> split(std::string_view s, char sep);
std::string join(const std::vector<std::string>& parts, std::string_view sep);

std::string to_lower(std::string_view s);
std::string to_upper(std::string_view s);
bool equals_ignore_case(std::string_view a, std::string_view b);
bool starts_with(std::string_view s, std::string_view p);
bool ends_with(std::string_view s, std::string_view p);
std::string replace_all(std::string s, std::string_view from, std::string_view to);
bool contains(std::string_view s, std::string_view p);

std::string uuid4();
std::string url_decode(std::string_view s);
std::string url_encode(std::string_view s);
std::string base64_encode(const std::string& in);
std::optional<std::string> base64_decode(const std::string& in);

// SQL literal quoting (standard_conforming_strings=on): ' -> ''.
std::string sql_quote(std::string_view s);
// Java's String.valueOf for numbers used in JSON-ish contexts.
std::string format_double(double v);

} // namespace cm::utils
