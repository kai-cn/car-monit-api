package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnGantryMapper.java
// 类/职责: OdsSzdnGantryMapper — 表 ods_szdn_gantry 的数据访问入口
// 对应 Go 文件: internal/repo/ods_szdn_gantry.go
// 关键映射:
//   extends BaseMapper<OdsSzdnGantry>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsSzdnGantryById(Id)   → GetByID
//   selectOdsSzdnGantryList(OdsSzdnGantry q) → List/Count（条件见 applyOdsSzdnGantryFilters）
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

// OdsSzdnGantryTable 对应 Java @TableName("ods_szdn_gantry") + XML 里的 `from jl_data01.ods_szdn_gantry`。
// 必须带 schema：openGauss 的默认 search_path 只有 "$user",public，不带前缀会报 42P01。
const OdsSzdnGantryTable = "jl_data01.ods_szdn_gantry"

// OdsSzdnGantryRepo 对应 Java 的 OdsSzdnGantryMapper（@Repository 由 main() 里的显式构造代替）
type OdsSzdnGantryRepo struct{ db *db.Client }

// NewOdsSzdnGantryRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsSzdnGantryRepo(c *db.Client) *OdsSzdnGantryRepo { return &OdsSzdnGantryRepo{db: c} }

// TableName 供测试与日志使用
func (r *OdsSzdnGantryRepo) TableName() string { return OdsSzdnGantryTable }

// GetByID 对应 OdsSzdnGantryMapper.selectOdsSzdnGantryById(Id)
func (r *OdsSzdnGantryRepo) GetByID(ctx context.Context, id string) (*model.OdsSzdnGantry, error) {
	var m model.OdsSzdnGantry
	err := r.db.ORM(ctx).Table(OdsSzdnGantryTable).Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsSzdnGantryRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsSzdnGantryMapper.selectOdsSzdnGantryList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsSzdnGantryRepo) List(ctx context.Context, q *model.OdsSzdnGantry, limit int) ([]model.OdsSzdnGantry, error) {
	tx := applyOdsSzdnGantryFilters(r.db.ORM(ctx).Table(OdsSzdnGantryTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsSzdnGantry
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnGantryRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsSzdnGantryList 配合 PageInfo#getTotal
func (r *OdsSzdnGantryRepo) Count(ctx context.Context, q *model.OdsSzdnGantry) (int64, error) {
	tx := applyOdsSzdnGantryFilters(r.db.ORM(ctx).Table(OdsSzdnGantryTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsSzdnGantryRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsSzdnGantryRepo) ListAll(ctx context.Context) ([]model.OdsSzdnGantry, error) {
	var list []model.OdsSzdnGantry
	if err := r.db.ORM(ctx).Table(OdsSzdnGantryTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnGantryRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsSzdnGantryRepo) Insert(ctx context.Context, m *model.OdsSzdnGantry) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnGantryTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnGantryRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsSzdnGantryRepo) BatchInsert(ctx context.Context, list []*model.OdsSzdnGantry, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsSzdnGantryTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsSzdnGantryRepo) Update(ctx context.Context, m *model.OdsSzdnGantry) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnGantryTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnGantryRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsSzdnGantryRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnGantryTable).Where("id = ?", id).Delete(&model.OdsSzdnGantry{}).Error; err != nil {
		return fmt.Errorf("OdsSzdnGantryRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsSzdnGantryFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsSzdnGantryFilters(tx *gorm.DB, q *model.OdsSzdnGantry) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="id != null and id != ''">
	if q.Id != "" {
		tx = tx.Where("id = ?", q.Id)
	}
	// XML <if test="gantryCode != null and gantryCode != ''">
	if model.NonEmpty(q.GantryCode) {
		tx = tx.Where("gantry_code = ?", q.GantryCode)
	}
	// XML <if test="gantryName != null and gantryName != ''">
	if model.NonEmpty(q.GantryName) {
		tx = tx.Where("gantry_name like ?", "%"+model.Val(q.GantryName)+"%")
	}
	// XML <if test="roadCode != null and roadCode != ''">
	if model.NonEmpty(q.RoadCode) {
		tx = tx.Where("road_code = ?", q.RoadCode)
	}
	// XML <if test="sectionCode != null and sectionCode != ''">
	if model.NonEmpty(q.SectionCode) {
		tx = tx.Where("section_code = ?", q.SectionCode)
	}
	// XML <if test="tollCode != null and tollCode != ''">
	if model.NonEmpty(q.TollCode) {
		tx = tx.Where("toll_code = ?", q.TollCode)
	}
	// XML <if test="orgCode != null and orgCode != ''">
	if model.NonEmpty(q.OrgCode) {
		tx = tx.Where("org_code = ?", q.OrgCode)
	}
	// XML <if test="hexCode != null and hexCode != ''">
	if model.NonEmpty(q.HexCode) {
		tx = tx.Where("hex_code = ?", q.HexCode)
	}
	// XML <if test="direction != null and direction != ''">
	if model.NonEmpty(q.Direction) {
		tx = tx.Where("direction = ?", q.Direction)
	}
	// XML <if test="pileNo != null and pileNo != ''">
	if model.NonEmpty(q.PileNo) {
		tx = tx.Where("pile_no = ?", q.PileNo)
	}
	// XML <if test="lon != null and lon != ''">
	if model.NonEmpty(q.Lon) {
		tx = tx.Where("lon = ?", q.Lon)
	}
	// XML <if test="lat != null and lat != ''">
	if model.NonEmpty(q.Lat) {
		tx = tx.Where("lat = ?", q.Lat)
	}
	// XML <if test="isVirtual != null and isVirtual != ''">
	if model.NonEmpty(q.IsVirtual) {
		tx = tx.Where("is_virtual = ?", q.IsVirtual)
	}
	// XML <if test="mileage != null and mileage != ''">
	if model.NonEmpty(q.Mileage) {
		tx = tx.Where("mileage = ?", q.Mileage)
	}
	// XML <if test="boundaryGantryType != null and boundaryGantryType != ''">
	if model.NonEmpty(q.BoundaryGantryType) {
		tx = tx.Where("boundary_gantry_type = ?", q.BoundaryGantryType)
	}
	// XML <if test="gantryType != null and gantryType != ''">
	if model.NonEmpty(q.GantryType) {
		tx = tx.Where("gantry_type = ?", q.GantryType)
	}
	// XML <if test="cityCode != null and cityCode != ''">
	if model.NonEmpty(q.CityCode) {
		tx = tx.Where("city_code = ?", q.CityCode)
	}
	// XML <if test="districtName != null and districtName != ''">
	if model.NonEmpty(q.DistrictName) {
		tx = tx.Where("district_name like ?", "%"+model.Val(q.DistrictName)+"%")
	}
	// XML <if test="belongGroup != null and belongGroup != ''">
	if model.NonEmpty(q.BelongGroup) {
		tx = tx.Where("belong_group = ?", q.BelongGroup)
	}
	// XML <if test="gantryCodeMerge != null and gantryCodeMerge != ''">
	if model.NonEmpty(q.GantryCodeMerge) {
		tx = tx.Where("gantry_code_merge = ?", q.GantryCodeMerge)
	}
	// XML <if test="gantryNameAlias != null and gantryNameAlias != ''">
	if model.NonEmpty(q.GantryNameAlias) {
		tx = tx.Where("gantry_name_alias = ?", q.GantryNameAlias)
	}
	// ---- END generated-from-XML ----
	return tx
}
