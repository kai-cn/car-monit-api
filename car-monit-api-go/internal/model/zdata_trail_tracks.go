package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailTracks.java
// 类/职责: ZdataTrailTracks — 表 zdata_trail_tracks 的实体
// 对应 Go 文件: internal/model/zdata_trail_tracks.go
// 关键映射: @TableName(value='zdata_trail_tracks', schema=None) → TableName()/Schema()；@TableId(uuid) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// ZdataTrailTracks 对应 Java 类 ZdataTrailTracks
type ZdataTrailTracks struct {
	Uuid              *string   `json:"uuid" gorm:"column:uuid;primaryKey"`                 // JAVA L38 @Excel(唯一标识符)
	Type              *int      `json:"type" gorm:"column:type"`                            // JAVA L44 @Excel(轨迹类型)
	PointCount        *int64    `json:"pointCount" gorm:"column:point_count"`               // JAVA L50 @Excel(轨迹点数量)
	PlateKey          *string   `json:"plateKey" gorm:"column:plate_key"`                   // JAVA L56 @Excel(车牌唯一标识)
	EnterTime         *DateTime `json:"enterTime" gorm:"column:enter_time"`                 // JAVA L63 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(进入时间)
	ExitTime          *DateTime `json:"exitTime" gorm:"column:exit_time"`                   // JAVA L70 @JsonFormat(yyyy-MM-dd HH:mm:ss) → DateTime @Excel(离开时间)
	TrailPoints       *string   `json:"trailPoints" gorm:"column:trail_points"`             // JAVA L76 @Excel(轨迹点集合，推荐存 JSON 格式，包含坐标/时间/速度等信息)
	EnterLocationcode *string   `json:"enterLocationcode" gorm:"column:enter_locationcode"` // JAVA L80 @Excel(进入位置code)
	ExitLocationcode  *string   `json:"exitLocationcode" gorm:"column:exit_locationcode"`   // JAVA L84 @Excel(离开位置code)
	TrackJosn         *string   `json:"trackJosn" gorm:"-"`                                 // JAVA L89 @Excel(集合详情)
	Enaxlecount       *int      `json:"enaxlecount" gorm:"-"`                               // JAVA L94 @Excel(入口车轴数)
	Entolllaneid      *string   `json:"entolllaneid" gorm:"-"`                              // JAVA L99 @Excel(入口车道编号)
	Entollstationid   *string   `json:"entollstationid" gorm:"-"`                           // JAVA L104 @Excel(入口收费站编号)
	Entollstationname *string   `json:"entollstationname" gorm:"-"`                         // JAVA L109 @Excel(入口收费站名称)
	Envehicleclass    *string   `json:"envehicleclass" gorm:"-"`                            // JAVA L114 @Excel(入口车型分类)
	Envehicleid       *string   `json:"envehicleid" gorm:"-"`                               // JAVA L119 @Excel(入口车辆编号)
	Envehicletype     *string   `json:"envehicletype" gorm:"-"`                             // JAVA L124 @Excel(入口车辆类型代码)
	Enweight          *float64  `json:"enweight" gorm:"-"`                                  // JAVA L129 @Excel(入口称重)
	Extolllaneid      *string   `json:"extolllaneid" gorm:"-"`                              // JAVA L134 @Excel(出口车道编号)
	Extollstationid   *string   `json:"extollstationid" gorm:"-"`                           // JAVA L139 @Excel(出口收费站编号)
	Extollstationname *string   `json:"extollstationname" gorm:"-"`                         // JAVA L144 @Excel(出口收费站名称)
	Exvehicleclass    *string   `json:"exvehicleclass" gorm:"-"`                            // JAVA L149 @Excel(出口车型分类)
	Exvehicleid       *string   `json:"exvehicleid" gorm:"-"`                               // JAVA L154 @Excel(出口车辆编号)
	Exvehicletype     *string   `json:"exvehicletype" gorm:"-"`                             // JAVA L159 @Excel(出口车辆类型代码)
	Exweight          *float64  `json:"exweight" gorm:"-"`                                  // JAVA L164 @Excel(出口称重)
	StartLon          *string   `json:"startLon" gorm:"-"`                                  // JAVA L170 @Excel(入口收费站经度)
	StratLat          *string   `json:"stratLat" gorm:"-"`                                  // JAVA L175 @Excel(入口收费站维度)
	EndLon            *string   `json:"endLon" gorm:"-"`                                    // JAVA L180 @Excel(出口收费站经度)
	EndLat            *string   `json:"endLat" gorm:"-"`                                    // JAVA L185 @Excel(出口收费站维度)
	FirtStationCode   *string   `json:"firtStationCode" gorm:"-"`                           // JAVA L190
	FirtStationName   *string   `json:"firtStationName" gorm:"-"`                           // JAVA L194
	FirtStationTime   *string   `json:"firtStationTime" gorm:"-"`                           // JAVA L198
	PlateColor        *string   `json:"plateColor" gorm:"-"`                                // JAVA L203
	CarType           *string   `json:"carType" gorm:"-"`                                   // JAVA L207
	CarNo             *string   `json:"carNo" gorm:"-"`                                     // JAVA L211
	CarVehicle        *string   `json:"carVehicle" gorm:"-"`                                // JAVA L215
	CarNum            *int64    `json:"carNum" gorm:"-"`                                    // JAVA L220
	PassType          *string   `json:"passType" gorm:"-"`                                  // JAVA L224
	EscapedType       *string   `json:"escapedType" gorm:"-"`                               // JAVA L228
	EscapedTypeRemark *string   `json:"escapedTypeRemark" gorm:"-"`                         // JAVA L233
	ApplyTime1        *string   `json:"applyTime1" gorm:"-"`                                // JAVA L237
	ApplyTime2        *string   `json:"applyTime2" gorm:"-"`                                // JAVA L241
	Flag              *string   `json:"flag" gorm:"-"`                                      // JAVA L245
	StartLonDec       *float64  `json:"startLonDec" gorm:"-"`                               // JAVA L251 @Excel(入口收费站经度)
	StratLatDec       *float64  `json:"stratLatDec" gorm:"-"`                               // JAVA L256 @Excel(入口收费站维度)
	EndLonDec         *float64  `json:"endLonDec" gorm:"-"`                                 // JAVA L261 @Excel(出口收费站经度)
	EndLatDec         *float64  `json:"endLatDec" gorm:"-"`                                 // JAVA L266 @Excel(出口收费站维度)
	EscapedTfcj       *string   `json:"escapedTfcj" gorm:"-"`                               // JAVA L271
	Trailtype         *string   `json:"trailtype" gorm:"-"`                                 // JAVA L276
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (ZdataTrailTracks) TableName() string {
	return "zdata_trail_tracks"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (ZdataTrailTracks) Schema() string {
	return ""
}
