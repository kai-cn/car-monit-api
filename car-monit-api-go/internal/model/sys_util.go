package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/SysUtil.java
// 类/职责: SysUtil — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/sys_util.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// SysUtil 对应 Java 类 SysUtil
type SysUtil struct {
	BussType      string `json:"bussType"`      // JAVA L9
	BussCode      string `json:"bussCode"`      // JAVA L12
	QueryCondtion string `json:"queryCondtion"` // JAVA L15
}
