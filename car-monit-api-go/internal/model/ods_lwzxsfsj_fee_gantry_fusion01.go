package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeGantryFusion01.java
// 类/职责: OdsLwzxsfsjFeeGantryFusion01 — 表 ods_lwzxsfsj_fee_gantry_fusion_01 的实体
// 对应 Go 文件: internal/model/ods_lwzxsfsj_fee_gantry_fusion01.go
// 关键映射: @TableName(value='ods_lwzxsfsj_fee_gantry_fusion_01', schema=None) → TableName()/Schema()；@TableId(None) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsLwzxsfsjFeeGantryFusion01 对应 Java 类 OdsLwzxsfsjFeeGantryFusion01
type OdsLwzxsfsjFeeGantryFusion01 struct {
	BigId                  string     `json:"bigId" gorm:"column:big_id"`                                  // JAVA L27
	Actualfeeclass         *string    `json:"actualfeeclass" gorm:"column:actualfeeclass"`                 // JAVA L31 @Excel(实际计费方式)
	Axlecount              *int64     `json:"axlecount" gorm:"column:axlecount"`                           // JAVA L35 @Excel(车轴数)
	Createtime             *Timestamp `json:"createtime" gorm:"column:createtime"`                         // JAVA L38 @Excel(创建时间)
	Discountfee            *int64     `json:"discountfee" gorm:"column:discountfee"`                       // JAVA L42 @Excel(优惠金额)
	Electricalpercentage   *int64     `json:"electricalpercentage" gorm:"column:electricalpercentage"`     // JAVA L46 @Excel(单片式OBU/CPC卡电量百分比)
	Enaxlecount            *int64     `json:"enaxlecount" gorm:"column:enaxlecount"`                       // JAVA L50 @Excel(入口车轴数)
	Entime                 *DateTime  `json:"entime" gorm:"column:entime"`                                 // JAVA L55 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(入站时间)
	Entolllanehex          *string    `json:"entolllanehex" gorm:"column:entolllanehex"`                   // JAVA L59 @Excel(入口车道hex)
	Entolllaneid           *string    `json:"entolllaneid" gorm:"column:entolllaneid"`                     // JAVA L63 @Excel(入口车道ID)
	Entollstationid        *string    `json:"entollstationid" gorm:"column:entollstationid"`               // JAVA L67 @Excel(入口收费站编码)
	Entollstationname      *string    `json:"entollstationname" gorm:"column:entollstationname"`           // JAVA L71 @Excel(入口收费站名称)
	Envehicleclass         *int64     `json:"envehicleclass" gorm:"column:envehicleclass"`                 // JAVA L75 @Excel(入口车种)
	Envehicleid            *string    `json:"envehicleid" gorm:"column:envehicleid"`                       // JAVA L79 @Excel(入口车牌号+车牌类型)
	Envehicleidcolor       *string    `json:"envehicleidcolor" gorm:"column:envehicleidcolor"`             // JAVA L83 @Excel(入口车牌号+颜色)
	Envehicletype          *int64     `json:"envehicletype" gorm:"column:envehicletype"`                   // JAVA L87 @Excel(入口车型)
	Enweight               *int64     `json:"enweight" gorm:"column:enweight"`                             // JAVA L91 @Excel(入口称重)
	Entryoperatorid        *string    `json:"entryoperatorid" gorm:"column:entryoperatorid"`               // JAVA L95 @Excel(入口操作人员id)
	Extime                 *DateTime  `json:"extime" gorm:"column:extime"`                                 // JAVA L100 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(出站时间)
	Extolllaneid           *string    `json:"extolllaneid" gorm:"column:extolllaneid"`                     // JAVA L104 @Excel(出口车道号编码)
	Extollstationid        *string    `json:"extollstationid" gorm:"column:extollstationid"`               // JAVA L108 @Excel(出口收费站编码)
	Extollstationname      *string    `json:"extollstationname" gorm:"column:extollstationname"`           // JAVA L112 @Excel(出口收费站名称)
	Exvehicleclass         *int64     `json:"exvehicleclass" gorm:"column:exvehicleclass"`                 // JAVA L116 @Excel(出口车种)
	Exvehicleid            *string    `json:"exvehicleid" gorm:"column:exvehicleid"`                       // JAVA L120 @Excel(出口车牌号+车牌类型)
	Exvehicletype          *int64     `json:"exvehicletype" gorm:"column:exvehicletype"`                   // JAVA L124 @Excel(出口车型)
	Exweight               *int64     `json:"exweight" gorm:"column:exweight"`                             // JAVA L128 @Excel(出口称重)
	Exitid                 *string    `json:"exitid" gorm:"column:exitid"`                                 // JAVA L132 @Excel(出口id)
	Fee                    *int64     `json:"fee" gorm:"column:fee"`                                       // JAVA L136 @Excel(费用)
	Feeboardplay           *string    `json:"feeboardplay" gorm:"column:feeboardplay"`                     // JAVA L140 @Excel(费显显示信息)
	Feemileage             *int64     `json:"feemileage" gorm:"column:feemileage"`                         // JAVA L144 @Excel(收费里程)
	Feerate                *string    `json:"feerate" gorm:"column:feerate"`                               // JAVA L148 @Excel(交易金额占比)
	Fusiondesc             *string    `json:"fusiondesc" gorm:"column:fusiondesc"`                         // JAVA L152 @Excel(融合描述)
	Fusionflag             *string    `json:"fusionflag" gorm:"column:fusionflag"`                         // JAVA L156 @Excel(融合标识,)
	Id                     *string    `json:"id" gorm:"column:id"`                                         // JAVA L159 @Excel(id)
	Identification         *string    `json:"identification" gorm:"column:identification"`                 // JAVA L163 @Excel(开票标识)
	Identifyvehicleid      *string    `json:"identifyvehicleid" gorm:"column:identifyvehicleid"`           // JAVA L167 @Excel(出口识别车牌号+车牌类型)
	Identifyvehicleidcolor *string    `json:"identifyvehicleidcolor" gorm:"column:identifyvehicleidcolor"` // JAVA L171 @Excel(出口识别车牌号+颜色)
	Lanetype               *string    `json:"lanetype" gorm:"column:lanetype"`                             // JAVA L175 @Excel(出口车道类型)
	Mediano                *string    `json:"mediano" gorm:"column:mediano"`                               // JAVA L179 @Excel(介质编码)
	Mediatype              *string    `json:"mediatype" gorm:"column:mediatype"`                           // JAVA L183 @Excel(通行介质)
	Nocardcount            *int64     `json:"nocardcount" gorm:"column:nocardcount"`                       // JAVA L187 @Excel(标签无卡累计次数)
	Obuid                  *string    `json:"obuid" gorm:"column:obuid"`                                   // JAVA L191 @Excel(OBU序号编码)
	Obusign                *string    `json:"obusign" gorm:"column:obusign"`                               // JAVA L195 @Excel(OBU 单/双片标识)
	Obutotalamount         *int64     `json:"obutotalamount" gorm:"column:obutotalamount"`                 // JAVA L199 @Excel(0BU 总累计交易金额)
	Obutotaldiscountamount *int64     `json:"obutotaldiscountamount" gorm:"column:obutotaldiscountamount"` // JAVA L203 @Excel(OBU累计优惠后通行费金额)
	Operid                 *string    `json:"operid" gorm:"column:operid"`                                 // JAVA L207 @Excel(操作id)
	Params                 *string    `json:"params" gorm:"column:params"`                                 // JAVA L211 @Excel(参数)
	Passid                 *string    `json:"passid" gorm:"column:passid"`                                 // JAVA L215 @Excel(通行id)
	Paycardid              *string    `json:"paycardid" gorm:"column:paycardid"`                           // JAVA L219 @Excel(支付id)
	Payfee                 *int64     `json:"payfee" gorm:"column:payfee"`                                 // JAVA L223 @Excel(应收总额)
	Paytype                *string    `json:"paytype" gorm:"column:paytype"`                               // JAVA L227 @Excel(支付类型)
	Provfee                *int64     `json:"provfee" gorm:"column:provfee"`                               // JAVA L231 @Excel(${comment})
	Provtranscount         *int64     `json:"provtranscount" gorm:"column:provtranscount"`                 // JAVA L235 @Excel(本省交易成功次数)
	Provincecount          *int64     `json:"provincecount" gorm:"column:provincecount"`                   // JAVA L239 @Excel(通行省份个数)
	Receivetime            *Day       `json:"receivetime" gorm:"column:receivetime"`                       // JAVA L244 @JsonFormat(yyyy-MM-dd) → Day @Excel(接收时间)
	Shift                  *string    `json:"shift" gorm:"column:shift"`                                   // JAVA L248 @Excel(工班号)
	Shortfee               *int64     `json:"shortfee" gorm:"column:shortfee"`                             // JAVA L252 @Excel(最短收费金额)
	Shortfeemileage        *int64     `json:"shortfeemileage" gorm:"column:shortfeemileage"`               // JAVA L256 @Excel(最短路径里程数)
	Signstatus             *string    `json:"signstatus" gorm:"column:signstatus"`                         // JAVA L260 @Excel(标记状态)
	Spcrateversion         *string    `json:"spcrateversion" gorm:"column:spcrateversion"`                 // JAVA L264 @Excel(全网最小费额费率版本号)
	Specialtype            *string    `json:"specialtype" gorm:"column:specialtype"`                       // JAVA L268 @Excel(特殊类型)
	Splitprovince          *string    `json:"splitprovince" gorm:"column:splitprovince"`                   // JAVA L272 @Excel(多条省内交易信息)
	Tac                    *string    `json:"tac" gorm:"column:tac"`                                       // JAVA L276 @Excel(TAC码)
	Terminalno             *string    `json:"terminalno" gorm:"column:terminalno"`                         // JAVA L280 @Excel(终端机编号)
	Terminaltransno        *string    `json:"terminaltransno" gorm:"column:terminaltransno"`               // JAVA L284 @Excel(PSAM卡脱机交易序列号)
	Transfee               *int64     `json:"transfee" gorm:"column:transfee"`                             // JAVA L288 @Excel(卡面扣费金额)
	Transpaytype           *string    `json:"transpaytype" gorm:"column:transpaytype"`                     // JAVA L292 @Excel(交易支付类型)
	Transtype              *string    `json:"transtype" gorm:"column:transtype"`                           // JAVA L296 @Excel(交易类型)
	Vehiclesign            *string    `json:"vehiclesign" gorm:"column:vehiclesign"`                       // JAVA L300 @Excel(车辆识别标识)
	Vehiclesignid          *string    `json:"vehiclesignid" gorm:"column:vehiclesignid"`                   // JAVA L304 @Excel(车牌识别流水号)
	Vid                    *string    `json:"vid" gorm:"column:vid"`                                       // JAVA L308 @Excel(车牌号ID)
	LoadTime               *Day       `json:"loadTime" gorm:"column:load_time"`                            // JAVA L313 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	GradeLevel             *int64     `json:"gradeLevel" gorm:"column:grade_level"`                        // JAVA L317 @Excel(分类分级)
	InApplyTime1           *string    `json:"inApplyTime1" gorm:"-"`                                       // JAVA L321
	InApplyTime2           *string    `json:"inApplyTime2" gorm:"-"`                                       // JAVA L324
	OutApplyTime1          *string    `json:"outApplyTime1" gorm:"-"`                                      // JAVA L327
	OutApplyTime2          *string    `json:"outApplyTime2" gorm:"-"`                                      // JAVA L330
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsLwzxsfsjFeeGantryFusion01) TableName() string {
	return "ods_lwzxsfsj_fee_gantry_fusion_01"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsLwzxsfsjFeeGantryFusion01) Schema() string {
	return ""
}
