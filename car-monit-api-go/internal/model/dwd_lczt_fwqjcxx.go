package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/DwdLcztFwqjcxx.java
// 类/职责: DwdLcztFwqjcxx — 表 dwd_lczt_fwqjcxx 的实体
// 对应 Go 文件: internal/model/dwd_lczt_fwqjcxx.go
// 关键映射: @TableName(value='dwd_lczt_fwqjcxx', schema=None) → TableName()/Schema()；@TableId(agent_pk) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// DwdLcztFwqjcxx 对应 Java 类 DwdLcztFwqjcxx
type DwdLcztFwqjcxx struct {
	AgentPk   *string `json:"agentPk" gorm:"column:agent_pk;primaryKey"` // JAVA L26
	Yxtzj     *string `json:"yxtzj" gorm:"column:yxtzj"`                 // JAVA L30 @Excel(源系统主键)
	Fwqbm     *string `json:"fwqbm" gorm:"column:fwqbm"`                 // JAVA L34 @Excel(服务区编码)
	Fwqmc     *string `json:"fwqmc" gorm:"column:fwqmc"`                 // JAVA L38 @Excel(服务区名称)
	Wd        *string `json:"wd" gorm:"column:wd"`                       // JAVA L42 @Excel(纬度)
	Fxmc      *string `json:"fxmc" gorm:"column:fxmc"`                   // JAVA L46 @Excel(方向名称)
	Fxdm      *string `json:"fxdm" gorm:"column:fxdm"`                   // JAVA L50 @Excel(方向代码)
	Jd        *string `json:"jd" gorm:"column:jd"`                       // JAVA L54 @Excel(经度)
	Sslxbh    *string `json:"sslxbh" gorm:"column:sslxbh"`               // JAVA L58 @Excel(所属路线编号)
	Sslxmc    *string `json:"sslxmc" gorm:"column:sslxmc"`               // JAVA L62 @Excel(所属路线名称)
	Ssldbh    *string `json:"ssldbh" gorm:"column:ssldbh"`               // JAVA L66 @Excel(所属路段编号)
	Ssldmc    *string `json:"ssldmc" gorm:"column:ssldmc"`               // JAVA L70 @Excel(所属路段名称)
	Sczhkgs   *string `json:"sczhkgs" gorm:"column:sczhkgs"`             // JAVA L74 @Excel(所处桩号(K格式))
	Sczhszgs  *string `json:"sczhszgs" gorm:"column:sczhszgs"`           // JAVA L78 @Excel(所处桩号(数值格式))
	Ssglzxbm  *string `json:"ssglzxbm" gorm:"column:ssglzxbm"`           // JAVA L82 @Excel(所属管理中心编码)
	Ssglzxmc  *string `json:"ssglzxmc" gorm:"column:ssglzxmc"`           // JAVA L86 @Excel(所属管理中心名称)
	Xzqhmc    *string `json:"xzqhmc" gorm:"column:xzqhmc"`               // JAVA L90 @Excel(行政区划名称)
	Yyrq      *string `json:"yyrq" gorm:"column:yyrq"`                   // JAVA L94 @Excel(营业日期)
	Cws       *string `json:"cws" gorm:"column:cws"`                     // JAVA L98 @Excel(车位数)
	Sfszlkk   *string `json:"sfszlkk" gorm:"column:sfszlkk"`             // JAVA L102 @Excel(是否设置了卡口)
	Cdzs      *string `json:"cdzs" gorm:"column:cdzs"`                   // JAVA L106 @Excel(充电桩数)
	Sfcyfw    *string `json:"sfcyfw" gorm:"column:sfcyfw"`               // JAVA L110 @Excel(是否餐饮服务)
	Sftgzsfw  *string `json:"sftgzsfw" gorm:"column:sftgzsfw"`           // JAVA L114 @Excel(是否提供住宿服务)
	Sftgqxfw  *string `json:"sftgqxfw" gorm:"column:sftgqxfw"`           // JAVA L118 @Excel(是否提供汽修服务)
	Sftgcsfw  *string `json:"sftgcsfw" gorm:"column:sftgcsfw"`           // JAVA L122 @Excel(是否提供超市服务)
	Sftgjyfw  *string `json:"sftgjyfw" gorm:"column:sftgjyfw"`           // JAVA L126 @Excel(是否提供加油服务)
	Mj        *string `json:"mj" gorm:"column:mj"`                       // JAVA L130 @Excel(面积(平方米))
	Sftgcshfw *string `json:"sftgcshfw" gorm:"column:sftgcshfw"`         // JAVA L134 @Excel(是否提供厕所服务)
	Xzqhdm    *string `json:"xzqhdm" gorm:"column:xzqhdm"`               // JAVA L138 @Excel(行政区划代码)
	Synx      *string `json:"synx" gorm:"column:synx"`                   // JAVA L142 @Excel(使用年限)
	Lyxt      *string `json:"lyxt" gorm:"column:lyxt"`                   // JAVA L146 @Excel(来源系统)
	LoadTime  *string `json:"loadTime" gorm:"column:load_time"`          // JAVA L150 @Excel(加载日期)
	AllColPk  *string `json:"allColPk" gorm:"column:all_col_pk"`         // JAVA L154 @Excel(全字段MD5)
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (DwdLcztFwqjcxx) TableName() string {
	return "dwd_lczt_fwqjcxx"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (DwdLcztFwqjcxx) Schema() string {
	return ""
}
