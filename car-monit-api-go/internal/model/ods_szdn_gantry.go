package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnGantry.java
// 类/职责: OdsSzdnGantry — 表 ods_szdn_gantry 的实体
// 对应 Go 文件: internal/model/ods_szdn_gantry.go
// 关键映射: @TableName(value='ods_szdn_gantry', schema=None) → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsSzdnGantry 对应 Java 类 OdsSzdnGantry
type OdsSzdnGantry struct {
	Id                 string  `json:"id" gorm:"column:id;primaryKey"`                        // JAVA L26
	GantryCode         *string `json:"gantryCode" gorm:"column:gantry_code"`                  // JAVA L30 @Excel(门架编号)
	GantryName         *string `json:"gantryName" gorm:"column:gantry_name"`                  // JAVA L34 @Excel(门架名称)
	RoadCode           *string `json:"roadCode" gorm:"column:road_code"`                      // JAVA L38 @Excel(所属路线编码)
	SectionCode        *string `json:"sectionCode" gorm:"column:section_code"`                // JAVA L42 @Excel(所属路段编码)
	TollCode           *string `json:"tollCode" gorm:"column:toll_code"`                      // JAVA L46 @Excel(所属收费站编码)
	OrgCode            *string `json:"orgCode" gorm:"column:org_code"`                        // JAVA L50 @Excel(所属管理中心机构编码)
	HexCode            *string `json:"hexCode" gorm:"column:hex_code"`                        // JAVA L54 @Excel(门架二进制编号)
	Direction          *string `json:"direction" gorm:"column:direction"`                     // JAVA L58 @Excel(方向)
	PileNo             *string `json:"pileNo" gorm:"column:pile_no"`                          // JAVA L62 @Excel(桩号)
	Lon                *string `json:"lon" gorm:"column:lon"`                                 // JAVA L66 @Excel(经度)
	Lat                *string `json:"lat" gorm:"column:lat"`                                 // JAVA L70 @Excel(纬度)
	IsVirtual          *string `json:"isVirtual" gorm:"column:is_virtual"`                    // JAVA L74 @Excel(是否虚门架)
	Mileage            *string `json:"mileage" gorm:"column:mileage"`                         // JAVA L78 @Excel(里程)
	BoundaryGantryType *string `json:"boundaryGantryType" gorm:"column:boundary_gantry_type"` // JAVA L82 @Excel(边界门架类型)
	GantryType         *string `json:"gantryType" gorm:"column:gantry_type"`                  // JAVA L86 @Excel(门架类型)
	CityCode           *string `json:"cityCode" gorm:"column:city_code"`                      // JAVA L90 @Excel(城市编码)
	DistrictName       *string `json:"districtName" gorm:"column:district_name"`              // JAVA L94 @Excel(行政区名称)
	BelongGroup        *string `json:"belongGroup" gorm:"column:belong_group"`                // JAVA L98 @Excel(是否属于集团，0：否；1：是)
	GantryCodeMerge    *string `json:"gantryCodeMerge" gorm:"column:gantry_code_merge"`       // JAVA L102 @Excel(门架编号)
	GantryNameAlias    *string `json:"gantryNameAlias" gorm:"column:gantry_name_alias"`       // JAVA L106 @Excel(门架别名)
	Remark             *string `json:"remark" gorm:"column:remark"`                           // JAVA L110 @Excel(备注)
	IsData             *string `json:"isData" gorm:"-"`                                       // JAVA L116
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnGantry) TableName() string {
	return "ods_szdn_gantry"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnGantry) Schema() string {
	return ""
}
