package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataLocationDictMapper.java
// 类/职责: ZdataLocationDictMapper — 表 zdata_location_dict 的数据访问入口
// 对应 Go 文件: internal/repo/zdata_location_dict.go
// 关键映射:
//   extends BaseMapper<ZdataLocationDict>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectZdataLocationDictById(BigId)   → GetByID
//   selectZdataLocationDictList(ZdataLocationDict q) → List/Count（条件见 applyZdataLocationDictFilters）
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

// ZdataLocationDictTable 对应 Java @TableName(value = 'zdata_location_dict', schema = None)
const ZdataLocationDictTable = "jl_data01.zdata_location_dict"

// ZdataLocationDictRepo 对应 Java 的 ZdataLocationDictMapper（@Repository 由 main() 里的显式构造代替）
type ZdataLocationDictRepo struct{ db *db.Client }

// NewZdataLocationDictRepo 对应 Spring @Repository 的 Bean 注册
func NewZdataLocationDictRepo(c *db.Client) *ZdataLocationDictRepo {
	return &ZdataLocationDictRepo{db: c}
}

// TableName 供测试与日志使用
func (r *ZdataLocationDictRepo) TableName() string { return ZdataLocationDictTable }

// GetByID 对应 ZdataLocationDictMapper.selectZdataLocationDictById(BigId)
func (r *ZdataLocationDictRepo) GetByID(ctx context.Context, id string) (*model.ZdataLocationDict, error) {
	var m model.ZdataLocationDict
	err := r.db.ORM(ctx).Table(ZdataLocationDictTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("ZdataLocationDictRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 ZdataLocationDictMapper.selectZdataLocationDictList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *ZdataLocationDictRepo) List(ctx context.Context, q *model.ZdataLocationDict, limit int) ([]model.ZdataLocationDict, error) {
	tx := applyZdataLocationDictFilters(r.db.ORM(ctx).Table(ZdataLocationDictTable), q)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.ZdataLocationDict
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataLocationDictRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectZdataLocationDictList 配合 PageInfo#getTotal
func (r *ZdataLocationDictRepo) Count(ctx context.Context, q *model.ZdataLocationDict) (int64, error) {
	tx := applyZdataLocationDictFilters(r.db.ORM(ctx).Table(ZdataLocationDictTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("ZdataLocationDictRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *ZdataLocationDictRepo) ListAll(ctx context.Context) ([]model.ZdataLocationDict, error) {
	var list []model.ZdataLocationDict
	if err := r.db.ORM(ctx).Table(ZdataLocationDictTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataLocationDictRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *ZdataLocationDictRepo) Insert(ctx context.Context, m *model.ZdataLocationDict) error {
	if err := r.db.ORM(ctx).Table(ZdataLocationDictTable).Create(m).Error; err != nil {
		return fmt.Errorf("ZdataLocationDictRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *ZdataLocationDictRepo) BatchInsert(ctx context.Context, list []*model.ZdataLocationDict, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(ZdataLocationDictTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *ZdataLocationDictRepo) Update(ctx context.Context, m *model.ZdataLocationDict) error {
	if err := r.db.ORM(ctx).Table(ZdataLocationDictTable).Save(m).Error; err != nil {
		return fmt.Errorf("ZdataLocationDictRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *ZdataLocationDictRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(ZdataLocationDictTable).Where("big_id = ?", id).Delete(&model.ZdataLocationDict{}).Error; err != nil {
		return fmt.Errorf("ZdataLocationDictRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyZdataLocationDictFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyZdataLocationDictFilters(tx *gorm.DB, q *model.ZdataLocationDict) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="id != null and id != ''">
	if q.Id != nil {
		tx = tx.Where("id = ?", q.Id)
	}
	// XML <if test="type != null and type != ''">
	if q.Type != "" {
		tx = tx.Where("type = ?", q.Type)
	}
	// XML <if test="name != null and name != ''">
	if model.NonEmpty(q.Name) {
		tx = tx.Where("name like ?", "%"+model.Val(q.Name)+"%")
	}
	// XML <if test="rawCode != null and rawCode != ''">
	if q.RawCode != "" {
		tx = tx.Where("raw_code = ?", q.RawCode)
	}
	// XML <if test="standardCode != null and standardCode != ''">
	if model.NonEmpty(q.StandardCode) {
		tx = tx.Where("standard_code = ?", q.StandardCode)
	}
	// XML <if test="roadcode != null and roadcode != ''">
	if model.NonEmpty(q.Roadcode) {
		tx = tx.Where("roadcode = ?", q.Roadcode)
	}
	// XML <if test="roadname != null and roadname != ''">
	if model.NonEmpty(q.Roadname) {
		tx = tx.Where("roadname like ?", "%"+model.Val(q.Roadname)+"%")
	}
	// XML <if test="sectioncode != null and sectioncode != ''">
	if model.NonEmpty(q.Sectioncode) {
		tx = tx.Where("sectioncode = ?", q.Sectioncode)
	}
	// XML <if test="sectionname != null and sectionname != ''">
	if model.NonEmpty(q.Sectionname) {
		tx = tx.Where("sectionname like ?", "%"+model.Val(q.Sectionname)+"%")
	}
	// XML <if test="tollcode != null and tollcode != ''">
	if model.NonEmpty(q.Tollcode) {
		tx = tx.Where("tollcode = ?", q.Tollcode)
	}
	// XML <if test="tollname != null and tollname != ''">
	if model.NonEmpty(q.Tollname) {
		tx = tx.Where("tollname like ?", "%"+model.Val(q.Tollname)+"%")
	}
	// XML <if test="orgcode != null and orgcode != ''">
	if model.NonEmpty(q.Orgcode) {
		tx = tx.Where("orgcode = ?", q.Orgcode)
	}
	// XML <if test="orgname != null and orgname != ''">
	if model.NonEmpty(q.Orgname) {
		tx = tx.Where("orgname like ?", "%"+model.Val(q.Orgname)+"%")
	}
	// XML <if test="createdAt != null">
	if q.CreatedAt != nil {
		tx = tx.Where("created_at = ?", q.CreatedAt)
	}
	// XML <if test="updatedAt != null">
	if q.UpdatedAt != nil {
		tx = tx.Where("updated_at = ?", q.UpdatedAt)
	}
	// ---- END generated-from-XML ----
	return tx
}
