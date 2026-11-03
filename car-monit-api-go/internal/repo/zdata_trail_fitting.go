package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataTrailFittingMapper.java
// 类/职责: ZdataTrailFittingMapper — 表 zdata_trail_fitting 的数据访问入口
// 对应 Go 文件: internal/repo/zdata_trail_fitting.go
// 关键映射:
//   extends BaseMapper<ZdataTrailFitting>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectZdataTrailFittingById(BigId)   → GetByID
//   selectZdataTrailFittingList(ZdataTrailFitting q) → List/Count（条件见 applyZdataTrailFittingFilters）
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

// ZdataTrailFittingTable 对应 Java @TableName(value = 'zdata_trail_fitting', schema = None)
const ZdataTrailFittingTable = "jl_data01.zdata_trail_fitting"

// ZdataTrailFittingRepo 对应 Java 的 ZdataTrailFittingMapper（@Repository 由 main() 里的显式构造代替）
type ZdataTrailFittingRepo struct{ db *db.Client }

// NewZdataTrailFittingRepo 对应 Spring @Repository 的 Bean 注册
func NewZdataTrailFittingRepo(c *db.Client) *ZdataTrailFittingRepo {
	return &ZdataTrailFittingRepo{db: c}
}

// TableName 供测试与日志使用
func (r *ZdataTrailFittingRepo) TableName() string { return ZdataTrailFittingTable }

// GetByID 对应 ZdataTrailFittingMapper.selectZdataTrailFittingById(BigId)
func (r *ZdataTrailFittingRepo) GetByID(ctx context.Context, id string) (*model.ZdataTrailFitting, error) {
	var m model.ZdataTrailFitting
	err := r.db.ORM(ctx).Table(ZdataTrailFittingTable).Where("big_id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("ZdataTrailFittingRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 ZdataTrailFittingMapper.selectZdataTrailFittingList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *ZdataTrailFittingRepo) List(ctx context.Context, q *model.ZdataTrailFitting, limit int) ([]model.ZdataTrailFitting, error) {
	tx := applyZdataTrailFittingFilters(r.db.ORM(ctx).Table(ZdataTrailFittingTable), q)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.ZdataTrailFitting
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailFittingRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectZdataTrailFittingList 配合 PageInfo#getTotal
func (r *ZdataTrailFittingRepo) Count(ctx context.Context, q *model.ZdataTrailFitting) (int64, error) {
	tx := applyZdataTrailFittingFilters(r.db.ORM(ctx).Table(ZdataTrailFittingTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("ZdataTrailFittingRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *ZdataTrailFittingRepo) ListAll(ctx context.Context) ([]model.ZdataTrailFitting, error) {
	var list []model.ZdataTrailFitting
	if err := r.db.ORM(ctx).Table(ZdataTrailFittingTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("ZdataTrailFittingRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *ZdataTrailFittingRepo) Insert(ctx context.Context, m *model.ZdataTrailFitting) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailFittingTable).Create(m).Error; err != nil {
		return fmt.Errorf("ZdataTrailFittingRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *ZdataTrailFittingRepo) BatchInsert(ctx context.Context, list []*model.ZdataTrailFitting, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(ZdataTrailFittingTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *ZdataTrailFittingRepo) Update(ctx context.Context, m *model.ZdataTrailFitting) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailFittingTable).Save(m).Error; err != nil {
		return fmt.Errorf("ZdataTrailFittingRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *ZdataTrailFittingRepo) DeleteByID(ctx context.Context, id string) error {
	if err := r.db.ORM(ctx).Table(ZdataTrailFittingTable).Where("big_id = ?", id).Delete(&model.ZdataTrailFitting{}).Error; err != nil {
		return fmt.Errorf("ZdataTrailFittingRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyZdataTrailFittingFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyZdataTrailFittingFilters(tx *gorm.DB, q *model.ZdataTrailFitting) *gorm.DB {
	if q == nil {
		return tx
	}
	if model.NonEmpty(q.Cid) {
		tx = tx.Where("cid = ?", q.Cid)
	}
	if model.NonEmpty(q.Entolllaneid) {
		tx = tx.Where("entolllaneid = ?", q.Entolllaneid)
	}
	if model.NonEmpty(q.Entollstationid) {
		tx = tx.Where("entollstationid = ?", q.Entollstationid)
	}
	if model.NonEmpty(q.Envehicleid) {
		tx = tx.Where("envehicleid = ?", q.Envehicleid)
	}
	if model.NonEmpty(q.Extolllaneid) {
		tx = tx.Where("extolllaneid = ?", q.Extolllaneid)
	}
	if model.NonEmpty(q.Extollstationid) {
		tx = tx.Where("extollstationid = ?", q.Extollstationid)
	}
	if model.NonEmpty(q.Exvehicleid) {
		tx = tx.Where("exvehicleid = ?", q.Exvehicleid)
	}
	return tx
}
