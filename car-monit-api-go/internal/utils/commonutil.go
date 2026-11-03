package utils

// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/CommonUtil.java:19-233
// 类/职责: CommonUtil — 空值归一 / 空白判定 / 收费站名称归一化（轨迹富集大量依赖）
// 对应 Go 文件: internal/utils/commonutil.go
// 关键映射:
//   isNull(Object)            → IsNull（null → ""，否则 trim）
//   isBlank / isNotBlank      → IsBlank / IsNotBlank
//   isInteger                 → IsInteger
//   deleteEnd                 → DeleteEnd
//   repalacePicUrl            → RepalacePicUrl
//   repalaceSzdnTollName      → RepalaceSzdnTollName
//
// DIFF: Java 的 isNull 接受 Object 并用 toString()；Go 用泛型约束到 any 后同样退化为字符串，
// 但对 nil 指针 / nil 接口都返回 ""（Java 里传 null 才返回 ""，传 0 会返回 "0"）。

import (
	"strconv"
	"strings"
)

// IsNull 对应 CommonUtil.isNull(Object)：nil → ""，否则 trim 后返回。
func IsNull(v any) string {
	if v == nil {
		return ""
	}
	switch s := v.(type) {
	case string:
		return strings.TrimSpace(s)
	case *string:
		if s == nil {
			return ""
		}
		return strings.TrimSpace(*s)
	default:
		return strings.TrimSpace(toString(v))
	}
}

// toString 把基础类型转字符串；未知类型返回空串（与 Java 的 String.valueOf 接近）。
func toString(v any) string {
	switch x := v.(type) {
	case int:
		return strconv.Itoa(x)
	case int32:
		return strconv.FormatInt(int64(x), 10)
	case int64:
		return strconv.FormatInt(x, 10)
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case float32:
		return strconv.FormatFloat(float64(x), 'f', -1, 32)
	case bool:
		return strconv.FormatBool(x)
	case *int64:
		if x == nil {
			return ""
		}
		return strconv.FormatInt(*x, 10)
	case *float64:
		if x == nil {
			return ""
		}
		return strconv.FormatFloat(*x, 'f', -1, 64)
	case *float32:
		if x == nil {
			return ""
		}
		return strconv.FormatFloat(float64(*x), 'f', -1, 32)
	case *int:
		if x == nil {
			return ""
		}
		return strconv.Itoa(*x)
	default:
		return ""
	}
}

// IsBlank 对应 CommonUtil.isBlank(String)：nil/空/纯空白
func IsBlank(s string) bool { return strings.TrimSpace(s) == "" }

// IsNotBlank 对应 CommonUtil.isNotBlank(String)
func IsNotBlank(s string) bool { return !IsBlank(s) }

// IsInteger 对应 CommonUtil.isInteger(String)：可带正负号的纯数字
func IsInteger(s string) bool {
	if s == "" {
		return false
	}
	if s[0] == '+' || s[0] == '-' {
		s = s[1:]
	}
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// RepalaceSzdnTollName 对应 CommonUtil.repalaceSzdnTollName（Java 方法名拼写就是 repalace，保持同名便于检索）：
// 依次去掉 "收费站" / "江西" / "站"，用于把收费站名归一成可当 map key 的短名。
//
// PARITY: Java 用 replaceAll(正则)，这里 "收费站"/"江西"/"站" 都是字面量无正则元字符，
// strings.ReplaceAll 语义等价（且不会出现正则回溯开销）。
func RepalaceSzdnTollName(tollName string) string {
	name := IsNull(tollName)
	if IsNotBlank(name) {
		name = strings.ReplaceAll(name, "收费站", "")
		name = strings.ReplaceAll(name, "江西", "")
		name = strings.ReplaceAll(name, "站", "")
	}
	return name
}

// DeleteEnd 对应 CommonUtil.deleteEnd(Object)：去掉末尾的一个逗号。
//
// 轨迹富集用它把 "a.jpg,b.jpg," 这种累加串收尾，避免前端拿到空图片项。
func DeleteEnd(s string) string {
	str := IsNull(s)
	if strings.HasSuffix(str, ",") {
		return str[:len(str)-1]
	}
	return str
}

// 图片域名替换常量，对应 CommonUtil.repalacePicUrl 里写死的两个地址
const (
	picInternalBase = "http://jxjt.isilon.com/ifs"
	picInternalHost = "http://jxjt.isilon.com"
	picPublicHost   = "http://36.200.30.144:9080"
)

// RepalacePicUrl 对应 CommonUtil.repalacePicUrl：把内网图片域名换成对外可访问地址。
//
// 注意顺序：先匹配带 /ifs 前缀的长串，否则短串会先把域名吃掉，路径就丢了。
func RepalacePicUrl(imagesArry string) string {
	s := IsNull(imagesArry)
	if IsBlank(s) {
		return s
	}
	if strings.Contains(s, picInternalBase) {
		return strings.ReplaceAll(s, picInternalBase, picPublicHost)
	}
	return strings.ReplaceAll(s, picInternalHost, picPublicHost)
}
