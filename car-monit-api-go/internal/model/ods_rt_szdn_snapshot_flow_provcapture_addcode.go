package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowProvcaptureAddcode.java
// 类/职责: OdsRtSzdnSnapshotFlowProvcaptureAddcode — 表 ods_rt_szdn_snapshot_flow_provcapture_addcode 的实体
// 对应 Go 文件: internal/model/ods_rt_szdn_snapshot_flow_provcapture_addcode.go
// 关键映射: @TableName(value='ods_rt_szdn_snapshot_flow_provcapture_addcode', schema=None) → TableName()/Schema()；@TableId(bigId) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

import ()

// OdsRtSzdnSnapshotFlowProvcaptureAddcode 对应 Java 类 OdsRtSzdnSnapshotFlowProvcaptureAddcode
type OdsRtSzdnSnapshotFlowProvcaptureAddcode struct {
	BigId                    *int64     `json:"bigId" gorm:"column:big_id;primaryKey"`                           // JAVA L30
	Deviceip                 *string    `json:"deviceip" gorm:"column:deviceip"`                                 // JAVA L32
	Tailcapturetimeunix      *int64     `json:"tailcapturetimeunix" gorm:"column:tailcapturetimeunix"`           // JAVA L34
	Tailcapturetime          *Timestamp `json:"tailcapturetime" gorm:"column:tailcapturetime"`                   // JAVA L36
	Extendattribute          *string    `json:"extendattribute" gorm:"column:extendattribute"`                   // JAVA L38
	Smallsideimagewidth      *int       `json:"smallsideimagewidth" gorm:"column:smallsideimagewidth"`           // JAVA L40
	Axletype                 *string    `json:"axletype" gorm:"column:axletype"`                                 // JAVA L42
	Smallsideimageheight     *int       `json:"smallsideimageheight" gorm:"column:smallsideimageheight"`         // JAVA L48 @Excel(小侧图高度)
	Platecolorcode           *int       `json:"platecolorcode" gorm:"column:platecolorcode"`                     // JAVA L54 @Excel(车牌颜色编码)
	Platecolor               *string    `json:"platecolor" gorm:"column:platecolor"`                             // JAVA L60 @Excel(车牌颜色)
	Cover                    *string    `json:"cover" gorm:"column:cover"`                                       // JAVA L66 @Excel(遮挡信息)
	Averageauthoritative     *int       `json:"averageauthoritative" gorm:"column:averageauthoritative"`         // JAVA L72 @Excel(平均可信度)
	Headlanecode             *int       `json:"headlanecode" gorm:"column:headlanecode"`                         // JAVA L78 @Excel(车头车道号)
	Specialvehicle           *int       `json:"specialvehicle" gorm:"column:specialvehicle"`                     // JAVA L84 @Excel(特殊车辆标识)
	Carlength                *int       `json:"carlength" gorm:"column:carlength"`                               // JAVA L90 @Excel(车长)
	Resulttype               *string    `json:"resulttype" gorm:"column:resulttype"`                             // JAVA L96 @Excel(结果类型)
	Carhight                 *int       `json:"carhight" gorm:"column:carhight"`                                 // JAVA L102 @Excel(车高)
	Carmodelscode            *int       `json:"carmodelscode" gorm:"column:carmodelscode"`                       // JAVA L108 @Excel(车型编码)
	Carmodels                *string    `json:"carmodels" gorm:"column:carmodels"`                               // JAVA L114 @Excel(车型)
	Laneposition             *string    `json:"laneposition" gorm:"column:laneposition"`                         // JAVA L120 @Excel(车道位置)
	Firstauthoritative       *int       `json:"firstauthoritative" gorm:"column:firstauthoritative"`             // JAVA L126 @Excel(首字可信度)
	Tailplateimageheight     *int       `json:"tailplateimageheight" gorm:"column:tailplateimageheight"`         // JAVA L132 @Excel(车尾车牌图高度)
	Axlecount                *int       `json:"axlecount" gorm:"column:axlecount"`                               // JAVA L138 @Excel(车轴数)
	Plateimagewidth          *int       `json:"plateimagewidth" gorm:"column:plateimagewidth"`                   // JAVA L144 @Excel(车牌图宽度)
	Specialclass             *string    `json:"specialclass" gorm:"column:specialclass"`                         // JAVA L150 @Excel(特殊类别)
	Tailplatenumber          *string    `json:"tailplatenumber" gorm:"column:tailplatenumber"`                   // JAVA L156 @Excel(车尾车牌号)
	Tailimage                *string    `json:"tailimage" gorm:"column:tailimage"`                               // JAVA L162 @Excel(车尾图路径)
	Sidecapturetimeunix      *int64     `json:"sidecapturetimeunix" gorm:"column:sidecapturetimeunix"`           // JAVA L168 @Excel(车身图采集时间(Unix时间戳))
	Sidecapturetime          *Day       `json:"sidecapturetime" gorm:"column:sidecapturetime"`                   // JAVA L175 @JsonFormat(yyyy-MM-dd) → Day @Excel(车身图采集时间(可读格式))
	Sidelanecode             *int       `json:"sidelanecode" gorm:"column:sidelanecode"`                         // JAVA L181 @Excel(车身车道号)
	Wheelbase                *int       `json:"wheelbase" gorm:"column:wheelbase"`                               // JAVA L187 @Excel(轴距)
	Attached                 *string    `json:"attached" gorm:"column:attached"`                                 // JAVA L193 @Excel(附加信息)
	Wheelcount               *int       `json:"wheelcount" gorm:"column:wheelcount"`                             // JAVA L199 @Excel(车轮数量)
	Guid                     *string    `json:"guid" gorm:"column:guid"`                                         // JAVA L205 @Excel(全局唯一标识符)
	Sideimagewidth           *int       `json:"sideimagewidth" gorm:"column:sideimagewidth"`                     // JAVA L211 @Excel(车身图宽度)
	Plateimageheight         *int       `json:"plateimageheight" gorm:"column:plateimageheight"`                 // JAVA L217 @Excel(车牌图高度)
	Datasource               *string    `json:"datasource" gorm:"column:datasource"`                             // JAVA L223 @Excel(数据来源)
	Carclass                 *string    `json:"carclass" gorm:"column:carclass"`                                 // JAVA L229 @Excel(车辆分类)
	Gantryid                 *string    `json:"gantryid" gorm:"column:gantryid"`                                 // JAVA L235 @Excel(门架编号)
	Smallsideimage           *string    `json:"smallsideimage" gorm:"column:smallsideimage"`                     // JAVA L241 @Excel(小侧图路径)
	Headimageheight          *int       `json:"headimageheight" gorm:"column:headimageheight"`                   // JAVA L247 @Excel(车头图高度)
	Sidescenetypecode        *int       `json:"sidescenetypecode" gorm:"column:sidescenetypecode"`               // JAVA L253 @Excel(车侧拍摄场景编码)
	Sidescenetype            *string    `json:"sidescenetype" gorm:"column:sidescenetype"`                       // JAVA L259 @Excel(车侧拍摄场景)
	Tailimagewidth           *int       `json:"tailimagewidth" gorm:"column:tailimagewidth"`                     // JAVA L265 @Excel(车尾图宽度)
	Envstate                 *string    `json:"envstate" gorm:"column:envstate"`                                 // JAVA L271 @Excel(环境状态)
	Headscenetypecode        *int       `json:"headscenetypecode" gorm:"column:headscenetypecode"`               // JAVA L277 @Excel(车头拍摄场景编码)
	Headscenetype            *string    `json:"headscenetype" gorm:"column:headscenetype"`                       // JAVA L283 @Excel(车头拍摄场景)
	Sidedrivingdirectioncode *int       `json:"sidedrivingdirectioncode" gorm:"column:sidedrivingdirectioncode"` // JAVA L289 @Excel(车侧行驶方向编码)
	Sidedrivingdirection     *string    `json:"sidedrivingdirection" gorm:"column:sidedrivingdirection"`         // JAVA L295 @Excel(车侧行驶方向)
	Sideimageheight          *int       `json:"sideimageheight" gorm:"column:sideimageheight"`                   // JAVA L301 @Excel(车身图高度)
	Speed                    *string    `json:"speed" gorm:"column:speed"`                                       // JAVA L307 @Excel(车速)
	Tailplateimage           *string    `json:"tailplateimage" gorm:"column:tailplateimage"`                     // JAVA L313 @Excel(车尾车牌图路径)
	Headdrivingdirectioncode *int       `json:"headdrivingdirectioncode" gorm:"column:headdrivingdirectioncode"` // JAVA L319 @Excel(车头行驶方向编码)
	Headdrivingdirection     *string    `json:"headdrivingdirection" gorm:"column:headdrivingdirection"`         // JAVA L325 @Excel(车头行驶方向)
	Cartype                  *string    `json:"cartype" gorm:"column:cartype"`                                   // JAVA L331 @Excel(车辆类型)
	Plateimage               *string    `json:"plateimage" gorm:"column:plateimage"`                             // JAVA L337 @Excel(车牌图路径)
	Changelane               *string    `json:"changelane" gorm:"column:changelane"`                             // JAVA L343 @Excel(变道信息)
	Sideimage                *string    `json:"sideimage" gorm:"column:sideimage"`                               // JAVA L349 @Excel(车身图路径)
	Tailplateposition        *string    `json:"tailplateposition" gorm:"column:tailplateposition"`               // JAVA L355 @Excel(车尾车牌位置)
	Headimagewidth           *int       `json:"headimagewidth" gorm:"column:headimagewidth"`                     // JAVA L361 @Excel(车头图宽度)
	Headimage                *string    `json:"headimage" gorm:"column:headimage"`                               // JAVA L367 @Excel(车头图路径)
	Carweight                *int       `json:"carweight" gorm:"column:carweight"`                               // JAVA L373 @Excel(车重)
	Tailimageheight          *int       `json:"tailimageheight" gorm:"column:tailimageheight"`                   // JAVA L379 @Excel(车尾图高度)
	Devicecode               *string    `json:"devicecode" gorm:"column:devicecode"`                             // JAVA L385 @Excel(设备编号)
	Platenumber              *string    `json:"platenumber" gorm:"column:platenumber"`                           // JAVA L391 @Excel(车牌号码)
	Tailplatecolorcode       *int       `json:"tailplatecolorcode" gorm:"column:tailplatecolorcode"`             // JAVA L397 @Excel(车尾车牌颜色编码)
	Tailplatecolor           *string    `json:"tailplatecolor" gorm:"column:tailplatecolor"`                     // JAVA L403 @Excel(车尾车牌颜色)
	Uploadtimeunix           *int64     `json:"uploadtimeunix" gorm:"column:uploadtimeunix"`                     // JAVA L409 @Excel(上传时间(Unix时间戳))
	Uploadtime               *Day       `json:"uploadtime" gorm:"column:uploadtime"`                             // JAVA L416 @JsonFormat(yyyy-MM-dd) → Day @Excel(上传时间(可读格式))
	Impostoraxlecount        *int       `json:"impostoraxlecount" gorm:"column:impostoraxlecount"`               // JAVA L422 @Excel(假轴数)
	Taillanecode             *int       `json:"taillanecode" gorm:"column:taillanecode"`                         // JAVA L428 @Excel(车尾车道号)
	Siteid                   *int       `json:"siteid" gorm:"column:siteid"`                                     // JAVA L434 @Excel(站点ID)
	Headcapturetimeunix      *int64     `json:"headcapturetimeunix" gorm:"column:headcapturetimeunix"`           // JAVA L440 @Excel(车头图采集时间(Unix时间戳))
	Headcapturetime          *Day       `json:"headcapturetime" gorm:"column:headcapturetime"`                   // JAVA L447 @JsonFormat(yyyy-MM-dd) → Day @Excel(车头图采集时间(可读格式))
	Plateposition            *string    `json:"plateposition" gorm:"column:plateposition"`                       // JAVA L453 @Excel(车牌位置)
	Tailplateimagewidth      *int       `json:"tailplateimagewidth" gorm:"column:tailplateimagewidth"`           // JAVA L459 @Excel(车尾车牌图宽度)
	Loadtime                 *Timestamp `json:"loadtime" gorm:"column:loadtime"`                                 // JAVA L461
	Gradelevel               *int       `json:"gradelevel" gorm:"column:gradelevel"`                             // JAVA L463
	Datauuid                 *string    `json:"datauuid" gorm:"column:datauuid"`                                 // JAVA L465
	Reserve1                 *string    `json:"reserve1" gorm:"column:reserve1"`                                 // JAVA L467
	Reserve2                 *string    `json:"reserve2" gorm:"column:reserve2"`                                 // JAVA L469
	Reserve3                 *string    `json:"reserve3" gorm:"column:reserve3"`                                 // JAVA L471
	QueryUuids               *string    `json:"queryUuids" gorm:"-"`                                             // JAVA L474
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsRtSzdnSnapshotFlowProvcaptureAddcode) TableName() string {
	return "ods_rt_szdn_snapshot_flow_provcapture_addcode"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsRtSzdnSnapshotFlowProvcaptureAddcode) Schema() string {
	return ""
}
