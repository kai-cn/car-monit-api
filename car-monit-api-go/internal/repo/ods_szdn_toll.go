package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnTollMapper.java
// 类/职责: OdsSzdnTollMapper — 表 ods_szdn_toll 的数据访问入口
// 对应 Go 文件: internal/repo/ods_szdn_toll.go
// 关键映射:
//   extends BaseMapper<OdsSzdnToll>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsSzdnTollById(Id)   → GetByID
//   selectOdsSzdnTollList(OdsSzdnToll q) → List/Count（条件见 applyOdsSzdnTollFilters）
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

// OdsSzdnTollTable 对应 Java @TableName(value = 'ods_szdn_toll', schema = None)
const OdsSzdnTollTable = "jl_data01.ods_szdn_toll"

// OdsSzdnTollRepo 对应 Java 的 OdsSzdnTollMapper（@Repository 由 main() 里的显式构造代替）
type OdsSzdnTollRepo struct{ db *db.Client }

// NewOdsSzdnTollRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsSzdnTollRepo(c *db.Client) *OdsSzdnTollRepo { return &OdsSzdnTollRepo{db: c} }

// TableName 供测试与日志使用
func (r *OdsSzdnTollRepo) TableName() string { return OdsSzdnTollTable }

// GetByID 对应 OdsSzdnTollMapper.selectOdsSzdnTollById(Id)
func (r *OdsSzdnTollRepo) GetByID(ctx context.Context, id string) (*model.OdsSzdnToll, error) {
	var m model.OdsSzdnToll
	err := r.db.ORM(ctx).Table(OdsSzdnTollTable).Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsSzdnTollRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsSzdnTollMapper.selectOdsSzdnTollList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsSzdnTollRepo) List(ctx context.Context, q *model.OdsSzdnToll, limit int) ([]model.OdsSzdnToll, error) {
	tx := applyOdsSzdnTollFilters(r.db.ORM(ctx).Table(OdsSzdnTollTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsSzdnToll
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnTollRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsSzdnTollList 配合 PageInfo#getTotal
func (r *OdsSzdnTollRepo) Count(ctx context.Context, q *model.OdsSzdnToll) (int64, error) {
	tx := applyOdsSzdnTollFilters(r.db.ORM(ctx).Table(OdsSzdnTollTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsSzdnTollRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsSzdnTollRepo) ListAll(ctx context.Context) ([]model.OdsSzdnToll, error) {
	var list []model.OdsSzdnToll
	if err := r.db.ORM(ctx).Table(OdsSzdnTollTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnTollRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsSzdnTollRepo) Insert(ctx context.Context, m *model.OdsSzdnToll) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsSzdnTollRepo) BatchInsert(ctx context.Context, list []*model.OdsSzdnToll, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsSzdnTollTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsSzdnTollRepo) Update(ctx context.Context, m *model.OdsSzdnToll) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsSzdnTollRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollTable).Where("id = ?", id).Delete(&model.OdsSzdnToll{}).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsSzdnTollFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsSzdnTollFilters(tx *gorm.DB, q *model.OdsSzdnToll) *gorm.DB {
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
	// XML <if test="idCard != null and idCard != ''">
	if model.NonEmpty(q.IdCard) {
		tx = tx.Where("id_card = ?", q.IdCard)
	}
	// XML <if test="tollCode != null and tollCode != ''">
	if model.NonEmpty(q.TollCode) {
		tx = tx.Where("toll_code = ?", q.TollCode)
	}
	// XML <if test="tollName != null and tollName != ''">
	if model.NonEmpty(q.TollName) {
		tx = tx.Where("toll_name like ?", "%"+model.Val(q.TollName)+"%")
	}
	// XML <if test="pileNo != null and pileNo != ''">
	if model.NonEmpty(q.PileNo) {
		tx = tx.Where("pile_no = ?", q.PileNo)
	}
	// XML <if test="orgName != null and orgName != ''">
	if model.NonEmpty(q.OrgName) {
		tx = tx.Where("org_name like ?", "%"+model.Val(q.OrgName)+"%")
	}
	// XML <if test="hexCode != null and hexCode != ''">
	if model.NonEmpty(q.HexCode) {
		tx = tx.Where("hex_code = ?", q.HexCode)
	}
	// XML <if test="stateCode != null and stateCode != ''">
	if model.NonEmpty(q.StateCode) {
		tx = tx.Where("state_code = ?", q.StateCode)
	}
	// XML <if test="orgCode != null and orgCode != ''">
	if model.NonEmpty(q.OrgCode) {
		tx = tx.Where("org_code = ?", q.OrgCode)
	}
	// XML <if test="longitude != null and longitude != ''">
	if model.NonEmpty(q.Longitude) {
		tx = tx.Where("longitude = ?", q.Longitude)
	}
	// XML <if test="latitude != null and latitude != ''">
	if model.NonEmpty(q.Latitude) {
		tx = tx.Where("latitude = ?", q.Latitude)
	}
	// XML <if test="openDate != null">
	if q.OpenDate != nil {
		tx = tx.Where("open_date = ?", q.OpenDate)
	}
	// XML <if test="tollAliasName != null and tollAliasName != ''">
	if model.NonEmpty(q.TollAliasName) {
		tx = tx.Where("toll_alias_name like ?", "%"+model.Val(q.TollAliasName)+"%")
	}
	// XML <if test="inMonitorResource != null and inMonitorResource != ''">
	if model.NonEmpty(q.InMonitorResource) {
		tx = tx.Where("in_monitor_resource = ?", q.InMonitorResource)
	}
	// XML <if test="laneMonitorResource != null and laneMonitorResource != ''">
	if model.NonEmpty(q.LaneMonitorResource) {
		tx = tx.Where("lane_monitor_resource = ?", q.LaneMonitorResource)
	}
	// XML <if test="squareMonitorResource != null and squareMonitorResource != ''">
	if model.NonEmpty(q.SquareMonitorResource) {
		tx = tx.Where("square_monitor_resource = ?", q.SquareMonitorResource)
	}
	// XML <if test="dynamicMonitorResource != null and dynamicMonitorResource != ''">
	if model.NonEmpty(q.DynamicMonitorResource) {
		tx = tx.Where("dynamic_monitor_resource = ?", q.DynamicMonitorResource)
	}
	// XML <if test="tollCodeMerge != null and tollCodeMerge != ''">
	if model.NonEmpty(q.TollCodeMerge) {
		tx = tx.Where("toll_code_merge = ?", q.TollCodeMerge)
	}
	// XML <if test="stateCodeMerge != null and stateCodeMerge != ''">
	if model.NonEmpty(q.StateCodeMerge) {
		tx = tx.Where("state_code_merge = ?", q.StateCodeMerge)
	}
	// XML <if test="tollNameMerge != null and tollNameMerge != ''">
	if model.NonEmpty(q.TollNameMerge) {
		tx = tx.Where("toll_name_merge = ?", q.TollNameMerge)
	}
	// XML <if test="sectionCode != null and sectionCode != ''">
	if model.NonEmpty(q.SectionCode) {
		tx = tx.Where("section_code = ?", q.SectionCode)
	}
	// XML <if test="tollOrgCode != null and tollOrgCode != ''">
	if model.NonEmpty(q.TollOrgCode) {
		tx = tx.Where("toll_org_code = ?", q.TollOrgCode)
	}
	// XML <if test="isAccess != null and isAccess != ''">
	if model.NonEmpty(q.IsAccess) {
		tx = tx.Where("is_access = ?", q.IsAccess)
	}
	// ---- END generated-from-XML ----
	return tx
}
