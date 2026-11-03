package utils

// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/StringUtils.java:450-495（toUnderScoreCase）
// 类/职责: 驼峰转下划线，用于把前端传来的 orderByColumn（实体属性名）换成数据库列名
// 对应 Go 文件: internal/utils/caseutil.go
//
// PARITY: 逐分支照抄 Java，包括两处容易改写错的细节：
//  1. 首字符的「前置是否大写」被显式置 false（Java L461-469）；
//  2. 最后一个字符不再更新「下一字符是否大写」，于是它沿用上一轮的值
//     —— 效果是末位永远走不进第一个分支。照搬是为了让 "IDCard" 这类输入
//     在两端得到同一个列名（Java 会得到 "i_d_card"，直觉上像是 bug，但改了就换列名）。

import (
	"strings"
	"unicode"
)

// ToUnderScoreCase 对应 StringUtils.toUnderScoreCase。空串原样返回。
func ToUnderScoreCase(s string) string {
	if s == "" {
		return s
	}
	var sb strings.Builder
	runes := []rune(s)
	n := len(runes)
	preUpper, curUpper, nextUpper := false, true, true
	for i, c := range runes {
		if i > 0 {
			preUpper = unicode.IsUpper(runes[i-1])
		} else {
			preUpper = false
		}
		curUpper = unicode.IsUpper(c)
		if i < n-1 {
			nextUpper = unicode.IsUpper(runes[i+1])
		}
		switch {
		case preUpper && curUpper && !nextUpper:
			sb.WriteRune('_')
		case i != 0 && !preUpper && curUpper:
			sb.WriteRune('_')
		}
		sb.WriteRune(unicode.ToLower(c))
	}
	return sb.String()
}
