package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnSection.java
// 类/职责: OdsSzdnSection — 表 ods_szdn_section 的实体
// 对应 Go 文件: internal/model/ods_szdn_section.go
// 关键映射: @TableName(value='ods_szdn_section', schema=None) → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsSzdnSection 对应 Java 类 OdsSzdnSection
//
// PARITY: start_pile_no / end_pile_no / mileage 三列在库里是 double precision，
// 而 Java 实体声明的是 Long（MyBatis 调 ResultSet#getLong，向零截断）。
// 上一版照字面翻成 *int64，pgx 严格执行类型，直接报
// "converting driver.Value type float64 to a int64"，整个 /base/section/list 500。
// 现在用 model.JavaLong 把 JDBC 的截断语义搬过来（见 internal/model/javalong.go）。
type OdsSzdnSection struct {
	Id           string    `json:"id" gorm:"column:id;primaryKey"`            // JAVA L28
	RoadCode     *string   `json:"roadCode" gorm:"column:road_code"`          // JAVA L32 @Excel(路线编码)
	RoadName     *string   `json:"roadName" gorm:"column:road_name"`          // JAVA L36 @Excel(路线名称)
	SectionCode  *string   `json:"sectionCode" gorm:"column:section_code"`    // JAVA L40 @Excel(路段编码)
	SectionName  *string   `json:"sectionName" gorm:"column:section_name"`    // JAVA L44 @Excel(路段名称)
	StartPileNo  *JavaLong `json:"startPileNo" gorm:"column:start_pile_no"`   // JAVA L48 private Long；列实际是 double precision，走 JavaLong 截断
	EndPileNo    *JavaLong `json:"endPileNo" gorm:"column:end_pile_no"`       // JAVA L52 private Long；列实际是 double precision
	OrgCode      *string   `json:"orgCode" gorm:"column:org_code"`            // JAVA L56 @Excel(机构代码)
	OrgName      *string   `json:"orgName" gorm:"column:org_name"`            // JAVA L60 @Excel(机构名称)
	OrgLevelCode *string   `json:"orgLevelCode" gorm:"column:org_level_code"` // JAVA L64 @Excel(层级代码)
	OrgCategory  *string   `json:"orgCategory" gorm:"column:org_category"`    // JAVA L68 @Excel(机构分类)
	Mileage      *JavaLong `json:"mileage" gorm:"column:mileage"`             // JAVA L72 private Long；列实际是 double precision
	OpenDate     *Day      `json:"openDate" gorm:"column:open_date"`          // JAVA L77 @JsonFormat(yyyy-MM-dd) → Day @Excel(通车日期)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsSzdnSection) TableName() string {
	return "ods_szdn_section"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsSzdnSection) Schema() string {
	return ""
}
