package utils

// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/DateUtils.java:24-200
// 类/职责: DateUtils — 日期格式化 / 加减 / 多格式解析的公共工具（被 12 个 Service 引用）
// 对应 Go 文件: internal/utils/dateutil.go
// 关键映射:
//   YYYY_MM_DD  = "yyyy-MM-dd"            → LayoutDate
//   formatDate(Date)                     → FormatDate
//   formatHour(Date) = "yyyy-MM-dd HH:00:00" → FormatHour
//   parseDateToStr("yyyyMMdd", date)     → FormatCompactDate（DelayMonitoringService 私有 formatDate）
//   addDays / addMinutes / addHours      → AddDays / AddMinutes / AddHours
//   parseDate(Object)                    → ParseDate
//
// DIFF: Java 用 SimpleDateFormat/DateFormatUtils（字符串里是日期字母模板），
// Go 的 layout 是"参考时间" 2006-01-02 15:04:05 —— 写错一个数字格式化结果就静默错乱，
// 因此这里把所有 layout 收敛成常量，业务代码不再出现裸 layout 字符串。
//
// DIFF: Java 的 Date 是可变对象，addDays 返回新对象但仍可能被调用方共享；
// Go 的 time.Time 是值类型，加减天然返回新值，没有"改到别人对象"的隐患。

import (
	"strings"
	"time"
)

// 常用 layout 常量（对应 Java 的格式字符串常量）
const (
	LayoutDate      = "2006-01-02"          // yyyy-MM-dd
	LayoutDateTime  = "2006-01-02 15:04:05" // yyyy-MM-dd HH:mm:ss
	LayoutHour      = "2006-01-02 15:00:00" // yyyy-MM-dd HH:00:00（整点对齐）
	LayoutCompact   = "20060102"            // yyyyMMdd
	LayoutCompactTS = "20060102150405"      // yyyyMMddHHmmss
)

// FormatDate 对应 DateUtils.formatDate(Date) = "yyyy-MM-dd"
func FormatDate(t time.Time) string { return t.Format(LayoutDate) }

// FormatHour 对应 DateUtils.formatHour(Date) = "yyyy-MM-dd HH:00:00"。
//
// 用途：DataLossDetectionService 按小时分组存上报消息 ID 集合，
// 整点对齐是 key 能正确聚合的前提，不能退化成 FormatDateTime。
func FormatHour(t time.Time) string { return t.Format(LayoutHour) }

// FormatCompactDate 对应 DelayMonitoringService 私有 formatDate(Date) = "yyyyMMdd"
func FormatCompactDate(t time.Time) string { return t.Format(LayoutCompact) }

// FormatDateTime 对应 DateUtils.YYYY_MM_DD_HH_MM_SS = "yyyy-MM-dd HH:mm:ss"
func FormatDateTime(t time.Time) string { return t.Format(LayoutDateTime) }

// AddDays 对应 DateUtils.addDays(Date, int)
func AddDays(t time.Time, days int) time.Time { return t.AddDate(0, 0, days) }

// AddHours 对应 DateUtils.addHours(Date, int)
func AddHours(t time.Time, hours int) time.Time { return t.Add(time.Duration(hours) * time.Hour) }

// AddMinutes 对应 DateUtils.addMinutes(Date, int)
func AddMinutes(t time.Time, minutes int) time.Time {
	return t.Add(time.Duration(minutes) * time.Minute)
}

// ParseDate 对应 DateUtils.parseDate(Object)：多格式尝试，解析失败返回零值 + error。
//
// DIFF: Java 返回 null 表示失败，调用方靠 NPE 暴露问题；
// Go 显式返回 error，强制调用方处理（不让脏数据静默进入时间窗口计算）。
func ParseDate(s string) (time.Time, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return time.Time{}, nil
	}
	layouts := []string{
		LayoutDateTime,
		LayoutDate,
		LayoutCompactTS,
		LayoutCompact,
		"2006-01-02T15:04:05",
		time.RFC3339,
		"2006-01-02 15:04",
		"2006-01",
		"2006/01/02 15:04:05",
		"2006/01/02",
		"2006.01.02 15:04:05",
		"2006.01.02",
	}
	var lastErr error
	for _, layout := range layouts {
		if t, err := time.ParseInLocation(layout, s, time.Local); err == nil {
			return t, nil
		} else {
			lastErr = err
		}
	}
	return time.Time{}, lastErr
}
