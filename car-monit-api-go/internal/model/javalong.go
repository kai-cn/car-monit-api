package model

// 本文件不对应单个 Java 类，而是补一种 Java→Go 迁移里必然踩到的形状：
// 实体声明成 Long，但库里那一列其实是 double precision / numeric。
//
// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnSection.java:48,52,72
//           pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnProvinceBorderVehicleWeightNewstructure.java
//           （MyBatis 的取值方式是 ResultSet#getLong）
// 对应 Go 文件: internal/model/javalong.go

import (
	"database/sql/driver"
	"fmt"
	"strconv"
	"time"
)

// JavaLong 对应「Java 声明是 Long、数据库列是浮点/numeric」的字段。
//
// 为什么不能直接用 *int64 或 *float64（这一类一旦踩到就是整接口 500，不是丢一个字段）：
//
//	MyBatis 按实体声明调 ResultSet#getLong，pgjdbc 读到 double precision 时**向零截断**
//	（12.7 -> 12），不报错、不丢行，响应里是个整数。
//	* 用 *int64：pgx 严格执行类型，报 "converting driver.Value type float64 to a int64"，
//	  整个 /base/section/list 直接 500，Java 却是 200。
//	* 用 *float64：能读出来，但 JSON 变成 12.7，Java 输出 12，值和类型两头都对不上。
//
// 所以把 JDBC 的截断语义搬到 Go 侧：内部按浮点收，序列化时截成整数。
//
// DIFF: Java 的 Long 是引用类型，NULL 输出 null。所以字段要写成 *JavaLong ——
// 列值为 NULL 时 GORM 不分配指针，json 自然输出 null，与 Java 一致。
type JavaLong float64

// Scan 实现 sql.Scanner：接受整数、浮点、numeric 的文本形态，一律向零截断。
func (l *JavaLong) Scan(v any) error {
	switch x := v.(type) {
	case nil:
		*l = 0
		return nil
	case int64:
		*l = JavaLong(x)
		return nil
	case int32:
		*l = JavaLong(x)
		return nil
	case int:
		*l = JavaLong(x)
		return nil
	case float64:
		*l = JavaLong(x)
		return nil
	case float32:
		*l = JavaLong(float64(x))
		return nil
	case bool:
		if x {
			*l = 1
		} else {
			*l = 0
		}
		return nil
	case []byte:
		return l.Scan(string(x))
	case string:
		if x == "" {
			*l = 0
			return nil
		}
		// numeric 在 pgx 的文本模式下来的是十进制字符串，小数也可能带尾随 0
		f, err := strconv.ParseFloat(x, 64)
		if err != nil {
			return fmt.Errorf("model.JavaLong: 无法解析 %q: %w", x, err)
		}
		*l = JavaLong(f)
		return nil
	case time.Time:
		return fmt.Errorf("model.JavaLong: 时间列不能映射成 Long")
	}
	return fmt.Errorf("model.JavaLong: 不支持的扫描类型 %T", v)
}

// Value 实现 driver.Valuer：写回时给一个真实整数（Java 的 Long 也是按整数落库的）。
func (l JavaLong) Value() (driver.Value, error) { return int64(l), nil }

// MarshalJSON 输出整数，对应 Jackson 序列化 java.lang.Long。
func (l JavaLong) MarshalJSON() ([]byte, error) {
	return []byte(strconv.FormatInt(int64(l), 10)), nil
}

// UnmarshalJSON 兼容整数与浮点两种输入。
func (l *JavaLong) UnmarshalJSON(b []byte) error {
	s := string(b)
	if s == "null" || s == `""` {
		*l = 0
		return nil
	}
	f, err := strconv.ParseFloat(trimQuotes(s), 64)
	if err != nil {
		f, err = strconv.ParseFloat(s, 64)
		if err != nil {
			return fmt.Errorf("model.JavaLong: 无法解析 %s: %w", s, err)
		}
	}
	*l = JavaLong(f)
	return nil
}

// Int64 取回截断后的整数值，供需要按整数比较的 Go 代码使用。
func (l JavaLong) Int64() int64 { return int64(l) }

// String 便于日志输出。
func (l JavaLong) String() string { return strconv.FormatInt(int64(l), 10) }
