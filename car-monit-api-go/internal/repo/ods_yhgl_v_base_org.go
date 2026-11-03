package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsYhglVBaseOrgMapper.java
// 类/职责: OdsYhglVBaseOrgMapper — 表 ods_yhgl_v_base_org 的数据访问入口
// 对应 Go 文件: internal/repo/ods_yhgl_v_base_org.go
// 关键映射:
//   extends BaseMapper<OdsYhglVBaseOrg>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsYhglVBaseOrgById(BigId)   → GetByID
//   selectOdsYhglVBaseOrgList(OdsYhglVBaseOrg q) → List/Count（条件见 applyOdsYhglVBaseOrgFilters）
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

// OdsYhglVBaseOrgTable 对应 Java @TableName(value = 'ods_yhgl_v_base_org', schema = None)
const OdsYhglVBaseOrgTable = "jl_data01.ods_yhgl_v_base_org"

// OdsYhglVBaseOrgRepo 对应 Java 的 OdsYhglVBaseOrgMapper（@Repository 由 main() 里的显式构造代替）
type OdsYhglVBaseOrgRepo struct{ db *db.Client }

// NewOdsYhglVBaseOrgRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsYhglVBaseOrgRepo(c *db.Client) *OdsYhglVBaseOrgRepo { return &OdsYhglVBaseOrgRepo{db: c} }

// TableName 供测试与日志使用
func (r *OdsYhglVBaseOrgRepo) TableName() string { return OdsYhglVBaseOrgTable }

// GetByID 对应 OdsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgById(BigId)
func (r *OdsYhglVBaseOrgRepo) GetByID(ctx context.Context, id string) (*model.OdsYhglVBaseOrg, error) {
	var m model.OdsYhglVBaseOrg
	err := r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsYhglVBaseOrgRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsYhglVBaseOrgRepo) List(ctx context.Context, q *model.OdsYhglVBaseOrg, limit int) ([]model.OdsYhglVBaseOrg, error) {
	tx := applyOdsYhglVBaseOrgFilters(r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsYhglVBaseOrg
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsYhglVBaseOrgRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsYhglVBaseOrgList 配合 PageInfo#getTotal
func (r *OdsYhglVBaseOrgRepo) Count(ctx context.Context, q *model.OdsYhglVBaseOrg) (int64, error) {
	tx := applyOdsYhglVBaseOrgFilters(r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsYhglVBaseOrgRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsYhglVBaseOrgRepo) ListAll(ctx context.Context) ([]model.OdsYhglVBaseOrg, error) {
	var list []model.OdsYhglVBaseOrg
	if err := r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsYhglVBaseOrgRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsYhglVBaseOrgRepo) Insert(ctx context.Context, m *model.OdsYhglVBaseOrg) error {
	if err := r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsYhglVBaseOrgRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsYhglVBaseOrgRepo) BatchInsert(ctx context.Context, list []*model.OdsYhglVBaseOrg, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsYhglVBaseOrgRepo) Update(ctx context.Context, m *model.OdsYhglVBaseOrg) error {
	if err := r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsYhglVBaseOrgRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsYhglVBaseOrgRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsYhglVBaseOrgTable).Where("big_id = ?", id).Delete(&model.OdsYhglVBaseOrg{}).Error; err != nil {
		return fmt.Errorf("OdsYhglVBaseOrgRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsYhglVBaseOrgFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsYhglVBaseOrgFilters(tx *gorm.DB, q *model.OdsYhglVBaseOrg) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null and bigId != ''">
	if q.BigId != "" {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="orgCode != null and orgCode != ''">
	if q.OrgCode != "" {
		tx = tx.Where("org_code = ?", q.OrgCode)
	}
	// XML <if test="orgName != null and orgName != ''">
	if model.NonEmpty(q.OrgName) {
		tx = tx.Where("org_name like ?", "%"+model.Val(q.OrgName)+"%")
	}
	// XML <if test="orgShortName != null and orgShortName != ''">
	if model.NonEmpty(q.OrgShortName) {
		tx = tx.Where("org_short_name like ?", "%"+model.Val(q.OrgShortName)+"%")
	}
	// XML <if test="orgParentId != null and orgParentId != ''">
	if model.NonEmpty(q.OrgParentId) {
		tx = tx.Where("org_parent_id = ?", q.OrgParentId)
	}
	// XML <if test="orgLevelCode != null and orgLevelCode != ''">
	if model.NonEmpty(q.OrgLevelCode) {
		tx = tx.Where("org_level_code = ?", q.OrgLevelCode)
	}
	// XML <if test="orgIsVirtual != null and orgIsVirtual != ''">
	if model.NonEmpty(q.OrgIsVirtual) {
		tx = tx.Where("org_is_virtual = ?", q.OrgIsVirtual)
	}
	// XML <if test="orgMaintenance != null and orgMaintenance != ''">
	if model.NonEmpty(q.OrgMaintenance) {
		tx = tx.Where("org_maintenance = ?", q.OrgMaintenance)
	}
	// XML <if test="orgSequence != null">
	if q.OrgSequence != nil {
		tx = tx.Where("org_sequence = ?", q.OrgSequence)
	}
	// XML <if test="orgIsManager != null and orgIsManager != ''">
	if model.NonEmpty(q.OrgIsManager) {
		tx = tx.Where("org_is_manager = ?", q.OrgIsManager)
	}
	// XML <if test="orgIsDeleted != null and orgIsDeleted != ''">
	if model.NonEmpty(q.OrgIsDeleted) {
		tx = tx.Where("org_is_deleted = ?", q.OrgIsDeleted)
	}
	// XML <if test="orgCategory != null">
	if q.OrgCategory != nil {
		tx = tx.Where("org_category = ?", q.OrgCategory)
	}
	// XML <if test="orgIsAuthorized != null and orgIsAuthorized != ''">
	if model.NonEmpty(q.OrgIsAuthorized) {
		tx = tx.Where("org_is_authorized = ?", q.OrgIsAuthorized)
	}
	// XML <if test="orgAddress != null and orgAddress != ''">
	if model.NonEmpty(q.OrgAddress) {
		tx = tx.Where("org_address = ?", q.OrgAddress)
	}
	// XML <if test="orgIsYhAutarky != null and orgIsYhAutarky != ''">
	if model.NonEmpty(q.OrgIsYhAutarky) {
		tx = tx.Where("org_is_yh_autarky = ?", q.OrgIsYhAutarky)
	}
	// XML <if test="loadTime != null">
	if q.LoadTime != nil {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="gradeLevel != null">
	if q.GradeLevel != nil {
		tx = tx.Where("grade_level = ?", q.GradeLevel)
	}
	// ---- END generated-from-XML ----
	return tx
}
