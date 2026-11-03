package model

// 本文件不对应单个 Java 类，而是为生成模型提供"Java 运行时行为"的 Go 等价物。
// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/DateUtils.java:1-999（日期格式化/解析）
//           + com.fasterxml.jackson.annotation.JsonFormat（序列化格式）

import (
	"database/sql/driver"
	"fmt"
	"strings"
	"time"
)

// Day 等价于 Java 中 `@JsonFormat(pattern = "yyyy-MM-dd") private Date xxx`。
//
// DIFF: Java 的 Date 是"毫秒时间戳 + 序列化时按注解格式化"，Go 的 time.Time 默认序列化为 RFC3339。
// 为了让前端拿到的 `receivedtime` 仍然是 "2026-10-31"（而不是 "2026-10-31T00:00:00+08:00"），
// 这里用一个自定义类型把"格式化"固化在类型的 MarshalJSON 上——这是 Go 里最常见的替代方案。
type Day time.Time

const dayLayout = "2006-01-02"

// NewDay 由 time.Time 构造
func NewDay(t time.Time) *Day {
	d := Day(t)
	return &d
}

// Time 取回底层 time.Time（Java 侧对应 Date#getTime 之后的强转）
func (d Day) Time() time.Time { return time.Time(d) }

// String 对应 DateUtils.parseDateToStr(date, "yyyy-MM-dd")
//
// 按 UTC 格式化：字段里存的是「和 Java 的 java.util.Date 相同的瞬间」（见 datetime.go 的 javaZone）。
// 实测：库里 open_date = 1899-12-30 00:00:00，Java 输出 1899-12-29，不转 UTC 就会多一天。
func (d Day) String() string { return time.Time(d).UTC().Format(dayLayout) }

// MarshalJSON 对应 Jackson @JsonFormat(pattern = "yyyy-MM-dd")
func (d Day) MarshalJSON() ([]byte, error) {
	return []byte(`"` + time.Time(d).UTC().Format(dayLayout) + `"`), nil
}

// UnmarshalJSON 兼容 "yyyy-MM-dd" 与 RFC3339 两种输入
func (d *Day) UnmarshalJSON(b []byte) error {
	s := strings.Trim(string(b), `"`)
	if s == "" || s == "null" {
		return nil
	}
	t, err := ParseTime(s)
	if err != nil {
		return err
	}
	*d = Day(t)
	return nil
}

// Scan 实现 sql.Scanner（数据库里是 timestamp without time zone）
//
// time.Time 分支必须 anchorTimestamp：库里是裸墙钟，pgx 当成 UTC、pgjdbc 当成 +08:00。
// 字符串分支则不能再挂：ParseTime 现在已经把文字挂到 javaZone 上了，再挂一次就减两轮 8 小时。
func (d *Day) Scan(v any) error {
	switch x := v.(type) {
	case nil:
		return nil
	case time.Time:
		*d = Day(anchorTimestamp(x))
		return nil
	case []byte:
		t, err := ParseTime(string(x))
		if err != nil {
			return err
		}
		*d = Day(t)
		return nil
	case string:
		t, err := ParseTime(x)
		if err != nil {
			return err
		}
		*d = Day(t)
		return nil
	}
	return fmt.Errorf("model.Day: 不支持的扫描类型 %T", v)
}

// Value 实现 driver.Valuer
func (d Day) Value() (driver.Value, error) { return time.Time(d), nil }

// ParseTime 等价于 Java 的 DateUtils.parseDate：一次尝试多种常见格式。
//
// DIFF: Java 用 SimpleDateFormat + 逐个 pattern 重试；Go 只能显式枚举 layout（Go 的 layout 是"参考时间"而非字母模板）。
//
// 用 javaZone 而不是 time.Local：Java 写到 Redis / ES 里的时间文字是 fastjson2 按 JVM
// 默认时区（Asia/Shanghai）格式化的裸墙钟，读回来必须挂同一个时区才能还原同一个瞬间。
// 写成 time.Local 会把结果绑到进程序的时区设置上：本机 Go 进程的 Local 其实是 UTC，
// 于是 /base/vehicleweight/map 里 checkTime 库里 2024-11-19 00:50 的记求，
// Java 输出 2024-11-18、Go 输出 2024-11-19（差一天）。
// 现在跟数据库分支走同一个 javaZone，两边不再受部署环境 TZ 影响。
func ParseTime(s string) (time.Time, error) {
	return parseTimeWith(s, javaZone)
}

// ParseTimeUTC 同 ParseTime，但把解析结果当成 UTC 瞬间。
//
// 保留给「输入确实是 Jackson 按 UTC 输出的 RFC3339 文字」的场景（比如比对两个服务
// 自己的响应）。Redis / ES 里的缓存不是这种：fastjson2 按 JVM 默认时区落字，
// 那里而要用 ParseTime（本地），理由见 datetime.go 的 parseQuotedTime。
func ParseTimeUTC(s string) (time.Time, error) {
	return parseTimeWith(s, time.UTC)
}

func parseTimeWith(s string, loc *time.Location) (time.Time, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return time.Time{}, nil
	}
	layouts := []string{
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
		time.RFC3339,
		time.RFC3339Nano,
		"2006-01-02 15:04:05.000",
		"2006-01-02",
		"2006/01/02 15:04:05",
		"2006/01/02",
	}
	var lastErr error
	for _, layout := range layouts {
		if t, err := time.ParseInLocation(layout, s, loc); err == nil {
			return t, nil
		} else {
			lastErr = err
		}
	}
	// 兼容纯数字时间戳（秒/毫秒）—— Java 侧常见于 unix 字段
	if n, err := parseInt64(s); err == nil {
		if n > 1e12 {
			return time.UnixMilli(n), nil
		}
		return time.Unix(n, 0), nil
	}
	return time.Time{}, fmt.Errorf("无法解析时间 %q: %w", s, lastErr)
}

func parseInt64(s string) (int64, error) {
	var n int64
	_, err := fmt.Sscanf(s, "%d", &n)
	return n, err
}

// FormatDateTime 等价于 DateUtils.YYYY_MM_DD_HH_MM_SS
func FormatDateTime(t time.Time) string { return t.Format("2006-01-02 15:04:05") }
