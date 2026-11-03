package repo

// JAVA 对照: pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnTollStationIpMapper.java
// 类/职责: OdsSzdnTollStationIpMapper — 表 ods_szdn_toll_station_ip 的数据访问入口
// 对应 Go 文件: internal/repo/ods_szdn_toll_station_ip.go
// 关键映射:
//   extends BaseMapper<OdsSzdnTollStationIp>       → 本文件手写的 CRUD 方法（Go 无 MyBatis-Plus 的接口默认实现）
//   selectOdsSzdnTollStationIpById(Id)   → GetByID
//   selectOdsSzdnTollStationIpList(OdsSzdnTollStationIp q) → List/Count（条件见 applyOdsSzdnTollStationIpFilters）
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

// OdsSzdnTollStationIpTable 对应 Java @TableName(value = 'ods_szdn_toll_station_ip', schema = None)
const OdsSzdnTollStationIpTable = "jl_data01.ods_szdn_toll_station_ip"

// OdsSzdnTollStationIpRepo 对应 Java 的 OdsSzdnTollStationIpMapper（@Repository 由 main() 里的显式构造代替）
type OdsSzdnTollStationIpRepo struct{ db *db.Client }

// NewOdsSzdnTollStationIpRepo 对应 Spring @Repository 的 Bean 注册
func NewOdsSzdnTollStationIpRepo(c *db.Client) *OdsSzdnTollStationIpRepo {
	return &OdsSzdnTollStationIpRepo{db: c}
}

// TableName 供测试与日志使用
func (r *OdsSzdnTollStationIpRepo) TableName() string { return OdsSzdnTollStationIpTable }

// GetByID 对应 OdsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpById(Id)
func (r *OdsSzdnTollStationIpRepo) GetByID(ctx context.Context, id int64) (*model.OdsSzdnTollStationIp, error) {
	var m model.OdsSzdnTollStationIp
	err := r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).Where("id = ?", id).Take(&m).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, fmt.Errorf("OdsSzdnTollStationIpRepo.GetByID: %w", err)
	}
	return &m, nil
}

// List 对应 OdsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpList(q)
// DIFF: Java 的 PageHelper.startPage() 通过 ThreadLocal 影响下一次查询；Go 的 limit 必须显式传入。
func (r *OdsSzdnTollStationIpRepo) List(ctx context.Context, q *model.OdsSzdnTollStationIp, limit int) ([]model.OdsSzdnTollStationIp, error) {
	tx := applyOdsSzdnTollStationIpFilters(r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable), q)
	// 调用方通过 orderByColumn/isAsc 指定的排序（见 handler.orderByClause）
	tx = ApplyOrder(ctx, tx)
	if limit > 0 {
		tx = tx.Limit(limit)
	}
	var list []model.OdsSzdnTollStationIp
	if err := tx.Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnTollStationIpRepo.List: %w", err)
	}
	return list, nil
}

// Count 对应 selectOdsSzdnTollStationIpList 配合 PageInfo#getTotal
func (r *OdsSzdnTollStationIpRepo) Count(ctx context.Context, q *model.OdsSzdnTollStationIp) (int64, error) {
	tx := applyOdsSzdnTollStationIpFilters(r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable), q)
	var n int64
	if err := tx.Count(&n).Error; err != nil {
		return 0, fmt.Errorf("OdsSzdnTollStationIpRepo.Count: %w", err)
	}
	return n, nil
}

// ListAll 对应部分 Controller 的 /listAll 端点（无条件全量，注意大表勿用）
func (r *OdsSzdnTollStationIpRepo) ListAll(ctx context.Context) ([]model.OdsSzdnTollStationIp, error) {
	var list []model.OdsSzdnTollStationIp
	if err := r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).Find(&list).Error; err != nil {
		return nil, fmt.Errorf("OdsSzdnTollStationIpRepo.ListAll: %w", err)
	}
	return list, nil
}

// Insert 对应 BaseMapper.insert(entity)
func (r *OdsSzdnTollStationIpRepo) Insert(ctx context.Context, m *model.OdsSzdnTollStationIp) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).Create(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollStationIpRepo.Insert: %w", err)
	}
	return nil
}

// BatchInsert 对应 MyBatis 的 foreach 批量插入；batchSize 控制单条 INSERT 的 value 数量
// DIFF: Java 由 MyBatis-Plus 的 saveBatch 分片；Go 需要自己切批，避免单条 SQL 过长。
func (r *OdsSzdnTollStationIpRepo) BatchInsert(ctx context.Context, list []*model.OdsSzdnTollStationIp, batchSize int) error {
	if len(list) == 0 {
		return nil
	}
	if batchSize <= 0 {
		batchSize = 500
	}
	return r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).CreateInBatches(list, batchSize).Error
}

// Update 对应 BaseMapper.updateById(entity)
func (r *OdsSzdnTollStationIpRepo) Update(ctx context.Context, m *model.OdsSzdnTollStationIp) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).Save(m).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollStationIpRepo.Update: %w", err)
	}
	return nil
}

// DeleteByID 对应 BaseMapper.deleteById(id)
func (r *OdsSzdnTollStationIpRepo) DeleteByID(ctx context.Context, id int64) error {
	if err := r.db.ORM(ctx).Table(OdsSzdnTollStationIpTable).Where("id = ?", id).Delete(&model.OdsSzdnTollStationIp{}).Error; err != nil {
		return fmt.Errorf("OdsSzdnTollStationIpRepo.DeleteByID: %w", err)
	}
	return nil
}

// applyOdsSzdnTollStationIpFilters 把 Java 侧 XML <if test="..."> 的条件重建为 Go 代码。
// 为空即不过滤，语义与 MyBatis 的 <if> 一致。
func applyOdsSzdnTollStationIpFilters(tx *gorm.DB, q *model.OdsSzdnTollStationIp) *gorm.DB {
	if q == nil {
		return tx
	}
	// ---- BEGIN generated-from-XML ----
	// XML <if test="tollCode != null and tollCode != ''">
	if q.TollCode != "" {
		tx = tx.Where("toll_code = ?", q.TollCode)
	}
	// XML <if test="tollName != null and tollName != ''">
	if q.TollName != "" {
		tx = tx.Where("toll_name like ?", "%"+q.TollName+"%")
	}
	// XML <if test="orgCode != null and orgCode != ''">
	if q.OrgCode != "" {
		tx = tx.Where("org_code = ?", q.OrgCode)
	}
	// XML <if test="ip != null and ip != ''">
	if q.Ip != "" {
		tx = tx.Where("ip = ?", q.Ip)
	}
	// XML <if test="brand != null and brand != ''">
	if model.NonEmpty(q.Brand) {
		tx = tx.Where("brand = ?", q.Brand)
	}
	// ---- END generated-from-XML ----
	return tx
}
