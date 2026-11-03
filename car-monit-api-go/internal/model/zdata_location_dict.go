package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataLocationDict.java
// 类/职责: ZdataLocationDict — 表 zdata_location_dict 的实体
// 对应 Go 文件: internal/model/zdata_location_dict.go
// 关键映射: @TableName(value='zdata_location_dict', schema=None) → TableName()/Schema()；@TableId(None) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// ZdataLocationDict 对应 Java 类 ZdataLocationDict
type ZdataLocationDict struct {
	Id           *int64   `json:"id" gorm:"column:id"`                      // JAVA L27
	Type         string   `json:"type" gorm:"column:type"`                  // JAVA L31 @Excel(类型)
	Name         *string  `json:"name" gorm:"column:name"`                  // JAVA L35 @Excel(收费站)
	RawCode      string   `json:"rawCode" gorm:"column:raw_code"`           // JAVA L39 @Excel(轨迹表和实时轨迹code)
	StandardCode *string  `json:"standardCode" gorm:"column:standard_code"` // JAVA L43 @Excel(收费站/门架code)
	Roadcode     *string  `json:"roadcode" gorm:"column:roadcode"`          // JAVA L47 @Excel(路线编码)
	Roadname     *string  `json:"roadname" gorm:"column:roadname"`          // JAVA L51 @Excel(路线名称)
	Sectioncode  *string  `json:"sectioncode" gorm:"column:sectioncode"`    // JAVA L55 @Excel(路段编码)
	Sectionname  *string  `json:"sectionname" gorm:"column:sectionname"`    // JAVA L59 @Excel(路段名称)
	Tollcode     *string  `json:"tollcode" gorm:"column:tollcode"`          // JAVA L63 @Excel(收费站编码)
	Tollname     *string  `json:"tollname" gorm:"column:tollname"`          // JAVA L67 @Excel(收费站名称)
	Orgcode      *string  `json:"orgcode" gorm:"column:orgcode"`            // JAVA L71 @Excel(组织机构编码)
	Orgname      *string  `json:"orgname" gorm:"column:orgname"`            // JAVA L75 @Excel(组织机构名称)
	CreatedAt    *Day     `json:"createdAt" gorm:"column:created_at"`       // JAVA L80 @JsonFormat(yyyy-MM-dd) → Day @Excel(创建时间)
	UpdatedAt    *Day     `json:"updatedAt" gorm:"column:updated_at"`       // JAVA L85 @JsonFormat(yyyy-MM-dd) → Day @Excel(修改时间)
	Latitude     *float64 `json:"latitude" gorm:"column:latitude"`          // JAVA L88
	Longitude    *float64 `json:"longitude" gorm:"column:longitude"`        // JAVA L91
	PileNoK      *string  `json:"pileNoK" gorm:"column:pile_no_k"`          // JAVA L94
	PileNo       *string  `json:"pileNo" gorm:"column:pile_no"`             // JAVA L97
	Direction    *AnyStr  `json:"direction" gorm:"column:direction"`        // JAVA L100 private String；列实际是 tinyint，走 AnyStr（见 anustr.go）
	Remark       *string  `json:"remark" gorm:"column:remark"`              // JAVA L104 @Excel(备注)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (ZdataLocationDict) TableName() string {
	return "zdata_location_dict"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (ZdataLocationDict) Schema() string {
	return ""
}
