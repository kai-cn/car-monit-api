#include "common/utils.h"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <random>
#include <sstream>

namespace cm::utils {

std::string trim(std::string_view s) {
  size_t b = 0, e = s.size();
  while (b < e && std::isspace(static_cast<unsigned char>(s[b]))) ++b;
  while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1]))) --e;
  return std::string(s.substr(b, e - b));
}

bool is_blank(std::string_view s) { return trim(s).empty(); }
bool is_not_blank(std::string_view s) { return !is_blank(s); }

std::string is_null(const std::optional<std::string>& s) {
  return s.has_value() ? trim(*s) : std::string();
}
std::string is_null(std::string_view s) { return trim(s); }

bool is_integer(std::string_view s) {
  if (s.empty()) return false;
  size_t i = 0;
  if (s[0] == '+' || s[0] == '-') i = 1;
  if (i >= s.size()) return false;
  for (; i < s.size(); ++i)
    if (s[i] < '0' || s[i] > '9') return false;
  return true;
}

std::string repalace_szdn_toll_name(std::string_view s) {
  std::string name = trim(s);
  if (is_not_blank(name)) {
    name = replace_all(std::move(name), "收费站", "");
    name = replace_all(std::move(name), "江西", "");
    name = replace_all(std::move(name), "站", "");
  }
  return name;
}

std::string delete_end(std::string_view s) {
  std::string str = trim(s);
  if (!str.empty() && str.back() == ',') str.pop_back();
  return str;
}

std::string repalace_pic_url(std::string_view s) {
  std::string v = trim(s);
  if (is_blank(v)) return v;
  constexpr std::string_view internal_base = "http://jxjt.isilon.com/ifs";
  constexpr std::string_view internal_host = "http://jxjt.isilon.com";
  constexpr std::string_view public_host = "http://36.200.30.144:9080";
  if (v.find(internal_base) != std::string::npos)
    return replace_all(std::move(v), internal_base, public_host);
  return replace_all(std::move(v), internal_host, public_host);
}

std::vector<std::string> split(std::string_view s, char sep) {
  std::vector<std::string> out;
  size_t start = 0;
  while (true) {
    size_t pos = s.find(sep, start);
    if (pos == std::string_view::npos) {
      out.emplace_back(s.substr(start));
      break;
    }
    out.emplace_back(s.substr(start, pos - start));
    start = pos + 1;
  }
  return out;
}

std::vector<std::string> split_csv(std::string_view s) {
  std::vector<std::string> out;
  for (auto& p : split(s, ',')) {
    auto t = trim(p);
    if (!t.empty()) out.push_back(std::move(t));
  }
  return out;
}

std::string join(const std::vector<std::string>& parts, std::string_view sep) {
  std::string out;
  for (size_t i = 0; i < parts.size(); ++i) {
    if (i) out.append(sep);
    out.append(parts[i]);
  }
  return out;
}

std::string to_lower(std::string_view s) {
  std::string out(s);
  std::transform(out.begin(), out.end(), out.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return out;
}

std::string to_upper(std::string_view s) {
  std::string out(s);
  std::transform(out.begin(), out.end(), out.begin(),
                 [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
  return out;
}

bool equals_ignore_case(std::string_view a, std::string_view b) {
  return to_lower(a) == to_lower(b);
}

bool starts_with(std::string_view s, std::string_view p) {
  return s.size() >= p.size() && s.substr(0, p.size()) == p;
}
bool ends_with(std::string_view s, std::string_view p) {
  return s.size() >= p.size() && s.substr(s.size() - p.size()) == p;
}
bool contains(std::string_view s, std::string_view p) { return s.find(p) != std::string_view::npos; }

std::string replace_all(std::string s, std::string_view from, std::string_view to) {
  if (from.empty()) return s;
  size_t pos = 0;
  while ((pos = s.find(from, pos)) != std::string::npos) {
    s.replace(pos, from.size(), to);
    pos += to.size();
  }
  return s;
}

std::string uuid4() {
  static thread_local std::mt19937_64 rng{std::random_device{}()};
  uint64_t a = rng(), b = rng();
  a = (a & 0xFFFFFFFFFFFF0FFFULL) | 0x0000000000004000ULL;
  b = (b & 0x3FFFFFFFFFFFFFFFULL) | 0x8000000000000000ULL;
  char buf[40];
  std::snprintf(buf, sizeof(buf), "%08x-%04x-%04x-%04x-%012llx",
                static_cast<unsigned>(a >> 32), static_cast<unsigned>((a >> 16) & 0xFFFF),
                static_cast<unsigned>(a & 0xFFFF), static_cast<unsigned>(b >> 48),
                static_cast<unsigned long long>(b & 0xFFFFFFFFFFFFULL));
  return buf;
}

std::string url_decode(std::string_view s) {
  std::string out;
  out.reserve(s.size());
  for (size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '+') {
      out.push_back(' ');
    } else if (s[i] == '%' && i + 2 < s.size()) {
      auto hex = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
      };
      int h = hex(s[i + 1]), l = hex(s[i + 2]);
      if (h >= 0 && l >= 0) {
        out.push_back(static_cast<char>(h * 16 + l));
        i += 2;
      } else {
        out.push_back(s[i]);
      }
    } else {
      out.push_back(s[i]);
    }
  }
  return out;
}

std::string url_encode(std::string_view s) {
  static const char* hex = "0123456789ABCDEF";
  std::string out;
  for (unsigned char c : s) {
    if (std::isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
      out.push_back(static_cast<char>(c));
    } else {
      out.push_back('%');
      out.push_back(hex[c >> 4]);
      out.push_back(hex[c & 15]);
    }
  }
  return out;
}

static const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string base64_encode(const std::string& in) {
  std::string out;
  int val = 0, bits = -6;
  for (unsigned char c : in) {
    val = (val << 8) + c;
    bits += 8;
    while (bits >= 0) {
      out.push_back(kB64[(val >> bits) & 0x3F]);
      bits -= 6;
    }
  }
  if (bits > -6) out.push_back(kB64[((val << 8) >> (bits + 8)) & 0x3F]);
  while (out.size() % 4) out.push_back('=');
  return out;
}

std::optional<std::string> base64_decode(const std::string& in) {
  std::vector<int> table(256, -1);
  for (int i = 0; i < 64; ++i) table[static_cast<unsigned char>(kB64[i])] = i;
  std::string out;
  int val = 0, bits = -8;
  for (unsigned char c : in) {
    if (c == '=') break;
    if (table[c] == -1) {
      if (std::isspace(c)) continue;
      return std::nullopt;
    }
    val = (val << 6) + table[c];
    bits += 6;
    if (bits >= 0) {
      out.push_back(static_cast<char>((val >> bits) & 0xFF));
      bits -= 8;
    }
  }
  return out;
}

std::string sql_quote(std::string_view s) {
  std::string out = "'";
  for (char c : s) {
    if (c == '\'') out += "''";
    else out.push_back(c);
  }
  out.push_back('\'');
  return out;
}

std::string format_double(double v) {
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%.17g", v);
  std::string s(buf);
  // Java/Jackson always keeps a decimal point for Double.
  if (s.find('.') == std::string::npos && s.find('e') == std::string::npos &&
      s.find("inf") == std::string::npos && s.find("nan") == std::string::npos)
    s += ".0";
  return s;
}

} // namespace cm::utils
