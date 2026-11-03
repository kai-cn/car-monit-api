package model

// 本文件为「Java 的序列化格式」补齐 Go 侧的等价类型。
//
// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/**（各实体上的 @JsonFormat 注解）
//           + com.fasterxml.jackson.databind.util.StdDateFormat（无注解时的默认格式）
// 对应 Go 文件: internal/model/datetime.go
//
// 为什么必须有这两个类型：
//
// Java 实体的时间字段只有三种落盘形态，而 Go 用 time.Time 一种类型全部包了，格式全都对不上：
//
//	Java 声明                                  序列化结果                      Go 的 time.Time 默认值
//	@JsonFormat(pattern="yyyy-MM-dd")          2012-12-01                      2012-12-01T00:00:00Z
//	@JsonFormat(pattern="yyyy-MM-dd HH:mm:ss") 2012-12-01 00:00:00             2012-12-01T00:00:00Z
//	(无注解) Date                              2025-11-16T07:14:17.000+00:00   2025-11-16T07:14:17Z
//
// Day 对应第一种，DateTime 对应第二种，Timestamp 对应第三种。

import (
	"database/sql/driver"
	"fmt"
	"time"
)

// JavaDateTimeLayout 等价于 Java 的 "yyyy-MM-dd HH:mm:ss"。
const JavaDateTimeLayout = "2006-01-02 15:04:05"

// JavaStdDateLayout 等价于 Jackson StdDateFormat 的输出：带毫秒、带 +00:00 时区。
//
// 注意用 -07:00 而不是 Z07:00：前者在 UTC 下输出 "+00:00"，后者输出 "Z"。
const JavaStdDateLayout = "2006-01-02T15:04:05.000-07:00"

// javaZone 是 Java 进程给「timestamp without time zone」列赋的时区。
//
// 为什么必须显式写出来（这是本次比对里量最大的一类差异，1048 处）：
//
//	库里所有时间列都是 timestamp without time zone（已用 information_schema 全量核实，
//	一个 timestamptz 都没有），存的是不带时区的裸墙钟，例如 2025-09-10 08:51:30。
//	* pgjdbc 读它时用 JVM 默认时区（Asia/Shanghai）拼成 java.util.Date，
//	  于是这个 Date 的真实瞬间是 00:51:30 UTC；Jackson 按 UTC 输出 -> "2025-09-10T00:51:30.000+00:00"。
//	* pgx v5 的 TimestampCodec 则直接把裸墙钟当成 UTC，瞬间是 08:51:30 UTC。
//	两边读同一个字节，差 8 小时。Go 直接把 pgx 的值打印出来就会多 8 小时：
//	java='2025-01-29 02:31:15'  go='2025-01-29 10:31:15'。
//
// 修正方式：读进来时把裸墙钟重挂（anchor）到 +08:00，输出时统一按 UTC 格式化，
// 这样 Go 的瞬间与 Jackson 的瞬间相同，文字也逐字相同。写回时 Value() 用的是这个
// 时间自身的墙钟字段（pgx 按 naive 编码），所以「读出来再写回去」不会发生漂移。
var javaZone = func() *time.Location {
	if l, err := time.LoadLocation("Asia/Shanghai"); err == nil {
		return l
	}
	// 精简镜像里没有 tzdata 时退化成固定 +08:00（中国 1991 年后无夏令时，语义等价）
	return time.FixedZone("Asia/Shanghai", 8*3600)
}()

// anchorTimestamp 把 pgx 读回的「墙钟按 UTC」重挂成「墙钟按 Asia/Shanghai」。
//
// 只对数据库读入的值调用。已经从 Java 格式的字符串解析出来的值不能再挂一次，
// 否则会偏移 8 小时（那种字符串本身已经是 UTC 文字）。
func anchorTimestamp(t time.Time) time.Time {
	if t.IsZero() {
		return t
	}
	u := t.UTC()
	return time.Date(u.Year(), u.Month(), u.Day(),
		u.Hour(), u.Minute(), u.Second(), u.Nanosecond(), javaZone)
}

// DateTime 等价于 Java 中 `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") private Date xxx`。
type DateTime time.Time

// NewDateTime 由 time.Time 构造
func NewDateTime(t time.Time) *DateTime {
	d := DateTime(t)
	return &d
}

// Time 取回底层 time.Time
func (d DateTime) Time() time.Time { return time.Time(d) }

// String 对应 DateUtils.parseDateToStr(date, "yyyy-MM-dd HH:mm:ss")
//
// 按 UTC 格式化：字段里存的是「和 Java 的 java.util.Date 相同的瞬间」，
// 而 Jackson 的 ObjectMapper 时区为 UTC，两边要对齐就必须都按 UTC 落字。
func (d DateTime) String() string { return time.Time(d).UTC().Format(JavaDateTimeLayout) }

// MarshalJSON 对应 Jackson @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
func (d DateTime) MarshalJSON() ([]byte, error) {
	return []byte(`"` + time.Time(d).UTC().Format(JavaDateTimeLayout) + `"`), nil
}

// UnmarshalJSON 兼容 "yyyy-MM-dd HH:mm:ss" 与 RFC3339 两种输入
func (d *DateTime) UnmarshalJSON(b []byte) error {
	t, err := parseQuotedTime(b)
	if err != nil || t == nil {
		return err
	}
	*d = DateTime(*t)
	return nil
}

// Scan 实现 sql.Scanner
func (d *DateTime) Scan(v any) error {
	t, err := scanTime(v)
	if err != nil || t == nil {
		return err
	}
	*d = DateTime(*t)
	return nil
}

// Value 实现 driver.Valuer
func (d DateTime) Value() (driver.Value, error) { return time.Time(d), nil }

// Timestamp 等价于 Java 中没有 @JsonFormat 注解的 java.util.Date 字段。
//
// Jackson 的 StdDateFormat 输出 "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"，本项目 ObjectMapper 的时区为 UTC，
// 因此实际值是 2025-11-16T07:14:17.000+00:00。Go 的 time.Time 默认输出 2025-11-16T07:14:17Z，
// 少了毫秒、时区也从 +00:00 变成了 Z —— 逐字比对时这就是差异。
type Timestamp time.Time

// NewTimestamp 由 time.Time 构造
func NewTimestamp(t time.Time) *Timestamp {
	ts := Timestamp(t)
	return &ts
}

// Time 取回底层 time.Time
func (ts Timestamp) Time() time.Time { return time.Time(ts) }

// String 按 Java 默认格式输出
func (ts Timestamp) String() string { return time.Time(ts).UTC().Format(JavaStdDateLayout) }

// MarshalJSON 对应 Jackson StdDateFormat（UTC）
func (ts Timestamp) MarshalJSON() ([]byte, error) {
	return []byte(`"` + time.Time(ts).UTC().Format(JavaStdDateLayout) + `"`), nil
}

// UnmarshalJSON 兼容任意可解析的时间字符串
func (ts *Timestamp) UnmarshalJSON(b []byte) error {
	t, err := parseQuotedTime(b)
	if err != nil || t == nil {
		return err
	}
	*ts = Timestamp(*t)
	return nil
}

// Scan 实现 sql.Scanner
func (ts *Timestamp) Scan(v any) error {
	t, err := scanTime(v)
	if err != nil || t == nil {
		return err
	}
	*ts = Timestamp(*t)
	return nil
}

// Value 实现 driver.Valuer
func (ts Timestamp) Value() (driver.Value, error) { return time.Time(ts), nil }

// parseQuotedTime 解开 `"..."` 并按本地墙钟解析；null/空串返回 (nil, nil)。
//
// 为什么按本地而不是 UTC：Redis / ES 里的时间文字是 fastjson2 写进去的，
// fastjson2 用 JVM 默认时区（Asia/Shanghai）格式化，所以存的是**本地墙钟**。
// Java 读回来时同样按默认时区解释，得到的瞬间 = 墙钟 - 8h，Jackson 再按 UTC 落字。
// Go 这边必须走同一条路径：ParseTime 已经把字符串挂到 time.Local，瞬间就是墙钟-8h，
// 输出端 MarshalJSON 再按 UTC 格式化，两头对上。
// 实测依据：/base/vehicleweight/map 里 checkTime 库里是 2024-11-19 00:xx，
// Java 输出 2024-11-18，按 UTC 解析的 Go 会输出 2024-11-19（差一天）。
func parseQuotedTime(b []byte) (*time.Time, error) {
	s := string(b)
	if s == "null" || s == `""` {
		return nil, nil
	}
	s = trimQuotes(s)
	if s == "" {
		return nil, nil
	}
	t, err := ParseTime(s)
	if err != nil {
		return nil, err
	}
	return &t, nil
}

// scanTime 把数据库返回值统一转成 *time.Time；nil 返回 (nil, nil)。
//
// time.Time 分支必须过 anchorTimestamp：见 javaZone 的说明，pgx 把裸墙钟当成 UTC，
// 而 pgjdbc 当成 +08:00，不重挂就会整体好 8 小时。
// 字符串分支不能再挂：ParseTime 已经按 javaZone 解了，再挂就是减两轮 8 小时。
func scanTime(v any) (*time.Time, error) {
	switch x := v.(type) {
	case nil:
		return nil, nil
	case time.Time:
		a := anchorTimestamp(x)
		return &a, nil
	case []byte:
		t, err := ParseTime(string(x))
		if err != nil {
			return nil, err
		}
		return &t, nil
	case string:
		t, err := ParseTime(x)
		if err != nil {
			return nil, err
		}
		return &t, nil
	}
	return nil, fmt.Errorf("model: 不支持的时间扫描类型 %T", v)
}

func trimQuotes(s string) string {
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		return s[1 : len(s)-1]
	}
	return s
}
