package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowAddcode.java
// 类/职责: OdsRtSzdnSnapshotFlowAddcode — 表 ods_rt_szdn_snapshot_flow_addcode 的实体
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_addcode.go
// 关键映射: @TableName(value='ods_rt_szdn_snapshot_flow_addcode', schema='jl_data01') → TableName()/Schema()；@TableId(big_id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsRtSzdnSnapshotFlowAddcode 对应 Java 类 OdsRtSzdnSnapshotFlowAddcode
type OdsRtSzdnSnapshotFlowAddcode struct {
	BigId            *string    `json:"bigId" gorm:"column:big_id;primaryKey"`           // JAVA L32 @TableId(big_id)；注意 selectVo 不查这一列，列表里它是 null
	Datasource       *string    `json:"datasource" gorm:"column:datasource"`             // JAVA L36 @Excel(数据类型)
	Cameratype       *string    `json:"cameratype" gorm:"column:cameratype"`             // JAVA L40 @Excel(设备类型)
	Deviceid         *string    `json:"deviceid" gorm:"column:deviceid"`                 // JAVA L44 @Excel(设备编号)
	Gantrycode       *string    `json:"gantrycode" gorm:"column:gantrycode"`             // JAVA L48 @Excel(门架编号)
	Gantryname       *string    `json:"gantryname" gorm:"column:gantryname"`             // JAVA L52 @Excel(门架名称)
	Roadcode         *string    `json:"roadcode" gorm:"column:roadcode"`                 // JAVA L56 @Excel(所属路线编码)
	Roadname         *string    `json:"roadname" gorm:"column:roadname"`                 // JAVA L60 @Excel(所属路线名称)
	Sectioncode      *string    `json:"sectioncode" gorm:"column:sectioncode"`           // JAVA L64 @Excel(所属路段编码)
	Sectionname      *string    `json:"sectionname" gorm:"column:sectionname"`           // JAVA L68 @Excel(所属路段名称)
	Tollcode         *string    `json:"tollcode" gorm:"column:tollcode"`                 // JAVA L72 @Excel(所属收费站编码)
	Tollname         *string    `json:"tollname" gorm:"column:tollname"`                 // JAVA L76 @Excel(所属收费站名称)
	Orgcode          *string    `json:"orgcode" gorm:"column:orgcode"`                   // JAVA L80 @Excel(所属管理中心机构编码)
	Orgname          *string    `json:"orgname" gorm:"column:orgname"`                   // JAVA L84 @Excel(所属管理中心机构名称)
	Direction        *int       `json:"direction" gorm:"column:direction"`               // JAVA L88 @Excel(方向)
	Hexcode          *string    `json:"hexcode" gorm:"column:hexcode"`                   // JAVA L92 @Excel(门架二进制编号)
	Pileno           *string    `json:"pileno" gorm:"column:pileno"`                     // JAVA L96 @Excel(桩号)
	Lon              *float64   `json:"lon" gorm:"column:lon"`                           // JAVA L100 @Excel(经度)
	Lat              *float64   `json:"lat" gorm:"column:lat"`                           // JAVA L104 @Excel(纬度)
	Deviceip         *string    `json:"deviceip" gorm:"column:deviceip"`                 // JAVA L108 @Excel(设备IP)
	Siteid           *int64     `json:"siteid" gorm:"column:siteid"`                     // JAVA L112 @Excel(站点ID)
	Laneid           *int       `json:"laneid" gorm:"column:laneid"`                     // JAVA L116 @Excel(车道编号)
	Snapshottimeunix *int64     `json:"snapshottimeunix" gorm:"column:snapshottimeunix"` // JAVA L120 @Excel(抓拍时间Unix格式)
	Snapshottime     *Timestamp `json:"snapshottime" gorm:"column:snapshottime"`         // JAVA L123
	Receivedtimeunix *int64     `json:"receivedtimeunix" gorm:"column:receivedtimeunix"` // JAVA L127 @Excel(接收时间Unix格式)
	Receivedtime     *Day       `json:"receivedtime" gorm:"column:receivedtime"`         // JAVA L132 @JsonFormat(yyyy-MM-dd) → Day @Excel(接收时间)
	Platenumber      *string    `json:"platenumber" gorm:"column:platenumber"`           // JAVA L136 @Excel(车牌号)
	Platecolor       *string    `json:"platecolor" gorm:"column:platecolor"`             // JAVA L140 @Excel(车牌颜色)
	Platecolorcode   *int       `json:"platecolorcode" gorm:"column:platecolorcode"`     // JAVA L144 @Excel(车牌颜色编码)
	Platetype        *string    `json:"platetype" gorm:"column:platetype"`               // JAVA L148 @Excel(车牌类型)
	Platetypecode    *int       `json:"platetypecode" gorm:"column:platetypecode"`       // JAVA L152 @Excel(车牌类型编码)
	Plateconfidence  *int       `json:"plateconfidence" gorm:"column:plateconfidence"`   // JAVA L156 @Excel(车牌置信度)
	Carbrand         *string    `json:"carbrand" gorm:"column:carbrand"`                 // JAVA L160 @Excel(车辆品牌)
	Carcolor         *string    `json:"carcolor" gorm:"column:carcolor"`                 // JAVA L164 @Excel(车辆颜色)
	Carcolorcode     *int       `json:"carcolorcode" gorm:"column:carcolorcode"`         // JAVA L168 @Excel(车辆颜色编码)
	Cartype          *string    `json:"cartype" gorm:"column:cartype"`                   // JAVA L172 @Excel(车辆类型)
	Cartypecode      *int       `json:"cartypecode" gorm:"column:cartypecode"`           // JAVA L176 @Excel(车辆类型编码)
	Cardirection     *string    `json:"cardirection" gorm:"column:cardirection"`         // JAVA L180 @Excel(行驶方向)
	Snappicturepath  *string    `json:"snappicturepath" gorm:"column:snappicturepath"`   // JAVA L184 @Excel(图片路径)
	Loadtime         *Day       `json:"loadtime" gorm:"column:loadtime"`                 // JAVA L189 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	Gradelevel       *int       `json:"gradelevel" gorm:"column:gradelevel"`             // JAVA L193 @Excel(分类分级)
	Datauuid         *string    `json:"datauuid" gorm:"column:datauuid"`                 // JAVA L197 @Excel(uuid)
	Reserve3         *string    `json:"reserve3" gorm:"column:reserve3"`                 // JAVA L201 @Excel(备用字段)
	Id               *string    `json:"id" gorm:"-"`                                     // JAVA L205
	SnapshottimeStr  *string    `json:"snapshottimeStr" gorm:"-"`                        // JAVA L209
	ApplyTime1       *string    `json:"applyTime1" gorm:"-"`                             // JAVA L213
	ApplyTime2       *string    `json:"applyTime2" gorm:"-"`                             // JAVA L216
	QueryUuids       *string    `json:"queryUuids" gorm:"-"`                             // JAVA L219
	Flag             *string    `json:"flag" gorm:"-"`                                   // JAVA L222
	SectionCodeStr   *string    `json:"sectionCodeStr" gorm:"-"`                         // JAVA L227
	Type             *string    `json:"type" gorm:"-"`                                   // JAVA L233
	Code             *string    `json:"code" gorm:"-"`                                   // JAVA L239
	CodeList         []string   `json:"codeList" gorm:"-"`                               // JAVA L245 List<...> → slice
	SectionList      []string   `json:"sectionList" gorm:"-"`                            // JAVA L252 List<...> → slice
	StartNum         *int       `json:"startNum" gorm:"-"`                               // JAVA L257
	EndNum           *int       `json:"endNum" gorm:"-"`                                 // JAVA L261
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsRtSzdnSnapshotFlowAddcode) TableName() string {
	return "jl_data01.ods_rt_szdn_snapshot_flow_addcode"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsRtSzdnSnapshotFlowAddcode) Schema() string {
	return "jl_data01"
}
