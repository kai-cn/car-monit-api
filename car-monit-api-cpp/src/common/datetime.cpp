#include "common/datetime.h"

#include <array>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <regex>

namespace cm::timeutil {
namespace {

// Howard Hinnant's civil calendar algorithms (public domain).
long long days_from_civil(int y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return static_cast<long long>(era) * 146097 + static_cast<long long>(doe) - 719468;
}

void civil_from_days(long long z, int& y, unsigned& m, unsigned& d) {
  z += 719468;
  const long long era = (z >= 0 ? z : z - 146096) / 146097;
  const unsigned doe = static_cast<unsigned>(z - era * 146097);
  const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  y = static_cast<int>(yoe) + static_cast<int>(era) * 400;
  const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const unsigned mp = (5 * doy + 2) / 153;
  d = doy - (153 * mp + 2) / 5 + 1;
  m = mp + (mp < 10 ? 3 : -9);
  y += (m <= 2);
}

struct Parts {
  int y = 1970;
  unsigned m = 1, d = 1;
  int hh = 0, mi = 0, ss = 0, ms = 0;
  int offset_minutes = 0;
  bool has_zone = false;
};

bool parse_parts(const std::string& raw, Parts& p) {
  std::string s;
  s.reserve(raw.size());
  for (char c : raw) {
    if (c != ' ' || (!s.empty() && s.back() != ' ')) s.push_back(c);
  }
  while (!s.empty() && s.back() == ' ') s.pop_back();
  while (!s.empty() && s.front() == ' ') s.erase(s.begin());
  if (s.empty()) return false;

  static const std::regex re(
      R"(^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T ](\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:\.(\d{1,9}))?)?)?(Z|[+-]\d{2}:?\d{2})?$)");
  std::smatch m;
  if (!std::regex_match(s, m, re)) return false;
  p.y = std::stoi(m[1]);
  p.m = static_cast<unsigned>(std::stoi(m[2]));
  p.d = static_cast<unsigned>(std::stoi(m[3]));
  if (m[4].matched) p.hh = std::stoi(m[4]);
  if (m[5].matched) p.mi = std::stoi(m[5]);
  if (m[6].matched) p.ss = std::stoi(m[6]);
  if (m[7].matched) {
    std::string frac = m[7];
    while (frac.size() < 3) frac.push_back('0');
    p.ms = std::stoi(frac.substr(0, 3));
  }
  if (m[8].matched) {
    p.has_zone = true;
    std::string z = m[8];
    if (z == "Z") {
      p.offset_minutes = 0;
    } else {
      int sign = z[0] == '-' ? -1 : 1;
      int oh = std::stoi(z.substr(1, 2));
      int om = std::stoi(z.substr(z.size() - 2));
      p.offset_minutes = sign * (oh * 60 + om);
    }
  }
  if (p.m < 1 || p.m > 12 || p.d < 1 || p.d > 31 || p.hh > 23 || p.mi > 59 || p.ss > 60)
    return false;
  return true;
}

} // namespace

std::optional<TimePoint> parse_naive(const std::string& s, int offset_minutes) {
  Parts p;
  if (!parse_parts(s, p)) return std::nullopt;
  long long secs = days_from_civil(p.y, p.m, p.d) * 86400LL +
                   p.hh * 3600LL + p.mi * 60LL + p.ss;
  secs -= static_cast<long long>(offset_minutes) * 60;
  return TimePoint(std::chrono::milliseconds(secs * 1000 + p.ms));
}

std::optional<TimePoint> parse_any(const std::string& s) {
  Parts p;
  if (!parse_parts(s, p)) return std::nullopt;
  int off = p.has_zone ? p.offset_minutes : kJavaZoneOffsetMinutes;
  long long secs = days_from_civil(p.y, p.m, p.d) * 86400LL +
                   p.hh * 3600LL + p.mi * 60LL + p.ss;
  secs -= static_cast<long long>(off) * 60;
  return TimePoint(std::chrono::milliseconds(secs * 1000 + p.ms));
}

std::optional<TimePoint> from_db_text(const std::string& s) {
  return parse_naive(s, kJavaZoneOffsetMinutes);
}

namespace {
Parts utc_parts(TimePoint tp) {
  const long long ms = to_millis(tp);
  long long secs = ms / 1000;
  long long rem = ms % 1000;
  if (rem < 0) { rem += 1000; secs -= 1; }
  long long days = secs / 86400;
  long long sod = secs % 86400;
  if (sod < 0) { sod += 86400; days -= 1; }
  Parts p;
  civil_from_days(days, p.y, p.m, p.d);
  p.hh = static_cast<int>(sod / 3600);
  p.mi = static_cast<int>((sod % 3600) / 60);
  p.ss = static_cast<int>(sod % 60);
  p.ms = static_cast<int>(rem);
  return p;
}

} // namespace

std::string format_day(TimePoint tp) {
  const Parts p = utc_parts(tp);
  char buf[16];
  std::snprintf(buf, sizeof(buf), "%04d-%02u-%02u", p.y, p.m, p.d);
  return buf;
}

std::string format_datetime(TimePoint tp) {
  const Parts p = utc_parts(tp);
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%04d-%02u-%02u %02d:%02d:%02d", p.y, p.m, p.d, p.hh, p.mi, p.ss);
  return buf;
}

std::string format_timestamp(TimePoint tp) {
  const Parts p = utc_parts(tp);
  char buf[48];
  std::snprintf(buf, sizeof(buf), "%04d-%02u-%02uT%02d:%02d:%02d.%03d+00:00", p.y, p.m, p.d, p.hh,
                p.mi, p.ss, p.ms);
  return buf;
}

std::string format_naive_plus8(TimePoint tp) {
  // Shift the instant into +08:00, then render the wall clock.
  const auto shifted = tp + std::chrono::minutes(kJavaZoneOffsetMinutes);
  return format_datetime(shifted);
}

std::string format_rfc3339(TimePoint tp) {
  const Parts p = utc_parts(tp);
  char buf[48];
  std::snprintf(buf, sizeof(buf), "%04d-%02u-%02uT%02d:%02d:%02d.%03dZ", p.y, p.m, p.d, p.hh, p.mi,
                p.ss, p.ms);
  return buf;
}

TimePoint now() { return std::chrono::system_clock::now(); }

TimePoint add_days(TimePoint tp, int days) { return tp + std::chrono::hours(24 * days); }
TimePoint add_hours(TimePoint tp, int hours) { return tp + std::chrono::hours(hours); }
TimePoint add_minutes(TimePoint tp, int minutes) { return tp + std::chrono::minutes(minutes); }

long long to_millis(TimePoint tp) {
  return std::chrono::duration_cast<std::chrono::milliseconds>(tp.time_since_epoch()).count();
}

TimePoint from_millis(long long ms) { return TimePoint(std::chrono::milliseconds(ms)); }

} // namespace cm::timeutil
