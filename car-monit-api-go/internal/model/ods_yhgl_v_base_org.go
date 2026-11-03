package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/OdsYhglVBaseOrg.java
// 类/职责: OdsYhglVBaseOrg — 表 ods_yhgl_v_base_org 的实体
// 对应 Go 文件: internal/model/ods_yhgl_v_base_org.go
// 关键映射: @TableName(value='ods_yhgl_v_base_org', schema=None) → TableName()/Schema()；@TableId(big_id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// OdsYhglVBaseOrg 对应 Java 类 OdsYhglVBaseOrg
type OdsYhglVBaseOrg struct {
	BigId           string  `json:"bigId" gorm:"column:big_id;primaryKey"`           // JAVA L29
	OrgCode         string  `json:"orgCode" gorm:"column:org_code"`                  // JAVA L33 @Excel(机构代码)
	OrgName         *string `json:"orgName" gorm:"column:org_name"`                  // JAVA L37 @Excel(机构名称)
	OrgShortName    *string `json:"orgShortName" gorm:"column:org_short_name"`       // JAVA L41 @Excel(机构简称)
	OrgParentId     *string `json:"orgParentId" gorm:"column:org_parent_id"`         // JAVA L45 @Excel(上级机构ID)
	OrgLevelCode    *string `json:"orgLevelCode" gorm:"column:org_level_code"`       // JAVA L49 @Excel(层级代码)
	OrgIsVirtual    *string `json:"orgIsVirtual" gorm:"column:org_is_virtual"`       // JAVA L53 @Excel(是否虚机构 1：虚机构，0：非需机构)
	OrgMaintenance  *string `json:"orgMaintenance" gorm:"column:org_maintenance"`    // JAVA L57 @Excel(是否是养护类)
	OrgSequence     *int64  `json:"orgSequence" gorm:"column:org_sequence"`          // JAVA L61 @Excel(机构顺序)
	OrgIsManager    *string `json:"orgIsManager" gorm:"column:org_is_manager"`       // JAVA L65 @Excel(是否管理单位，主要指是否是路段管理单位(1：是,0：否))
	OrgIsDeleted    *string `json:"orgIsDeleted" gorm:"column:org_is_deleted"`       // JAVA L69 @Excel(是否删除 1：是 0：否)
	OrgCategory     *string `json:"orgCategory" gorm:"column:org_category"`          // JAVA L73 @Excel(机构分类： 01集团 02公司 03管理中心 10部门 11所 12服务区 13养护区 14站 15项目办 16信息中心 17项目部  99其它)
	OrgIsAuthorized *string `json:"orgIsAuthorized" gorm:"column:org_is_authorized"` // JAVA L77 @Excel(是否授权机构 1：是 0：否)
	OrgAddress      *string `json:"orgAddress" gorm:"column:org_address"`            // JAVA L81 @Excel(机构地址)
	OrgIsYhAutarky  *string `json:"orgIsYhAutarky" gorm:"column:org_is_yh_autarky"`  // JAVA L85 @Excel(是自营养护单位)
	LoadTime        *Day    `json:"loadTime" gorm:"column:load_time"`                // JAVA L90 @JsonFormat(yyyy-MM-dd) → Day @Excel(加载时间)
	GradeLevel      *int    `json:"gradeLevel" gorm:"column:grade_level"`            // JAVA L94 @Excel(分类分级)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (OdsYhglVBaseOrg) TableName() string {
	return "ods_yhgl_v_base_org"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (OdsYhglVBaseOrg) Schema() string {
	return ""
}
