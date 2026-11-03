package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/CarVO.java
// 类/职责: CarVO — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/car_vo.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// CarVO 对应 Java 类 CarVO
type CarVO struct {
	CarId     string `json:"carId"`     // JAVA L9
	CarNo     string `json:"carNo"`     // JAVA L12
	TrackId   string `json:"trackId"`   // JAVA L15
	TrackJosn string `json:"trackJosn"` // JAVA L18
	Flag      string `json:"flag"`      // JAVA L21
}
