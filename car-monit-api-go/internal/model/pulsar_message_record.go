package model

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/domain/PulsarMessageRecord.java
// 类/职责: PulsarMessageRecord — DTO/VO（无独立表）
// 对应 Go 文件: internal/model/pulsar_message_record.go
// 关键映射: 纯 POJO（无 @TableName）→ 无 gorm tag 的普通 struct；@Data → 导出字段；
// DIFF: Lombok @Data 的 getter/setter 不再生成；Go 侧字段直接导出，JSON 名与 Java 字段名保持一致。

import ()

// PulsarMessageRecord 对应 Java 类 PulsarMessageRecord
type PulsarMessageRecord struct {
	Id          string     `json:"id"`          // JAVA L17
	DataId      string     `json:"dataId"`      // JAVA L20
	Topic       string     `json:"topic"`       // JAVA L23
	MessageJson string     `json:"messageJson"` // JAVA L26
	Status      *int       `json:"status"`      // JAVA L29
	RetryCount  *int       `json:"retryCount"`  // JAVA L32
	MessageId   string     `json:"messageId"`   // JAVA L35
	CreateTime  *Timestamp `json:"createTime"`  // JAVA L38
	SendTime    *Timestamp `json:"sendTime"`    // JAVA L41
	ErrorMsg    string     `json:"errorMsg"`    // JAVA L44
}
