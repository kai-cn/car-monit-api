package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeRecords01.java
// 类/职责: OdsLwzxsfsjFeeRecords01 — 表 ods_lwzxsfsj_fee_records_01 的实体
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_records01.go
// 关键映射: @TableName(value='ods_lwzxsfsj_fee_records_01', schema=None) → TableName()/Schema()；@TableId(big_id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsLwzxsfsjFeeRecords01 对应 Java 类 OdsLwzxsfsjFeeRecords01
type OdsLwzxsfsjFeeRecords01 struct {
	BigId                      string    `json:"bigId" gorm:"column:big_id;primaryKey"`                               // JAVA L32
	Algorithmidentifier        *string   `json:"algorithmidentifier" gorm:"column:algorithmidentifier"`               // JAVA L36 @Excel(算法标识)
	Antennaid                  *string   `json:"antennaid" gorm:"column:antennaid"`                                   // JAVA L40 @Excel(天线ID编号(天线头编号))
	Axlecount                  *int64    `json:"axlecount" gorm:"column:axlecount"`                                   // JAVA L44 @Excel(车轴数)
	Balanceafter               *float64  `json:"balanceafter" gorm:"column:balanceafter"`                             // JAVA L48 @Excel(交易后余额)
	Balancebefore              *float64  `json:"balancebefore" gorm:"column:balancebefore"`                           // JAVA L52 @Excel(交易前余额)
	Cardfeesumafter            *float64  `json:"cardfeesumafter" gorm:"column:cardfeesumafter"`                       // JAVA L56 @Excel(本次交易后卡片累计金额)
	Cardfeesumbefore           *float64  `json:"cardfeesumbefore" gorm:"column:cardfeesumbefore"`                     // JAVA L60 @Excel(本次交易前卡片累计金额)
	Computerorder              *string   `json:"computerorder" gorm:"column:computerorder"`                           // JAVA L64 @Excel(控制器序号)
	Consumetime                *int64    `json:"consumetime" gorm:"column:consumetime"`                               // JAVA L68 @Excel(交易耗时)
	Cpucardid                  *string   `json:"cpucardid" gorm:"column:cpucardid"`                                   // JAVA L72 @Excel(CPU卡编号)
	Cpucardtype                *string   `json:"cpucardtype" gorm:"column:cpucardtype"`                               // JAVA L76 @Excel(CPU卡类型)
	Cpuenddate                 *string   `json:"cpuenddate" gorm:"column:cpuenddate"`                                 // JAVA L80 @Excel(CPU截止日期)
	Cpuissueid                 *string   `json:"cpuissueid" gorm:"column:cpuissueid"`                                 // JAVA L84 @Excel(CPU卡片发行方标识)
	Cpunetid                   *string   `json:"cpunetid" gorm:"column:cpunetid"`                                     // JAVA L88 @Excel(CPU卡片网络编号)
	Cpustartdate               *string   `json:"cpustartdate" gorm:"column:cpustartdate"`                             // JAVA L92 @Excel(CPU起始日期)
	Cpuvehicleplate            *string   `json:"cpuvehicleplate" gorm:"column:cpuvehicleplate"`                       // JAVA L96 @Excel(CPU 内车牌号码)
	Cpuvehicletype             *string   `json:"cpuvehicletype" gorm:"column:cpuvehicletype"`                         // JAVA L100 @Excel(CPU内车型)
	Cpuversion                 *string   `json:"cpuversion" gorm:"column:cpuversion"`                                 // JAVA L104 @Excel(CPU用户卡版本号)
	Dealstatus                 *string   `json:"dealstatus" gorm:"column:dealstatus"`                                 // JAVA L108 @Excel(处理状态)
	Discountfee                *float64  `json:"discountfee" gorm:"column:discountfee"`                               // JAVA L112 @Excel(优惠金额)
	Discountfeegroup           *string   `json:"discountfeegroup" gorm:"column:discountfeegroup"`                     // JAVA L116 @Excel(优惠金额组合)
	Enlanetype                 *string   `json:"enlanetype" gorm:"column:enlanetype"`                                 // JAVA L120 @Excel(入口车道类型)
	Entime                     *DateTime `json:"entime" gorm:"column:entime"`                                         // JAVA L125 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(进站时间)
	Entolllaneid               *string   `json:"entolllaneid" gorm:"column:entolllaneid"`                             // JAVA L129 @Excel(进站收费站车道号)
	Entollstationhex           *string   `json:"entollstationhex" gorm:"column:entollstationhex"`                     // JAVA L133 @Excel(进站收费站hex编码)
	Fee                        *float64  `json:"fee" gorm:"column:fee"`                                               // JAVA L137 @Excel(费用)
	Feecalcresult              *string   `json:"feecalcresult" gorm:"column:feecalcresult"`                           // JAVA L141 @Excel(计费模块响应计费结果)
	Feecalcspecial             *string   `json:"feecalcspecial" gorm:"column:feecalcspecial"`                         // JAVA L145 @Excel(计费接口特情值)
	Feecalcspecials            *string   `json:"feecalcspecials" gorm:"column:feecalcspecials"`                       // JAVA L149 @Excel(计费特情值组合)
	Feegroup                   *string   `json:"feegroup" gorm:"column:feegroup"`                                     // JAVA L153 @Excel(交易金额组合)
	Feeinfo1                   *string   `json:"feeinfo1" gorm:"column:feeinfo1"`                                     // JAVA L157 @Excel(计费信息1)
	Feeinfo2                   *string   `json:"feeinfo2" gorm:"column:feeinfo2"`                                     // JAVA L161 @Excel(计费信息2)
	Feeinfo3                   *string   `json:"feeinfo3" gorm:"column:feeinfo3"`                                     // JAVA L165 @Excel(计费信息3)
	Feemileage                 *float64  `json:"feemileage" gorm:"column:feemileage"`                                 // JAVA L169 @Excel(收费里程)
	Feeprovbeginhex            *string   `json:"feeprovbeginhex" gorm:"column:feeprovbeginhex"`                       // JAVA L173 @Excel(本省计费起点)
	Feespare1                  *string   `json:"feespare1" gorm:"column:feespare1"`                                   // JAVA L177 @Excel(计费协议保留字段1)
	Feespare2                  *string   `json:"feespare2" gorm:"column:feespare2"`                                   // JAVA L181 @Excel(计费协议保留字段2)
	Feevehicletype             *string   `json:"feevehicletype" gorm:"column:feevehicletype"`                         // JAVA L185 @Excel(计费车型)
	Gantryhex                  *string   `json:"gantryhex" gorm:"column:gantryhex"`                                   // JAVA L189 @Excel(门架Hex值)
	Gantryhexopposite          *string   `json:"gantryhexopposite" gorm:"column:gantryhexopposite"`                   // JAVA L193 @Excel(对向门架Hex值)
	Gantryid                   *string   `json:"gantryid" gorm:"column:gantryid"`                                     // JAVA L197 @Excel(门架编码)
	Gantryordernum             *int64    `json:"gantryordernum" gorm:"column:gantryordernum"`                         // JAVA L201 @Excel(门架顺序号)
	Gantrytype                 *string   `json:"gantrytype" gorm:"column:gantrytype"`                                 // JAVA L205 @Excel(门架类型)
	Holidaystate               *string   `json:"holidaystate" gorm:"column:holidaystate"`                             // JAVA L209 @Excel(节假日状态)
	Hourbatchno                *string   `json:"hourbatchno" gorm:"column:hourbatchno"`                               // JAVA L213 @Excel(小时批次号)
	Keyversion                 *string   `json:"keyversion" gorm:"column:keyversion"`                                 // JAVA L217 @Excel(消费密钥版本号)
	Lastgantryhex              *string   `json:"lastgantryhex" gorm:"column:lastgantryhex"`                           // JAVA L221 @Excel(上一个门架的hex编号)
	Lastgantrytime             *DateTime `json:"lastgantrytime" gorm:"column:lastgantrytime"`                         // JAVA L226 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(通过上一个门架的时间)
	Matchstatus                *string   `json:"matchstatus" gorm:"column:matchstatus"`                               // JAVA L230 @Excel(匹配状态)
	Mediatype                  *string   `json:"mediatype" gorm:"column:mediatype"`                                   // JAVA L234 @Excel(通行介质类型)
	Nocardtimesafter           *int64    `json:"nocardtimesafter" gorm:"column:nocardtimesafter"`                     // JAVA L238 @Excel(本次交易后累计无卡次数)
	Nocardtimesbefore          *int64    `json:"nocardtimesbefore" gorm:"column:nocardtimesbefore"`                   // JAVA L242 @Excel(本次交易前累计无卡次数)
	Obuelectrical              *int64    `json:"obuelectrical" gorm:"column:obuelectrical"`                           // JAVA L246 @Excel(OBU/CPC卡电量百分比)
	Obuenddate                 *string   `json:"obuenddate" gorm:"column:obuenddate"`                                 // JAVA L250 @Excel(OBU/CPC截止日期)
	Obufeesumafter             *float64  `json:"obufeesumafter" gorm:"column:obufeesumafter"`                         // JAVA L254 @Excel(本次交易后标签累计实收金额)
	Obufeesumbefore            *float64  `json:"obufeesumbefore" gorm:"column:obufeesumbefore"`                       // JAVA L258 @Excel(本次交易前标签累计实收金额)
	Obuinfotyperead            *string   `json:"obuinfotyperead" gorm:"column:obuinfotyperead"`                       // JAVA L262 @Excel(读取标签入口信息类型)
	Obuinfotypewrite           *string   `json:"obuinfotypewrite" gorm:"column:obuinfotypewrite"`                     // JAVA L266 @Excel(本次写入标签入口信息类型)
	Obuissueid                 *string   `json:"obuissueid" gorm:"column:obuissueid"`                                 // JAVA L270 @Excel(OBU/CPC发行方标识)
	Obulastgantryhex           *string   `json:"obulastgantryhex" gorm:"column:obulastgantryhex"`                     // JAVA L274 @Excel(OBU中上一个门架HEX)
	Obulastgantrytime          *DateTime `json:"obulastgantrytime" gorm:"column:obulastgantrytime"`                   // JAVA L279 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(OBU中通过上一个门架时间)
	Obumac                     *string   `json:"obumac" gorm:"column:obumac"`                                         // JAVA L283 @Excel(OBU /CPC物理地址)
	Obumileageafter            *float64  `json:"obumileageafter" gorm:"column:obumileageafter"`                       // JAVA L287 @Excel(本次交易后标签累计里程)
	Obumileagebefore           *float64  `json:"obumileagebefore" gorm:"column:obumileagebefore"`                     // JAVA L291 @Excel(本次交易前标签累计里程)
	Obupassstate               *string   `json:"obupassstate" gorm:"column:obupassstate"`                             // JAVA L295 @Excel(标签入口状态)
	Obupayfeesumafter          *float64  `json:"obupayfeesumafter" gorm:"column:obupayfeesumafter"`                   // JAVA L299 @Excel(本次交易后标签累计应收金额)
	Obupayfeesumbefore         *float64  `json:"obupayfeesumbefore" gorm:"column:obupayfeesumbefore"`                 // JAVA L303 @Excel(本次交易前标签累计应收金额)
	Obuprovfeesumafter         *float64  `json:"obuprovfeesumafter" gorm:"column:obuprovfeesumafter"`                 // JAVA L307 @Excel(本次交易后标签累计金额)
	Obuprovfeesumbefore        *float64  `json:"obuprovfeesumbefore" gorm:"column:obuprovfeesumbefore"`               // JAVA L311 @Excel(本次交易前标签累计金额 )
	Obuprovpayfeesumafter      *float64  `json:"obuprovpayfeesumafter" gorm:"column:obuprovpayfeesumafter"`           // JAVA L315 @Excel(本次交易后标签累计应收金额)
	Obuprovpayfeesumbefore     *float64  `json:"obuprovpayfeesumbefore" gorm:"column:obuprovpayfeesumbefore"`         // JAVA L319 @Excel(本次交易前标签累计应收金额)
	Obuprovtradesuccnumafter   *int64    `json:"obuprovtradesuccnumafter" gorm:"column:obuprovtradesuccnumafter"`     // JAVA L323 @Excel(省内本次交易后标签累计写入成功数量)
	Obuprovtradesuccnumbefore  *int64    `json:"obuprovtradesuccnumbefore" gorm:"column:obuprovtradesuccnumbefore"`   // JAVA L327 @Excel(省内本次交易前标签累计写入成功数量)
	Obusign                    *string   `json:"obusign" gorm:"column:obusign"`                                       // JAVA L331 @Excel(OBU 单/双片标识)
	Obusn                      *string   `json:"obusn" gorm:"column:obusn"`                                           // JAVA L335 @Excel(OBU/CPC序号编码)
	Obustartdate               *string   `json:"obustartdate" gorm:"column:obustartdate"`                             // JAVA L339 @Excel(OBU/CPC起始日期)
	Obustate                   *string   `json:"obustate" gorm:"column:obustate"`                                     // JAVA L343 @Excel(OBU/CPC状态)
	Obutotaltradesuccnumafter  *int64    `json:"obutotaltradesuccnumafter" gorm:"column:obutotaltradesuccnumafter"`   // JAVA L347 @Excel(本次交易后标签累计写入成功总量)
	Obutotaltradesuccnumbefore *int64    `json:"obutotaltradesuccnumbefore" gorm:"column:obutotaltradesuccnumbefore"` // JAVA L351 @Excel(本次交易前标签累计写入成功总量)
	Obutraderesult             *string   `json:"obutraderesult" gorm:"column:obutraderesult"`                         // JAVA L355 @Excel(标签写入结果)
	Obuvehicleplate            *string   `json:"obuvehicleplate" gorm:"column:obuvehicleplate"`                       // JAVA L359 @Excel(obu车牌)
	Obuvehicletype             *string   `json:"obuvehicletype" gorm:"column:obuvehicletype"`                         // JAVA L363 @Excel(obu车牌类型)
	Obuversion                 *string   `json:"obuversion" gorm:"column:obuversion"`                                 // JAVA L367 @Excel(OBU/CPC版本号)
	Params                     *string   `json:"params" gorm:"column:params"`                                         // JAVA L371 @Excel(参数)
	Passid                     *string   `json:"passid" gorm:"column:passid"`                                         // JAVA L375 @Excel(通行id)
	Passstate                  *string   `json:"passstate" gorm:"column:passstate"`                                   // JAVA L379 @Excel(通行状态)
	Pathfitflag                *string   `json:"pathfitflag" gorm:"column:pathfitflag"`                               // JAVA L383 @Excel(本次计费拟合结果标识)
	Payfee                     *float64  `json:"payfee" gorm:"column:payfee"`                                         // JAVA L387 @Excel(应收金额)
	Payfeegroup                *string   `json:"payfeegroup" gorm:"column:payfeegroup"`                               // JAVA L391 @Excel(应收金额组合)
	Pcrsuversion               *string   `json:"pcrsuversion" gorm:"column:pcrsuversion"`                             // JAVA L395 @Excel(PC-RSU接口协议版本号)
	Provminfee                 *float64  `json:"provminfee" gorm:"column:provminfee"`                                 // JAVA L399 @Excel(本省累计通行金额参考)
	Provincenumafter           *int64    `json:"provincenumafter" gorm:"column:provincenumafter"`                     // JAVA L403 @Excel(本次交易后累计省份数量)
	Provincenumbefore          *int64    `json:"provincenumbefore" gorm:"column:provincenumbefore"`                   // JAVA L407 @Excel(本次交易前累计省份数量)
	Ratecompute                *string   `json:"ratecompute" gorm:"column:ratecompute"`                               // JAVA L411 @Excel(计费模块计费模式)
	Ratefitcount               *int64    `json:"ratefitcount" gorm:"column:ratefitcount"`                             // JAVA L415 @Excel(计费模块拟合点总数)
	Rateversion                *string   `json:"rateversion" gorm:"column:rateversion"`                               // JAVA L419 @Excel(计费模块和计费参数版本号)
	Readciphertextverify       *string   `json:"readciphertextverify" gorm:"column:readciphertextverify"`             // JAVA L423 @Excel(本次交易读取的EF04加密摘要验证结果)
	Receivetime                *DateTime `json:"receivetime" gorm:"column:receivetime"`                               // JAVA L428 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(接收时间)
	Servicetype                *string   `json:"servicetype" gorm:"column:servicetype"`                               // JAVA L432 @Excel(交易的服务类型)
	Stationdbtime              *DateTime `json:"stationdbtime" gorm:"column:stationdbtime"`                           // JAVA L437 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(门架后台入库时间)
	Stationdealtime            *DateTime `json:"stationdealtime" gorm:"column:stationdealtime"`                       // JAVA L442 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(门架后台处理时间)
	Stationmatchtime           *DateTime `json:"stationmatchtime" gorm:"column:stationmatchtime"`                     // JAVA L447 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(门架后台匹配时间)
	Stationvalidtime           *DateTime `json:"stationvalidtime" gorm:"column:stationvalidtime"`                     // JAVA L452 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(门架后台去重时间)
	Tac                        *string   `json:"tac" gorm:"column:tac"`                                               // JAVA L456 @Excel(TAC码)
	Terminalno                 *string   `json:"terminalno" gorm:"column:terminalno"`                                 // JAVA L460 @Excel(终端机编号)
	Terminaltransno            *string   `json:"terminaltransno" gorm:"column:terminaltransno"`                       // JAVA L464 @Excel(PSAM卡脱机交易序列号)
	Tollintervalid             *string   `json:"tollintervalid" gorm:"column:tollintervalid"`                         // JAVA L468 @Excel(收费单元编号组合)
	Tollintervalsign           *string   `json:"tollintervalsign" gorm:"column:tollintervalsign"`                     // JAVA L472 @Excel(收费单元处理标识)
	Totalweight                *float64  `json:"totalweight" gorm:"column:totalweight"`                               // JAVA L476 @Excel(车货总重)
	Tradeid                    *string   `json:"tradeid" gorm:"column:tradeid"`                                       // JAVA L480 @Excel(计费交易编号)
	Tradereadciphertext        *string   `json:"tradereadciphertext" gorm:"column:tradereadciphertext"`               // JAVA L484 @Excel(本次交易读取的EF04加密摘要)
	Traderesult                *string   `json:"traderesult" gorm:"column:traderesult"`                               // JAVA L488 @Excel(卡片复合交易结果)
	Tradetype                  *string   `json:"tradetype" gorm:"column:tradetype"`                                   // JAVA L492 @Excel(交易类型)
	Tradewriteciphertext       *string   `json:"tradewriteciphertext" gorm:"column:tradewriteciphertext"`             // JAVA L496 @Excel(本次交易生成的EF04加密摘要)
	Transfee                   *float64  `json:"transfee" gorm:"column:transfee"`                                     // JAVA L500 @Excel(卡面扣费金额)
	Transno                    *string   `json:"transno" gorm:"column:transno"`                                       // JAVA L504 @Excel(IC卡交易序号)
	Transtime                  *DateTime `json:"transtime" gorm:"column:transtime"`                                   // JAVA L509 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(计费交易时间)
	Transtype                  *string   `json:"transtype" gorm:"column:transtype"`                                   // JAVA L513 @Excel(交易类型标识)
	Validstatus                *string   `json:"validstatus" gorm:"column:validstatus"`                               // JAVA L517 @Excel(去重状态)
	Vehicleclass               *string   `json:"vehicleclass" gorm:"column:vehicleclass"`                             // JAVA L521 @Excel(车种)
	Vehiclehight               *float64  `json:"vehiclehight" gorm:"column:vehiclehight"`                             // JAVA L525 @Excel(车高)
	Vehiclelength              *float64  `json:"vehiclelength" gorm:"column:vehiclelength"`                           // JAVA L529 @Excel(车长)
	Vehicleplate               *string   `json:"vehicleplate" gorm:"column:vehicleplate"`                             // JAVA L533 @Excel(车牌号+类型)
	Vehicleseat                *string   `json:"vehicleseat" gorm:"column:vehicleseat"`                               // JAVA L537 @Excel(车辆座位数/载重)
	Vehiclesign                *string   `json:"vehiclesign" gorm:"column:vehiclesign"`                               // JAVA L541 @Excel(车辆状态标识)
	Vehicletype                *string   `json:"vehicletype" gorm:"column:vehicletype"`                               // JAVA L545 @Excel(车辆类型)
	Vehicleusertype            *string   `json:"vehicleusertype" gorm:"column:vehicleusertype"`                       // JAVA L549 @Excel(车辆用户类型)
	Vehiclewidth               *float64  `json:"vehiclewidth" gorm:"column:vehiclewidth"`                             // JAVA L553 @Excel(车宽)
	Verifycode                 *string   `json:"verifycode" gorm:"column:verifycode"`                                 // JAVA L557 @Excel(校验码)
	LoadTime                   *DateTime `json:"loadTime" gorm:"column:load_time"`                                    // JAVA L562 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(加载时间)
	GradeLevel                 *int64    `json:"gradeLevel" gorm:"column:grade_level"`                                // JAVA L566 @Excel(分类分级)
	Cid                        *string   `json:"cid" gorm:"column:cid"`                                               // JAVA L570 @Excel(cid)
	CidList                    []string  `json:"cidList" gorm:"-"`                                                    // JAVA L573 List<...> → slice
	InApplyTime1               *string   `json:"inApplyTime1" gorm:"-"`                                               // JAVA L578
	InApplyTime2               *string   `json:"inApplyTime2" gorm:"-"`                                               // JAVA L581
	OutApplyTime1              *string   `json:"outApplyTime1" gorm:"-"`                                              // JAVA L584
	OutApplyTime2              *string   `json:"outApplyTime2" gorm:"-"`                                              // JAVA L587
	PlateColor                 *string   `json:"plateColor" gorm:"-"`                                                 // JAVA L591
	GantryName                 *string   `json:"gantryName" gorm:"-"`                                                 // JAVA L596
	Flag                       *string   `json:"flag" gorm:"-"`                                                       // JAVA L599
	SectionCodeStr             *string   `json:"sectionCodeStr" gorm:"-"`                                             // JAVA L603
	Type                       *string   `json:"type" gorm:"-"`                                                       // JAVA L609
	Code                       *string   `json:"code" gorm:"-"`                                                       // JAVA L615
	CodeList                   []string  `json:"codeList" gorm:"-"`                                                   // JAVA L621 List<...> → slice
	SectionList                []string  `json:"sectionList" gorm:"-"`                                                // JAVA L627 List<...> → slice
	TranstimeStr               *string   `json:"transtimeStr" gorm:"-"`                                               // JAVA L633
	LastgantrytimeStr          *string   `json:"lastgantrytimeStr" gorm:"-"`                                          // JAVA L639
	StartNum                   *int      `json:"startNum" gorm:"-"`                                                   // JAVA L644
	EndNum                     *int      `json:"endNum" gorm:"-"`                                                     // JAVA L648
	Sectioncode                *string   `json:"sectioncode" gorm:"-"`                                                // JAVA L654
	OrderByFlag                *string   `json:"orderByFlag" gorm:"-"`                                                // JAVA L661
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsLwzxsfsjFeeRecords01) TableName() string {
	return "ods_lwzxsfsj_fee_records_01"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsLwzxsfsjFeeRecords01) Schema() string {
	return ""
}
