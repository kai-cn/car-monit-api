package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/CarParaVO.java
// 类/职责: CarParaVO — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/car_para_vo.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

import ()

// CarParaVO 对应 Java 类 CarParaVO
type CarParaVO struct {
	Carlist      []CarVO    `json:"carlist"`      // JAVA L14 List<...> → slice
	CarNo        string     `json:"carNo"`        // JAVA L17
	ApplyTime1   string     `json:"applyTime1"`   // JAVA L20
	ApplyTime2   string     `json:"applyTime2"`   // JAVA L22
	CarNoList    []string   `json:"carNoList"`    // JAVA L27 List<...> → slice
	PageNum      *int       `json:"pageNum"`      // JAVA L30
	PageSize     *int       `json:"pageSize"`     // JAVA L33
	StartNum     *int       `json:"startNum"`     // JAVA L38
	EndNum       *int       `json:"endNum"`       // JAVA L41
	StarTime     *int       `json:"starTime"`     // JAVA L45
	EndTime      *int       `json:"endTime"`      // JAVA L48
	Flag         string     `json:"flag"`         // JAVA L51
	SectionList  []string   `json:"sectionList"`  // JAVA L57 List<...> → slice
	LastExitTime *Timestamp `json:"lastExitTime"` // JAVA L62
}
