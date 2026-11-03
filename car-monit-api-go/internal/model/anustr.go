package model

// 本文件不对应单个 Java 类，而是补另一类 Java→Go 的形状差：
// 实体声明成 String，但库里那一列其实是 tinyint / array 这类非字符列。
//
// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataLocationDict.java:100
//           （direction 声明 String，列 direction 是 tinyint）
//           pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailFitting.java:99
//           （trailpoints 声明 String，列 trailpoints 是 ARRAY）
//           MyBatis 的取值方式是 ResultSet#getString
// 对应 Go 文件: internal/model/anustr.go

import (
	"database/sql/driver"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// AnyStr 对应「Java 声明是 String、数据库列不是字符类型」的字段。
//
// DIFF: MyBatis 调 ResultSet#getString，pgjdbc 会把标量转文本（tinyint 1 -> "1"），
// 数组则给出 Postgres 的数组字面量（{a,b}）。Go 的 *string 在 Scan 阶段会因为
// 「不支持的扫描类型 int32 / []string」直接失败，整个查询报错。
// AnyStr 自己实现 Scan，把 JDBC 的转换搬到 Go 侧。
//
// 列可空时字段要写成 *AnyStr：NULL 时 GORM 不分配指针，JSON 输出 null，与 Java 一致。
type AnyStr string

// Scan 实现 sql.Scanner：任何标量/数组都转成 pgjdbc getString 返回的文本。
func (s *AnyStr) Scan(v any) error {
	switch x := v.(type) {
	case nil:
		*s = ""
		return nil
	case string:
		*s = AnyStr(x)
		return nil
	case []byte:
		*s = AnyStr(x)
		return nil
	case bool:
		*s = AnyStr(strconv.FormatBool(x))
		return nil
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		*s = AnyStr(fmt.Sprint(x))
		return nil
	case float32:
		*s = AnyStr(strconv.FormatFloat(float64(x), 'f', -1, 32))
		return nil
	case float64:
		*s = AnyStr(strconv.FormatFloat(x, 'f', -1, 64))
		return nil
	case time.Time:
		*s = AnyStr(x.Format("2006-01-02 15:04:05"))
		return nil
	}
	// 数组分支：pgx 给的是 []string / []any / driver.Value 切片，
	// pgjdbc 对数组的 getString 结果是 Postgres 数组字面量 {a,b}。
	rv, err := toSlice(v)
	if err != nil {
		return fmt.Errorf("model.AnyStr: 不支持的扫描类型 %T", v)
	}
	parts := make([]string, len(rv))
	for i, e := range rv {
		parts[i] = arrayElemText(e)
	}
	*s = AnyStr("{" + strings.Join(parts, ",") + "}")
	return nil
}

// toSlice 把 pgx 返回的各种切片形态统一成 []any。
func toSlice(v any) ([]any, error) {
	switch x := v.(type) {
	case []string:
		out := make([]any, len(x))
		for i := range x {
			out[i] = x[i]
		}
		return out, nil
	case []any:
		return x, nil
	}
	return nil, fmt.Errorf("不是切片")
}

// arrayElemText 按 Postgres 数组字面量的规则渲染一个元素：
// 含特殊字符时加双引号，内部双引号再转义。
func arrayElemText(e any) string {
	t := fmt.Sprint(e)
	if t == "" {
		return `""`
	}
	if strings.ContainsAny(t, `{},"\\ `) || t != strings.TrimSpace(t) {
		return `"` + strings.ReplaceAll(strings.ReplaceAll(t, `\`, `\\`), `"`, `\"`) + `"`
	}
	return t
}

// Value 实现 driver.Valuer。
func (s AnyStr) Value() (driver.Value, error) { return string(s), nil }

// String 便于日志与拼接。
func (s AnyStr) String() string { return string(s) }

// AnyStrVal 从 *AnyStr 取回普通 string（nil 当空串）。
//
// DIFF: 不能直接 (*p).String() —— String() 是值接收者，p 为 nil 时会 panic。
// 这里用函数形式做一次 nil 判断，语义上等价于 Java 的 Objects.toString(s, "")。
func AnyStrVal(s *AnyStr) string {
	if s == nil {
		return ""
	}
	return string(*s)
}
