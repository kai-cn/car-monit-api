package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/SuspiciousCarVO.java
// 类/职责: SuspiciousCarVO — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/suspicious_car_vo.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// SuspiciousCarVO 对应 Java 类 SuspiciousCarVO
type SuspiciousCarVO struct {
	SignatureKey  string      `json:"signatureKey"`  // JAVA L14
	TimeStamp     *int64      `json:"timeStamp"`     // JAVA L19
	Signature     string      `json:"signature"`     // JAVA L25
	TrailInfoList []TrailInfo `json:"trailInfoList"` // JAVA L27 List<...> → slice
}
