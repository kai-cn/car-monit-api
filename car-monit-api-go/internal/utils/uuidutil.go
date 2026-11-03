package utils

// JAVA 对照: pro-base-common/src/main/java/com/ruoyi/common/utils/StringUtils.java:29-31
//           `return UUID.randomUUID().toString().replaceAll("-", "");`
// 类/职责: 生成"去横线 UUID"，对应 Java 的 StringUtils.getUUID()
// 对应 Go 文件: internal/utils/uuidutil.go
//
// PARITY: Java 侧几乎所有对外可见的 id（行 key、抓拍 uuid 回填等）都是 **32 位十六进制、无横线**，
// 而 google/uuid 的 NewString() 是 36 位带横线。两者长度和字符集都不同，
// 前端把返回值当 key 或做正则校验时会踩到 —— 必须统一走这个函数。
//
// 注意区分：导出任务的 taskId 在 Java 侧是**带横线**的标准 UUID
// （实测 :9902 返回 `7441f716-bdfa-4e2c-9203-...`），那类场景应继续用 uuid.NewString()，不要用本函数。

import (
	"strings"

	"github.com/google/uuid"
)

// GetUUID 对应 StringUtils.getUUID()：一个随机 UUID，去掉全部横线，长度 32。
func GetUUID() string {
	return strings.ReplaceAll(uuid.NewString(), "-", "")
}
