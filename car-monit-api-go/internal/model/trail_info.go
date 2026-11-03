package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailInfo.java
// 类/职责: TrailInfo — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/trail_info.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。
//
// PARITY（P-SER-1）：TrailUuid 与 TrailBo 的字符串字段同理 —— Java 没赋值时是 null。
// 但要注意赋值来源：SysUtilController.java:81/131 是 `setTrailUuid(CommonUtil.isNull(plateKey))`，
// 而 CommonUtil.isNull 空值返回的是**空串**（CommonUtil.java:19），所以两个轨迹接口下
// 这个字段是 ""、不是 null；changeTrailInfo 那条路径（请求体直接反序列化）才是 null。
// 改成 *string 后赋值点必须显式写 model.Str("") 才能保住 ""。

import ()

// TrailInfo 对应 Java 类 TrailInfo
type TrailInfo struct {
	TrailUuid *string           `json:"trailUuid"` // JAVA L14
	EnterTime *Timestamp        `json:"enterTime"` // JAVA L19
	Tracks    *ZdataTrailTracks `json:"tracks"`    // JAVA L22
	TrailList []TrailBo         `json:"trailList"` // JAVA L27 List<...> → slice
}
