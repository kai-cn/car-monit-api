package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnProvinceBorderVehicleWeightNewstructure.java
// 类/职责: OdsSzdnProvinceBorderVehicleWeightNewstructure — 表 ods_szdn_province_border_vehicle_weight_newstructure 的实体
// 对应 Go 文件: internal/model/ods_szdn_province_border_vehicle_weight_newstructure.go
// 关键映射: @TableName(value='ods_szdn_province_border_vehicle_weight_newstructure', schema=None) → TableName()/Schema()；@TableId(datauuid) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// PARITY: 这张表是本项目里唯一「列名大小写混杂」的表 —— 既有一批驼峰列（dataSource /
// plateNo / checkTime / ...），又有三个下划线列（load_time / grade_level / datauuid）。
// 数据库里没有 data_source 之类的下划线版本，所以 column 标签必须与驼峰完全一致；
// GORM 的 postgres 方言会把列名包成 "dataSource"，正好等价于 Java XML 里的 t."dataSource"。
// 一旦按 snake_case 写标签，GORM 不会报错，只会悄悄把这些字段读成 NULL —— 接口上表现为"整行字段全空"。
//
// JAVA 对照: OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.xml:42-73 的 select 列表（逐列带双引号）。

// OdsSzdnProvinceBorderVehicleWeightNewstructure 对应 Java 类 OdsSzdnProvinceBorderVehicleWeightNewstructure
type OdsSzdnProvinceBorderVehicleWeightNewstructure struct {
	DataSource         *string   `json:"dataSource" gorm:"column:dataSource"`                 // JAVA L33 @Excel(数据来源)
	DataType           *string   `json:"dataType" gorm:"column:dataType"`                     // JAVA L39 @Excel(数据类型)
	PlateNo            *string   `json:"plateNo" gorm:"column:plateNo"`                       // JAVA L45 @Excel(车牌号)
	SiteId             *string   `json:"siteId" gorm:"column:siteId"`                         // JAVA L51 @Excel(站点ID)
	Location           *string   `json:"location" gorm:"column:location"`                     // JAVA L57 @Excel(设备地点)
	DriveNo            *int64    `json:"driveNo" gorm:"column:driveNo"`                       // JAVA L63 @Excel(车道号)
	PlateColor         *string   `json:"plateColor" gorm:"column:plateColor"`                 // JAVA L69 @Excel(车牌颜色索引)
	PlateColorCode     *string   `json:"plateColorCode" gorm:"column:plateColorCode"`         // JAVA L75 @Excel(车牌颜色代码)
	PlateType          *string   `json:"plateType" gorm:"column:plateType"`                   // JAVA L81 @Excel(车牌类型索引)
	PlateTypeCode      *string   `json:"plateTypeCode" gorm:"column:plateTypeCode"`           // JAVA L87 @Excel(车牌类型代码)
	VehicleColor       *string   `json:"vehicleColor" gorm:"column:vehicleColor"`             // JAVA L93 @Excel(车辆颜色代号)
	VehicleColorCode   *string   `json:"vehicleColorCode" gorm:"column:vehicleColorCode"`     // JAVA L99 @Excel(车辆颜色代码)
	VehicleType        *string   `json:"vehicleType" gorm:"column:vehicleType"`               // JAVA L105 @Excel(车辆类型代号)
	VehicleTypeCode    *string   `json:"vehicleTypeCode" gorm:"column:vehicleTypeCode"`       // JAVA L111 @Excel(车辆类型代码)
	VehicleSpeed       *int64    `json:"vehicleSpeed" gorm:"column:vehicleSpeed"`             // JAVA L117 @Excel(车辆速度)
	IsOverweight       *int64    `json:"isOverweight" gorm:"column:isOverweight"`             // JAVA L123 @Excel(是否超载)
	AxleNum            *int64    `json:"axleNum" gorm:"column:axleNum"`                       // JAVA L129 @Excel(轴数)
	OverWeight         *int64    `json:"overWeight" gorm:"column:overWeight"`                 // JAVA L135 @Excel(超重量)
	VehicleWeight      *int64    `json:"vehicleWeight" gorm:"column:vehicleWeight"`           // JAVA L141 @Excel(重量)
	LimitWeight        *int64    `json:"limitWeight" gorm:"column:limitWeight"`               // JAVA L147 @Excel(车辆限重)
	CheckTimeUnix      *int64    `json:"checkTimeUnix" gorm:"column:checkTimeUnix"`           // JAVA L153 @Excel(检测时间Unix格式)
	CheckTime          *Day      `json:"checkTime" gorm:"column:checkTime"`                   // JAVA L160 @JsonFormat(yyyy-MM-dd) → Day @Excel(检测时间)
	AxleModel          *int64    `json:"axleModel" gorm:"column:axleModel"`                   // JAVA L166 @Excel(轴型)
	LoadRate           *JavaLong `json:"loadRate" gorm:"column:loadRate"`                     // JAVA L172 private Long；列实际是 double precision，走 JavaLong 截断
	AxleArray          *string   `json:"axleArray" gorm:"column:axleArray"`                   // JAVA L178 @Excel(轴型详细数据)
	WeighingImagesArry *string   `json:"weighingImagesArry" gorm:"column:weighingImagesArry"` // JAVA L184 @Excel(图片数组)
	LoadTime           *Day      `json:"loadTime" gorm:"column:load_time"`                    // JAVA L191 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	GradeLevel         *int64    `json:"gradeLevel" gorm:"column:grade_level"`                // JAVA L197 @Excel(分类分级)
	Datauuid           *string   `json:"datauuid" gorm:"column:datauuid;primaryKey"`          // JAVA L204 @Excel(datauuid)
	Reserve1           *string   `json:"reserve1" gorm:"column:reserve1"`                     // JAVA L206
	Reserve2           *string   `json:"reserve2" gorm:"column:reserve2"`                     // JAVA L208
	Reserve3           *string   `json:"reserve3" gorm:"column:reserve3"`                     // JAVA L210
	QueryUuids         *string   `json:"queryUuids" gorm:"-"`                                 // JAVA L213
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnProvinceBorderVehicleWeightNewstructure) TableName() string {
	return "ods_szdn_province_border_vehicle_weight_newstructure"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnProvinceBorderVehicleWeightNewstructure) Schema() string {
	return ""
}
