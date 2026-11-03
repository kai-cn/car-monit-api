package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/TrailBo.java
// 类/职责: TrailBo — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/trail_bo.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。
//
// PARITY（P-SER-1）：字符串字段统一是 *string，不是 string。
// Java 的 String 是引用类型，未赋值时是 null，Jackson 就输出 null；Go 的 string 零值是 ""，
// 于是 carTrackQueryByTime / carTrackQueryByCarNo / changeTrailInfo / getByTrailBo 的响应体里
// 每个没填的字段都差一次（实测残余 11 条用例，TrailBo 层 null 3907 处 / "" 19 处）。
// 本仓对「Java 可空 String」的既定写法就是 *string + Val/NonEmpty/Str（见 nullstr.go），
// DB 可空列早先已按此收敛，TrailBo 因为是 DTO 漏掉了。
//
// 为什么不做成「空串一律编码成 null」的自定义类型：Java 有**合法输出 ""** 的字段，
// 类型级一刀切会把它们翻转成新差异 ——
//   - imagesArry：SysUtilServiceImpl.java:1198/1205/1213 显式 setImagesArry("")，
//     且 L1219-1220 无条件过 repalacePicUrl(deleteEnd(...))，getByTrailBo 下永远非 null；
//   - devName：SysUtilServiceImpl.java:740 setDevName(CommonUtil.isNull(code).replaceAll(...))，
//     code 为空时得到 ""。
//     这两处在 Java 报文里实测共 19 个 ""，改指针后必须写成 Str("") 才保得住。

// TrailBo 对应 Java 类 TrailBo
type TrailBo struct {
	PointUuid               *string                                         `json:"pointUuid"`               // JAVA L11
	StateType               *string                                         `json:"stateType"`               // JAVA L21
	PointFlag               *string                                         `json:"pointFlag"`               // JAVA L24
	PointJosn               *string                                         `json:"pointJosn"`               // JAVA L27
	BorderWeighingCaptureBO *OdsSzdnProvinceBorderVehicleWeightNewstructure `json:"borderWeighingCaptureBO"` // JAVA L29
	GantryCaptureBO         *OdsRtSzdnSnapshotFlowAddcode                   `json:"gantryCaptureBO"`         // JAVA L31
	ProvCaptureBO           *OdsRtSzdnSnapshotFlowProvcaptureAddcode        `json:"provCaptureBO"`           // JAVA L33
	StationCapture          *OdsRtSzdnSnapshotFlowStationcaptureAddcode     `json:"stationCapture"`          // JAVA L35
	FeeRecord               *OdsLwzxsfsjFeeRecords01                        `json:"feeRecord"`               // JAVA L37
	FeeStationEnter         *OdsLwzxsfsjFeeStationEnter01                   `json:"feeStationEnter"`         // JAVA L39
	FeeStationExit          *OdsLwzxsfsjFeeStationExit01                    `json:"feeStationExit"`          // JAVA L41
	CaptureTime             *string                                         `json:"captureTime"`             // JAVA L45
	DirectionIn             *bool                                           `json:"directionIn"`             // JAVA L48
	LocationCode            *string                                         `json:"locationCode"`            // JAVA L51
	LocationName            *string                                         `json:"locationName"`            // JAVA L54
	StandardCode            *string                                         `json:"standardCode"`            // JAVA L57
	Longitude               *string                                         `json:"longitude"`               // JAVA L60
	Latitude                *string                                         `json:"latitude"`                // JAVA L63
	LocationFlag            *string                                         `json:"locationFlag"`            // JAVA L67
	IpType                  *string                                         `json:"ipType"`                  // JAVA L74
	LocationJosn            *string                                         `json:"locationJosn"`            // JAVA L77
	GantryIpBO              *OdsSzdnGantryIp                                `json:"gantryIpBO"`              // JAVA L79
	StationIpBO             *OdsSzdnTollStationIp                           `json:"stationIpBO"`             // JAVA L81
	DevCode                 *string                                         `json:"devCode"`                 // JAVA L85
	DevName                 *string                                         `json:"devName"`                 // JAVA L88
	ImagesArry              *string                                         `json:"imagesArry"`              // JAVA L91
	Lon                     *float64                                        `json:"lon"`                     // JAVA L94
	Lat                     *float64                                        `json:"lat"`                     // JAVA L97
	RoadCode                *string                                         `json:"roadCode"`                // JAVA L100
	SectionCode             *string                                         `json:"sectionCode"`             // JAVA L103
	OrgCode                 *string                                         `json:"orgCode"`                 // JAVA L106
	Direction               *string                                         `json:"direction"`               // JAVA L109
	Pileno                  *string                                         `json:"pileno"`                  // JAVA L112
	PreCaptureTime          *string                                         `json:"preCaptureTime"`          // JAVA L115
	CountNum                *int                                            `json:"countNum"`                // JAVA L118
	Platenumber             *string                                         `json:"platenumber"`             // JAVA L120
	LocationId              *string                                         `json:"locationId"`              // JAVA L122
	IsQuery                 *string                                         `json:"isQuery"`                 // JAVA L126
	Platecolor              *string                                         `json:"platecolor"`              // JAVA L130
	IsVirtual               *string                                         `json:"isVirtual"`               // JAVA L133
}
