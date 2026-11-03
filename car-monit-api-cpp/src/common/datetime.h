#pragma once
// Java time semantics reproduced for the migration:
//   * database columns are `timestamp without time zone`; pgjdbc interprets the
//     wall clock in the JVM zone (Asia/Shanghai, +08:00) and Jackson renders it
//     in UTC.  Every naive timestamp is therefore anchored at +08:00 and
//     formatted in UTC.
//   * @JsonFormat("yyyy-MM-dd")                  -> format_day
//   * @JsonFormat("yyyy-MM-dd HH:mm:ss")         -> format_datetime
//   * no annotation (java.util.Date / StdDateFormat) -> format_timestamp
#include <chrono>
#include <optional>
#include <string>

namespace cm::timeutil {

using TimePoint = std::chrono::system_clock::time_point;

constexpr int kJavaZoneOffsetMinutes = 480; // Asia/Shanghai, no DST since 1991

std::optional<TimePoint> parse_naive(const std::string& s,
                                     int offset_minutes = kJavaZoneOffsetMinutes);
// Parses either a Java-style wall clock or a RFC3339 timestamp with explicit zone.
std::optional<TimePoint> parse_any(const std::string& s);

std::string format_day(TimePoint tp);       // yyyy-MM-dd (UTC)
std::string format_datetime(TimePoint tp);  // yyyy-MM-dd HH:mm:ss (UTC)
std::string format_timestamp(TimePoint tp); // yyyy-MM-ddTHH:mm:ss.SSS+00:00 (UTC)
std::string format_naive_plus8(TimePoint tp); // yyyy-MM-dd HH:mm:ss in +08:00 (SQL literal)
std::string format_rfc3339(TimePoint tp);

TimePoint now();
TimePoint add_days(TimePoint tp, int days);
TimePoint add_hours(TimePoint tp, int hours);
TimePoint add_minutes(TimePoint tp, int minutes);

// Milliseconds since epoch.
long long to_millis(TimePoint tp);
TimePoint from_millis(long long ms);

// Converts a database text value (timestamp without time zone, or a date) into
// a TimePoint anchored at +08:00.
std::optional<TimePoint> from_db_text(const std::string& s);

} // namespace cm::timeutil
