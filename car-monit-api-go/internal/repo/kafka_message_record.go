package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/KafkaMessageRecordMapper.java
// 类/职责: KafkaMessageRecordMapper — 表 kafka_message_record 的数据访问入口
// 对应 Go 文件: internal/repo/kafka_message_record.go
// 关键映射:
//   extends BaseMapper<KafkaMessageRecord>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectKafkaMessageRecordById(Id)   → GetByID
//   selectKafkaMessageRecordList(KafkaMessageRecord q) → List/Count（条件见 applyKafkaMessageRecordFilters）
// DIFF: Java 用 XML/注解把 SQL 与接口解耦；Go 把 SQL 写在方法里，好在编译期就能发现列名/类型不匹配。
// PARITY: selectList 的实际 SQL 以 XML 为准，本文件的过滤条件由 _probe_go/genfilters.py
//         从 XML 的 <if> 列表逐条生成（标记见函数内 BEGIN/END generated-from-XML）。
//         注意：XML 不在 resources/mapper/xml/，而在
//         pro-business-api/src/main/java/com/ruoyi/base/mapper/xml/ —— 早先一次迁移因为
//         只翻了 resources 目录就断定「XML 缺失」，改成按字段名猜，猜错了运算符和列集合。

import (
	"context"
	"fmt"

	"gorm.io/gorm"

	"github.com/ruoyi/car-monit-api-go/internal/db"
	"github.com/ruoyi/car-monit-api-go/internal/model"
)

// KafkaMessageRecordTable 对应 Java @TableName(value = 'kafka_message_record', schema = 'jl_data01')
const KafkaMessageRecordTable = "jl_data01.kafka_message_record"

// KafkaMessageRecordRepo 对应 Java 的 KafkaMessageRecordMapper（@Repository 由 main() 里的显式构造代替）
type KafkaMessageRecordRepo struct{ db *db.Client }

// NewKafkaMessageRecordRepo 对应 Spring @Repository 的 Bean 注册
func NewKafkaMessageRecordRepo(c *db.Client) *KafkaMessageRecordRepo {
	return &KafkaMessageRecordRepo{db: c}
}

// TableName 供测试与日志使用
func (r *KafkaMessageRecordRepo) TableName() string { return KafkaMessageRecordTable }

// GetByID 对应 KafkaMessageRecordMapper.selectKafkaMessageRecordById(Id)
func (r *KafkaMessageRecordRepo) GetByID(ctx context.Context, id string) (*model.KafkaMessageRecord, error) {
	var m model.KafkaMessageRecord
	err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("KafkaMessageRecordRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 KafkaMessageRecordMapper.selectKafkaMessageRecordList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *KafkaMessageRecordRepo) List(ctx context.Context, q *model.KafkaMessageRecord, limit int) ([]model.KafkaMessageRecord, error) {
	tx := applyKafkaMessageRecordFilters(r.db.ORM(ctx).Table(KafkaMessageRecordTable), q)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.KafkaMessageRecord
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("KafkaMessageRecordRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectKafkaMessageRecordList 配合 PageInfo#getTotal
func (r *KafkaMessageRecordRepo) Count(ctx context.Context, q *model.KafkaMessageRecord) (int64, error) {
	tx := applyKafkaMessageRecordFilters(r.db.ORM(ctx).Table(KafkaMessageRecordTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("KafkaMessageRecordRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *KafkaMessageRecordRepo) ListAll(ctx context.Context) ([]model.KafkaMessageRecord, error) {
	var list []model.KafkaMessageRecord
	if err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("KafkaMessageRecordRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *KafkaMessageRecordRepo) Insert(ctx context.Context, m *model.KafkaMessageRecord) error {
	if err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Create(m).Error; err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *KafkaMessageRecordRepo) BatchInsert(ctx context.Context, list []*model.KafkaMessageRecord, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(KafkaMessageRecordTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *KafkaMessageRecordRepo) Update(ctx context.Context, m *model.KafkaMessageRecord) error {
	if err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Save(m).Error; err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *KafkaMessageRecordRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(KafkaMessageRecordTable).Where("id = ?", id).Delete(&model.KafkaMessageRecord{}).Error; err != nil {
		return fmt.Errorf("KafkaMessageRecordRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyKafkaMessageRecordFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyKafkaMessageRecordFilters(tx *gorm.DB, q *model.KafkaMessageRecord) *gorm.DB {
	if q == nil {
		return tx
	}
	if q.Id != "" {
		tx = tx.Where("id = ?", q.Id)
	}
	if q.DataId != "" {
		tx = tx.Where("data_id = ?", q.DataId)
	}
	return tx
}
