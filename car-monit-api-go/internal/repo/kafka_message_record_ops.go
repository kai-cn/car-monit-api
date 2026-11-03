package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/KafkaMessageRecordMapper.java
// 类/职责: KafkaMessageRecordMapper — 消息发送记录的状态机（待发/成功/失败/死信）+ 失败重试扫描
// 对应 Go 文件: internal/repo/kafka_message_record_ops.go
// 关键映射:
//   updateStatusById(id, status, sendTime) → UpdateStatusByID
//   incrementRetryCount(id, errorMsg)      → IncrementRetryCount
//   selectFailedRecords(maxRetry, limit)   → SelectFailedRecords
//
// 说明：手写文件，重新运行 tools/gen_repos.py 不会覆盖。
//
// 关键映射（SQL 见 KafkaMessageRecordMapper.xml）：
//
//	selectFailedRecords  → XML:32-38  SELECT * ... WHERE status IN (0, 2) AND retry_count < #{maxRetryCount}
//	                                  ORDER BY create_time ASC LIMIT #{limit}
//	updateStatusById     → XML:45-49  UPDATE ... SET status = #{status}, send_time = #{sendTime} WHERE id = #{id}
//	incrementRetryCount  → XML:60-64  UPDATE ... SET retry_count = retry_count + 1, error_msg = ..., status = 2
//
// PARITY（status IN (0, 2)）: 0 = 待发送、2 = 发送失败。两者都要重试 —— 只取 2 的话，
// 「入库后进程在首次发送前崩掉」的消息（status 停 0）就永远不会被发出，而 DDL 里 status 的
// 默认值正是 0（kafka_message_record.sql:6），所以这个分支是常态而不是边缘情况。
//
// PARITY（status 取值）: 0=待发 1=成功 2=失败 3=死信（KafkaProducerService/DataReliabilityService 的注释口径）；
// XML 只用到 0/2，3 是 Java 侧 BaseMapper.insert 写入的死信行，不参与重试扫描。
//
// DIFF（COALESCE）: XML 直接写 `retry_count < #{maxRetryCount}`，依赖 DDL 的 DEFAULT 0 保证非 NULL。
// Go 侧保留 COALESCE(retry_count, 0)：GORM 对 *int 为 nil 的字段会显式插入 NULL，
// 而 DDL 默认值只在「不写该列」时生效，两者叠在一起就可能出现 NULL；包一层 COALESCE 让
// 重试计数等价于 0，不会把 Go 自己插入的行排除在外。

import (
	"context"
	"fmt"
	"time"

	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// 消息状态常量，对应 Java 侧散落在各处的 0/1/2/3 魔数
const (
	MsgStatusPending = 0
	MsgStatusSuccess = 1
	MsgStatusFailed  = 2
	MsgStatusDead    = 3
)

// UpdateStatusByID 对应 updateStatusById(id, status, sendTime)
func (r *KafkaMessageRecordRepo) UpdateStatusByID(ctx context.Context, id string, status int, sendTime time.Time) error {
	err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).
		Where("id = ?", id).
		Updates(map[string]any{"status": status, "send_time": sendTime}).Error
	if err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.UpdateStatusByID: %w", err)
	}
	return nil
}

// IncrementRetryCount 对应 incrementRetryCount(id, errorMsg)：
// 重试次数 +1、状态置为失败、记录错误信息——一条 UPDATE 完成（与 Java 的 @Update SQL 语义一致）。
func (r *KafkaMessageRecordRepo) IncrementRetryCount(ctx context.Context, id, errorMsg string) error {
	err := r.db.ORM(ctx).Exec(
		"UPDATE "+KafkaMessageRecordTable+" SET retry_count = COALESCE(retry_count, 0) + 1, status = ?, error_msg = ? WHERE id = ?",
		MsgStatusFailed, truncate(errorMsg, 500), id).Error
	if err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.IncrementRetryCount: %w", err)
	}
	return nil
}

// SelectFailedRecords 对应 selectFailedRecords(maxRetryCount, limit)：
// 取「待发送(0) 或 发送失败(2) 且还有重试额度」的消息，按创建时间升序优先补偿最早的消息。
//
// 注意这里是 IN (0, 2) 而不是 = 2，理由见文件头 PARITY。
func (r *KafkaMessageRecordRepo) SelectFailedRecords(ctx context.Context, maxRetry, limit int) ([]model.KafkaMessageRecord, error) {
	if limit <= 0 {
		limit = 100
	}
	var list []model.KafkaMessageRecord
	err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).
		Where("status IN ? AND COALESCE(retry_count, 0) < ?", []int{MsgStatusPending, MsgStatusFailed}, maxRetry).
		Order("create_time ASC").
		Limit(limit).
		Find(&list).Error
	if err != nil {
		return nil, fmt.Errorf("KafkaMessageRecordRepo.SelectFailedRecords: %w", err)
	}
	return list, nil
}

// InsertDeadLetter 对应 DataReliabilityService.markAsDeadLetter 里的 insert（status=3）
func (r *KafkaMessageRecordRepo) InsertDeadLetter(ctx context.Context, rec *model.KafkaMessageRecord) error {
	status := MsgStatusDead
	rec.Status = &status
	if err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Create(rec).Error; err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.InsertDeadLetter: %w", err)
	}
	return nil
}

// truncate 截断错误信息，避免超过列宽（error_msg 常见为 varchar(500)）
func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
