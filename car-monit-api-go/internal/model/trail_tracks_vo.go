package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailTracksVo.java
// 类/职责: TrailTracksVo — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/trail_tracks_vo.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// TrailTracksVo 对应 Java 类 TrailTracksVo
type TrailTracksVo struct {
	PlateKey      string    `json:"plateKey"`      // JAVA L21
	EnterTime     *DateTime `json:"enterTime"`     // JAVA L27 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime
	ExitTime      *DateTime `json:"exitTime"`      // JAVA L33 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime
	Trailpoints   string    `json:"trailpoints"`   // JAVA L38
	Envehicletype string    `json:"envehicletype"` // JAVA L43
}
