package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnTollStationIp.java
// 类/职责: OdsSzdnTollStationIp — 表 ods_szdn_toll_station_ip 的实体
// 对应 Go 文件: internal/model/ods_szdn_toll_station_ip.go
// 关键映射: @TableName(value='ods_szdn_toll_station_ip', schema=None) → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsSzdnTollStationIp 对应 Java 类 OdsSzdnTollStationIp
type OdsSzdnTollStationIp struct {
	Id          *int64       `json:"id" gorm:"column:id;primaryKey"`   // JAVA L27
	TollCode    string       `json:"tollCode" gorm:"column:toll_code"` // JAVA L29
	TollName    string       `json:"tollName" gorm:"column:toll_name"` // JAVA L31
	OrgCode     string       `json:"orgCode" gorm:"column:org_code"`   // JAVA L33
	Ip          string       `json:"ip" gorm:"column:ip"`              // JAVA L35
	Brand       *string      `json:"brand" gorm:"column:brand"`        // JAVA L37
	OdsSzdnToll *OdsSzdnToll `json:"odsSzdnToll" gorm:"-"`             // JAVA L41
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnTollStationIp) TableName() string {
	return "ods_szdn_toll_station_ip"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnTollStationIp) Schema() string {
	return ""
}
