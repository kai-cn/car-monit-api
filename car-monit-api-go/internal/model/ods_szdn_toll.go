package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnToll.java
// 类/职责: OdsSzdnToll — 表 ods_szdn_toll 的实体
// 对应 Go 文件: internal/model/ods_szdn_toll.go
// 关键映射: @TableName(value='ods_szdn_toll', schema=None) → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsSzdnToll 对应 Java 类 OdsSzdnToll
type OdsSzdnToll struct {
	Id                     string  `json:"id" gorm:"column:id;primaryKey"`                                // JAVA L28
	RoadCode               *string `json:"roadCode" gorm:"column:road_code"`                              // JAVA L32 @Excel(路线编号)
	IdCard                 *string `json:"idCard" gorm:"column:id_card"`                                  // JAVA L36 @Excel(收费站业务唯一编码)
	TollCode               *string `json:"tollCode" gorm:"column:toll_code"`                              // JAVA L40 @Excel(收费站编号)
	TollName               *string `json:"tollName" gorm:"column:toll_name"`                              // JAVA L44 @Excel(收费站名称)
	PileNo                 *string `json:"pileNo" gorm:"column:pile_no"`                                  // JAVA L48 @Excel(桩号)
	OrgName                *string `json:"orgName" gorm:"column:org_name"`                                // JAVA L52 @Excel(所属机构名称)
	HexCode                *string `json:"hexCode" gorm:"column:hex_code"`                                // JAVA L56 @Excel(收费站HEX编码)
	StateCode              *string `json:"stateCode" gorm:"column:state_code"`                            // JAVA L60 @Excel(国网编号)
	OrgCode                *string `json:"orgCode" gorm:"column:org_code"`                                // JAVA L64 @Excel(机构编码)
	Longitude              *string `json:"longitude" gorm:"column:longitude"`                             // JAVA L68 @Excel(经度)
	Latitude               *string `json:"latitude" gorm:"column:latitude"`                               // JAVA L72 @Excel(纬度)
	OpenDate               *Day    `json:"openDate" gorm:"column:open_date"`                              // JAVA L77 @JsonFormat(yyyy-MM-dd) → Day @Excel(开通日期)
	TollAliasName          *string `json:"tollAliasName" gorm:"column:toll_alias_name"`                   // JAVA L81 @Excel(收费站别名)
	InMonitorResource      *string `json:"inMonitorResource" gorm:"column:in_monitor_resource"`           // JAVA L85 @Excel(入口治超监控资源，多个以英文逗号分割)
	LaneMonitorResource    *string `json:"laneMonitorResource" gorm:"column:lane_monitor_resource"`       // JAVA L89 @Excel(车道抓拍监控资源，多个以英文逗号分割)
	SquareMonitorResource  *string `json:"squareMonitorResource" gorm:"column:square_monitor_resource"`   // JAVA L93 @Excel(广场监控资源，多个以英文逗号分割)
	DynamicMonitorResource *string `json:"dynamicMonitorResource" gorm:"column:dynamic_monitor_resource"` // JAVA L97 @Excel(动环监控资源，多个以英文逗号分割)
	TollCodeMerge          *string `json:"tollCodeMerge" gorm:"column:toll_code_merge"`                   // JAVA L101 @Excel(收费站编号)
	StateCodeMerge         *string `json:"stateCodeMerge" gorm:"column:state_code_merge"`                 // JAVA L105 @Excel(国网编号)
	TollNameMerge          *string `json:"tollNameMerge" gorm:"column:toll_name_merge"`                   // JAVA L109 @Excel(收费站名称)
	SectionCode            *string `json:"sectionCode" gorm:"column:section_code"`                        // JAVA L113 @Excel(所属路段编码)
	TollOrgCode            *string `json:"tollOrgCode" gorm:"column:toll_org_code"`                       // JAVA L117 @Excel(收费站对应机构编码)
	IsAccess               *string `json:"isAccess" gorm:"column:is_access"`                              // JAVA L121 @Excel(流水是否接入)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnToll) TableName() string {
	return "ods_szdn_toll"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnToll) Schema() string {
	return ""
}
