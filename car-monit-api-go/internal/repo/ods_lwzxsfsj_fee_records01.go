package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeRecords01Mapper.java
// 类/职责: OdsLwzxsfsjFeeRecords01Mapper — 表 ods_lwzxsfsj_fee_records_01 的数据访问入口
// 对应 Go 文件: internal/repo/ods_lwzxsfsj_fee_records01.go
// 关键映射:
//   extends BaseMapper<OdsLwzxsfsjFeeRecords01>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsLwzxsfsjFeeRecords01ById(BigId)   → GetByID
//   selectOdsLwzxsfsjFeeRecords01List(OdsLwzxsfsjFeeRecords01 q) → List/Count（条件见 applyOdsLwzxsfsjFeeRecords01Filters）
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

// OdsLwzxsfsjFeeRecords01Table 对应 Java @TableName(value = 'ods_lwzxsfsj_fee_records_01', schema = None)
const OdsLwzxsfsjFeeRecords01Table = "jl_data01.ods_lwzxsfsj_fee_records_01"

// OdsLwzxsfsjFeeRecords01Repo 对应 Java 的 OdsLwzxsfsjFeeRecords01Mapper（@Repository 由 main() 里的显式构造代替）
type OdsLwzxsfsjFeeRecords01Repo struct{ db *db.Client }

// NewOdsLwzxsfsjFeeRecords01Repo 对应 Spring @Repository 的 Bean 注册
func NewOdsLwzxsfsjFeeRecords01Repo(c *db.Client) *OdsLwzxsfsjFeeRecords01Repo {
	return &OdsLwzxsfsjFeeRecords01Repo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsLwzxsfsjFeeRecords01Repo) TableName() string { return OdsLwzxsfsjFeeRecords01Table }

// GetByID 对应 OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01ById(BigId)
func (r *OdsLwzxsfsjFeeRecords01Repo) GetByID(ctx context.Context, id string) (*model.OdsLwzxsfsjFeeRecords01, error) {
	var m model.OdsLwzxsfsjFeeRecords01
	err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsLwzxsfsjFeeRecords01Mapper.selectOdsLwzxsfsjFeeRecords01List(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsLwzxsfsjFeeRecords01Repo) List(ctx context.Context, q *model.OdsLwzxsfsjFeeRecords01, limit int) ([]model.OdsLwzxsfsjFeeRecords01, error) {
	tx := applyOdsLwzxsfsjFeeRecords01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsLwzxsfsjFeeRecords01
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsLwzxsfsjFeeRecords01List 配合 PageInfo#getTotal
func (r *OdsLwzxsfsjFeeRecords01Repo) Count(ctx context.Context, q *model.OdsLwzxsfsjFeeRecords01) (int64, error) {
	tx := applyOdsLwzxsfsjFeeRecords01Filters(r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsLwzxsfsjFeeRecords01Repo) ListAll(ctx context.Context) ([]model.OdsLwzxsfsjFeeRecords01, error) {
	var list []model.OdsLwzxsfsjFeeRecords01
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsLwzxsfsjFeeRecords01Repo) Insert(ctx context.Context, m *model.OdsLwzxsfsjFeeRecords01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Create(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsLwzxsfsjFeeRecords01Repo) BatchInsert(ctx context.Context, list []*model.OdsLwzxsfsjFeeRecords01, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsLwzxsfsjFeeRecords01Repo) Update(ctx context.Context, m *model.OdsLwzxsfsjFeeRecords01) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Save(m).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsLwzxsfsjFeeRecords01Repo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsLwzxsfsjFeeRecords01Table).Where("big_id = ?", id).Delete(&model.OdsLwzxsfsjFeeRecords01{}).Error; err != nil {
		return fmt.Errorf("OdsLwzxsfsjFeeRecords01Repo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsLwzxsfsjFeeRecords01Filters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsLwzxsfsjFeeRecords01Filters(tx *gorm.DB, q *model.OdsLwzxsfsjFeeRecords01) *gorm.DB {
	if q == nil {
		return tx
	}
	if model.NonEmpty(q.Vehicleplate) {
		tx = tx.Where("vehicleplate ILIKE ?", "%"+model.Val(q.Vehicleplate)+"%")
	}
	if q.BigId != "" {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	if model.NonEmpty(q.Antennaid) {
		tx = tx.Where("antennaid = ?", q.Antennaid)
	}
	if model.NonEmpty(q.Cpucardid) {
		tx = tx.Where("cpucardid = ?", q.Cpucardid)
	}
	if model.NonEmpty(q.Cpuissueid) {
		tx = tx.Where("cpuissueid = ?", q.Cpuissueid)
	}
	if model.NonEmpty(q.Cpunetid) {
		tx = tx.Where("cpunetid = ?", q.Cpunetid)
	}
	if model.NonEmpty(q.Entolllaneid) {
		tx = tx.Where("entolllaneid = ?", q.Entolllaneid)
	}
	if model.NonEmpty(q.Gantryid) {
		tx = tx.Where("gantryid = ?", q.Gantryid)
	}
	if model.NonEmpty(q.Obuissueid) {
		tx = tx.Where("obuissueid = ?", q.Obuissueid)
	}
	if model.NonEmpty(q.Passid) {
		tx = tx.Where("passid = ?", q.Passid)
	}
	if model.NonEmpty(q.Tollintervalid) {
		tx = tx.Where("tollintervalid = ?", q.Tollintervalid)
	}
	if model.NonEmpty(q.Tradeid) {
		tx = tx.Where("tradeid = ?", q.Tradeid)
	}
	if model.NonEmpty(q.Verifycode) {
		tx = tx.Where("verifycode = ?", q.Verifycode)
	}
	// CodeList 由 Controller 从 code（逗号分隔）展开而来，本表对应门架编号列。
	// PARITY: resources/mapper/xml 里没有本 Mapper 的 XML，无法确认 Java 的 <foreach> 作用于哪一列；
	// 本表只有 gantryid 能承接「门架/收费站/服务区」这套编码，因此按 gantryid IN 实现。
	if len(q.CodeList) > 0 {
		tx = tx.Where("gantryid IN ?", q.CodeList)
	}
	return tx
}
