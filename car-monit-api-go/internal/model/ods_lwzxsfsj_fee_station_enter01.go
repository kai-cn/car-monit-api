package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeStationEnter01.java
// 类/职责: OdsLwzxsfsjFeeStationEnter01 — 表 ods_lwzxsfsj_fee_station_enter_01 的实体
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_station_enter01.go
// 关键映射: @TableName(value='ods_lwzxsfsj_fee_station_enter_01', schema=None) → TableName()/Schema()；@TableId(bigId) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsLwzxsfsjFeeStationEnter01 对应 Java 类 OdsLwzxsfsjFeeStationEnter01
type OdsLwzxsfsjFeeStationEnter01 struct {
	BigId                *int64   `json:"bigId" gorm:"column:big_id;primaryKey"`                   // JAVA L32
	Cardid               *string  `json:"cardid" gorm:"column:cardid"`                             // JAVA L38 @Excel(CPC卡或ETC卡的编号)
	Electricalpercentage *int64   `json:"electricalpercentage" gorm:"column:electricalpercentage"` // JAVA L44 @Excel(单片式OBU/CPC卡电量百分比)
	Enaxlecount          *int64   `json:"enaxlecount" gorm:"column:enaxlecount"`                   // JAVA L50 @Excel(入站车轴数)
	Entime               *Day     `json:"entime" gorm:"column:entime"`                             // JAVA L57 @JsonFormat(yyyy-MM-dd) → Day @Excel(入站时间)
	Entolllanehex        *string  `json:"entolllanehex" gorm:"column:entolllanehex"`               // JAVA L63 @Excel(入口车道hex)
	Entolllaneid         *string  `json:"entolllaneid" gorm:"column:entolllaneid"`                 // JAVA L69 @Excel(入口车道id)
	Entollstationid      *string  `json:"entollstationid" gorm:"column:entollstationid"`           // JAVA L75 @Excel(入口收费站编码)
	Enweight             *float64 `json:"enweight" gorm:"column:enweight"`                         // JAVA L81 @Excel(入口称重)
	Identifyvehicleid    *string  `json:"identifyvehicleid" gorm:"column:identifyvehicleid"`       // JAVA L87 @Excel(车牌号+车牌类型)
	Lanetype             *string  `json:"lanetype" gorm:"column:lanetype"`                         // JAVA L93 @Excel(车道类型)
	Mediatype            *string  `json:"mediatype" gorm:"column:mediatype"`                       // JAVA L99 @Excel(介质类型)
	Operid               *string  `json:"operid" gorm:"column:operid"`                             // JAVA L105 @Excel(操作id)
	Operationmedia       *string  `json:"operationmedia" gorm:"column:operationmedia"`             // JAVA L111 @Excel(作业媒介)
	Params               *string  `json:"params" gorm:"column:params"`                             // JAVA L117 @Excel(参数)
	Passid               *string  `json:"passid" gorm:"column:passid"`                             // JAVA L123 @Excel(通行id)
	Receivetime          *Day     `json:"receivetime" gorm:"column:receivetime"`                   // JAVA L130 @JsonFormat(yyyy-MM-dd) → Day @Excel(接收时间)
	Shift                *string  `json:"shift" gorm:"column:shift"`                               // JAVA L136 @Excel(工班号)
	Signstatus           *string  `json:"signstatus" gorm:"column:signstatus"`                     // JAVA L142 @Excel(标记状态)
	Specialtype          *string  `json:"specialtype" gorm:"column:specialtype"`                   // JAVA L148 @Excel(特殊类型)
	Tac                  *string  `json:"tac" gorm:"column:tac"`                                   // JAVA L154 @Excel(TAC码)
	Terminalno           *string  `json:"terminalno" gorm:"column:terminalno"`                     // JAVA L160 @Excel(终端机编号)
	Terminaltransno      *string  `json:"terminaltransno" gorm:"column:terminaltransno"`           // JAVA L166 @Excel(PSAM卡脱机交易序列号)
	Transfee             *float64 `json:"transfee" gorm:"column:transfee"`                         // JAVA L172 @Excel(交易金额)
	Transtype            *string  `json:"transtype" gorm:"column:transtype"`                       // JAVA L178 @Excel(交易类型)
	Vcount               *int64   `json:"vcount" gorm:"column:vcount"`                             // JAVA L184 @Excel(总数)
	Vehicleclass         *string  `json:"vehicleclass" gorm:"column:vehicleclass"`                 // JAVA L190 @Excel(车种)
	Vehicleid            *string  `json:"vehicleid" gorm:"column:vehicleid"`                       // JAVA L196 @Excel(车牌号+车牌类型)
	Vehiclesign          *string  `json:"vehiclesign" gorm:"column:vehiclesign"`                   // JAVA L202 @Excel(车辆识别标识)
	Vehiclesignid        *string  `json:"vehiclesignid" gorm:"column:vehiclesignid"`               // JAVA L208 @Excel(车牌识别流水号)
	Vehicletype          *string  `json:"vehicletype" gorm:"column:vehicletype"`                   // JAVA L214 @Excel(车辆类型)
	LoadTime             *Day     `json:"loadTime" gorm:"column:load_time"`                        // JAVA L221 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	GradeLevel           *string  `json:"gradeLevel" gorm:"column:grade_level"`                    // JAVA L227 @Excel(分类分级)
	Cid                  *string  `json:"cid" gorm:"column:cid"`                                   // JAVA L231 @Excel(cid)
	CidList              []string `json:"cidList" gorm:"-"`                                        // JAVA L234 List<...> → slice
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsLwzxsfsjFeeStationEnter01) TableName() string {
	return "ods_lwzxsfsj_fee_station_enter_01"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsLwzxsfsjFeeStationEnter01) Schema() string {
	return ""
}
