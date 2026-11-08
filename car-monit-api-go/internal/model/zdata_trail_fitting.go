package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailFitting.java
// 类/职责: ZdataTrailFitting — 表 zdata_trail_fitting 的实体
// 对应 Go 文件: internal/model/zdata_trail_fitting.go
// 关键映射: @TableName(value='zdata_trail_fitting', schema=None) → TableName()/Schema()；@TableId(None) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// ZdataTrailFitting 对应 Java 类 ZdataTrailFitting
type ZdataTrailFitting struct {
	Cid               *string    `json:"cid" gorm:"column:cid"`                             // JAVA L26
	Enaxlecount       *int       `json:"enaxlecount" gorm:"column:enaxlecount"`             // JAVA L30 @Excel(入口车轴数)
	Entime            *Day       `json:"entime" gorm:"column:entime"`                       // JAVA L35 @JsonFormat(yyyy-MM-dd) → Day @Excel(入口时间)
	Entolllaneid      *string    `json:"entolllaneid" gorm:"column:entolllaneid"`           // JAVA L39 @Excel(入口车道编号)
	Entollstationid   *string    `json:"entollstationid" gorm:"column:entollstationid"`     // JAVA L43 @Excel(入口收费站编号)
	Entollstationname *string    `json:"entollstationname" gorm:"column:entollstationname"` // JAVA L47 @Excel(入口收费站名称)
	Envehicleclass    *int       `json:"envehicleclass" gorm:"column:envehicleclass"`       // JAVA L51 @Excel(入口车型分类)
	Envehicleid       *string    `json:"envehicleid" gorm:"column:envehicleid"`             // JAVA L55 @Excel(入口车辆编号)
	Envehicletype     *int       `json:"envehicletype" gorm:"column:envehicletype"`         // JAVA L59 @Excel(入口车辆类型代码)
	Enweight          *int64     `json:"enweight" gorm:"column:enweight"`                   // JAVA L63 @Excel(入口称重)
	Extime            *Timestamp `json:"extime" gorm:"column:extime"`                       // JAVA L67 @Excel(出口时间)
	Extolllaneid      *string    `json:"extolllaneid" gorm:"column:extolllaneid"`           // JAVA L71 @Excel(出口车道编号)
	Extollstationid   *string    `json:"extollstationid" gorm:"column:extollstationid"`     // JAVA L75 @Excel(出口收费站编号)
	Extollstationname *string    `json:"extollstationname" gorm:"column:extollstationname"` // JAVA L79 @Excel(出口收费站名称)
	Exvehicleclass    *int       `json:"exvehicleclass" gorm:"column:exvehicleclass"`       // JAVA L83 @Excel(出口车型分类)
	Exvehicleid       *string    `json:"exvehicleid" gorm:"column:exvehicleid"`             // JAVA L87 @Excel(出口车辆编号)
	Exvehicletype     *int       `json:"exvehicletype" gorm:"column:exvehicletype"`         // JAVA L91 @Excel(出口车辆类型代码)
	Exweight          *int64     `json:"exweight" gorm:"column:exweight"`                   // JAVA L95 @Excel(出口称重)
	Trailpoints       AnyStr     `json:"trailpoints" gorm:"column:trailpoints"`             // JAVA L99 private String；列实际是 ARRAY，走 AnyStr（见 anustr.go）
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (ZdataTrailFitting) TableName() string {
	return "zdata_trail_fitting"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (ZdataTrailFitting) Schema() string {
	return ""
}
