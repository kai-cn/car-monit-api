package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsCxztFwqcllsMapper.java
// 类/职责: OdsCxztFwqcllsMapper — 表 ods_cxzt_fwqclls 的数据访问入口
// 对应 Go 文件: internal/repo/ods_cxzt_fwqclls.go
// 关键映射:
//   extends BaseMapper<OdsCxztFwqclls>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsCxztFwqcllsById(BigId)   → GetByID
//   selectOdsCxztFwqcllsList(OdsCxztFwqclls q) → List/Count（条件见 applyOdsCxztFwqcllsFilters）
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

// OdsCxztFwqcllsTable 对应 Java @TableName(value = 'ods_cxzt_fwqclls', schema = None)
const OdsCxztFwqcllsTable = "jl_data01.ods_cxzt_fwqclls"

// OdsCxztFwqcllsRepo 对应 Java 的 OdsCxztFwqcllsMapper（@Repository 由 main() 里的显式构造代替）
type OdsCxztFwqcllsRepo struct{ db *db.Client }

// NewOdsCxztFwqcllsRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsCxztFwqcllsRepo(c *db.Client) *OdsCxztFwqcllsRepo { return &OdsCxztFwqcllsRepo{db: c} }

// TableName 供测试与日志使用
func (r *OdsCxztFwqcllsRepo) TableName() string { return OdsCxztFwqcllsTable }

// GetByID 对应 OdsCxztFwqcllsMapper.selectOdsCxztFwqcllsById(BigId)
func (r *OdsCxztFwqcllsRepo) GetByID(ctx context.Context, id int64) (*model.OdsCxztFwqclls, error) {
	var m model.OdsCxztFwqclls
	err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsCxztFwqcllsRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsCxztFwqcllsRepo) List(ctx context.Context, q *model.OdsCxztFwqclls, limit int) ([]model.OdsCxztFwqclls, error) {
	tx := applyOdsCxztFwqcllsFilters(r.db.ORM(ctx).Table(OdsCxztFwqcllsTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsCxztFwqclls
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsCxztFwqcllsRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsCxztFwqcllsList 配合 PageInfo#getTotal
func (r *OdsCxztFwqcllsRepo) Count(ctx context.Context, q *model.OdsCxztFwqclls) (int64, error) {
	tx := applyOdsCxztFwqcllsFilters(r.db.ORM(ctx).Table(OdsCxztFwqcllsTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsCxztFwqcllsRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsCxztFwqcllsRepo) ListAll(ctx context.Context) ([]model.OdsCxztFwqclls, error) {
	var list []model.OdsCxztFwqclls
	if err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsCxztFwqcllsRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsCxztFwqcllsRepo) Insert(ctx context.Context, m *model.OdsCxztFwqclls) error {
	if err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsCxztFwqcllsRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsCxztFwqcllsRepo) BatchInsert(ctx context.Context, list []*model.OdsCxztFwqclls, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsCxztFwqcllsRepo) Update(ctx context.Context, m *model.OdsCxztFwqclls) error {
	if err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsCxztFwqcllsRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsCxztFwqcllsRepo) DeleteByID(ctx context.Context, id int64) error {
	if err := r.db.ORM(ctx).Table(OdsCxztFwqcllsTable).Where("big_id = ?", id).Delete(&model.OdsCxztFwqclls{}).Error; err != nil {
		return fmt.Errorf("OdsCxztFwqcllsRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsCxztFwqcllsFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsCxztFwqcllsFilters(tx *gorm.DB, q *model.OdsCxztFwqclls) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="bigId != null">
	if q.BigId != nil {
		tx = tx.Where("big_id = ?", q.BigId)
	}
	// XML <if test="datauuid != null and datauuid != ''">
	if model.NonEmpty(q.Datauuid) {
		tx = tx.Where("datauuid = ?", q.Datauuid)
	}
	// XML <if test="targetpicurl != null and targetpicurl != ''">
	if model.NonEmpty(q.Targetpicurl) {
		tx = tx.Where("targetpicurl = ?", q.Targetpicurl)
	}
	// XML <if test="vehiclebrand != null and vehiclebrand != ''">
	if model.NonEmpty(q.Vehiclebrand) {
		tx = tx.Where("vehiclebrand = ?", q.Vehiclebrand)
	}
	// XML <if test="platepicurl != null and platepicurl != ''">
	if model.NonEmpty(q.Platepicurl) {
		tx = tx.Where("platepicurl = ?", q.Platepicurl)
	}
	// XML <if test="rollvehiclestype != null and rollvehiclestype != ''">
	if model.NonEmpty(q.Rollvehiclestype) {
		tx = tx.Where("rollvehiclestype = ?", q.Rollvehiclestype)
	}
	// XML <if test="plateno != null and plateno != ''">
	if model.NonEmpty(q.Plateno) {
		tx = tx.Where("plateno = ?", q.Plateno)
	}
	// XML <if test="directionname != null and directionname != ''">
	if model.NonEmpty(q.Directionname) {
		tx = tx.Where("directionname like ?", "%"+model.Val(q.Directionname)+"%")
	}
	// XML <if test="platetype != null and platetype != ''">
	if model.NonEmpty(q.Platetype) {
		tx = tx.Where("platetype = ?", q.Platetype)
	}
	// XML <if test="dangmark != null and dangmark != ''">
	if model.NonEmpty(q.Dangmark) {
		tx = tx.Where("dangmark = ?", q.Dangmark)
	}
	// XML <if test="crosstime != null">
	if q.Crosstime != nil {
		tx = tx.Where("crosstime = ?", q.Crosstime)
	}
	// XML <if test="axles != null and axles != ''">
	if model.NonEmpty(q.Axles) {
		tx = tx.Where("axles = ?", q.Axles)
	}
	// XML <if test="devicename != null and devicename != ''">
	if model.NonEmpty(q.Devicename) {
		tx = tx.Where("devicename like ?", "%"+model.Val(q.Devicename)+"%")
	}
	// XML <if test="ipaddress != null and ipaddress != ''">
	if model.NonEmpty(q.Ipaddress) {
		tx = tx.Where("ipaddress = ?", q.Ipaddress)
	}
	// XML <if test="servicename != null and servicename != ''">
	if model.NonEmpty(q.Servicename) {
		tx = tx.Where("servicename like ?", "%"+model.Val(q.Servicename)+"%")
	}
	// XML <if test="vehicletype != null and vehicletype != ''">
	if model.NonEmpty(q.Vehicletype) {
		tx = tx.Where("vehicletype = ?", q.Vehicletype)
	}
	// XML <if test="loadTime != null and loadTime != ''">
	if model.NonEmpty(q.LoadTime) {
		tx = tx.Where("load_time = ?", q.LoadTime)
	}
	// XML <if test="gradeLevel != null and gradeLevel != ''">
	if model.NonEmpty(q.GradeLevel) {
		tx = tx.Where("grade_level = ?", q.GradeLevel)
	}
	// XML <if test="uuidList != null and uuidList.size() > 0">
	if len(q.UuidList) > 0 {
		tx = tx.Where("datauuid IN ?", q.UuidList)
	}
	// ---- END generated-from-XML ----
	return tx
}
