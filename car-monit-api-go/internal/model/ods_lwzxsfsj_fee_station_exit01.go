package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeStationExit01.java
// 类/职责: OdsLwzxsfsjFeeStationExit01 — 表 ods_lwzxsfsj_fee_station_exit_01 的实体
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_station_exit01.go
// 关键映射: @TableName(value='ods_lwzxsfsj_fee_station_exit_01', schema=None) → TableName()/Schema()；@TableId(big_id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsLwzxsfsjFeeStationExit01 对应 Java 类 OdsLwzxsfsjFeeStationExit01
type OdsLwzxsfsjFeeStationExit01 struct {
	BigId                  string    `json:"bigId" gorm:"column:big_id;primaryKey"`                       // JAVA L32
	Actualfeeclass         *string   `json:"actualfeeclass" gorm:"column:actualfeeclass"`                 // JAVA L36 @Excel(实际计费方式)
	Axlecount              *int      `json:"axlecount" gorm:"column:axlecount"`                           // JAVA L40 @Excel(车轴数)
	Discountfee            *int64    `json:"discountfee" gorm:"column:discountfee"`                       // JAVA L44 @Excel(优惠金额)
	Electricalpercentage   *int      `json:"electricalpercentage" gorm:"column:electricalpercentage"`     // JAVA L48 @Excel(单片式OBU/CPC卡电量百分比)
	Enaxlecount            *int      `json:"enaxlecount" gorm:"column:enaxlecount"`                       // JAVA L52 @Excel(入站车轴数)
	Entime                 *DateTime `json:"entime" gorm:"column:entime"`                                 // JAVA L57 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(进站时间)
	Entolllanehex          *string   `json:"entolllanehex" gorm:"column:entolllanehex"`                   // JAVA L61 @Excel(入口车道hex)
	Entolllaneid           *string   `json:"entolllaneid" gorm:"column:entolllaneid"`                     // JAVA L65 @Excel(进站收费站车道号)
	Entollstationid        *string   `json:"entollstationid" gorm:"column:entollstationid"`               // JAVA L69 @Excel(入口收费站编码)
	Entollstationname      *string   `json:"entollstationname" gorm:"column:entollstationname"`           // JAVA L73 @Excel(入口收费站名称)
	Envehicleclass         *int      `json:"envehicleclass" gorm:"column:envehicleclass"`                 // JAVA L77 @Excel(入口车种)
	Envehicleid            *string   `json:"envehicleid" gorm:"column:envehicleid"`                       // JAVA L81 @Excel(入口车牌号+车牌类型)
	Envehicletype          *int      `json:"envehicletype" gorm:"column:envehicletype"`                   // JAVA L85 @Excel(入口车型)
	Enweight               *int64    `json:"enweight" gorm:"column:enweight"`                             // JAVA L89 @Excel(入口称重)
	Entryoperatorid        *string   `json:"entryoperatorid" gorm:"column:entryoperatorid"`               // JAVA L93 @Excel(入口操作人员id)
	Extime                 *DateTime `json:"extime" gorm:"column:extime"`                                 // JAVA L98 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(出站时间)
	Extolllaneid           *string   `json:"extolllaneid" gorm:"column:extolllaneid"`                     // JAVA L102 @Excel(出口车道号编码)
	Extollstationid        *string   `json:"extollstationid" gorm:"column:extollstationid"`               // JAVA L106 @Excel(出口收费站编码)
	Extollstationname      *string   `json:"extollstationname" gorm:"column:extollstationname"`           // JAVA L110 @Excel(出口收费站名称)
	Exvehicleclass         *int      `json:"exvehicleclass" gorm:"column:exvehicleclass"`                 // JAVA L114 @Excel(出口车种)
	Exvehicleid            *string   `json:"exvehicleid" gorm:"column:exvehicleid"`                       // JAVA L118 @Excel(出口车牌号+车牌类型)
	Exvehicletype          *int      `json:"exvehicletype" gorm:"column:exvehicletype"`                   // JAVA L122 @Excel(出口车型)
	Fee                    *int64    `json:"fee" gorm:"column:fee"`                                       // JAVA L126 @Excel(费用)
	Exweight               *int64    `json:"exweight" gorm:"column:exweight"`                             // JAVA L130 @Excel(出口称重)
	Feeboardplay           *string   `json:"feeboardplay" gorm:"column:feeboardplay"`                     // JAVA L134 @Excel(费显显示信息)
	Feemileage             *int64    `json:"feemileage" gorm:"column:feemileage"`                         // JAVA L138 @Excel(收费里程)
	Identification         *string   `json:"identification" gorm:"column:identification"`                 // JAVA L142 @Excel(开票标识)
	Feerate                *float64  `json:"feerate" gorm:"column:feerate"`                               // JAVA L146 @Excel(交易金额占比)
	Identifyvehicleid      *string   `json:"identifyvehicleid" gorm:"column:identifyvehicleid"`           // JAVA L150 @Excel(车牌号+车牌类型)
	Lanetype               *string   `json:"lanetype" gorm:"column:lanetype"`                             // JAVA L154 @Excel(车道类型)
	Mediano                *string   `json:"mediano" gorm:"column:mediano"`                               // JAVA L158 @Excel(介质编码)
	Mediatype              *string   `json:"mediatype" gorm:"column:mediatype"`                           // JAVA L162 @Excel(通行介质类型)
	Nocardcount            *int      `json:"nocardcount" gorm:"column:nocardcount"`                       // JAVA L166 @Excel(标签无卡累计次数)
	Obuid                  *string   `json:"obuid" gorm:"column:obuid"`                                   // JAVA L170 @Excel(OBU序号编码)
	Obusign                *string   `json:"obusign" gorm:"column:obusign"`                               // JAVA L174 @Excel(OBU 单/双片标识)
	Obutotalamount         *int64    `json:"obutotalamount" gorm:"column:obutotalamount"`                 // JAVA L178 @Excel(0BU 总累计交易金额)
	Obutotaldiscountamount *int64    `json:"obutotaldiscountamount" gorm:"column:obutotaldiscountamount"` // JAVA L182 @Excel(OBU累计优惠后通行费金额)
	Params                 *string   `json:"params" gorm:"column:params"`                                 // JAVA L186 @Excel(参数)
	Operid                 *string   `json:"operid" gorm:"column:operid"`                                 // JAVA L190 @Excel(操作id)
	Passid                 *string   `json:"passid" gorm:"column:passid"`                                 // JAVA L194 @Excel(通行id)
	Paycardid              *string   `json:"paycardid" gorm:"column:paycardid"`                           // JAVA L198 @Excel(支付id)
	Payfee                 *int64    `json:"payfee" gorm:"column:payfee"`                                 // JAVA L202 @Excel(应收金额)
	Paytype                *string   `json:"paytype" gorm:"column:paytype"`                               // JAVA L206 @Excel(支付类型)
	Provfee                *int64    `json:"provfee" gorm:"column:provfee"`                               // JAVA L209
	Provtranscount         *int      `json:"provtranscount" gorm:"column:provtranscount"`                 // JAVA L213 @Excel(本省交易成功次数)
	Provincecount          *int      `json:"provincecount" gorm:"column:provincecount"`                   // JAVA L217 @Excel(通行省份个数)
	Shift                  *string   `json:"shift" gorm:"column:shift"`                                   // JAVA L221 @Excel(工班号)
	Receivetime            *DateTime `json:"receivetime" gorm:"column:receivetime"`                       // JAVA L226 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(接收时间)
	Shortfee               *int64    `json:"shortfee" gorm:"column:shortfee"`                             // JAVA L230 @Excel(最短收费金额)
	Shortfeemileage        *int64    `json:"shortfeemileage" gorm:"column:shortfeemileage"`               // JAVA L234 @Excel(最短路径里程数)
	Signstatus             *string   `json:"signstatus" gorm:"column:signstatus"`                         // JAVA L238 @Excel(标记状态)
	Spcrateversion         *string   `json:"spcrateversion" gorm:"column:spcrateversion"`                 // JAVA L242 @Excel(全网最小费额费率版本号)
	Tac                    *string   `json:"tac" gorm:"column:tac"`                                       // JAVA L246 @Excel(TAC码)
	Specialtype            *string   `json:"specialtype" gorm:"column:specialtype"`                       // JAVA L250 @Excel(特殊类型)
	Splitprovince          *string   `json:"splitprovince" gorm:"column:splitprovince"`                   // JAVA L254 @Excel(多条省内交易信息)
	Terminalno             *string   `json:"terminalno" gorm:"column:terminalno"`                         // JAVA L258 @Excel(终端机编号)
	Terminaltransno        *string   `json:"terminaltransno" gorm:"column:terminaltransno"`               // JAVA L262 @Excel(PSAM卡脱机交易序列号)
	Transfee               *int64    `json:"transfee" gorm:"column:transfee"`                             // JAVA L266 @Excel(卡面扣费金额)
	Transpaytype           *string   `json:"transpaytype" gorm:"column:transpaytype"`                     // JAVA L270 @Excel(交易支付类型)
	Transtype              *string   `json:"transtype" gorm:"column:transtype"`                           // JAVA L274 @Excel(交易类型标识)
	LoadTime               *DateTime `json:"loadTime" gorm:"column:load_time"`                            // JAVA L279 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(加载时间)
	Vehiclesign            *string   `json:"vehiclesign" gorm:"column:vehiclesign"`                       // JAVA L283 @Excel(车辆状态标识)
	GradeLevel             *string   `json:"gradeLevel" gorm:"column:grade_level"`                        // JAVA L287 @Excel(分类分级)
	Vehiclesignid          *string   `json:"vehiclesignid" gorm:"column:vehiclesignid"`                   // JAVA L291 @Excel(车牌识别流水号)
	Cid                    *string   `json:"cid" gorm:"column:cid"`                                       // JAVA L295 @Excel(cid)
	CidList                []string  `json:"cidList" gorm:"-"`                                            // JAVA L298 List<...> → slice
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsLwzxsfsjFeeStationExit01) TableName() string {
	return "ods_lwzxsfsj_fee_station_exit_01"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsLwzxsfsjFeeStationExit01) Schema() string {
	return ""
}
