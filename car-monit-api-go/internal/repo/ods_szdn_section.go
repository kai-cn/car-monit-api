package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnSectionMapper.java
// 类/职责: OdsSzdnSectionMapper — 表 ods_szdn_section 的数据访问入口
// 对应 Go 文件: internal/repo/ods_szdn_section.go
// 关键映射:
//   extends BaseMapper<OdsSzdnSection>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsSzdnSectionById(Id)   → GetByID
//   selectOdsSzdnSectionList(OdsSzdnSection q) → List/Count（条件见 applyOdsSzdnSectionFilters）
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

// OdsSzdnSectionTable 对应 Java @TableName(value = 'ods_szdn_section', schema = None)
const OdsSzdnSectionTable = "jl_data01.ods_szdn_section"

// OdsSzdnSectionRepo 对应 Java 的 OdsSzdnSectionMapper（@Repository 由 main() 里的显式构造代替）
type OdsSzdnSectionRepo struct{ db *db.Client }

// NewOdsSzdnSectionRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsSzdnSectionRepo(c *db.Client) *OdsSzdnSectionRepo { return &OdsSzdnSectionRepo{db: c} }

// TableName 供测试与日志使用
func (r *OdsSzdnSectionRepo) TableName() string { return OdsSzdnSectionTable }

// GetByID 对应 OdsSzdnSectionMapper.selectOdsSzdnSectionById(Id)
func (r *OdsSzdnSectionRepo) GetByID(ctx context.Context, id string) (*model.OdsSzdnSection, error) {
	var m model.OdsSzdnSection
	err := r.db.ORM(ctx).Table(OdsSzdnSectionTable).Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsSzdnSectionRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsSzdnSectionMapper.selectOdsSzdnSectionList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsSzdnSectionRepo) List(ctx context.Context, q *model.OdsSzdnSection, limit int) ([]model.OdsSzdnSection, error) {
	tx := applyOdsSzdnSectionFilters(r.db.ORM(ctx).Table(OdsSzdnSectionTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsSzdnSection
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnSectionRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsSzdnSectionList 配合 PageInfo#getTotal
func (r *OdsSzdnSectionRepo) Count(ctx context.Context, q *model.OdsSzdnSection) (int64, error) {
	tx := applyOdsSzdnSectionFilters(r.db.ORM(ctx).Table(OdsSzdnSectionTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsSzdnSectionRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsSzdnSectionRepo) ListAll(ctx context.Context) ([]model.OdsSzdnSection, error) {
	var list []model.OdsSzdnSection
	if err := r.db.ORM(ctx).Table(OdsSzdnSectionTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnSectionRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsSzdnSectionRepo) Insert(ctx context.Context, m *model.OdsSzdnSection) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnSectionTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnSectionRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsSzdnSectionRepo) BatchInsert(ctx context.Context, list []*model.OdsSzdnSection, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsSzdnSectionTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsSzdnSectionRepo) Update(ctx context.Context, m *model.OdsSzdnSection) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnSectionTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnSectionRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsSzdnSectionRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnSectionTable).Where("id = ?", id).Delete(&model.OdsSzdnSection{}).Error; err != nil {
		return fmt.Errorf("OdsSzdnSectionRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsSzdnSectionFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsSzdnSectionFilters(tx *gorm.DB, q *model.OdsSzdnSection) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="id != null and id != ''">
	if q.Id != "" {
		tx = tx.Where("id = ?", q.Id)
	}
	// XML <if test="roadCode != null and roadCode != ''">
	if model.NonEmpty(q.RoadCode) {
		tx = tx.Where("road_code = ?", q.RoadCode)
	}
	// XML <if test="roadName != null and roadName != ''">
	if model.NonEmpty(q.RoadName) {
		tx = tx.Where("road_name like ?", "%"+model.Val(q.RoadName)+"%")
	}
	// XML <if test="sectionCode != null and sectionCode != ''">
	if model.NonEmpty(q.SectionCode) {
		tx = tx.Where("section_code = ?", q.SectionCode)
	}
	// XML <if test="sectionName != null and sectionName != ''">
	if model.NonEmpty(q.SectionName) {
		tx = tx.Where("section_name like ?", "%"+model.Val(q.SectionName)+"%")
	}
	// XML <if test="startPileNo != null">
	if q.StartPileNo != nil {
		tx = tx.Where("start_pile_no = ?", q.StartPileNo)
	}
	// XML <if test="endPileNo != null">
	if q.EndPileNo != nil {
		tx = tx.Where("end_pile_no = ?", q.EndPileNo)
	}
	// XML <if test="orgCode != null and orgCode != ''">
	if model.NonEmpty(q.OrgCode) {
		tx = tx.Where("org_code = ?", q.OrgCode)
	}
	// XML <if test="orgName != null and orgName != ''">
	if model.NonEmpty(q.OrgName) {
		tx = tx.Where("org_name like ?", "%"+model.Val(q.OrgName)+"%")
	}
	// XML <if test="orgLevelCode != null and orgLevelCode != ''">
	if model.NonEmpty(q.OrgLevelCode) {
		tx = tx.Where("org_level_code = ?", q.OrgLevelCode)
	}
	// XML <if test="orgCategory != null and orgCategory != ''">
	if model.NonEmpty(q.OrgCategory) {
		tx = tx.Where("org_category = ?", q.OrgCategory)
	}
	// XML <if test="mileage != null">
	if q.Mileage != nil {
		tx = tx.Where("mileage = ?", q.Mileage)
	}
	// XML <if test="openDate != null">
	if q.OpenDate != nil {
		tx = tx.Where("open_date = ?", q.OpenDate)
	}
	// ---- END generated-from-XML ----
	return tx
}
