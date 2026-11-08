package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/KafkaMessageRecord.java
// 类/职责: KafkaMessageRecord — 表 kafka_message_record 的实体
// 对应 Go 文件: internal/model/kafka_message_record.go
// 关键映射: @TableName(value='kafka_message_record', schema='jl_data01') → TableName()/Schema()；@TableId(id) → primaryKey；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

// KafkaMessageRecord 对应 Java 类 KafkaMessageRecord
type KafkaMessageRecord struct {
	Id          string     `json:"id" gorm:"column:id;primaryKey"`         // JAVA L29
	DataId      string     `json:"dataId" gorm:"column:data_id"`           // JAVA L37
	Topic       string     `json:"topic" gorm:"column:topic"`              // JAVA L45
	MessageJson string     `json:"messageJson" gorm:"column:message_json"` // JAVA L53
	Status      *int       `json:"status" gorm:"column:status"`            // JAVA L65
	RetryCount  *int       `json:"retryCount" gorm:"column:retry_count"`   // JAVA L73
	CreateTime  *Timestamp `json:"createTime" gorm:"column:create_time"`   // JAVA L81
	SendTime    *Timestamp `json:"sendTime" gorm:"column:send_time"`       // JAVA L89
	ErrorMsg    *string    `json:"errorMsg" gorm:"column:error_msg"`       // JAVA L97
}

// TableName 对应 Java @TableName —— GORM 表名解析入口
func (KafkaMessageRecord) TableName() string {
	return "jl_data01.kafka_message_record"
}

// Schema 对应 Java @TableName(schema = ...)，用于手写 SQL 时拼接限定名
func (KafkaMessageRecord) Schema() string {
	return "jl_data01"
}
