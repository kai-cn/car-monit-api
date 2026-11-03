package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/DwdLcztSfsjcxx.java
// 类/职责: DwdLcztSfsjcxx — 表 dwd_lczt_sfsjcxx 的实体
// 对应 Go 文件: internal/model/dwd_lczt_sfsjcxx.go
// 关键映射: @TableName(value='dwd_lczt_sfsjcxx', schema=None) → TableName()/Schema()；@TableId(agent_pk) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// DwdLcztSfsjcxx 对应 Java 类 DwdLcztSfsjcxx
type DwdLcztSfsjcxx struct {
	AgentPk  string  `json:"agentPk" gorm:"column:agent_pk;primaryKey"` // JAVA L26
	Yxtzj    *string `json:"yxtzj" gorm:"column:yxtzj"`                 // JAVA L30 @Excel(源系统主键)
	Sfsbm    *string `json:"sfsbm" gorm:"column:sfsbm"`                 // JAVA L34 @Excel(收费所编码)
	Sfsmc    *string `json:"sfsmc" gorm:"column:sfsmc"`                 // JAVA L38 @Excel(收费所名称)
	Jd       *string `json:"jd" gorm:"column:jd"`                       // JAVA L42 @Excel(经度)
	Wd       *string `json:"wd" gorm:"column:wd"`                       // JAVA L46 @Excel(纬度)
	Sslxbh   *string `json:"sslxbh" gorm:"column:sslxbh"`               // JAVA L50 @Excel(所属路线编号)
	Sslxmc   *string `json:"sslxmc" gorm:"column:sslxmc"`               // JAVA L54 @Excel(所属路线名称)
	Ssldbh   *string `json:"ssldbh" gorm:"column:ssldbh"`               // JAVA L58 @Excel(所属路段编号)
	Ssldmc   *string `json:"ssldmc" gorm:"column:ssldmc"`               // JAVA L62 @Excel(所属路段名称)
	SczhK    *string `json:"sczhK" gorm:"column:sczh_k"`                // JAVA L66 @Excel(所处桩号(K格式))
	SczhN    *string `json:"sczhN" gorm:"column:sczh_n"`                // JAVA L70 @Excel(所处桩号(数值格式))
	Ssglzxbm *string `json:"ssglzxbm" gorm:"column:ssglzxbm"`           // JAVA L74 @Excel(所属管理中心编码)
	Ssglzxmc *string `json:"ssglzxmc" gorm:"column:ssglzxmc"`           // JAVA L78 @Excel(所属管理中心名称)
	Lyxt     *string `json:"lyxt" gorm:"column:lyxt"`                   // JAVA L82 @Excel(来源系统)
	LoadTime *string `json:"loadTime" gorm:"column:load_time"`          // JAVA L86 @Excel(加载日期)
	AllColPk *string `json:"allColPk" gorm:"column:all_col_pk"`         // JAVA L90 @Excel(全字段MD5)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (DwdLcztSfsjcxx) TableName() string {
	return "dwd_lczt_sfsjcxx"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (DwdLcztSfsjcxx) Schema() string {
	return ""
}
