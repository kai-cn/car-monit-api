package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailInfo.java
// 类/职责: TrailInfo — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/trail_info.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

import ()

// TrailInfo 对应 Java 类 TrailInfo
type TrailInfo struct {
	TrailUuid string            `json:"trailUuid"` // JAVA L14
	EnterTime *Timestamp        `json:"enterTime"` // JAVA L19
	Tracks    *ZdataTrailTracks `json:"tracks"`    // JAVA L22
	TrailList []TrailBo         `json:"trailList"` // JAVA L27 List<...> → slice
}
