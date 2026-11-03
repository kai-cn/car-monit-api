package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/DwdLcztSfsjcxxMapper.java
// 类/职责: DwdLcztSfsjcxxMapper — 表 dwd_lczt_sfsjcxx 的数据访问入口
// 对应 Go 文件: internal/repo/dwd_lczt_sfsjcxx.go
// 关键映射:
//   extends BaseMapper<DwdLcztSfsjcxx>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectDwdLcztSfsjcxxById(AgentPk)   → GetByID
//   selectDwdLcztSfsjcxxList(DwdLcztSfsjcxx q) → List/Count（条件见 applyDwdLcztSfsjcxxFilters）
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

// DwdLcztSfsjcxxTable 对应 Java @TableName(value = 'dwd_lczt_sfsjcxx', schema = None)
const DwdLcztSfsjcxxTable = "jl_data01.dwd_lczt_sfsjcxx"

// DwdLcztSfsjcxxRepo 对应 Java 的 DwdLcztSfsjcxxMapper（@Repository 由 main() 里的显式构造代替）
type DwdLcztSfsjcxxRepo struct{ db *db.Client }

// NewDwdLcztSfsjcxxRepo 对应 Spring @Repository 的 Bean 注册
func NewDwdLcztSfsjcxxRepo(c *db.Client) *DwdLcztSfsjcxxRepo { return &DwdLcztSfsjcxxRepo{db: c} }

// TableName 供测试与日志使用
func (r *DwdLcztSfsjcxxRepo) TableName() string { return DwdLcztSfsjcxxTable }

// GetByID 对应 DwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxById(AgentPk)
func (r *DwdLcztSfsjcxxRepo) GetByID(ctx context.Context, id string) (*model.DwdLcztSfsjcxx, error) {
	var m model.DwdLcztSfsjcxx
	err := r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).Where("agent_pk = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("DwdLcztSfsjcxxRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 DwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *DwdLcztSfsjcxxRepo) List(ctx context.Context, q *model.DwdLcztSfsjcxx, limit int) ([]model.DwdLcztSfsjcxx, error) {
	tx := applyDwdLcztSfsjcxxFilters(r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.DwdLcztSfsjcxx
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("DwdLcztSfsjcxxRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectDwdLcztSfsjcxxList 配合 PageInfo#getTotal
func (r *DwdLcztSfsjcxxRepo) Count(ctx context.Context, q *model.DwdLcztSfsjcxx) (int64, error) {
	tx := applyDwdLcztSfsjcxxFilters(r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("DwdLcztSfsjcxxRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *DwdLcztSfsjcxxRepo) ListAll(ctx context.Context) ([]model.DwdLcztSfsjcxx, error) {
	var list []model.DwdLcztSfsjcxx
	if err := r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("DwdLcztSfsjcxxRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *DwdLcztSfsjcxxRepo) Insert(ctx context.Context, m *model.DwdLcztSfsjcxx) error {
	if err := r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).Create(m).Error; err != nil {
		return fmt.Errorf("DwdLcztSfsjcxxRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *DwdLcztSfsjcxxRepo) BatchInsert(ctx context.Context, list []*model.DwdLcztSfsjcxx, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *DwdLcztSfsjcxxRepo) Update(ctx context.Context, m *model.DwdLcztSfsjcxx) error {
	if err := r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).Save(m).Error; err != nil {
		return fmt.Errorf("DwdLcztSfsjcxxRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *DwdLcztSfsjcxxRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(DwdLcztSfsjcxxTable).Where("agent_pk = ?", id).Delete(&model.DwdLcztSfsjcxx{}).Error; err != nil {
		return fmt.Errorf("DwdLcztSfsjcxxRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyDwdLcztSfsjcxxFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyDwdLcztSfsjcxxFilters(tx *gorm.DB, q *model.DwdLcztSfsjcxx) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="agentPk != null and agentPk != ''">
	if q.AgentPk != "" {
		tx = tx.Where("agent_pk = ?", q.AgentPk)
	}
	// XML <if test="yxtzj != null and yxtzj != ''">
	if model.NonEmpty(q.Yxtzj) {
		tx = tx.Where("yxtzj = ?", q.Yxtzj)
	}
	// XML <if test="sfsbm != null and sfsbm != ''">
	if model.NonEmpty(q.Sfsbm) {
		tx = tx.Where("sfsbm = ?", q.Sfsbm)
	}
	// XML <if test="sfsmc != null and sfsmc != ''">
	if model.NonEmpty(q.Sfsmc) {
		tx = tx.Where("sfsmc = ?", q.Sfsmc)
	}
	// XML <if test="jd != null and jd != ''">
	if model.NonEmpty(q.Jd) {
		tx = tx.Where("jd = ?", q.Jd)
	}
	// XML <if test="wd != null and wd != ''">
	if model.NonEmpty(q.Wd) {
		tx = tx.Where("wd = ?", q.Wd)
	}
	// XML <if test="sslxbh != null and sslxbh != ''">
	if model.NonEmpty(q.Sslxbh) {
		tx = tx.Where("sslxbh = ?", q.Sslxbh)
	}
	// XML <if test="sslxmc != null and sslxmc != ''">
	if model.NonEmpty(q.Sslxmc) {
		tx = tx.Where("sslxmc = ?", q.Sslxmc)
	}
	// XML <if test="ssldbh != null and ssldbh != ''">
	if model.NonEmpty(q.Ssldbh) {
		tx = tx.Where("ssldbh = ?", q.Ssldbh)
	}
	// XML <if test="ssldmc != null and ssldmc != ''">
	if model.NonEmpty(q.Ssldmc) {
		tx = tx.Where("ssldmc = ?", q.Ssldmc)
	}
	// XML <if test="sczhK != null and sczhK != ''">
	if model.NonEmpty(q.SczhK) {
		tx = tx.Where("sczh_k = ?", q.SczhK)
	}
	// XML <if test="sczhN != null and sczhN != ''">
	if model.NonEmpty(q.SczhN) {
		tx = tx.Where("sczh_n = ?", q.SczhN)
	}
	// XML <if test="ssglzxbm != null and ssglzxbm != ''">
	if model.NonEmpty(q.Ssglzxbm) {
		tx = tx.Where("ssglzxbm = ?", q.Ssglzxbm)
	}
	// XML <if test="ssglzxmc != null and ssglzxmc != ''">
	if model.NonEmpty(q.Ssglzxmc) {
		tx = tx.Where("ssglzxmc = ?", q.Ssglzxmc)
	}
	// XML <if test="lyxt != null and lyxt != ''">
	if model.NonEmpty(q.Lyxt) {
		tx = tx.Where("lyxt = ?", q.Lyxt)
	}
	// XML <if test="loadTime != null and loadTime != ''">
	if model.NonEmpty(q.LoadTime) {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="allColPk != null and allColPk != ''">
	if model.NonEmpty(q.AllColPk) {
		tx = tx.Where("all_col_pk = ?", q.AllColPk)
	}
	// ---- END generated-from-XML ----
	return tx
}
