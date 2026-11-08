package utils

// 本文件负责"错误与日志文本脱敏"：启动失败、连接失败等报错可能把 DSN 里的口令带出来，
// 而启动日志会被运维/CI 直接看到、也可能进工单与截图。
//
// 设计取舍：
//   - 显式传入的 secret（配置里读到的 password）按原值与 URL-encode 形式各替换一次；
//   - 再加一层通用正则兜底（password=/pwd=/token= 等键值形态），覆盖 pgx / go-redis
//     等第三方库自行拼进错误文本的情况；
//   - 不追求"绝对不可逆"，只保证常见泄漏面（启动失败回显）不出现明文口令。

import (
	"errors"
	"net/url"
	"regexp"
	"strings"
)

// secretKeyPattern 匹配常见"键=值"形态的敏感字段。
//
// 只替换值部分，保留键名便于定位问题（"password=***" 比整段消失更有信息量）。
var secretKeyPattern = regexp.MustCompile(`(?i)\b(password|passwd|pwd|secret|token|access[_-]?key)=([^\s&;,'"]+)`)

// RedactedPlaceholder 是脱敏后的占位符。
const RedactedPlaceholder = "***"

// RedactString 把文本中的敏感串替换成 ***。
//
// 空 secret 会被忽略（否则空串会匹配到所有位置，把文本撕成碎片）；
// 长度 < 3 的 secret 也只做正则兜底，避免误伤正常单词。
func RedactString(s string, secrets ...string) string {
	if s == "" {
		return s
	}
	for _, secret := range secrets {
		if len(secret) < 3 {
			continue
		}
		s = strings.ReplaceAll(s, secret, RedactedPlaceholder)
		// DSN/URL 里的口令常被 URL-encode（@ → %40、/ → %2F），这里补一次。
		if enc := url.QueryEscape(secret); enc != secret {
			s = strings.ReplaceAll(s, enc, RedactedPlaceholder)
		}
	}
	return secretKeyPattern.ReplaceAllString(s, "$1="+RedactedPlaceholder)
}

// RedactError 返回一个已脱敏的 error；err 为 nil 时原样返回 nil。
//
// 保留原始错误链会泄漏明文，所以这里只保留脱敏后的文本（不再 Unwrap）。
func RedactError(err error, secrets ...string) error {
	if err == nil {
		return nil
	}
	return errors.New(RedactString(err.Error(), secrets...))
}
