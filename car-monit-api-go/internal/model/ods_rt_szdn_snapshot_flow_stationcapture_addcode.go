package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowStationcaptureAddcode.java
// 类/职责: OdsRtSzdnSnapshotFlowStationcaptureAddcode — 表 ods_rt_szdn_snapshot_flow_stationcapture_addcode 的实体
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_stationcapture_addcode.go
// 关键映射: @TableName(value='ods_rt_szdn_snapshot_flow_stationcapture_addcode', schema=None) → TableName()/Schema()；@TableId(bigId) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsRtSzdnSnapshotFlowStationcaptureAddcode 对应 Java 类 OdsRtSzdnSnapshotFlowStationcaptureAddcode
type OdsRtSzdnSnapshotFlowStationcaptureAddcode struct {
	BigId             *int64  `json:"bigId" gorm:"column:big_id;primaryKey"`             // JAVA L30
	Datasource        *string `json:"datasource" gorm:"column:datasource"`               // JAVA L36 @Excel(数据类型)
	Cameratype        *string `json:"cameratype" gorm:"column:cameratype"`               // JAVA L42 @Excel(设备类型)
	Deviceid          *string `json:"deviceid" gorm:"column:deviceid"`                   // JAVA L48 @Excel(设备编号)
	Deviceip          *string `json:"deviceip" gorm:"column:deviceip"`                   // JAVA L54 @Excel(设备IP)
	Tollcode          *string `json:"tollcode" gorm:"column:tollcode"`                   // JAVA L60 @Excel(收费站编码)
	Tollname          *string `json:"tollname" gorm:"column:tollname"`                   // JAVA L66 @Excel(收费站名称)
	Orgcode           *int64  `json:"orgcode" gorm:"column:orgcode"`                     // JAVA L72 @Excel(组织机构编码)
	Siteid            *int64  `json:"siteid" gorm:"column:siteid"`                       // JAVA L78 @Excel(站点ID)
	Laneid            *int    `json:"laneid" gorm:"column:laneid"`                       // JAVA L84 @Excel(车道编号)
	Snapshottimeunix  *int64  `json:"snapshottimeunix" gorm:"column:snapshottimeunix"`   // JAVA L90 @Excel(抓拍时间Unix格式)
	Snapshottime      *Day    `json:"snapshottime" gorm:"column:snapshottime"`           // JAVA L97 @JsonFormat(yyyy-MM-dd) → Day @Excel(抓拍时间)
	Receivedtimeunix  *int64  `json:"receivedtimeunix" gorm:"column:receivedtimeunix"`   // JAVA L103 @Excel(接收时间Unix格式)
	Receivedtime      *Day    `json:"receivedtime" gorm:"column:receivedtime"`           // JAVA L110 @JsonFormat(yyyy-MM-dd) → Day @Excel(接收时间)
	Platenumber       *string `json:"platenumber" gorm:"column:platenumber"`             // JAVA L116 @Excel(车牌号)
	Platecolorcode    *int    `json:"platecolorcode" gorm:"column:platecolorcode"`       // JAVA L122 @Excel(车牌颜色编码)
	Platecolor        *string `json:"platecolor" gorm:"column:platecolor"`               // JAVA L128 @Excel(车牌颜色)
	Platetypecode     *int    `json:"platetypecode" gorm:"column:platetypecode"`         // JAVA L134 @Excel(车牌类型编码)
	Platetype         *string `json:"platetype" gorm:"column:platetype"`                 // JAVA L140 @Excel(车牌类型)
	Plateconfidence   *int    `json:"plateconfidence" gorm:"column:plateconfidence"`     // JAVA L146 @Excel(车牌置信度)
	Carbrand          *string `json:"carbrand" gorm:"column:carbrand"`                   // JAVA L152 @Excel(车辆品牌)
	Carcolorcode      *int    `json:"carcolorcode" gorm:"column:carcolorcode"`           // JAVA L158 @Excel(车辆颜色编码)
	Carcolor          *string `json:"carcolor" gorm:"column:carcolor"`                   // JAVA L164 @Excel(车辆颜色)
	Cartypecode       *int    `json:"cartypecode" gorm:"column:cartypecode"`             // JAVA L170 @Excel(车辆类型编码)
	Cartype           *string `json:"cartype" gorm:"column:cartype"`                     // JAVA L176 @Excel(车辆类型)
	Cardirectioncode  *int    `json:"cardirectioncode" gorm:"column:cardirectioncode"`   // JAVA L182 @Excel(行驶方向编码)
	Cardirection      *string `json:"cardirection" gorm:"column:cardirection"`           // JAVA L188 @Excel(行驶方向)
	Snappicturepath   *string `json:"snappicturepath" gorm:"column:snappicturepath"`     // JAVA L194 @Excel(图片路径)
	Loadtime          *Day    `json:"loadtime" gorm:"column:loadtime"`                   // JAVA L201 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	Gradelevel        *int    `json:"gradelevel" gorm:"column:gradelevel"`               // JAVA L207 @Excel(分类分级)
	Datauuid          *string `json:"datauuid" gorm:"column:datauuid"`                   // JAVA L209
	Maindirection     *string `json:"maindirection" gorm:"column:maindirection"`         // JAVA L211
	Maindirectionname *string `json:"maindirectionname" gorm:"column:maindirectionname"` // JAVA L213
	Reserve3          *string `json:"reserve3" gorm:"column:reserve3"`                   // JAVA L215
	QueryUuids        *string `json:"queryUuids" gorm:"-"`                               // JAVA L218
	ApplyTime1        *string `json:"applyTime1" gorm:"-"`                               // JAVA L222
	ApplyTime2        *string `json:"applyTime2" gorm:"-"`                               // JAVA L225
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsRtSzdnSnapshotFlowStationcaptureAddcode) TableName() string {
	return "ods_rt_szdn_snapshot_flow_stationcapture_addcode"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsRtSzdnSnapshotFlowStationcaptureAddcode) Schema() string {
	return ""
}
