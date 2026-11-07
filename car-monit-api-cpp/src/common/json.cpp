#include "common/json.h"

#include <cctype>

namespace cm {
namespace {

// 占位前后缀：只用 ASCII 可见字符，nlohmann 不会转义，便于整体替换回数字字面量。
const std::string kPre = "@@cmrawdec:";
const std::string kPost = ":@cmrawdec@@";

bool is_json_number_literal(const std::string& s) {
  std::size_t i = 0;
  const std::size_t n = s.size();
  if (i < n && s[i] == '-') ++i;
  bool digits = false;
  while (i < n && std::isdigit(static_cast<unsigned char>(s[i]))) {
    ++i;
    digits = true;
  }
  if (i < n && s[i] == '.') {
    ++i;
    while (i < n && std::isdigit(static_cast<unsigned char>(s[i]))) {
      ++i;
      digits = true;
    }
  }
  if (!digits) return false;
  if (i < n && (s[i] == 'e' || s[i] == 'E')) {
    ++i;
    if (i < n && (s[i] == '+' || s[i] == '-')) ++i;
    bool exp_digits = false;
    while (i < n && std::isdigit(static_cast<unsigned char>(s[i]))) {
      ++i;
      exp_digits = true;
    }
    if (!exp_digits) return false;
  }
  return i == n;
}

} // namespace

Json json_raw_decimal(const std::string& literal) {
  if (!is_json_number_literal(literal)) return Json(literal);
  return Json(kPre + literal + kPost);
}

bool json_raw_decimal_literal(const Json& v, std::string& literal) {
  if (!v.is_string()) return false;
  const std::string& s = v.get_ref<const std::string&>();
  if (s.size() <= kPre.size() + kPost.size()) return false;
  if (s.compare(0, kPre.size(), kPre) != 0) return false;
  if (s.compare(s.size() - kPost.size(), kPost.size(), kPost) != 0) return false;
  literal = s.substr(kPre.size(), s.size() - kPre.size() - kPost.size());
  return true;
}

std::string json_dump(const Json& j) {
  std::string out = j.dump();
  const std::string quoted_pre = "\"" + kPre;
  const std::string quoted_post = kPost + "\"";
  std::size_t pos = 0;
  while ((pos = out.find(quoted_pre, pos)) != std::string::npos) {
    std::size_t end = out.find(quoted_post, pos);
    if (end == std::string::npos) break;
    std::string literal =
        out.substr(pos + quoted_pre.size(), end - pos - quoted_pre.size());
    out.replace(pos, end + quoted_post.size() - pos, literal);
    pos += literal.size();
  }
  return out;
}

} // namespace cm
