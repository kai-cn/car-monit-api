package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsCxztFwqclls.java
// 类/职责: OdsCxztFwqclls — 表 ods_cxzt_fwqclls 的实体
// 对应 Go 文件: internal/model/ods_cxzt_fwqclls.go
// 关键映射: @TableName(value='ods_cxzt_fwqclls', schema=None) → TableName()/Schema()；@TableId(None) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsCxztFwqclls 对应 Java 类 OdsCxztFwqclls
type OdsCxztFwqclls struct {
	BigId            *int64     `json:"bigId" gorm:"column:big_id"`                      // JAVA L26
	Datauuid         *string    `json:"datauuid" gorm:"column:datauuid"`                 // JAVA L28
	Targetpicurl     *string    `json:"targetpicurl" gorm:"column:targetpicurl"`         // JAVA L32 @Excel(抓拍照片url)
	Vehiclebrand     *string    `json:"vehiclebrand" gorm:"column:vehiclebrand"`         // JAVA L36 @Excel(车辆品牌)
	Platepicurl      *string    `json:"platepicurl" gorm:"column:platepicurl"`           // JAVA L40 @Excel(车牌照片)
	Rollvehiclestype *string    `json:"rollvehiclestype" gorm:"column:rollvehiclestype"` // JAVA L44 @Excel(车类型)
	Plateno          *string    `json:"plateno" gorm:"column:plateno"`                   // JAVA L48 @Excel(车牌)
	Directionname    *string    `json:"directionname" gorm:"column:directionname"`       // JAVA L52 @Excel(方向名称)
	Platetype        *string    `json:"platetype" gorm:"column:platetype"`               // JAVA L56 @Excel(车牌类型)
	Dangmark         *string    `json:"dangmark" gorm:"column:dangmark"`                 // JAVA L60 @Excel(是否危化品车)
	Crosstime        *Timestamp `json:"crosstime" gorm:"column:crosstime"`               // JAVA L64 @Excel(通过时间)
	Axles            *string    `json:"axles" gorm:"column:axles"`                       // JAVA L68 @Excel(坐标)
	Devicename       *string    `json:"devicename" gorm:"column:devicename"`             // JAVA L72 @Excel(设备名称)
	Ipaddress        *string    `json:"ipaddress" gorm:"column:ipaddress"`               // JAVA L76 @Excel(IP地址)
	Servicename      *string    `json:"servicename" gorm:"column:servicename"`           // JAVA L80 @Excel(服务区名称)
	Vehicletype      *string    `json:"vehicletype" gorm:"column:vehicletype"`           // JAVA L84 @Excel(车辆类型)
	LoadTime         *string    `json:"loadTime" gorm:"column:load_time"`                // JAVA L88 @Excel(加载时间)
	GradeLevel       *string    `json:"gradeLevel" gorm:"column:grade_level"`            // JAVA L92 @Excel(分类分级)
	UuidList         []string   `json:"uuidList" gorm:"-"`                               // JAVA L95 List<...> → slice
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsCxztFwqclls) TableName() string {
	return "ods_cxzt_fwqclls"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsCxztFwqclls) Schema() string {
	return ""
}
