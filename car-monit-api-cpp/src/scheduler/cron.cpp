#include "scheduler/cron.h"

#include <vector>

namespace cm::scheduler {
namespace {

bool is_wild(const std::string& s) { return s == "*" || s == "?"; }

bool parse_int(const std::string& s, int& out) {
  if (s.empty()) return false;
  int v = 0;
  for (char c : s) {
    if (c < '0' || c > '9') return false;
    v = v * 10 + (c - '0');
    if (v > 9999) return false;
  }
  out = v;
  return true;
}

std::vector<std::string> split_fields(const std::string& expr) {
  std::vector<std::string> out;
  std::size_t start = 0;
  while (start <= expr.size()) {
    auto pos = expr.find(' ', start);
    std::string tok =
        expr.substr(start, pos == std::string::npos ? std::string::npos : pos - start);
    if (!tok.empty()) out.push_back(tok);
    if (pos == std::string::npos) break;
    start = pos + 1;
  }
  return out;
}

std::vector<std::string> split_commas(const std::string& field) {
  std::vector<std::string> out;
  std::size_t start = 0;
  while (start <= field.size()) {
    auto pos = field.find(',', start);
    std::string tok =
        field.substr(start, pos == std::string::npos ? std::string::npos : pos - start);
    out.push_back(tok);
    if (pos == std::string::npos) break;
    start = pos + 1;
  }
  return out;
}

struct FieldSpec {
  int lo, hi;
  bool dow; // 周字段：token 的 0 归一为 7（周日）
};

constexpr FieldSpec kSpecs[6] = {
    {0, 59, false}, // 秒
    {0, 59, false}, // 分
    {0, 23, false}, // 时
    {1, 31, false}, // 日
    {1, 12, false}, // 月
    {1, 7, true},   // 周（Spring 内部口径：1=周一 … 7=周日）
};

// 校验单 token 语法；返回解析出的头部数值区间（单值时 a==b）。
// head 为空表示通配（*/step 或纯通配）。
bool parse_head(const std::string& tok, const FieldSpec& spec, bool& wild_head, int& a, int& b,
                bool& has_step, int& step) {
  wild_head = false;
  has_step = false;
  step = 1;
  std::string head = tok;
  if (auto slash = tok.find('/'); slash != std::string::npos) {
    head = tok.substr(0, slash);
    int st = 0;
    if (!parse_int(tok.substr(slash + 1), st) || st <= 0) return false;
    step = st;
    has_step = true;
  }
  if (is_wild(head)) {
    wild_head = true;
    return true;
  }
  auto norm = [&spec](int n) { return spec.dow && n == 0 ? 7 : n; };
  if (auto dash = head.find('-'); dash != std::string::npos) {
    int x = 0, y = 0;
    if (!parse_int(head.substr(0, dash), x) || !parse_int(head.substr(dash + 1), y)) return false;
    a = norm(x);
    b = norm(y);
    return a >= spec.lo && b <= spec.hi && a <= b; // 不支持回绕区间（Spring 同）
  }
  int x = 0;
  if (!parse_int(head, x)) return false;
  a = norm(x);
  b = has_step ? spec.hi : a; // a/step：从 a 递增到字段上限
  return a >= spec.lo && a <= spec.hi;
}

bool match_token(const std::string& tok, int v, const FieldSpec& spec) {
  if (is_wild(tok)) return true;
  bool wild_head = false, has_step = false;
  int a = 0, b = 0, step = 1;
  if (!parse_head(tok, spec, wild_head, a, b, has_step, step)) return false;
  if (wild_head) {
    // */step：从字段下限开始每 step 一个
    return (v - spec.lo) % step == 0;
  }
  if (!has_step && a == b) return v == a; // 单值：精确匹配
  // 区间（a-b 或 a/step）：[a, b] 内从 a 起每 step 一个
  return v >= a && v <= b && (v - a) % step == 0;
}

bool match_field(const std::string& field, int v, const FieldSpec& spec) {
  for (const auto& tok : split_commas(field)) {
    if (match_token(tok, v, spec)) return true;
  }
  return false;
}

} // namespace

bool cron_match(const std::string& expr, const WallTime& t) {
  auto f = split_fields(expr);
  if (f.size() != 6) return false;
  // tm_wday（0=周日）转 Spring 内部口径（1=周一 … 7=周日）。
  const int dow = t.wday == 0 ? 7 : t.wday;
  const int vals[6] = {t.second, t.minute, t.hour, t.day, t.month, dow};
  for (int i = 0; i < 6; ++i) {
    if (!match_field(f[i], vals[i], kSpecs[i])) return false;
  }
  return true;
}

bool cron_validate(const std::string& expr) {
  auto f = split_fields(expr);
  if (f.size() != 6) return false;
  for (int i = 0; i < 6; ++i) {
    for (const auto& tok : split_commas(f[i])) {
      bool wild_head = false, has_step = false;
      int a = 0, b = 0, step = 1;
      if (!parse_head(tok, kSpecs[i], wild_head, a, b, has_step, step)) return false;
    }
  }
  return true;
}

} // namespace cm::scheduler
