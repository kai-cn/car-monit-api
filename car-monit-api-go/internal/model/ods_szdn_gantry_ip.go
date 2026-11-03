package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantryIp.java
// 类/职责: OdsSzdnGantryIp — 表 ods_szdn_gantry_ip 的实体
// 对应 Go 文件: internal/model/ods_szdn_gantry_ip.go
// 关键映射: @TableName(value='ods_szdn_gantry_ip', schema=None) → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsSzdnGantryIp 对应 Java 类 OdsSzdnGantryIp
type OdsSzdnGantryIp struct {
	Id            *int64         `json:"id" gorm:"column:id;primaryKey"`       // JAVA L29
	GantryCode    string         `json:"gantryCode" gorm:"column:gantry_code"` // JAVA L35 @Excel(门架编号)
	GantryName    string         `json:"gantryName" gorm:"column:gantry_name"` // JAVA L41 @Excel(门架名称)
	OrgCode       string         `json:"orgCode" gorm:"column:org_code"`       // JAVA L47 @Excel(机构编码)
	Ip            string         `json:"ip" gorm:"column:ip"`                  // JAVA L53 @Excel(设备ip)
	Brand         *string        `json:"brand" gorm:"column:brand"`            // JAVA L55
	Type          *string        `json:"type" gorm:"column:type"`              // JAVA L61 @Excel(类型1是省界门架)
	OdsSzdnGantry *OdsSzdnGantry `json:"odsSzdnGantry" gorm:"-"`               // JAVA L65
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnGantryIp) TableName() string {
	return "ods_szdn_gantry_ip"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnGantryIp) Schema() string {
	return ""
}
